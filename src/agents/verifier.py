"""
verifier.py -- the verifier agent: try to REFUTE a finding, with every claim checked by code.

Stage 1 (code only): is the finding grounded?
    * the model's quoted code really appears on the proposed line (validate_line)
    * the suspect reproduces when the deterministic rule is re-run (not a stale/invented candidate)
Stage 2 (LLM, adversarial): a different prompt asks the model to find a reason the finding is NOT a
    bug (a 'Not a bug' exemption from the rule, or a guard/invariant in the code). A refutation only
    counts if it points to a specific line and quotes it, and code confirms that quote is on that
    line. A refutation the code cannot confirm is ignored, so the verifier cannot invent excuses.
"""
from __future__ import annotations

import json

from codefacts import api as cf

from .findings import Finding
from .reasoning import (rule_text, _excerpts, _function_source, READ_ONLY_TOOLS)
from .toolbox import ToolBox

REFUTE_SCHEMA = {
    "type": "object",
    "properties": {
        "exemption_considered": {"type": "string"},
        "guard_quote": {"type": "string"},
        "guard_line": {"type": "integer"},
        "reason": {"type": "string"},
        "refuted": {"type": "boolean"},
    },
    "required": ["exemption_considered", "guard_quote", "guard_line", "reason", "refuted"],
}

SYSTEM = (
    "You are a skeptical senior firmware reviewer. A colleague claims the suspect below is a real bug. "
    "Your job is to try to REFUTE the claim, using only (a) the 'Not a bug' exemptions in the rule and "
    "(b) guards or invariants visible in the code (for example an index that is only ever updated with a "
    "modulo, a critical section around every access, a wait for completion).\n"
    "Rules you must follow:\n"
    "- Set refuted=true ONLY if you can point to one specific line that makes the code safe.\n"
    "- guard_quote must be the exact text of that line and guard_line its line number.\n"
    "- If you cannot point to such a line, set refuted=false and leave guard_quote empty.\n"
    "- Do not refute because you dislike the style, or because the code might work in some cases.\n"
    "Answer in JSON only."
)


def _quote_ok(file: str, line: int, quote: str, lo: int, hi: int) -> bool:
    if not quote.strip() or not (lo <= line <= hi):
        return False
    return cf.validate_line(file, line, quote)["valid"]


HEDGES = ("may ", "might", "could", "suggests", "imply", "implies", "however", "possibly",
          "likely", "appears", "seems", "probably", "perhaps")


def refutation_defect(finding: Finding, out: dict) -> str:
    """Code-side sanity checks on a refutation. Returns '' if acceptable, else why it is rejected.
    (1) the 'guard' cannot be the suspect line itself; (2) a refutation must be certain: hedged or
    self-contradicting reasoning ('may', 'however') is not a proof of safety."""
    try:
        gl = int(out.get("guard_line", 0))
    except Exception:
        return "guard_line is not a number"
    if gl == finding.line:
        return "the cited guard is the suspect line itself"
    # Only for exit-path bugs is "a guard AFTER the suspect cannot protect it" true: a later give does not run on an
    # early return. For invariants (an index kept in range by a modulo update on the next line) and for completion
    # waits after an async HAL call, the protecting line legitimately comes AFTER the suspect line.
    if finding.bug_type == "RTOS-02" and gl > finding.line:
        return "the cited guard comes AFTER the suspect line, so it cannot protect that exit path"
    low = " " + str(out.get("reason", "")).lower() + " "
    for h in HEDGES:
        if h in low:
            return f"hedged reasoning ('{h.strip()}')"
    return ""


def grounding_check(file: str, finding: Finding, cand: dict) -> tuple[bool, str]:
    """Stage 1: pure code."""
    # The LINE is always tool-proposed (never the model's), so a sloppy model quote does not make the
    # finding ungrounded; the quote is replaced by the real source text. Reproduction is what counts.
    if not finding.quote_on_line:
        try:
            finding.code_quote = cf.get_snippet(file, finding.line, finding.line)["text"].strip()
        except Exception:
            pass
    again = cf.get_candidates(file, finding.bug_type)["candidates"]
    if not any(c["line"] == finding.line for c in again):
        return False, "the suspect does not reproduce when the rule is re-run"
    return True, "quote matches the line and the suspect reproduces"


def verify(llm, file: str, finding: Finding, cand: dict, toolbox: ToolBox | None = None) -> Finding:
    ok, why = grounding_check(file, finding, cand)
    finding.grounded = ok
    if not ok:
        finding.verified = False
        finding.verifier_reason = "ungrounded: " + why
        return finding

    fn = cand.get("function")
    lo, hi = 1, len(cf.load(file).lines)
    user = (
        f"RULE ({finding.bug_type}), from the project's SPEC:\n{rule_text(finding.bug_type)}\n\n"
        f"CLAIM: {finding.bug_type} at line {finding.line}: {finding.reason}\n"
        f"Quoted code: {finding.code_quote}\n\n"
        f"EVIDENCE EXCERPTS:\n{_excerpts(file, cand)}\n\n"
        f"FUNCTION SOURCE:\n{_function_source(file, fn)}\n\n"
        "Try to refute the claim. Check each 'Not a bug' exemption of the rule against the code, and look "
        "for a guard or invariant in the source above. Give your JSON answer."
    )
    msgs = [{"role": "system", "content": SYSTEM}, {"role": "user", "content": user}]
    tokens, out = 0, None
    for _ in range(2):
        r = llm.chat(msgs, fmt=REFUTE_SCHEMA)
        tokens += r["prompt_tokens"] + r["completion_tokens"]
        try:
            out = json.loads(r["message"].get("content", ""))
            if isinstance(out.get("refuted"), bool):
                break
        except Exception:
            out = None
    finding.tokens += tokens
    if out is None:
        finding.verified = True
        finding.verifier_reason = "verifier gave no usable answer; finding kept"
        return finding
    if out["refuted"]:
        bad = refutation_defect(finding, out)
        if bad:
            finding.verified = True
            finding.verifier_reason = f"refutation rejected by code ({bad}); finding kept. ({out['reason'][:160]})"
            return finding
        if _quote_ok(file, int(out["guard_line"]), out["guard_quote"], lo, hi):
            finding.verified = False
            finding.verifier_reason = (f"refuted by line {out['guard_line']} ({out['guard_quote'].strip()}): "
                                       f"{out['reason']}")
        else:
            finding.verified = True
            finding.verifier_reason = ("refutation ignored: the cited line/quote could not be confirmed by code. "
                                       f"({out['reason'][:200]})")
    else:
        finding.verified = True
        finding.verifier_reason = "no valid refutation: " + out.get("reason", "")[:200]
    return finding
