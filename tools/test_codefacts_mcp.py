#!/usr/bin/env python3
"""Smoke test: start the code-facts MCP server over stdio and call it like an agent would.
Usage: python tools/test_codefacts_mcp.py"""
import asyncio, json, sys
from pathlib import Path
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

ROOT = Path(__file__).resolve().parent.parent


def err(res):
    return bool(getattr(res, "isError", getattr(res, "is_error", False)))


async def main():
    params = StdioServerParameters(command=sys.executable,
                                   args=[str(ROOT / "src" / "servers" / "codefacts_server.py")])
    ok = True
    async with stdio_client(params) as (r, w):
        async with ClientSession(r, w) as s:
            await s.initialize()
            names = [t.name for t in (await s.list_tools()).tools]
            print(len(names), "tools:", names); ok &= len(names) == 14
            res = await s.call_tool("get_candidates", {"file": "dev/d07.c", "bug_type": "RTOS-03"})
            d = json.loads(res.content[0].text)
            print("d07 RTOS-03 candidates:", d["count"]); ok &= d["count"] == 1
            res = await s.call_tool("validate_line", {"file": "dev/d07.c", "line": 60, "expected_text": "xQueueSendFromISR"})
            v = json.loads(res.content[0].text)["valid"]; print("validate_line (right):", v); ok &= v
            res = await s.call_tool("validate_line", {"file": "dev/d07.c", "line": 1, "expected_text": "xQueueSendFromISR"})
            v = json.loads(res.content[0].text)["valid"]; print("validate_line (wrong line):", v); ok &= (v is False)
            bad = await s.call_tool("get_snippet", {"file": str(Path.home() / "outside.c"), "start": 1, "end": 2})
            print("file outside allowed folders blocked:", err(bad)); ok &= err(bad)
    print("\nPASS" if ok else "\nFAIL")
    sys.exit(0 if ok else 1)

asyncio.run(main())
