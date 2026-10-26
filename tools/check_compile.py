#!/usr/bin/env python3
"""
check_compile.py -- compile-check benchmark files against the real STM32F4 HAL
and FreeRTOS headers using `arm-none-eabi-gcc -fsyntax-only`.

Rule (SPEC section 4): every benchmark file must compile with ZERO ERRORS.
Warnings are NOT a failure -- they are recorded, because whether GCC already
warns about a seeded bug is part of the GCC baseline result.

Usage:
    python tools/check_compile.py benchmark/files/*.c
    python tools/check_compile.py benchmark/dev --warnings-json warnings.json

Works on Windows and Linux. Expects the layout:
    firmix/
      include/            stm32f4xx_hal_conf.h, FreeRTOSConfig.h
      deps/               cmsis_device_f4, cmsis_core, stm32f4xx_hal_driver, FreeRTOS-Kernel
"""
import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

INCLUDES = [
    ROOT / "include",
    ROOT / "deps" / "cmsis_device_f4" / "Include",
    ROOT / "deps" / "cmsis_core" / "CMSIS" / "Core" / "Include",
    ROOT / "deps" / "stm32f4xx_hal_driver" / "Inc",
    ROOT / "deps" / "FreeRTOS-Kernel" / "include",
    ROOT / "deps" / "FreeRTOS-Kernel" / "portable" / "GCC" / "ARM_CM4F",
]

FLAGS = [
    "-mcpu=cortex-m4", "-mthumb", "-mfloat-abi=hard", "-mfpu=fpv4-sp-d16",
    "-DSTM32F411xE", "-DUSE_HAL_DRIVER",
    "-std=gnu11", "-fsyntax-only", "-Wall", "-Wextra",
    "-fdiagnostics-plain-output",
]

DIAG = re.compile(r"^(?P<file>.+?):(?P<line>\d+):(?:\d+:)?\s*(?P<kind>warning|error|fatal error):\s*(?P<msg>.*)$")


def compile_one(path: Path):
    cmd = ["arm-none-eabi-gcc", *FLAGS]
    for inc in INCLUDES:
        cmd += ["-I", str(inc)]
    cmd.append(str(path))
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
    except FileNotFoundError:
        sys.exit("arm-none-eabi-gcc not found on PATH. Install the Arm GNU Toolchain.")
    errors, warnings = [], []
    for raw in proc.stderr.splitlines():
        m = DIAG.match(raw)
        if not m:
            continue
        # keep only diagnostics located in the benchmark file itself
        if Path(m["file"]).name != path.name:
            continue
        item = {"line": int(m["line"]), "msg": m["msg"]}
        (warnings if m["kind"] == "warning" else errors).append(item)
    # a non-zero exit with no parsed error still means failure (e.g. missing header)
    failed = proc.returncode != 0
    return failed, errors, warnings, proc.stderr


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("paths", nargs="+", help="C files or directories")
    ap.add_argument("--warnings-json", help="write per-file warnings to this JSON file")
    ap.add_argument("-v", "--verbose", action="store_true", help="print full compiler output on failure")
    args = ap.parse_args()

    files = []
    for p in map(Path, args.paths):
        files += sorted(p.glob("*.c")) if p.is_dir() else [p]

    all_warnings, bad = {}, 0
    for f in files:
        failed, errors, warnings, raw = compile_one(f)
        all_warnings[f.name] = warnings
        status = "FAIL" if failed else "ok"
        print(f"{status:4}  {f.name:32} warnings={len(warnings)}")
        if failed:
            bad += 1
            for e in errors[:5]:
                print(f"        error line {e['line']}: {e['msg']}")
            if args.verbose or not errors:
                print(raw[-1500:])
    if args.warnings_json:
        Path(args.warnings_json).write_text(json.dumps(all_warnings, indent=2))
    print(f"\n{len(files) - bad}/{len(files)} files compile without errors")
    sys.exit(1 if bad else 0)


if __name__ == "__main__":
    main()
