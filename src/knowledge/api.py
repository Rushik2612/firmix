"""api.py -- knowledge tools as plain functions (the MCP server wraps these). Deterministic."""
from __future__ import annotations

from .store import Store

_STORE: Store | None = None


def _s() -> Store:
    global _STORE
    if _STORE is None:
        _STORE = Store.load()
    return _STORE


def search_docs(query: str, k: int = 5, source_contains: str | None = None) -> dict:
    """Keyword (BM25) search over STM32 HAL, FreeRTOS, CMSIS docs and the project SPEC. Every hit has a citation (file:line)."""
    k = max(1, min(int(k), 10))
    return {"query": query, "hits": _s().search(query, k, source_contains)}


def lookup_symbol(name: str) -> dict:
    """Exact lookup of an API/macro/bug-type name (e.g. xQueueSendFromISR, HAL_NVIC_SetPriority, RTOS-03)."""
    hits = _s().lookup(name)
    return {"symbol": name, "found": bool(hits), "hits": hits[:5]}


def get_chunk(chunk_id: int) -> dict:
    """Fetch one documentation chunk by id (ids come from search_docs / lookup_symbol)."""
    h = _s().get(int(chunk_id))
    return {"found": h is not None, "chunk": h}


def index_info() -> dict:
    """What the index is built from: chunk count and the git revisions of the source repos."""
    s = _s()
    return {"chunks": len(s.chunks), "meta": s.meta}


TOOLS = [search_docs, lookup_symbol, get_chunk, index_info]
