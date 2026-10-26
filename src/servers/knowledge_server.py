#!/usr/bin/env python3
"""
knowledge_server.py -- MCP server: citable STM32 / FreeRTOS / CMSIS documentation lookup.

No LLM inside. Index = doc comments from the real open-source repos in deps/ plus SPEC.md,
searched with BM25. Every answer carries a file:line citation.
Run (stdio):  python src/servers/knowledge_server.py     (build the index first: python tools/build_knowledge.py)
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from knowledge import api  # noqa: E402

try:
    from mcp.server.mcpserver import MCPServer as _Server
except ImportError:
    from mcp.server.fastmcp import FastMCP as _Server

server = _Server("firmix-knowledge")
for _fn in api.TOOLS:
    server.add_tool(_fn, name=_fn.__name__, description=(_fn.__doc__ or _fn.__name__).strip())

if __name__ == "__main__":
    server.run()
