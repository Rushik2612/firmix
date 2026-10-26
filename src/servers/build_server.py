#!/usr/bin/env python3
"""
build_server.py -- MCP server: compile and lint STM32 C code with the real toolchain.

No LLM inside. Used by the fixer agent to prove a proposed patch compiles.
Run (stdio):  python src/servers/build_server.py
Env: FIRMIX_GCC, FIRMIX_CPPCHECK (paths), FIRMIX_WORKSPACE (extra readable folder)
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from buildtools import api  # noqa: E402

try:
    from mcp.server.mcpserver import MCPServer as _Server
except ImportError:
    from mcp.server.fastmcp import FastMCP as _Server

server = _Server("firmix-build")
for _fn in api.TOOLS:
    server.add_tool(_fn, name=_fn.__name__, description=(_fn.__doc__ or _fn.__name__).strip())

if __name__ == "__main__":
    server.run()
