"""
reasoning.py -- the reasoning agent: judge ONE code-facts candidate at a time.

Why per-candidate: the tools (not the LLM) decide WHERE to look and supply the line number.
The LLM only answers "is this suspect a real bug of this type, given the rule's own
exemptions?" with evidence in front of it. It cannot invent a bug at a line no tool proposed.

Flow per candidate
  1. build a prompt: the SPEC rule text, the candidate + its evidence excerpts, the function source
  2. let the model call up to MAX_TOOL_ROUNDS rounds of read-only tools if it needs more context
  3. force a JSON verdict (schema-constrained) with an exact code quote
"""
from __future__ import annotations

import json

from codefacts import api as cf
from knowledge import api as kn

from .findings import Finding, dedupe
from .toolbox import ToolBox

MAX_TOOL_ROUNDS = 2
READ_ONLY_TOOLS = ["get_function_source", "get_calls", "get_accesses", "get_priorities",
                   "get_snippet", "find_line", "lookup_symbol", "search_docs"]

GROUPS = {"interrupts": ("INT-01", "INT-02", "INT-03"), "RTOS": ("RTOS-01", "RTOS-02", "RTOS-03"),
          "peripherals": ("PER-01", "PER-02"), "memory": ("MEM-01", "MEM-02")}

VERDICT_SCHEMA = {
    "type": "object",
    "properties": {                     # order matters: reasoning first, decision last
        "exemption_checked": {"type": "string"},
        "reason": {"type": "string"},
        "code_quote": {"type": "string"},
        "line": {"type": "integer"},
        "verdict": {"type": "string", "enum": ["bug", "not_bug", "unsure"]},
    },
    "required": ["exemption_checked", "reason", "code_quote", "line", "verdict"],
}

SYSTEM = (
    "You are a careful firmware reviewer for STM32F4 (Cortex-M4, HAL, FreeRTOS). A static analysis "
    "tool found ONE suspect. Decide if it is a real bug of the stated type.\n"
    "Rules you must follow:\n"
    "- Use only the code, tool facts and rule text given here, or returned by tools you call.\n"
    "- Never invent a line number. Use the suspect's line unless a tool shows a better one.\n"
    "- Read the rule's 'Not a bug' list literally and say which exemption you checked.\n"
    "- code_quote must be the exact text of the line you point at.\n"
    "- If the evidence is not enough to decide, answer \"unsure\". Do not guess.\n"
    "Answer in JSON only."
)


def rule_text(bug_type: str) -> str:
    hits = kn.lookup_symbol(bug_type)["hits"]
    for h in hits:
        if h["citation"].startswith("SPEC.md"):
            return h["text"]
    return f"(no rule text found for {bug_type})"


def _excerpts(file: str, cand: dict, width: int = 2) -> str:
    seen, parts = set(), []
    for ev in cand["evidence"]:
        ln = ev["line"]
        if ln <= 1 or ln in seen:
            continue
        seen.add(ln)
        snip = cf.get_snippet(file, max(1, ln - width), ln + width)["text"]
        parts.append(f"[{ev['fact']}]\n{snip}")
    return "\n\n".join(parts[:6]) or "(none)"


def _function_source(file: str, name: str | None, limit: int = 70) -> str:
    if not name:
        return "(file scope)"
    try:
        src = cf.get_function_source(file, name)["source"]
    except Exception:
        return "(unavailable)"
    lines = src.splitlines()
    return "\n".join(lines[:limit]) + ("\n...[truncated]" if len(lines) > limit else "")


# Flags the code-facts rules attach to a candidate. Which side of the argument each one is on:
EXEMPTION_FLAGS = {
    "all_task_accesses_in_critical_section": "every task-side access is inside a critical section",
    "pin_also_configured_output_elsewhere": "the pin is also configured as an output somewhere (runtime mode switch?)",
    "function_waits_for_completion": "the function waits for the transfer to finish",
    "pin_may_be_gpio_by_design": "the pin may be used as plain GPIO on purpose",
    "also_called_from_task": "the function is also called from task code",
    "mutex_confirmed": None,
}


def _flag_lines(flags: dict) -> tuple[str, str]:
    """Return (symptoms, possible exemptions) as short text. Only TRUE exemption flags are listed."""
    exempt, other = [], []
    for k, v in flags.items():
        if k in EXEMPTION_FLAGS:
            if v and EXEMPTION_FLAGS[k]:
                exempt.append(f"{k}: {EXEMPTION_FLAGS[k]}")
        elif v not in (False, None, ""):
            other.append(f"{k} = {v}")
    return ("; ".join(other) or "none"), ("; ".join(exempt) or "none flagged by the tool")


def build_prompt(file: str, cand: dict) -> str:
    symptoms, exemptions = _flag_lines(cand["flags"])
    return (
        f"RULE ({cand['bug_type']}), from the project's SPEC:\n{rule_text(cand['bug_type'])}\n\n"
        f"SUSPECT: {cand['bug_type']} at line {cand['line']}"
        f"{' in function ' + cand['function'] if cand.get('function') else ''}\n"
        f"Tool summary: {cand['summary']}\n"
        f"Facts the tool recorded (these describe the code; they are NOT exemptions): {symptoms}\n"
        f"Possible exemptions the tool noticed (check them against the rule): {exemptions}\n\n"
        f"EVIDENCE EXCERPTS (line numbers shown):\n{_excerpts(file, cand)}\n\n"
        f"FUNCTION SOURCE:\n{_function_source(file, cand.get('function'))}\n\n"
        "Task: (1) does the code match the rule's 'Bug' description? (2) does any 'Not a bug' "
        "exemption apply? You may call a tool if you need more context. Then give your JSON verdict."
    )


def _parse(content: str):
    try:
        d = json.loads(content)
        if d.get("verdict") in ("bug", "not_bug", "unsure"):
            return d
    except Exception:
        pass
    return None


def judge_candidate(llm, file: str, cand: dict, toolbox: ToolBox | None = None) -> Finding:
    tb = toolbox or ToolBox(READ_ONLY_TOOLS)
    start_log = len(tb.log)
    msgs = [{"role": "system", "content": SYSTEM}, {"role": "user", "content": build_prompt(file, cand)}]
    tokens = 0
    for _ in range(MAX_TOOL_ROUNDS):
        r = llm.chat(msgs, tools=tb.schemas)
        tokens += r["prompt_tokens"] + r["completion_tokens"]
        calls = r["message"].get("tool_calls") or []
        if not calls:
            break
        msgs.append(r["message"])
        for c in calls:
            fn = c["function"]
            args = fn.get("arguments") or {}
            if isinstance(args, str):
                try:
                    args = json.loads(args)
                except Exception:
                    args = {}
            msgs.append({"role": "tool", "tool_name": fn["name"], "content": tb.call(fn["name"], args)})
    msgs.append({"role": "user", "content": "Now give your final JSON verdict."})
    verdict = None
    for _ in range(2):                                   # one retry if the JSON is unusable
        r = llm.chat(msgs, fmt=VERDICT_SCHEMA)
        tokens += r["prompt_tokens"] + r["completion_tokens"]
        verdict = _parse(r["message"].get("content", ""))
        if verdict:
            break
    made = [{"tool": e["tool"], "args": e["args"]} for e in tb.log[start_log:]]
    if not verdict:
        return Finding(file, cand["bug_type"], cand["line"], "unsure", "model gave no valid verdict",
                       candidate_rule=cand["rule"], candidate_summary=cand["summary"],
                       tool_calls=made, tokens=tokens)
    # The anchor line ALWAYS comes from the tool-proposed candidate. The LLM's own line and quote are
    # only checked by code (does the quote appear on that line?), never trusted as the location.
    quote = verdict["code_quote"]
    on_line = bool(quote.strip()) and cf.validate_line(file, cand["line"], quote)["valid"]
    return Finding(file, cand["bug_type"], cand["line"], verdict["verdict"], verdict["reason"],
                   quote, verdict["exemption_checked"], cand["rule"], cand["summary"],
                   made, model_line=int(verdict["line"]), quote_on_line=on_line, tokens=tokens)


def run_reasoning(llm, file: str, groups: list[str] | None = None):
    """Judge every candidate of the chosen groups. Returns (findings, per-candidate log)."""
    wanted = None
    if groups:
        wanted = {t for g in groups for t in GROUPS[g]}
    cands = cf.get_candidates(file)["candidates"]
    findings, log = [], []
    for c in cands:
        if wanted and c["bug_type"] not in wanted:
            continue
        f = judge_candidate(llm, file, c)
        findings.append(f)
        log.append({"candidate": c, "finding": f.to_dict()})
    return dedupe(findings), log
