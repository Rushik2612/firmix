#!/usr/bin/env python3
"""Plumbing test with a scripted fake LLM (no Ollama needed): checks that candidates flow into
prompts, tool calls are executed and logged, verdict JSON is parsed, and the test split is refused."""
import json, sys
from pathlib import Path
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src")); sys.path.insert(0, str(ROOT / "tools"))
from agents.reasoning import run_reasoning
import run_agents


class FakeLLM:
    """Round 1: asks for a tool. Then: answers 'bug' at the candidate's own line, quoting that line."""
    def __init__(self):
        self.calls = self.prompt_tokens = self.completion_tokens = 0
        self.asked_tool = False

    def chat(self, messages, tools=None, fmt=None):
        self.calls += 1
        if tools and not self.asked_tool:
            self.asked_tool = True
            return {"message": {"role": "assistant", "content": "", "tool_calls": [
                {"function": {"name": "get_priorities", "arguments": {"file": "dev/d07.c"}}}]},
                "prompt_tokens": 10, "completion_tokens": 2}
        if fmt:
            user = messages[1]["content"]
            line = int(user.split(" at line ")[1].split()[0])
            quote = [l for l in Path(ROOT / "benchmark/dev/d07.c").read_text().splitlines()][line - 1].strip()
            v = {"exemption_checked": "none applies", "reason": "matches rule", "code_quote": quote,
                 "line": line, "verdict": "bug"}
            return {"message": {"role": "assistant", "content": json.dumps(v)}, "prompt_tokens": 10, "completion_tokens": 5}
        return {"message": {"role": "assistant", "content": "ok"}, "prompt_tokens": 1, "completion_tokens": 1}


ok = True
llm = FakeLLM()
findings, log = run_reasoning(llm, "dev/d07.c")
bugs = [f for f in findings if f.verdict == "bug"]
print("findings:", [(f.bug_type, f.line, f.verdict) for f in findings])
ok &= any(f.bug_type == "RTOS-03" and f.line == 60 for f in bugs)
print("tool call executed and logged:", any(f.tool_calls for f in findings)); ok &= any(f.tool_calls for f in findings)
from agents.reasoning import build_prompt
pr = build_prompt("dev/d07.c", log[0]["candidate"])
has_rule = "Not a bug" in pr and "EVIDENCE EXCERPTS" in pr and "FUNCTION SOURCE" in pr
print("prompt contains rule, evidence and function source:", has_rule); ok &= has_rule
try:
    run_agents.main(["--split", "test"]); ok = False; print("test split NOT refused")
except SystemExit as e:
    print("test split refused:", "Refusing" in str(e)); ok &= "Refusing" in str(e)
print("\nPASS" if ok else "\nFAIL"); sys.exit(0 if ok else 1)
