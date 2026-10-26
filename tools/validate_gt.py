#!/usr/bin/env python3
"""
validate_gt.py -- check benchmark/ground_truth.json against the files on disk
and print progress towards the 50-file target.

Run it after every file you add:
    python tools/validate_gt.py

Errors (exit code 1):  malformed entries, wrong line numbers, anchor snippet not
                       on the anchor line, unlisted .c files, non-neutral names.
Warnings:              comments that hint at the bug (bug/seeded/TODO/...).
"""
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BENCH = ROOT / "benchmark"

GROUPS = {
    "INT-01": "interrupts", "INT-02": "interrupts", "INT-03": "interrupts",
    "RTOS-01": "rtos", "RTOS-02": "rtos", "RTOS-03": "rtos",
    "PER-01": "peripherals", "PER-02": "peripherals",
    "MEM-01": "memory", "MEM-02": "memory",
}
TARGET_BUGGY_PER_TYPE = 4
TARGET_CLEAN = 10

TEST_NAME = re.compile(r"^f\d{3}\.c$")
DEV_NAME = re.compile(r"^d\d{2}\.c$")
HINT_WORDS = re.compile(
    r"\b(bug|buggy|seeded|vulnerab\w*|fixme|todo|xxx|hack|intentional\w*|"
    r"should be volatile|race condition here|missing volatile)\b", re.I)
COMMENT = re.compile(r"/\*.*?\*/|//[^\n]*", re.S)

errors, warnings = [], []


def err(msg):
    errors.append(msg)


def warn(msg):
    warnings.append(msg)


def check_entry(e, seen):
    f = e.get("file")
    if not f:
        return err(f"entry without 'file': {e}")
    if f in seen:
        return err(f"{f}: duplicate entry")
    seen.add(f)
    path = BENCH / f
    if not path.exists():
        return err(f"{f}: file does not exist")

    split, label = e.get("split"), e.get("label")
    if split not in ("test", "dev"):
        err(f"{f}: split must be 'test' or 'dev'")
    if label not in ("buggy", "clean"):
        return err(f"{f}: label must be 'buggy' or 'clean'")
    folder = f.split("/")[0]
    if (split == "test") != (folder == "files"):
        err(f"{f}: split '{split}' does not match folder '{folder}'")
    name = path.name
    if split == "test" and not TEST_NAME.match(name):
        err(f"{f}: test files must be named fNNN.c (neutral names, no hints)")
    if split == "dev" and not DEV_NAME.match(name):
        err(f"{f}: dev files must be named dNN.c")

    text = path.read_text(encoding="utf-8", errors="replace")
    lines = text.splitlines()

    for c in COMMENT.findall(text):
        m = HINT_WORDS.search(c)
        if m:
            warn(f"{f}: comment hints at a bug ('{m.group(0)}') -- remove it")

    if label == "clean":
        if e.get("near_miss_of") not in GROUPS:
            err(f"{f}: clean files need 'near_miss_of' set to a valid bug type")
        for k in ("bug_type", "anchor_line", "accepted_lines", "anchor_snippet"):
            if k in e:
                err(f"{f}: clean file must not have '{k}'")
        return

    bt = e.get("bug_type")
    if bt not in GROUPS:
        return err(f"{f}: unknown bug_type '{bt}'")
    al, acc, snip = e.get("anchor_line"), e.get("accepted_lines"), e.get("anchor_snippet")
    if not isinstance(al, int) or not (1 <= al <= len(lines)):
        return err(f"{f}: anchor_line {al} out of range (file has {len(lines)} lines)")
    if not snip:
        return err(f"{f}: anchor_snippet required (text that must appear on the anchor line)")
    if snip not in lines[al - 1]:
        err(f"{f}: anchor_snippet {snip!r} not found on line {al}: {lines[al-1].strip()!r}")
    if not isinstance(acc, list) or al not in acc:
        err(f"{f}: accepted_lines must be a list that includes anchor_line")
    else:
        for n in acc:
            if not isinstance(n, int) or not (1 <= n <= len(lines)):
                err(f"{f}: accepted line {n} out of range")


def main():
    gt_path = BENCH / "ground_truth.json"
    if not gt_path.exists():
        sys.exit("benchmark/ground_truth.json not found")
    try:
        gt = json.loads(gt_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as ex:
        sys.exit(f"ground_truth.json is not valid JSON: {ex}")

    seen = set()
    entries = gt.get("entries", [])
    for e in entries:
        check_entry(e, seen)

    # every C file on disk must be listed
    for folder in ("files", "dev"):
        for p in sorted((BENCH / folder).glob("*.c")):
            rel = f"{folder}/{p.name}"
            if rel not in seen:
                err(f"{rel}: file exists but has no ground-truth entry")

    # progress table (test split only)
    test = [e for e in entries if e.get("split") == "test"]
    print("TEST SET PROGRESS (target 4 buggy per type + 10 clean)")
    print(f"{'type':8} {'group':12} {'buggy':>6} {'near-miss clean':>16}")
    tb = tc = 0
    for bt, grp in GROUPS.items():
        b = sum(1 for e in test if e.get("bug_type") == bt)
        c = sum(1 for e in test if e.get("near_miss_of") == bt)
        tb += b
        tc += c
        print(f"{bt:8} {grp:12} {b:>3}/{TARGET_BUGGY_PER_TYPE}  {c:>10}/1")
    print(f"{'TOTAL':21} {tb:>3}/{TARGET_BUGGY_PER_TYPE*len(GROUPS)}  {tc:>10}/{TARGET_CLEAN}")
    dev = [e for e in entries if e.get("split") == "dev"]
    print(f"dev set: {len(dev)} files ({sum(e.get('label')=='buggy' for e in dev)} buggy, "
          f"{sum(e.get('label')=='clean' for e in dev)} clean)\n")

    for w in warnings:
        print("WARN ", w)
    for x in errors:
        print("ERROR", x)
    print(f"\n{len(errors)} error(s), {len(warnings)} warning(s)")
    sys.exit(1 if errors else 0)


if __name__ == "__main__":
    main()
