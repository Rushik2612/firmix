"""
toolbox.py -- gives agents the tools of the three servers and LOGS every call.

The functions are the same ones the MCP servers expose (codefacts.api, buildtools.api,
knowledge.api). In the evaluation they are called in-process (fast, deterministic); the MCP
servers expose the identical functions for the live demo. The log is the audit trail: a
finding may only cite evidence that really appears here.
"""
from __future__ import annotations

import inspect
import json
import typing

from codefacts import api as cf
from buildtools import api as bd
from knowledge import api as kn

ALL_TOOLS = {f.__name__: f for mod in (cf, bd, kn) for f in mod.TOOLS}
RESULT_LIMIT = 2500        # characters of tool output shown to the LLM


def _json_type(annotation) -> str:
    s = str(annotation)
    if "int" in s:
        return "integer"
    return "string"


def schema_for(fn) -> dict:
    sig = inspect.signature(fn)
    props, required = {}, []
    for name, p in sig.parameters.items():
        props[name] = {"type": _json_type(p.annotation)}
        if p.default is inspect.Parameter.empty:
            required.append(name)
    desc = (fn.__doc__ or fn.__name__).strip().split("\n")[0]
    return {"type": "function", "function": {
        "name": fn.__name__, "description": desc,
        "parameters": {"type": "object", "properties": props, "required": required}}}


class ToolBox:
    def __init__(self, allowed: list[str]):
        unknown = [a for a in allowed if a not in ALL_TOOLS]
        if unknown:
            raise ValueError(f"unknown tools: {unknown}")
        self.allowed = allowed
        self.log: list[dict] = []

    @property
    def schemas(self):
        return [schema_for(ALL_TOOLS[n]) for n in self.allowed]

    def call(self, name: str, args: dict | None) -> str:
        """Run a tool; return text for the LLM. Errors are returned as text, never raised."""
        args = args or {}
        if name not in self.allowed:
            out = {"error": f"tool '{name}' is not available to this agent"}
        else:
            try:
                out = ALL_TOOLS[name](**args)
            except Exception as e:
                out = {"error": f"{type(e).__name__}: {e}"}
        self.log.append({"tool": name, "args": args, "result": out})
        text = json.dumps(out, default=str)
        return text if len(text) <= RESULT_LIMIT else text[:RESULT_LIMIT] + " ...[truncated]"
