#!/usr/bin/env python3
"""Evaluation plumbing test (no Ollama): the scoring counts TP/FN/FP/hallucination exactly as defined,
and the single-LLM baseline's output is checked by code (wrong quote / out-of-range line = hallucination)."""
import json, subprocess, sys, tempfile
from pathlib import Path
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src")); sys.path.insert(0, str(ROOT / "tools"))
from agents.findings import Finding
from agents.single import run_single
import run_eval as E

ok = True
def check(n, c):
    global ok; print(f"{n}:", bool(c)); ok &= bool(c)

F = lambda file, bt, line, qol=True: Finding(file=file, bug_type=bt, line=line, verdict="bug", quote_on_line=qol)
rows = [
    {"file": "a.c", "label": "buggy", "bug_type": "INT-01", "accepted_lines": [10]},
    {"file": "b.c", "label": "buggy", "bug_type": "RTOS-02", "accepted_lines": [20, 22]},
    {"file": "c.c", "label": "buggy", "bug_type": "MEM-01", "accepted_lines": [30]},
    {"file": "d.c", "label": "clean"},
]
per = {"a.c": [F("a.c", "INT-01", 10)],                                     # TP
       "b.c": [F("b.c", "RTOS-02", 21)],                                    # right type, wrong line -> FN + FP
       "c.c": [F("c.c", "MEM-01", 30), F("c.c", "INT-02", 5, qol=False)],   # TP + hallucinated FP in another group
       "d.c": [F("d.c", "PER-01", 3)]}                                      # FP on a clean file
c = E.score_run(rows, per)
check("ALL counts: tp=2 fn=1 fp=3 reported=5 halluc=1", c["ALL"] == {"tp": 2, "fn": 1, "fp": 3, "reported": 5, "halluc": 1, "loose": 3})
check("interrupts group: tp=1 fn=0 fp=1 (the hallucinated INT-02) halluc=1", c["interrupts"] == {"tp": 1, "fn": 0, "fp": 1, "reported": 2, "halluc": 1, "loose": 1})
check("RTOS group: tp=0 fn=1 fp=1", (c["RTOS"]["tp"], c["RTOS"]["fn"], c["RTOS"]["fp"]) == (0, 1, 1))
check("peripherals group: FP from the clean file counted there", c["peripherals/HAL"]["fp"] == 1 and c["peripherals/HAL"]["tp"] == 0)
r = E.rates(c["ALL"])
check("rates: recall 2/3, precision 2/5, halluc 1/5", abs(r["recall"] - 2/3) < 1e-9 and abs(r["precision"] - 0.4) < 1e-9 and abs(r["halluc"] - 0.2) < 1e-9)
check("lenient recall counts right-type-wrong-line as found: 3/3", abs(r["recall_loose"] - 1.0) < 1e-9)
check("rates with nothing reported: precision/halluc are None, not a crash", E.rates({"tp": 0, "fn": 2, "fp": 0, "reported": 0, "halluc": 0, "loose": 0})["precision"] is None)

class Fake:
    def __init__(self, items): self.items, self.calls, self.prompt_tokens, self.completion_tokens = items, 0, 0, 0
    def chat(self, messages, tools=None, fmt=None):
        self.calls += 1
        return {"message": {"content": json.dumps({"findings": self.items})}, "prompt_tokens": 5, "completion_tokens": 5}

SRC = (ROOT / "benchmark/dev/d10.c").read_text().split("\n")
ln = next(i + 1 for i, l in enumerate(SRC) if "i <= SAMPLE_COUNT" in l)
good = {"reason": "x", "code_quote": SRC[ln - 1].strip(), "line": ln, "bug_type": "MEM-01"}
badq = {"reason": "x", "code_quote": "this text is nowhere", "line": ln, "bug_type": "MEM-02"}
oor = {"reason": "x", "code_quote": "x", "line": 9999, "bug_type": "PER-01"}
fs, _ = run_single(Fake([good, badq, oor]), "dev/d10.c")
by = {(f.bug_type): f for f in fs}
check("single LLM: correct line+quote is grounded", by["MEM-01"].quote_on_line is True)
check("single LLM: quote not on the line -> hallucination flag", by["MEM-02"].quote_on_line is False)
check("single LLM: out-of-range line -> hallucination flag, no crash", by["PER-01"].quote_on_line is False)
fs, _ = run_single(Fake([]), "dev/d12.c")
check("single LLM: empty answer on a clean file -> no findings", fs == [])

from agents.single import run_single_variant
class Seq:
    """returns the same JSON for every call and counts calls"""
    def __init__(self, payload): self.payload, self.calls = payload, 0
    def chat(self, messages, tools=None, fmt=None):
        self.calls += 1
        return {"message": {"content": json.dumps(self.payload)}, "prompt_tokens": 1, "completion_tokens": 1}
chk = {"checks": [{"bug_type": t, "reason": "x", "code_quote": "", "line": 0, "present": False} for t in ("INT-01", "INT-02")] +
       [{"bug_type": "MEM-01", "reason": "x", "code_quote": SRC[ln - 1].strip(), "line": ln, "present": True}]}
fs, _ = run_single_variant(Seq(chk), "dev/d10.c", "checklist")
check("checklist variant: only present=true entries become findings", [f.bug_type for f in fs] == ["MEM-01"] and fs[0].quote_on_line)
llm = Seq({"findings": [good]})
fs, _ = run_single_variant(llm, "dev/d10.c", "pertype")
check("pertype variant: ten calls per file, ids outside the asked type ignored by schema/enum use", llm.calls == 10)
fs, _ = run_single_variant(Seq({"findings": [good]}), "dev/d10.c", "open")
check("open variant parses findings", len(fs) == 1 and fs[0].quote_on_line)
fs, _ = run_single_variant(Seq("not even json"), "dev/d10.c", "open")
check("open variant: garbage answer does not crash", fs == [])

with tempfile.TemporaryDirectory() as t:
    p = subprocess.run([sys.executable, str(ROOT / "tools/run_eval.py"), "--split", "dev", "--setups", "rules", "--out", t],
                       capture_output=True, text=True)
    md = (Path(t) / "eval_dev.md")
    check("run_eval end-to-end with the rules setup writes a table", p.returncode == 0 and md.exists() and "Rules only" in md.read_text())
p = subprocess.run([sys.executable, str(ROOT / "tools/run_eval.py"), "--split", "test", "--setups", "rules"], capture_output=True, text=True)
check("run_eval refuses the TEST split without --allow-test", p.returncode != 0 and "Refusing" in (p.stdout + p.stderr))
print("\nPASS" if ok else "\nFAIL"); sys.exit(0 if ok else 1)
