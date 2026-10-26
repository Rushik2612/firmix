#!/usr/bin/env python3
"""
measure_candidates.py -- how many seeded bugs does the deterministic candidate stage surface?

Candidate RECALL  = buggy files with >=1 candidate of the SAME bug type on an accepted line.
This is the ceiling for everything downstream: the LLM judge can only confirm what the
code-facts stage proposes. Candidate COUNT on clean files shows how much the judge must reject.
MEASUREMENT ONLY: never edit rules after looking at test-set output without logging it.

Usage:  python tools/measure_candidates.py --split test|dev
"""
import argparse, json, sys
from collections import defaultdict
from pathlib import Path
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))
from codefacts.facts import Facts
from codefacts.rules import all_candidates

GROUPS = {"INT": "interrupts", "RTOS": "RTOS", "PER": "peripherals/HAL", "MEM": "memory"}

def wilson(k, n, z=1.96):
    if n == 0: return (0, 0)
    p = k / n; d = 1 + z*z/n; c = (p + z*z/(2*n)) / d
    h = z * ((p*(1-p)/n + z*z/(4*n*n)) ** 0.5) / d
    return (max(0, c-h), min(1, c+h))

ap = argparse.ArgumentParser(); ap.add_argument("--split", default="test"); ap.add_argument("-v", action="store_true")
a = ap.parse_args()
gt = json.load(open(ROOT / "benchmark" / "ground_truth.json", encoding="utf-8"))["entries"]
rows = [e for e in gt if e["split"] == a.split]
hit, tot = defaultdict(int), defaultdict(int)
misses, clean_counts, per_file_noise = [], {}, {}
for e in rows:
    F = Facts(ROOT / "benchmark" / e["file"])
    cs = all_candidates(F)
    name = Path(e["file"]).stem
    if e["label"] == "clean":
        clean_counts[name] = len(cs)
        continue
    g = GROUPS[e["bug_type"].split("-")[0]]
    tot[g] += 1
    good = [c for c in cs if c.bug_type == e["bug_type"] and (c.line in e["accepted_lines"]
            or any(l in e["accepted_lines"] for l in c.alt_lines))]
    if good: hit[g] += 1
    else: misses.append((name, e["bug_type"], e["accepted_lines"], [(c.bug_type, c.line) for c in cs]))
    per_file_noise[name] = len(cs) - len(good)
K, N = sum(hit.values()), sum(tot.values())
lo, hi = wilson(K, N)
print(f"split={a.split}  candidate recall: {K}/{N} = {100*K/max(N,1):.0f}%  (95% CI {100*lo:.0f}-{100*hi:.0f}%)")
for g in GROUPS.values():
    if tot[g]: print(f"  {g:<16} {hit[g]}/{tot[g]}")
print("misses:")
for m in misses: print("  ", m)
if clean_counts:
    print(f"clean files: candidates per file = {clean_counts}; files with >=1 candidate: {sum(1 for v in clean_counts.values() if v)}/{len(clean_counts)}")
if per_file_noise:
    import statistics
    print(f"extra (non-matching) candidates per buggy file: mean {statistics.mean(per_file_noise.values()):.1f}, max {max(per_file_noise.values())}")
