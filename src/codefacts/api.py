"""
api.py -- the code-facts tools as plain Python functions returning JSON-friendly data.

The MCP server (servers/codefacts_server.py) is a thin wrapper over these, so they can be
unit-tested without MCP. Everything here is deterministic: same file in, same facts out.
Agents never get to invent a line number: `validate_line` and `find_line` let CODE check them.
"""
from __future__ import annotations

import os
import re
from pathlib import Path

from .facts import Facts
from . import rules

ROOT = Path(__file__).resolve().parents[2]
# files the server may read: the repo's benchmark/ folder, plus an optional workspace dir
_ALLOWED = [ROOT / "benchmark"]
if os.environ.get("FIRMIX_WORKSPACE"):
    _ALLOWED.append(Path(os.environ["FIRMIX_WORKSPACE"]).resolve())

_CACHE: dict[str, tuple[float, Facts]] = {}


class FactsError(ValueError):
    pass


def _resolve(file: str) -> Path:
    p = Path(file)
    if not p.is_absolute():
        p = ROOT / "benchmark" / p if not (ROOT / p).exists() else ROOT / p
    p = p.resolve()
    if p.suffix not in (".c", ".h"):
        raise FactsError("only .c and .h files can be analysed")
    if not any(a == p or a in p.parents for a in _ALLOWED):
        raise FactsError(f"file is outside the allowed folders: {[str(a) for a in _ALLOWED]}")
    if not p.exists():
        raise FactsError(f"no such file: {file}")
    return p


def load(file: str) -> Facts:
    p = _resolve(file)
    mt = p.stat().st_mtime
    hit = _CACHE.get(str(p))
    if hit and hit[0] == mt:
        return hit[1]
    F = Facts(p)
    _CACHE[str(p)] = (mt, F)
    return F


# --------------------------------------------------------------------------- tools
def list_functions(file: str) -> dict:
    F = load(file)
    return {"file": file, "functions": [
        {"name": n, "start": f.start, "end": f.end, "static": f.is_static,
         "isr_context": n in F.isr_context, "isr_chain": F.isr_context.get(n)}
        for n, f in sorted(F.functions.items(), key=lambda kv: kv[1].start)]}


def get_function_source(file: str, name: str) -> dict:
    F = load(file)
    if name not in F.functions:
        raise FactsError(f"no function '{name}' in {file}")
    f = F.functions[name]
    return {"name": name, "start": f.start, "end": f.end, "source": F.snippet(f.start, f.end)}


def get_calls(file: str, function: str | None = None, name: str | None = None) -> dict:
    F = load(file)
    rows = [{"line": c.line, "function": c.function, "name": c.name, "args": c.args,
             "in_isr_context": F.is_isr(c.function)}
            for c in F.calls
            if (function is None or c.function == function) and (name is None or c.name == name
                                                                  or re.fullmatch(name, c.name))]
    return {"file": file, "calls": sorted(rows, key=lambda r: r["line"])}


def get_isr_context(file: str) -> dict:
    F = load(file)
    return {"file": file, "roots": sorted(F.isr_roots), "isr_functions": F.isr_context,
            "rule": "SPEC section 2: *_IRQHandler, SysTick_Handler, HAL_*Callback (not Msp*), and callees"}


def get_globals(file: str) -> dict:
    F = load(file)
    return {"file": file, "globals": [g.__dict__ for g in sorted(F.globals.values(), key=lambda g: g.line)],
            "macros": F.macros}


def get_shared_variables(file: str) -> dict:
    F = load(file)
    out = []
    for var, d in rules._shared_vars(F).items():
        g = F.globals[var]
        out.append({"var": var, "type": g.type, "volatile": g.volatile, "decl_line": g.line,
                    "isr_accesses": [{"line": a.line, "function": a.function, "kind": a.kind} for a in d["isr"]],
                    "task_accesses": [{"line": a.line, "function": a.function, "kind": a.kind,
                                       "in_loop_condition": a.in_loop_cond, "in_critical_section": a.in_critical}
                                      for a in d["task"]]})
    return {"file": file, "shared_variables": out}


def get_accesses(file: str, var: str) -> dict:
    F = load(file)
    return {"file": file, "var": var,
            "accesses": [{"line": a.line, "function": a.function, "kind": a.kind,
                          "in_loop_condition": a.in_loop_cond, "in_critical_section": a.in_critical,
                          "in_isr_context": F.is_isr(a.function), "text": a.text}
                         for a in F.accesses if a.var == var]}


def get_priorities(file: str) -> dict:
    F = load(file)
    return {"file": file, "max_syscall_priority": rules.MAX_SYSCALL_PRIO,
            "priorities": [{"irq": irq, "preempt_priority": pre, "line": ln, "call": txt,
                            "handler": rules.irq_handler_name(irq)}
                           for irq, pre, ln, txt in rules.priorities(F)]}


def get_gpio_configs(file: str) -> dict:
    F = load(file)
    return {"file": file, "configs": [{k: v for k, v in c.items() if k not in ("raw_mode", "raw_alt")}
                                      for c in rules.gpio_configs(F)]}


def get_clock_enables(file: str) -> dict:
    F = load(file)
    return {"file": file, "clock_enables": {k: [{"line": l, "function": f} for l, f in v]
                                            for k, v in rules.clock_enables(F).items()}}


def get_candidates(file: str, bug_type: str | None = None) -> dict:
    F = load(file)
    cs = [c.to_dict() for c in rules.all_candidates(F) if bug_type is None or c.bug_type == bug_type]
    return {"file": file, "count": len(cs), "candidates": cs}


def get_snippet(file: str, start: int, end: int) -> dict:
    F = load(file)
    if start < 1 or end < start or end - start > 200:
        raise FactsError("need 1 <= start <= end and at most 200 lines")
    return {"file": file, "start": start, "end": min(end, len(F.lines)), "text": F.snippet(start, end)}


def _norm(s: str) -> str:
    return re.sub(r"\s+", " ", s.strip())


def validate_line(file: str, line: int, expected_text: str) -> dict:
    """Code check for a claimed finding: does `expected_text` really appear on `line`?
    This is the line-number guard (an LLM's line number is never trusted on its own)."""
    F = load(file)
    if not 1 <= line <= len(F.lines):
        return {"valid": False, "reason": "line out of range", "line_count": len(F.lines)}
    actual = F.line_text(line)
    ok = bool(_norm(expected_text)) and _norm(expected_text) in _norm(actual)
    out = {"valid": ok, "line": line, "actual_text": actual.strip()}
    if not ok:
        out["suggested_lines"] = find_line(file, expected_text)["lines"]
    return out


def find_line(file: str, text: str) -> dict:
    F = load(file)
    n = _norm(text)
    return {"file": file, "text": text,
            "lines": [i for i, l in enumerate(F.lines, start=1) if n and n in _norm(l)]}


TOOLS = [list_functions, get_function_source, get_calls, get_isr_context, get_globals,
         get_shared_variables, get_accesses, get_priorities, get_gpio_configs,
         get_clock_enables, get_candidates, get_snippet, validate_line, find_line]
