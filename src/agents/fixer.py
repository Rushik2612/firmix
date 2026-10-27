"""
fixer.py -- the fixer agent: propose a MINIMAL patch for one verified finding, and let code judge it.

The LLM proposes line-range edits (not a whole rewritten file). Code then decides, never the LLM:
  1. the edits are well formed (in range, not overlapping, at most MAX_EDITS, at most MAX_CHANGED lines)
  2. the patched file compiles and adds no new compiler warnings          (build server, check_fix)
  3. the bug is gone: the deterministic rule that found it no longer flags the same bug type in the
     same function                                                         (code-facts re-run)
If a check fails, the exact failure is fed back and the model retries (MAX_ATTEMPTS in total).

fix success = compiles + no new warnings + bug removed + small diff.
Known limit (state it in the README): "bug removed" is judged by the same rule that found the bug, so
a fix could satisfy the rule without being semantically right. Mitigation: small-diff cap, compile check,
plus a hand review of every fix on the dev set (and a sample on the test set).
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, field, asdict
from pathlib import Path

from codefacts import api as cf
from codefacts import rules
from codefacts.facts import Facts
from buildtools import api as bt

from .reasoning import rule_text

MAX_ATTEMPTS = 3          # first try + 2 retries
MAX_EDITS = 3
MAX_CHANGED = 15          # lines added + removed, as counted by the build server

FIX_SCHEMA = {
    "type": "object",
    "properties": {
        "explanation": {"type": "string"},
        "edits": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "start_line": {"type": "integer"},
                    "end_line": {"type": "integer"},
                    "new_text": {"type": "string"},
                },
                "required": ["start_line", "end_line", "new_text"],
            },
        },
    },
    "required": ["explanation", "edits"],
}

SYSTEM = (
    "You fix ONE bug in STM32F4 C firmware with the smallest possible change.\n"
    "Rules you must follow:\n"
    "- Return edits. Each edit replaces original lines start_line..end_line (inclusive, 1-based, line numbers "
    "exactly as shown) with new_text. To insert, replace one line with that line plus the new lines.\n"
    "- At most 3 edits and as few changed lines as possible. Do not reformat, rename, or refactor.\n"
    "- Fix the stated bug type only. Keep the behaviour otherwise identical.\n"
    "- Fix the faulty USE, not the setup other code relies on: do not change a pin's mode, a peripheral's "
    "configuration or a priority that other code depends on just to silence the rule; remove or redirect the "
    "faulty call instead, unless the rule's bug is the configuration itself.\n"
    "- A mutex or semaphore does NOT protect against an interrupt. To protect data shared with an ISR use a "
    "short critical section (taskENTER_CRITICAL/taskEXIT_CRITICAL or __disable_irq/__enable_irq).\n"
    "- Use only standard C, the HAL and FreeRTOS APIs already used in the file. Do not add new #include lines.\n"
    "- new_text must be valid C that compiles. Keep the original indentation. Do NOT copy the line-number "
    "labels (the 'NN|' prefixes) into new_text; write only the code.\n"
    "Answer in JSON only."
)


@dataclass
class FixResult:
    file: str
    bug_type: str
    line: int
    function: str | None
    success: bool = False
    compiles: bool = False
    bug_removed: bool = False
    new_warnings: int = 0
    changed_lines: int = 0
    introduced_suspects: list = field(default_factory=list)   # reported, not part of success
    attempts: int = 0
    failure: str = ""
    explanation: str = ""
    diff: str = ""
    patched_source: str = ""
    tokens: int = 0

    def to_dict(self):
        return asdict(self)


def _numbered(file: str, start: int, end: int) -> str:
    text = cf.get_snippet(file, start, end)["text"].splitlines()
    return "\n".join(f"{start + i:4d}| {t}" for i, t in enumerate(text))


def _context(file: str, cand: dict) -> str:
    """Numbered function source + numbered windows around each evidence line, merged and de-duplicated."""
    n = len(cf.load(file).lines)
    spans = []
    fn = cand.get("function")
    if fn:
        try:
            f = cf.get_function_source(file, fn)
            spans.append((f["start"], min(f["end"], f["start"] + 80)))
        except Exception:
            pass
    for ev in cand.get("evidence", []):
        ln = ev["line"]
        if ln > 1:
            spans.append((max(1, ln - 2), min(n, ln + 2)))
    spans.append((max(1, cand["line"] - 3), min(n, cand["line"] + 3)))
    spans.sort()
    merged = []
    for s, e in spans:
        if merged and s <= merged[-1][1] + 1:
            merged[-1] = (merged[-1][0], max(merged[-1][1], e))
        else:
            merged.append((s, e))
    return "\n...\n".join(_numbered(file, s, e) for s, e in merged[:8])


_LINE_LABEL = re.compile(r"^[ \t]*\d+[ \t]*[|:][ \t]?")


def strip_line_labels(text: str) -> str:
    """The prompt shows code as '  12| code'. Models sometimes copy that label into new_text. A real C line
    never starts with 'digits|' or 'digits:' (a label like '10:' is not valid C), so strip it."""
    return "\n".join(_LINE_LABEL.sub("", ln) for ln in text.split("\n"))


def apply_edits(source: str, edits: list, shown: set[int] | None = None) -> tuple[str | None, str]:
    """Apply edits to the original source. Returns (patched, '') or (None, why-rejected)."""
    lines = source.split("\n")
    n = len(lines)
    if not edits:
        return None, "no edits were given"
    if len(edits) > MAX_EDITS:
        return None, f"too many edits ({len(edits)}); at most {MAX_EDITS}"
    spans = []
    for e in edits:
        try:
            s, t = int(e["start_line"]), int(e["end_line"])
        except Exception:
            return None, "an edit has a non-numeric line number"
        if not (1 <= s <= t <= n):
            return None, f"edit lines {s}-{t} are outside the file (1-{n})"
        if t - s > 40:
            return None, "an edit replaces more than 40 lines; make a smaller change"
        spans.append((s, t, strip_line_labels(str(e.get("new_text", "")))))
    spans.sort()
    for a, b in zip(spans, spans[1:]):
        if b[0] <= a[1]:
            return None, f"edits overlap ({a[0]}-{a[1]} and {b[0]}-{b[1]})"
    for s, t, new in reversed(spans):          # bottom-up so earlier line numbers stay valid
        lines[s - 1:t] = new.split("\n") if new != "" else []
    return "\n".join(lines), ""


def bug_still_present(patched: str, cand: dict) -> tuple[bool, list]:
    """Re-run the deterministic rules on the patched source. The bug counts as removed when no candidate of
    the same bug type remains in the same function. Returns (still_present, introduced_suspects)."""
    F = Facts(patched.encode("utf-8"))
    after = rules.all_candidates(F)
    still = any(c.bug_type == cand["bug_type"] and c.function == cand.get("function") for c in after)
    return still, after


def fix_finding(llm, file: str, cand: dict) -> FixResult:
    """cand = a code-facts candidate dict (bug_type, line, function, rule, summary, evidence)."""
    res = FixResult(file=file, bug_type=cand["bug_type"], line=cand["line"], function=cand.get("function"))
    original = Path(cf._resolve(file)).read_text(encoding="utf-8", errors="replace")
    before = {(c["bug_type"], c["function"], c["rule"]) for c in cf.get_candidates(file)["candidates"]}

    user = (
        f"BUG TYPE {cand['bug_type']} at line {cand['line']} (in function {cand.get('function')}).\n"
        f"Why it was flagged: {cand['summary']}\n\n"
        f"RULE from the project's SPEC (the 'Bug' part says what is wrong, 'Not a bug' says what is fine):\n"
        f"{rule_text(cand['bug_type'])}\n\n"
        f"ORIGINAL CODE (line numbers shown before the |):\n{_context(file, cand)}\n\n"
        "Give the smallest edits that remove this bug. JSON only."
    )
    msgs = [{"role": "system", "content": SYSTEM}, {"role": "user", "content": user}]

    for attempt in range(1, MAX_ATTEMPTS + 1):
        res.attempts = attempt
        r = llm.chat(msgs, fmt=FIX_SCHEMA)
        res.tokens += r["prompt_tokens"] + r["completion_tokens"]
        raw = r["message"].get("content", "")
        try:
            out = json.loads(raw)
            res.explanation = str(out.get("explanation", ""))[:300]
            patched, why = apply_edits(original, out.get("edits", []))
        except Exception as e:
            patched, why = None, f"the answer was not valid JSON edits ({e})"

        problem = why
        if patched is not None:
            try:
                chk = bt.check_fix(file, patched)
            except Exception as e:                      # e.g. an #include the build server refuses
                chk = None
                problem = f"the build server refused the patch ({e})"
            if chk is not None:
                res.compiles = bool(chk["compiles"])
                res.new_warnings = len(chk["new_warnings"])
                res.changed_lines = chk["changed_lines"]
                res.diff = chk["diff"]
                res.patched_source = patched
                if not chk["compiles"]:
                    problem = "the patch does not compile:\n" + "\n".join(map(str, chk["errors"][:5]))
                elif chk["new_warnings"]:
                    problem = "the patch adds compiler warnings:\n" + "\n".join(str(w["msg"]) for w in chk["new_warnings"][:4])
                elif chk["changed_lines"] > MAX_CHANGED:
                    problem = f"the patch changes {chk['changed_lines']} lines; keep it under {MAX_CHANGED}"
                else:
                    still, after = bug_still_present(patched, cand)
                    res.introduced_suspects = sorted(
                        {f"{c.bug_type}@{c.function}" for c in after if (c.bug_type, c.function, c.rule) not in before})
                    res.bug_removed = not still
                    if still:
                        problem = ("the patch compiles, but the same rule still flags this bug type in "
                                   f"function {cand.get('function')}. Fix the actual cause described in the rule.")
                    else:
                        res.success, res.failure = True, ""
                        return res
        res.failure = problem
        msgs.append({"role": "assistant", "content": raw})
        msgs.append({"role": "user", "content": f"Your patch was rejected: {problem}\nGive corrected edits against "
                                                  "the ORIGINAL line numbers shown above. JSON only."})
    return res
