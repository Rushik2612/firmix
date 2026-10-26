"""
store.py -- BM25 keyword index + search over the doc chunks. Pure Python, no model download.

Why BM25 first: questions about firmware docs are full of EXACT identifiers
(xQueueSendFromISR, HAL_NVIC_SetPriority). Exact-term search finds those reliably, works
offline, is deterministic, and can be explained in an interview. Embeddings can be added later
if the retrieval evaluation (tools/eval_retrieval.py) shows BM25 is not enough.
"""
from __future__ import annotations

import json
import math
import re
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
INDEX_PATH = ROOT / "knowledge" / "index.json"
K1, B = 1.5, 0.75
SYMBOL_BOOST = 6.0

_WORD = re.compile(r"[A-Za-z_][A-Za-z0-9_]*|\d+")
_STOP = {"the", "a", "an", "of", "to", "in", "is", "are", "and", "or", "for", "on", "be", "it",
         "this", "that", "with", "as", "by", "at", "from", "which", "what", "how", "do", "does"}


def tokenize(text: str) -> list[str]:
    """lowercase words; identifiers also contribute their camelCase/underscore parts."""
    toks = []
    for w in _WORD.findall(text):
        lw = w.lower()
        toks.append(lw)
        parts = re.sub(r"([a-z])([A-Z])", r"\1 \2", w).replace("_", " ").lower().split()
        if len(parts) > 1:
            toks.extend(parts)
    return [t for t in toks if t not in _STOP and len(t) > 1]


class Store:
    def __init__(self, chunks: list[dict], meta: dict | None = None):
        self.chunks = chunks
        self.meta = meta or {}
        self.tf = [Counter(tokenize((c.get("symbol") or "") + " " + (c.get("symbol") or "") + " " + c["text"]))
                   for c in chunks]
        self.len = [sum(t.values()) for t in self.tf]
        self.avg = sum(self.len) / max(len(self.len), 1)
        df = Counter()
        for t in self.tf:
            df.update(t.keys())
        n = len(chunks)
        self.idf = {w: math.log(1 + (n - d + 0.5) / (d + 0.5)) for w, d in df.items()}
        self.by_symbol: dict[str, list[int]] = {}
        for i, c in enumerate(chunks):
            if c.get("symbol"):
                self.by_symbol.setdefault(c["symbol"].lower(), []).append(i)

    # ------------------------------------------------------------------ io
    @classmethod
    def load(cls, path: Path = INDEX_PATH) -> "Store":
        d = json.loads(Path(path).read_text(encoding="utf-8"))
        return cls(d["chunks"], d.get("meta"))

    def save(self, path: Path = INDEX_PATH):
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        Path(path).write_text(json.dumps({"meta": self.meta, "chunks": self.chunks}, indent=0), encoding="utf-8")

    # --------------------------------------------------------------- search
    def search(self, query: str, k: int = 5, source: str | None = None):
        q = tokenize(query)
        qset = set(q)
        scores = []
        qsyms = {w.lower() for w in _WORD.findall(query)}
        for i, tf in enumerate(self.tf):
            c = self.chunks[i]
            if source and source not in c["source"]:
                continue
            s = 0.0
            for w in qset:
                f = tf.get(w, 0)
                if f:
                    s += self.idf.get(w, 0) * f * (K1 + 1) / (f + K1 * (1 - B + B * self.len[i] / self.avg))
            if c.get("symbol") and c["symbol"].lower() in qsyms:
                s += SYMBOL_BOOST          # exact API name in the question
            if s > 0:
                scores.append((s, i))
        scores.sort(key=lambda x: -x[0])
        return [self._hit(i, s) for s, i in scores[:k]]

    def lookup(self, symbol: str):
        return [self._hit(i, None) for i in self.by_symbol.get(symbol.lower(), [])]

    def get(self, chunk_id: int):
        return self._hit(chunk_id, None) if 0 <= chunk_id < len(self.chunks) else None

    def _hit(self, i, score):
        c = self.chunks[i]
        return {"id": c["id"], "score": None if score is None else round(score, 3),
                "citation": f"{c['source']}:{c['line']}", "symbol": c.get("symbol"), "text": c["text"]}
