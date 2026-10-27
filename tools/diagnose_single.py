#!/usr/bin/env python3
"""
diagnose_single.py -- is the single-LLM baseline losing answers in my harness? DEV split only.
For each dev file it makes the same call run_single makes and prints: did the JSON parse, how many findings, how many
tokens were generated (num_predict is 1024: reaching it means the answer was cut off), and Ollama's done_reason.
A parse failure or a truncated answer would silently become 'no findings' in run_single, which would make the baseline
look weaker than it is. This script only READS; it changes nothing.

    python tools/diagnose_single.py
"""
import json, sys
from pathlib import Path
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))
from agents.llm import OllamaLLM
from agents.single import SYSTEM, SCHEMA, _rules
from codefacts import api as cf

gt = json.loads((ROOT / "benchmark/ground_truth.json").read_text(encoding="utf-8"))["entries"]
llm = OllamaLLM()
rules = _rules()
bad = trunc = 0
for e in [x for x in gt if x["split"] == "dev"]:
    f = e["file"]
    numbered = "\n".join(f"{i:4d}| {l}" for i, l in enumerate(cf.load(f).lines, start=1))
    user = f"BUG TYPES AND RULES:\n{rules}\n\nFILE {f} (line numbers before the |):\n{numbered}\n\nList the bugs. JSON only."
    r = llm.chat([{"role": "system", "content": SYSTEM}, {"role": "user", "content": user}], fmt=SCHEMA)
    raw = r["message"].get("content", "")
    try:
        n = len(json.loads(raw).get("findings", [])); ok = True
    except Exception:
        n, ok = -1, False
    cut = r["completion_tokens"] >= 1000 or r.get("done_reason") == "length"
    bad += (not ok); trunc += cut
    print(f"{f.split('/')[-1]:7} truth={e.get('bug_type', 'clean'):7} parse_ok={ok!s:5} findings={n:2d} prompt_tok={r['prompt_tokens']:5d} "
          f"gen_tok={r['completion_tokens']:4d} done={r.get('done_reason')} {'TRUNCATED' if cut else ''}")
print(f"\nparse failures: {bad}   truncated answers: {trunc}   (both should be 0 for the baseline to be trusted)")
