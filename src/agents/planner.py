"""
planner.py -- the planner agent: decide WHAT to look at, before any expensive reasoning.

Two planners, so the choice is measured, not assumed:

  code planner (default)  Deterministic. Asks code-facts for candidates, groups them by bug group, orders the groups
                          by how many suspects they have, and records the plan. It cannot lose a bug the candidate
                          stage found; it only organises the work and gives a log of what was planned.
  LLM triage (variant)    The model sees the candidate list and may DROP candidates it thinks are not worth a deep
                          review. Code enforces that it can only drop ids that exist; it can never add anything.
                          This is an experiment: dropping can only lose recall, so it must save enough calls to be
                          worth it. See CHANGELOG for the measurement.

Why the planner is so thin: the tools already scope the work (the LLM judges only candidates the tools proposed),
so a group with no candidates already costs zero LLM calls.
"""
from __future__ import annotations

import json

from codefacts import api as cf

from .reasoning import GROUPS

TRIAGE_SCHEMA = {
    "type": "object",
    "properties": {
        "reasoning": {"type": "string"},
        "skip": {"type": "array", "items": {"type": "integer"}},
    },
    "required": ["reasoning", "skip"],
}

TRIAGE_SYSTEM = (
    "You plan a firmware bug review. A static tool listed suspects (numbered). Reviewing each costs time. "
    "List the numbers of suspects that are OBVIOUSLY harmless false alarms and can be skipped. "
    "If you are not sure, do NOT skip it. Skipping a real bug is much worse than reviewing a harmless suspect. "
    "Answer in JSON only."
)


def _group_of(bug_type: str) -> str:
    for g, types in GROUPS.items():
        if bug_type in types:
            return g
    return "other"


def make_plan(file: str) -> dict:
    cands = cf.get_candidates(file)["candidates"]
    groups: dict[str, list] = {}
    for c in cands:
        groups.setdefault(_group_of(c["bug_type"]), []).append(c)
    order = sorted(groups, key=lambda g: (-len(groups[g]), g))
    return {"file": file, "n_candidates": len(cands), "groups": groups, "order": order,
            "skipped": [], "planner": "code"}


def llm_triage(llm, plan: dict) -> dict:
    """Let the model drop candidates. Only ids that exist are honoured. Mutates and returns the plan."""
    flat = [(i, c) for i, c in enumerate(c for g in plan["order"] for c in plan["groups"][g])]
    if len(flat) <= 1:
        plan["planner"] = "llm_triage"
        return plan
    listing = "\n".join(f"{i}. {c['bug_type']} at line {c['line']} in {c.get('function')}: {c['summary']}"
                        f"{' [flags: ' + ', '.join(c['flags']) + ']' if c.get('flags') else ''}" for i, c in flat)
    r = llm.chat([{"role": "system", "content": TRIAGE_SYSTEM},
                  {"role": "user", "content": f"File {plan['file']}. Suspects:\n{listing}\n\nWhich can be skipped?"}],
                 fmt=TRIAGE_SCHEMA)
    plan["tokens"] = r["prompt_tokens"] + r["completion_tokens"]
    try:
        skip = {int(x) for x in json.loads(r["message"].get("content", "")).get("skip", [])}
    except Exception:
        skip = set()
    valid = {i for i, _ in flat}
    drop = {id(c) for i, c in flat if i in (skip & valid)}
    for g in list(plan["groups"]):
        kept = [c for c in plan["groups"][g] if id(c) not in drop]
        plan["skipped"] += [(c["bug_type"], c["line"]) for c in plan["groups"][g] if id(c) in drop]
        plan["groups"][g] = kept
    plan["planner"] = "llm_triage"
    return plan
