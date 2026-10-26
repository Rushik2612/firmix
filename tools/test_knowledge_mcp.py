#!/usr/bin/env python3
"""Smoke test for the knowledge MCP server. Usage: python tools/test_knowledge_mcp.py"""
import asyncio, json, sys
from pathlib import Path
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

ROOT = Path(__file__).resolve().parent.parent


def data(res):
    return json.loads(res.content[0].text)


async def main():
    params = StdioServerParameters(command=sys.executable,
                                   args=[str(ROOT / "src" / "servers" / "knowledge_server.py")])
    ok = True
    async with stdio_client(params) as (r, w):
        async with ClientSession(r, w) as s:
            await s.initialize()
            names = [t.name for t in (await s.list_tools()).tools]
            print(len(names), "tools:", names); ok &= len(names) == 4
            d = data(await s.call_tool("lookup_symbol", {"name": "HAL_NVIC_SetPriority"}))
            print("lookup HAL_NVIC_SetPriority:", d["found"], "->", d["hits"][0]["citation"] if d["found"] else "")
            ok &= d["found"]
            d = data(await s.call_tool("search_docs", {"query": "give a semaphore from an ISR", "k": 3}))
            top = [h["symbol"] for h in d["hits"]]
            print("search 'give a semaphore from an ISR':", top); ok &= "xSemaphoreGiveFromISR" in top
            d = data(await s.call_tool("lookup_symbol", {"name": "RTOS-03"}))
            print("lookup RTOS-03 (project rule):", d["found"], "->", d["hits"][0]["citation"] if d["found"] else "")
            ok &= d["found"]
            d = data(await s.call_tool("index_info", {}))
            print("index chunks:", d["chunks"]); ok &= d["chunks"] > 500
    print("\nPASS" if ok else "\nFAIL")
    sys.exit(0 if ok else 1)

asyncio.run(main())
