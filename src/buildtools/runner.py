"""
runner.py -- compile and lint STM32 C source with the real toolchain. Deterministic, no LLM.

Used by the build MCP server. The key job: decide whether a PROPOSED FIX compiles and
whether it introduced new warnings, so a fix is never accepted on the LLM's word alone.

Safety: source text comes from an agent, so it is treated as untrusted:
  * only plain-name #include "x.h" / <x.h> lines are allowed (no paths, no ..),
  * size and time limits,
  * the compiler is run with a fixed argument list (no shell),
  * output is written to a fresh temp dir that is deleted afterwards.
"""
from __future__ import annotations

import difflib
import os
import re
import shutil
import subprocess
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

INCLUDES = [
    ROOT / "include",
    ROOT / "deps" / "cmsis_device_f4" / "Include",
    ROOT / "deps" / "cmsis_core" / "CMSIS" / "Core" / "Include",
    ROOT / "deps" / "stm32f4xx_hal_driver" / "Inc",
    ROOT / "deps" / "FreeRTOS-Kernel" / "include",
    ROOT / "deps" / "FreeRTOS-Kernel" / "portable" / "GCC" / "ARM_CM4F",
]
GCC_FLAGS = ["-mcpu=cortex-m4", "-mthumb", "-mfloat-abi=hard", "-mfpu=fpv4-sp-d16",
             "-DSTM32F411xE", "-DUSE_HAL_DRIVER", "-std=gnu11", "-Wall", "-Wextra",
             "-fdiagnostics-plain-output", "-c"]
CPP_BASE = ["--enable=warning,style,performance,portability", "--inconclusive", "--std=c11",
            "--platform=unix32", "--quiet", "--suppress=missingInclude",
            "--suppress=missingIncludeSystem",
            "--template={file}|{line}|{id}|{severity}|{message}"]
CPP_DEFS = ["-DSTM32F411xE", "-DUSE_HAL_DRIVER", "-D__GNUC__=13", "-D__ARM_ARCH_7EM__=1",
            "-D__ARM_ARCH_PROFILE=77", "-D__ARM_ARCH=7", "-D__ARM_FP=4"]

MAX_SOURCE_BYTES = 200_000
TIMEOUT_S = 120
GCC_DIAG = re.compile(r"^(?P<file>.+?):(?P<line>\d+):(?:\d+:)?\s*(?P<kind>warning|error|fatal error):\s*(?P<msg>.*)$")
INCLUDE_LINE = re.compile(r'^\s*#\s*include(_next)?\s*[<"]([^>"]*)[>"]', re.M)
SAFE_INCLUDE = re.compile(r"^[A-Za-z0-9_]+\.h$")


class BuildError(ValueError):
    pass


def _gcc() -> str:
    exe = os.environ.get("FIRMIX_GCC") or shutil.which("arm-none-eabi-gcc")
    if not exe:
        raise BuildError("arm-none-eabi-gcc not found on PATH (or set FIRMIX_GCC)")
    return exe


def _cppcheck() -> str:
    exe = os.environ.get("FIRMIX_CPPCHECK") or shutil.which("cppcheck")
    for guess in (r"C:\Program Files\Cppcheck\cppcheck.exe", "/usr/bin/cppcheck"):
        if not exe and Path(guess).exists():
            exe = guess
    if not exe:
        raise BuildError("cppcheck not found (set FIRMIX_CPPCHECK)")
    return exe


def check_source_safe(source: str) -> None:
    if len(source.encode("utf-8", "replace")) > MAX_SOURCE_BYTES:
        raise BuildError(f"source larger than {MAX_SOURCE_BYTES} bytes")
    for m in INCLUDE_LINE.finditer(source):
        if m.group(1):
            raise BuildError("#include_next is not allowed")
        if not SAFE_INCLUDE.match(m.group(2)):
            raise BuildError(f"#include '{m.group(2)}' is not allowed: only plain header names like stm32f4xx_hal.h")
    if re.search(r"__has_include|#\s*pragma\s+GCC\s+(plugin|dependency)", source):
        raise BuildError("preprocessor feature not allowed")


def _inc_args():
    out = []
    for i in INCLUDES:
        out += ["-I", str(i)]
    return out


def _compile_one(path: Path, opt: str, tmp: Path):
    cmd = [_gcc(), *GCC_FLAGS, opt, "-o", str(tmp / "out.o"), *_inc_args(), str(path)]
    proc = subprocess.run(cmd, capture_output=True, text=True, timeout=TIMEOUT_S, cwd=str(tmp))
    errors, warnings = [], []
    for raw in proc.stderr.splitlines():
        m = GCC_DIAG.match(raw)
        if m and Path(m["file"]).name == path.name:
            item = {"line": int(m["line"]), "msg": m["msg"]}
            (warnings if m["kind"] == "warning" else errors).append(item)
    failed = proc.returncode != 0
    return failed, errors, warnings, proc.stderr


def compile_path(path: Path, label: str | None = None) -> dict:
    """GCC -Wall -Wextra at -O0 and -O2. ok = compiles with zero errors at both levels."""
    results, all_err, all_warn, ok = {}, {}, {}, True
    with tempfile.TemporaryDirectory() as t:
        tmp = Path(t)
        for opt in ("-O0", "-O2"):
            failed, errs, warns, stderr = _compile_one(path, opt, tmp)
            results[opt] = {"errors": errs, "warnings": warns}
            if failed:
                ok = False
                if not errs:          # failed without a parsed error (missing header, etc.)
                    results[opt]["raw_stderr_head"] = stderr[:600]
            for e in errs:
                all_err[(e["line"], e["msg"])] = e
            for w in warns:
                all_warn[(w["line"], w["msg"])] = w
    return {"ok": ok, "file": label or str(path), "by_opt": results,
            "errors": sorted(all_err.values(), key=lambda x: x["line"]),
            "warnings": sorted(all_warn.values(), key=lambda x: x["line"])}


def compile_text(source: str, name: str = "patched.c") -> dict:
    check_source_safe(source)
    name = re.sub(r"[^A-Za-z0-9_.]", "_", name)[:60] or "patched.c"
    if not name.endswith(".c"):
        name += ".c"
    with tempfile.TemporaryDirectory() as t:
        p = Path(t) / name
        p.write_text(source, encoding="utf-8")
        return compile_path(p, label=name)


def cppcheck_path(path: Path, label: str | None = None) -> dict:
    exe = _cppcheck()
    findings, aborted = {}, False

    def run(cmd):
        nonlocal aborted
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=TIMEOUT_S * 3)
        for raw in proc.stderr.splitlines():
            parts = raw.split("|", 4)
            if len(parts) != 5:
                continue
            f, line, cid, sev, msg = parts
            if cid == "preprocessorErrorDirective":
                aborted = True
            if Path(f).name == path.name and line.isdigit():
                findings[(int(line), cid)] = {"line": int(line), "id": cid, "severity": sev, "msg": msg}

    run([exe, *CPP_BASE, *CPP_DEFS, *[f"-I{i}" for i in INCLUDES], str(path)])   # with headers
    run([exe, *CPP_BASE, str(path)])                                              # file alone
    rows = sorted(findings.values(), key=lambda x: x["line"])
    return {"file": label or str(path), "findings": rows,
            "serious": [r for r in rows if r["severity"] in ("error", "warning")],
            "headers_pass_aborted": aborted}


def cppcheck_text(source: str, name: str = "patched.c") -> dict:
    check_source_safe(source)
    name = re.sub(r"[^A-Za-z0-9_.]", "_", name)[:60] or "patched.c"
    if not name.endswith(".c"):
        name += ".c"
    with tempfile.TemporaryDirectory() as t:
        p = Path(t) / name
        p.write_text(source, encoding="utf-8")
        return cppcheck_path(p, label=name)


def check_fix(original_path: Path, patched_source: str, label: str | None = None) -> dict:
    """Does the patched file compile, did it add warnings the original did not have,
    and how big is the change? Does NOT decide whether the bug is gone (that is judged
    by re-running the detector on the patched source in the evaluation harness)."""
    original = original_path.read_text(encoding="utf-8", errors="replace")
    before = compile_path(original_path, label=label)
    after = compile_text(patched_source, name=original_path.name)
    seen = {w["msg"] for w in before["warnings"]}
    new_warnings = [w for w in after["warnings"] if w["msg"] not in seen]
    diff = list(difflib.unified_diff(original.splitlines(), patched_source.splitlines(), lineterm="", n=0))
    changed = sum(1 for d in diff if d[:1] in "+-" and d[:3] not in ("+++", "---"))
    return {
        "compiles": after["ok"],
        "errors": after["errors"],
        "new_warnings": new_warnings,
        "original_compiled": before["ok"],
        "changed_lines": changed,
        "diff": "\n".join(diff[:80]),
    }
