"""
single.py -- the SINGLE-LLM baseline: the model reads the whole file and lists bugs. No tools, no candidates,
no verifier. It gets the SAME rule text (SPEC) and the SAME pinned model as every other LLM setup, so the
comparison isolates what the tools, the per-candidate structure and the verifier add.

Code still checks its output the same way for every setup: a finding whose quoted code is not on the line it
names (or whose line is out of range) is a HALLUCINATED finding. This baseline does not get the line-number
anchoring that the tool-grounded setups get for free; that is exactly the point of the comparison.
"""
from __future__ import annotations

import json

from codefacts import api as cf

from .findings import Finding, dedupe
from .reasoning import rule_text

ALL_TYPES = ["INT-01", "INT-02", "INT-03", "RTOS-01", "RTOS-02", "RTOS-03", "PER-01", "PER-02", "MEM-01", "MEM-02"]

SCHEMA = {
    "type": "object",
    "properties": {
        "findings": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "reason": {"type": "string"},
                    "code_quote": {"type": "string"},
                    "line": {"type": "integer"},
                    "bug_type": {"type": "string", "enum": ALL_TYPES},
                },
                "required": ["reason", "code_quote", "line", "bug_type"],
            },
        }
    },
    "required": ["findings"],
}

SYSTEM = (
    "You are a careful firmware reviewer for STM32F4 (Cortex-M4, HAL, FreeRTOS). Read the file and report every "
    "real bug that matches one of the listed bug types. Report nothing that falls under a rule's 'Not a bug' list. "
    "Report only bugs you are confident about; if the file has none, return an empty list.\n"
    "For each finding give the bug type, the line number exactly as shown, and the exact text of that line."
)


def _rules() -> str:
    return "\n\n".join(rule_text(t) for t in ALL_TYPES)


def run_single(llm, file: str):
    src = cf.load(file).lines
    numbered = "\n".join(f"{i:4d}| {l}" for i, l in enumerate(src, start=1))
    user = f"BUG TYPES AND RULES:\n{_rules()}\n\nFILE {file} (line numbers before the |):\n{numbered}\n\nList the bugs. JSON only."
    r = llm.chat([{"role": "system", "content": SYSTEM}, {"role": "user", "content": user}], fmt=SCHEMA)
    tokens = r["prompt_tokens"] + r["completion_tokens"]
    try:
        items = json.loads(r["message"].get("content", "")).get("findings", [])
    except Exception:
        items = []
    out, log = [], []
    for it in items:
        try:
            line, quote = int(it["line"]), str(it["code_quote"])
        except Exception:
            continue
        v = cf.validate_line(file, line, quote)
        f = Finding(file=file, bug_type=it["bug_type"], line=line, verdict="bug", reason=str(it.get("reason", ""))[:300],
                    code_quote=quote, model_line=line, quote_on_line=v["valid"], grounded=v["valid"], tokens=0)
        out.append(f)
        log.append({"finding": f.to_dict(), "reported": True})
    if out:
        out[0].tokens = tokens
    return dedupe(out), log + [{"single_tokens": tokens}]
