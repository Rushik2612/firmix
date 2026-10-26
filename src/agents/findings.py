"""findings.py -- the Finding record all agents and the evaluation share."""
from __future__ import annotations

from dataclasses import dataclass, field, asdict


@dataclass
class Finding:
    file: str
    bug_type: str
    line: int
    verdict: str                      # bug | not_bug | unsure
    reason: str = ""
    code_quote: str = ""
    exemption_checked: str = ""
    candidate_rule: str = ""
    candidate_summary: str = ""
    tool_calls: list = field(default_factory=list)   # [{"tool","args"}] actually made for this finding
    model_line: int | None = None     # the line the LLM claimed (kept only as a check; never used as the anchor)
    quote_on_line: bool | None = None # code check: does the LLM's quote really appear on `line`?
    grounded: bool | None = None      # set by the verifier's code check
    verified: bool | None = None      # set by the verifier's second opinion (False = validly refuted)
    verifier_reason: str = ""
    tokens: int = 0

    def to_dict(self):
        return asdict(self)


def dedupe(findings: list[Finding]) -> list[Finding]:
    """One finding per (bug_type, line); keep a 'bug' verdict over others."""
    best: dict[tuple, Finding] = {}
    for f in findings:
        k = (f.bug_type, f.line)
        if k not in best or (f.verdict == "bug" and best[k].verdict != "bug"):
            best[k] = f
    return sorted(best.values(), key=lambda f: (f.line, f.bug_type))
