#!/usr/bin/env python3
"""Build knowledge/index.json from the real docs in deps/ + SPEC.md. Run from the firmix folder."""
import json, subprocess, sys
from pathlib import Path
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))
from knowledge.chunker import build_chunks
from knowledge.store import Store, INDEX_PATH


def rev(p):
    try:
        return subprocess.run(["git", "-C", str(p), "rev-parse", "--short", "HEAD"],
                              capture_output=True, text=True).stdout.strip() or None
    except Exception:
        return None

chunks, missing = build_chunks(ROOT)
meta = {"deps_revisions": {d.name: rev(d) for d in (ROOT / "deps").iterdir() if d.is_dir()},
        "missing_files": missing, "chunk_count": len(chunks)}
Store(chunks, meta).save()
from collections import Counter
print(f"{len(chunks)} chunks -> {INDEX_PATH}")
print("missing source files:", missing or "none")
for src, n in Counter(c["source"] for c in chunks).most_common():
    print(f"  {n:4d}  {src}")
