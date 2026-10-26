#!/usr/bin/env python3
"""Verifier plumbing test with a scripted fake LLM (no Ollama): checks that a refutation only counts
when code confirms its quote, and that ungrounded findings are dropped before the LLM is asked."""
import json, sys
from pathlib import Path
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))
from agents.pipeline import run_setup

SRC = (ROOT / "benchmark/dev/d03.c").read_text().splitlines()
GUARD = SRC[57].strip()          # line 58: if (rx_count < RX_BUF_LEN) {


class Fake:
    def __init__(self, judge_quote, refute):
        self.judge_quote, self.refute = judge_quote, refute
        self.calls = self.prompt_tokens = self.completion_tokens = 0
        self.verifier_calls = 0

    def chat(self, messages, tools=None, fmt=None):
        self.calls += 1
        msg = lambda d: {"message": {"role": "assistant", "content": json.dumps(d)}, "prompt_tokens": 1, "completion_tokens": 1}
        if fmt and "refuted" in fmt["properties"]:
            self.verifier_calls += 1
            return msg(self.refute)
        if fmt:
            line = int(messages[1]["content"].split(" at line ")[1].split()[0])
            q = self.judge_quote if self.judge_quote is not None else SRC[line - 1].strip()
            return msg({"exemption_checked": "none", "reason": "looks like a bug", "code_quote": q, "line": line, "verdict": "bug"})
        return {"message": {"role": "assistant", "content": ""}, "prompt_tokens": 1, "completion_tokens": 1}


def mem01_at_59(findings):
    return [f for f in findings if f.bug_type == "MEM-01" and f.line == 59]


ok = True
valid = {"exemption_considered": "bounded write", "guard_quote": GUARD, "guard_line": 58, "reason": "write is guarded by the count check", "refuted": True}
invented = {"exemption_considered": "bounded write", "guard_quote": "if (rx_head < 32) {", "guard_line": 58, "reason": "made up", "refuted": True}
none = {"exemption_considered": "none", "guard_quote": "", "guard_line": 0, "reason": "nothing applies", "refuted": False}

f, _ = run_setup(Fake(None, valid), "dev/d03.c", use_verifier=True)
print("valid refutation drops the finding:", not mem01_at_59(f)); ok &= not mem01_at_59(f)
f, _ = run_setup(Fake(None, invented), "dev/d03.c", use_verifier=True)
print("invented refutation is ignored (finding kept):", bool(mem01_at_59(f))); ok &= bool(mem01_at_59(f))
f, _ = run_setup(Fake(None, none), "dev/d03.c", use_verifier=True)
print("no refutation keeps the finding:", bool(mem01_at_59(f))); ok &= bool(mem01_at_59(f))
llm = Fake("this text is not on the line", none)
f, log = run_setup(llm, "dev/d03.c", use_verifier=True)
print("wrong model quote -> finding kept, quote replaced by real line text:", bool(mem01_at_59(f)) and "this text" not in mem01_at_59(f)[0].code_quote)
ok &= bool(mem01_at_59(f)) and "this text" not in mem01_at_59(f)[0].code_quote
f, _ = run_setup(Fake(None, valid), "dev/d03.c", use_verifier=False)
print("without verifier the same finding survives:", bool(mem01_at_59(f))); ok &= bool(mem01_at_59(f))
print("\nPASS" if ok else "\nFAIL"); sys.exit(0 if ok else 1)
