#!/usr/bin/env python3
"""
run_baseline.py -- Step 5: the GCC + cppcheck baseline on the frozen test set.

What it does
  1. Compiles every test file with arm-none-eabi-gcc (-c, so the optimizer runs;
     -fsyntax-only would hide optimizer warnings) at -O0 and -O2 with -Wall -Wextra.
  2. Runs cppcheck on every test file.
  3. Scores both tools against benchmark/ground_truth.json.

Scoring rule (deliberately LENIENT toward the baseline):
  A buggy file counts as DETECTED if the tool gives at least one warning on a line
  in that file's accepted_lines. The warning's TEXT and TYPE are not checked, because
  GCC and cppcheck do not use our 10 bug types. A real detector (Firmix) must also
  get the bug type right, so this makes the baseline look at least as good as it is.
  A clean file counts as a FALSE ALARM if the tool gives any warning anywhere in it.
  Warnings outside the accepted lines of a buggy file are counted as 'other warnings'.

Only the test split is scored (the 50 frozen files). Nothing here is tuned.

Usage (from the firmix folder):
    python tools/run_baseline.py
    python tools/run_baseline.py --cppcheck "C:/Program Files/Cppcheck/cppcheck.exe"
Output:
    results/baseline_raw.json   every warning, per file, per tool
    results/baseline_summary.md the table for the README
"""
import argparse
import json
import re
import shutil
import subprocess
import sys
import tempfile
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BENCH = ROOT / "benchmark"

INCLUDES = [
    ROOT / "include",
    ROOT / "deps" / "cmsis_device_f4" / "Include",
    ROOT / "deps" / "cmsis_core" / "CMSIS" / "Core" / "Include",
    ROOT / "deps" / "stm32f4xx_hal_driver" / "Inc",
    ROOT / "deps" / "FreeRTOS-Kernel" / "include",
    ROOT / "deps" / "FreeRTOS-Kernel" / "portable" / "GCC" / "ARM_CM4F",
]

GCC_FLAGS = [
    "-mcpu=cortex-m4", "-mthumb", "-mfloat-abi=hard", "-mfpu=fpv4-sp-d16",
    "-DSTM32F411xE", "-DUSE_HAL_DRIVER", "-std=gnu11",
    "-Wall", "-Wextra", "-fdiagnostics-plain-output", "-c",
]
GCC_DIAG = re.compile(r"^(?P<file>.+?):(?P<line>\d+):(?:\d+:)?\s*warning:\s*(?P<msg>.*)$")

GROUPS = {"INT": "interrupts", "RTOS": "RTOS", "PER": "peripherals/HAL", "MEM": "memory"}


def group_of(bug_type: str) -> str:
    return GROUPS[bug_type.split("-")[0]]


def run_gcc(path: Path):
    """Return the set of (line, msg) GCC warnings in this file, over -O0 and -O2."""
    found = {}
    with tempfile.TemporaryDirectory() as tmp:
        for opt in ("-O0", "-O2"):
            cmd = ["arm-none-eabi-gcc", *GCC_FLAGS, opt, "-o", str(Path(tmp) / "x.o")]
            for inc in INCLUDES:
                cmd += ["-I", str(inc)]
            cmd.append(str(path))
            proc = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
            for raw in proc.stderr.splitlines():
                m = GCC_DIAG.match(raw)
                if m and Path(m["file"]).name == path.name:
                    found[(int(m["line"]), m["msg"])] = opt
    return [{"line": l, "msg": m, "opt": o} for (l, m), o in sorted(found.items())]


CPP_BASE = [
    "--enable=warning,style,performance,portability", "--inconclusive",
    "--std=c11", "--platform=unix32", "--quiet",
    "--suppress=missingInclude", "--suppress=missingIncludeSystem",
    "--template={file}|{line}|{id}|{severity}|{message}",
]
# cppcheck does not know the ARM/GCC macros that the CMSIS headers insist on;
# without these it stops at '#error Unknown compiler' and reports NOTHING.
CPP_ARM_DEFS = ["-DSTM32F411xE", "-DUSE_HAL_DRIVER", "-D__GNUC__=13",
                "-D__ARM_ARCH_7EM__=1", "-D__ARM_ARCH_PROFILE=77",
                "-D__ARM_ARCH=7", "-D__ARM_FP=4"]


def _cpp_once(cmd, path):
    proc = subprocess.run(cmd, capture_output=True, text=True, timeout=600)
    out, aborted = [], False
    for raw in proc.stderr.splitlines():
        parts = raw.split("|", 4)
        if len(parts) != 5:
            continue
        f, line, cid, sev, msg = parts
        if cid == "preprocessorErrorDirective":
            aborted = True
        if Path(f).name != path.name or not line.isdigit():
            continue
        out.append({"line": int(line), "id": cid, "severity": sev, "msg": msg})
    return out, aborted


def run_cppcheck(exe: str, path: Path):
    """Two passes, merged: (1) with the real HAL/CMSIS headers, (2) file alone.
    Pass 1 sees types and macros; pass 2 avoids header trouble. Union is the fairest
    to the baseline."""
    with_hdr = [exe, *CPP_BASE, *CPP_ARM_DEFS] + [f"-I{i}" for i in INCLUDES] + [str(path)]
    alone = [exe, *CPP_BASE, str(path)]
    a, aborted = _cpp_once(with_hdr, path)
    if aborted:
        print(f"   WARNING: cppcheck hit a preprocessor #error on {path.name} (headers pass)")
    b, _ = _cpp_once(alone, path)
    merged = {(w["line"], w["id"]): w for w in a + b}
    return [merged[k] for k in sorted(merged)]


def is_serious(w):
    """GCC warnings and cppcheck error/warning severity count as serious.
    cppcheck style/performance/portability/information hints do not."""
    return w.get("severity", "warning") in ("error", "warning")


def score(entries, results):
    """results: {file -> [warnings]} for one tool. Returns a summary dict."""
    s = {"detected": 0, "detected_serious": 0, "false_alarm_serious": 0,
         "buggy": 0, "false_alarm_files": 0, "clean": 0,
         "warnings_total": 0, "warnings_on_bug_line": 0,
         "by_group": defaultdict(lambda: {"detected": 0, "buggy": 0}),
         "detected_files": [], "false_alarm_list": []}
    for e in entries:
        name = Path(e["file"]).stem
        warns = results.get(name, [])
        s["warnings_total"] += len(warns)
        serious = [w for w in warns if is_serious(w)]
        if e["label"] == "clean":
            s["clean"] += 1
            if serious:
                s["false_alarm_serious"] += 1
            if warns:
                s["false_alarm_files"] += 1
                s["false_alarm_list"].append(name)
            continue
        s["buggy"] += 1
        g = group_of(e["bug_type"])
        s["by_group"][g]["buggy"] += 1
        hit = [w for w in warns if w["line"] in e["accepted_lines"]]
        s["warnings_on_bug_line"] += len(hit)
        if any(is_serious(w) for w in hit):
            s["detected_serious"] += 1
        if hit:
            s["detected"] += 1
            s["by_group"][g]["detected"] += 1
            s["detected_files"].append(name)
    s["by_group"] = dict(s["by_group"])
    return s


def wilson(k, n, z=1.96):
    if n == 0:
        return (0.0, 0.0)
    p = k / n
    d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    h = z * ((p * (1 - p) / n + z * z / (4 * n * n)) ** 0.5) / d
    return (max(0.0, c - h), min(1.0, c + h))


def fmt(k, n):
    lo, hi = wilson(k, n)
    return f"{k}/{n} ({100*k/n:.0f}%, 95% CI {100*lo:.0f}-{100*hi:.0f}%)" if n else "0/0"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--cppcheck", default=None, help="path to cppcheck executable")
    ap.add_argument("--out", default=str(ROOT / "results"))
    args = ap.parse_args()

    if not shutil.which("arm-none-eabi-gcc"):
        sys.exit("arm-none-eabi-gcc not found on PATH.")
    cpp = args.cppcheck or shutil.which("cppcheck")
    if not cpp:
        for guess in (r"C:\Program Files\Cppcheck\cppcheck.exe", "/usr/bin/cppcheck"):
            if Path(guess).exists():
                cpp = guess
    if not cpp:
        sys.exit("cppcheck not found. Pass --cppcheck <path>.")

    gt = json.load(open(BENCH / "ground_truth.json", encoding="utf-8"))
    entries = [e for e in gt["entries"] if e["split"] == "test"]
    assert len(entries) == 50, f"expected 50 test entries, got {len(entries)}"

    raw = {"gcc": {}, "cppcheck": {}}
    for i, e in enumerate(entries, 1):
        path = BENCH / e["file"]
        name = path.stem
        raw["gcc"][name] = run_gcc(path)
        raw["cppcheck"][name] = run_cppcheck(cpp, path)
        print(f"[{i:2d}/50] {name}  gcc={len(raw['gcc'][name])}  cppcheck={len(raw['cppcheck'][name])}", flush=True)

    # combined = union of both tools' warnings
    raw["combined"] = {n: raw["gcc"][n] + raw["cppcheck"][n] for n in raw["gcc"]}

    summ = {k: score(entries, raw[k]) for k in ("gcc", "cppcheck", "combined")}

    out = Path(args.out)
    out.mkdir(exist_ok=True)
    json.dump(raw, open(out / "baseline_raw.json", "w", encoding="utf-8"), indent=1)

    lines = ["# Baseline: GCC + cppcheck on the frozen 50-file test set", "",
             "Detected = at least one warning on an accepted line of the buggy file (type not checked; lenient to the baseline).",
             "False alarm = clean file with any warning.", "",
             "'Any' counts every warning, including cppcheck style hints. 'Serious' counts only GCC warnings and cppcheck error/warning severity.", "",
             "| Tool | Detected, any (of 40) | Detected, serious (of 40) | Clean files flagged, any (of 10) | Clean files flagged, serious (of 10) | Warnings total |",
             "|---|---|---|---|---|---|"]
    for k, label in (("gcc", "GCC -Wall -Wextra (-O0/-O2)"), ("cppcheck", "cppcheck"), ("combined", "GCC + cppcheck")):
        s = summ[k]
        lines.append(f"| {label} | {fmt(s['detected'], s['buggy'])} | {fmt(s['detected_serious'], s['buggy'])} | {s['false_alarm_files']}/{s['clean']} | {s['false_alarm_serious']}/{s['clean']} | {s['warnings_total']} |")
    lines += ["", "## Per bug group (GCC + cppcheck combined)", "", "| Group | Detected |", "|---|---|"]
    for g, v in sorted(summ["combined"]["by_group"].items()):
        lines.append(f"| {g} | {fmt(v['detected'], v['buggy'])} |")
    lines += ["", "## Files detected", ""]
    for k in ("gcc", "cppcheck"):
        lines.append(f"- {k}: {', '.join(summ[k]['detected_files']) or 'none'}")
    lines += ["", "## Clean files that drew a warning", ""]
    for k in ("gcc", "cppcheck"):
        lines.append(f"- {k}: {', '.join(summ[k]['false_alarm_list']) or 'none'}")
    text = "\n".join(lines) + "\n"
    (out / "baseline_summary.md").write_text(text, encoding="utf-8")
    print("\n" + text)


if __name__ == "__main__":
    main()
