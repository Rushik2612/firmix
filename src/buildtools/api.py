"""api.py -- the build tools as plain functions (the MCP server wraps these)."""
from __future__ import annotations

from codefacts.api import _resolve, FactsError   # same allowed-folder rule as code-facts
from . import runner


def compile_file(file: str) -> dict:
    """Compile a benchmark file with arm-none-eabi-gcc (-Wall -Wextra, -O0 and -O2)."""
    return runner.compile_path(_resolve(file), label=file)


def compile_source(source: str, name: str = "patched.c") -> dict:
    """Compile C source text (e.g. a proposed fix). Only plain #include names are allowed."""
    return runner.compile_text(source, name)


def cppcheck_file(file: str) -> dict:
    """Run cppcheck on a benchmark file."""
    return runner.cppcheck_path(_resolve(file), label=file)


def cppcheck_source(source: str, name: str = "patched.c") -> dict:
    """Run cppcheck on C source text."""
    return runner.cppcheck_text(source, name)


def check_fix(file: str, patched_source: str) -> dict:
    """Check a proposed fix: does it compile, did it add new warnings, how many lines changed."""
    return runner.check_fix(_resolve(file), patched_source, label=file)


TOOLS = [compile_file, compile_source, cppcheck_file, cppcheck_source, check_fix]
