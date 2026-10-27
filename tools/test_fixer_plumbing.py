#!/usr/bin/env python3
"""Fixer plumbing test with a scripted fake LLM (no Ollama). Checks that CODE, not the model, decides
whether a fix counts: compile check, 'bug still present' re-run, retry with feedback, bad-edit rejection."""
import json, sys
from pathlib import Path
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))
from agents.fixer import fix_finding, apply_edits
from codefacts import api as cf

FILE = "dev/d10.c"
SRC = (ROOT / "benchmark" / FILE).read_text().split("\n")
LOOP = next(i + 1 for i, l in enumerate(SRC) if "i <= SAMPLE_COUNT" in l)
cand = next(c for c in cf.get_candidates(FILE)["candidates"] if c["bug_type"] == "MEM-01")


class Fake:
    """Returns the scripted answers in order; records the messages it was sent."""
    def __init__(self, answers):
        self.answers, self.seen, self.calls = list(answers), [], 0
        self.prompt_tokens = self.completion_tokens = 0

    def chat(self, messages, tools=None, fmt=None):
        self.calls += 1
        self.seen.append(messages[-1]["content"])
        return {"message": {"role": "assistant", "content": json.dumps(self.answers.pop(0))},
                "prompt_tokens": 1, "completion_tokens": 1}


def edit(text, line=LOOP):
    return {"explanation": "x", "edits": [{"start_line": line, "end_line": line, "new_text": text}]}


good = edit(SRC[LOOP - 1].replace("<=", "<"))
broken = edit(SRC[LOOP - 1].replace("<=", "<") + " +++")          # does not compile
noop = edit(SRC[LOOP - 1])                                          # compiles, bug still there
oob = {"explanation": "x", "edits": [{"start_line": 9999, "end_line": 9999, "new_text": "x"}]}
ok = True

def check(name, cond):
    global ok
    print(f"{name}:", bool(cond)); ok &= bool(cond)

r = fix_finding(Fake([good]), FILE, cand)
check("good fix succeeds on attempt 1 (compiles, bug removed)", r.success and r.attempts == 1 and r.compiles and r.bug_removed)
check("good fix is a small diff", 0 < r.changed_lines <= 4)

llm = Fake([broken, good])
r = fix_finding(llm, FILE, cand)
check("non-compiling fix is rejected, compiler feedback sent, retry succeeds", r.success and r.attempts == 2 and "does not compile" in llm.seen[1])

llm = Fake([noop, good])
r = fix_finding(llm, FILE, cand)
check("a fix that compiles but leaves the bug is NOT a success on that attempt", r.attempts == 2 and "still flags" in llm.seen[1])

r = fix_finding(Fake([noop, noop, noop]), FILE, cand)
check("three failed attempts -> failure, not success", (not r.success) and r.attempts == 3 and r.compiles and not r.bug_removed)

r = fix_finding(Fake([oob, oob, oob]), FILE, cand)
check("out-of-range edits are rejected by code", (not r.success) and "outside the file" in r.failure)

p, why = apply_edits("a\nb\nc", [{"start_line": 1, "end_line": 2, "new_text": "x"}, {"start_line": 2, "end_line": 3, "new_text": "y"}])
check("overlapping edits are rejected", p is None and "overlap" in why)
p, why = apply_edits("a\nb\nc", [{"start_line": 2, "end_line": 2, "new_text": "b1\nb2"}])
check("insert via multi-line replacement works", p == "a\nb1\nb2\nc")

p, why = apply_edits("a\nb\nc", [{"start_line": 2, "end_line": 2, "new_text": "  10: int b;"}])
check("copied line-number label '  10: ' is stripped from new_text", p == "a\nint b;\nc")
p, why = apply_edits("a\nb\nc", [{"start_line": 2, "end_line": 2, "new_text": "  11| x = 1;\n  12| y = 2;"}])
check("copied 'NN|' labels are stripped", p == "a\nx = 1;\ny = 2;\nc")
p, why = apply_edits("a\nb\nc", [{"start_line": 2, "end_line": 2, "new_text": "case 1: x();"}])
check("real code like 'case 1:' is left alone", p == "a\ncase 1: x();\nc")
print("\nPASS" if ok else "\nFAIL"); sys.exit(0 if ok else 1)
