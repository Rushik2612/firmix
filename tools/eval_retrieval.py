#!/usr/bin/env python3
"""Retrieval evaluation for the knowledge server: recall@k and MRR on knowledge/queries.json.
A hit = any expected symbol appears among the top-k results' symbols."""
import json, sys
from pathlib import Path
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))
from knowledge.store import Store

store = Store.load()
qs = json.loads((ROOT / "knowledge" / "queries.json").read_text(encoding="utf-8"))["queries"]
r1 = r3 = r5 = 0
rr = 0.0
rows = []
for q in qs:
    hits = store.search(q["q"], k=5)
    exp = {e.lower() for e in q["expect"]}
    rank = next((i + 1 for i, h in enumerate(hits) if (h["symbol"] or "").lower() in exp), None)
    r1 += rank == 1; r3 += bool(rank and rank <= 3); r5 += bool(rank)
    rr += 1 / rank if rank else 0
    rows.append((rank, q["q"], [h["symbol"] for h in hits[:3]]))
n = len(qs)
print(f"queries: {n}   recall@1 {r1}/{n}   recall@3 {r3}/{n}   recall@5 {r5}/{n}   MRR {rr/n:.2f}")
for rank, q, top in rows:
    print(f"  {'ok ' if rank and rank <= 3 else 'MISS'} rank={rank}  {q[:60]:<60} top3={top}")
