"""pipeline.py -- the setups that combine the agents. Each returns (findings, log)."""
from __future__ import annotations

from codefacts import api as cf

from .findings import dedupe
from .reasoning import judge_candidate, GROUPS
from .verifier import verify


def run_setup(llm, file: str, use_verifier: bool, groups: list[str] | None = None):
    wanted = {t for g in groups for t in GROUPS[g]} if groups else None
    cands = cf.get_candidates(file)["candidates"]
    kept, log = [], []
    for c in cands:
        if wanted and c["bug_type"] not in wanted:
            continue
        f = judge_candidate(llm, file, c)
        if use_verifier and f.verdict == "bug":
            verify(llm, file, f, c)
        survives = f.verdict == "bug" and (not use_verifier or (f.grounded and f.verified))
        log.append({"candidate": c, "finding": f.to_dict(), "reported": survives})
        if survives:
            kept.append(f)
    return dedupe(kept), log
