#!/usr/bin/env python3
"""
codefacts_server.py -- MCP server #1 of 3: deterministic facts about an STM32 C file.

No LLM inside. Every tool is a function of the source text (tree-sitter), so a finding that
cites these tools can be re-run and re-checked.

Run (stdio):   python src/servers/codefacts_server.py
Optional:      FIRMIX_WORKSPACE=/path/to/extra/dir  (extra folder the server may read)
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from codefacts import api  # noqa: E402

try:                                    # mcp >= 2
    from mcp.server.mcpserver import MCPServer as _Server
except ImportError:                     # mcp 1.x
    from mcp.server.fastmcp import FastMCP as _Server

server = _Server("firmix-codefacts")

for _fn in api.TOOLS:
    server.add_tool(_fn, name=_fn.__name__, description=(_fn.__doc__ or _fn.__name__).strip().split("\n")[0]
                    if _fn.__doc__ else _fn.__name__)

if __name__ == "__main__":
    server.run()
