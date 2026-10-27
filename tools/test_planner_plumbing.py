#!/usr/bin/env python3
"""Planner plumbing test (fake LLM): the planner may only DROP existing candidates, never add or invent."""
import json, sys
from pathlib import Path
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))
from agents.planner import make_plan, llm_triage

class Fake:
    def __init__(self, skip): self.skip, self.calls = skip, 0
    def chat(self, messages, tools=None, fmt=None):
        self.calls += 1
        return {"message": {"content": json.dumps({"reasoning": "x", "skip": self.skip})}, "prompt_tokens": 1, "completion_tokens": 1}

ok = True
def check(n, c):
    global ok; print(f"{n}:", bool(c)); ok &= bool(c)

FILE = "dev/d03.c"                                   # three candidates (2x MEM-01, 1x INT-02)
p = make_plan(FILE)
total = sum(len(v) for v in p["groups"].values())
check("code planner keeps every candidate the tools found", total == p["n_candidates"] == 3)
check("groups are ordered and named", set(p["order"]) == set(p["groups"]) and p["planner"] == "code")
p = llm_triage(Fake([0]), make_plan(FILE))
check("LLM triage can drop an existing candidate", sum(len(v) for v in p["groups"].values()) == 2 and len(p["skipped"]) == 1)
p = llm_triage(Fake([99, -1, 7]), make_plan(FILE))
check("invented / out-of-range ids are ignored (nothing dropped, nothing added)", sum(len(v) for v in p["groups"].values()) == 3 and not p["skipped"])
llm = Fake([0])
p = llm_triage(llm, make_plan("dev/d01.c"))           # one candidate: nothing to triage, LLM not called
check("single-candidate file: LLM not even called", llm.calls == 0 and sum(len(v) for v in p["groups"].values()) == 1)
p = llm_triage(Fake([0]), make_plan("dev/d12.c"))     # zero candidates
check("zero-candidate file: empty plan, no crash", p["groups"] == {} )
print("\nPASS" if ok else "\nFAIL"); sys.exit(0 if ok else 1)
