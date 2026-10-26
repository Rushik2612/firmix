#!/usr/bin/env python3
"""Smoke test for the build MCP server. Usage: python tools/test_build_mcp.py"""
import asyncio, json, sys
from pathlib import Path
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

ROOT = Path(__file__).resolve().parent.parent


def err(res):
    return bool(getattr(res, "isError", getattr(res, "is_error", False)))


def data(res):
    return json.loads(res.content[0].text)


async def main():
    params = StdioServerParameters(command=sys.executable,
                                   args=[str(ROOT / "src" / "servers" / "build_server.py")])
    ok = True
    src = (ROOT / "benchmark" / "files" / "f028.c").read_text(encoding="utf-8")
    good = src.replace("sizeof(header_template))", "sizeof(frame))", 1)
    broken = src.replace("sizeof(header_template))", "sizeof(header_template)", 1)
    async with stdio_client(params) as (r, w):
        async with ClientSession(r, w) as s:
            await s.initialize()
            names = [t.name for t in (await s.list_tools()).tools]
            print(len(names), "tools:", names); ok &= len(names) == 5
            d = data(await s.call_tool("compile_file", {"file": "files/f001.c"}))
            print("f001 compiles:", d["ok"], "| warnings:", len(d["warnings"])); ok &= d["ok"]
            d = data(await s.call_tool("compile_file", {"file": "files/f028.c"}))
            print("f028 GCC warns about the overflow:", bool(d["warnings"])); ok &= bool(d["warnings"])
            d = data(await s.call_tool("check_fix", {"file": "files/f028.c", "patched_source": good}))
            print("good fix compiles:", d["compiles"], "| new warnings:", len(d["new_warnings"])); ok &= d["compiles"]
            d = data(await s.call_tool("check_fix", {"file": "files/f028.c", "patched_source": broken}))
            print("broken fix compiles:", d["compiles"]); ok &= (d["compiles"] is False)
            bad = await s.call_tool("compile_source", {"source": '#include "../../x.h"\nint a;'})
            print("path-trick #include blocked:", err(bad)); ok &= err(bad)
            d = data(await s.call_tool("cppcheck_file", {"file": "files/f028.c"}))
            print("cppcheck serious findings on f028:", len(d["serious"]), "| aborted:", d["headers_pass_aborted"])
            ok &= len(d["serious"]) >= 1 and not d["headers_pass_aborted"]
    print("\nPASS" if ok else "\nFAIL")
    sys.exit(0 if ok else 1)

asyncio.run(main())
