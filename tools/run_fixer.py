#!/usr/bin/env python3
"""
run_fixer.py -- measure the fixer on a split. Isolated from detection: for each buggy file it fixes the
code-facts candidate that matches the ground truth (bug type + accepted line), so fixer quality is not
mixed up with detector mistakes. (The full pipeline later chains detect -> verify -> fix.)

DEV SET ONLY by default; the test split needs --allow-test and a CHANGELOG entry.

    python tools/run_fixer.py --split dev
    python tools/run_fixer.py --split dev --files d05,d06

Success = patch compiles + adds no new compiler warnings + the rule no longer flags the bug + small diff.
Patched files are saved in runs/fixes/ so YOU can read each one: passing the rule is not proof the fix is right.
"""
import argparse, json, sys, time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from agents.llm import OllamaLLM, LLMError   # noqa: E402
from agents.fixer import fix_finding         # noqa: E402
from codefacts import api as cf              # noqa: E402


def main(argv=None, llm=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--split", default="dev", choices=["dev", "test"])
    ap.add_argument("--files", default=None)
    ap.add_argument("--allow-test", action="store_true")
    ap.add_argument("--out", default=str(ROOT / "runs"))
    a = ap.parse_args(argv)
    if a.split == "test" and not a.allow_test:
        sys.exit("Refusing to run on the frozen TEST split without --allow-test (and a CHANGELOG entry).")
    gt = json.loads((ROOT / "benchmark" / "ground_truth.json").read_text(encoding="utf-8"))["entries"]
    rows = [e for e in gt if e["split"] == a.split and e["label"] != "clean"]
    if a.files:
        keep = set(a.files.split(","))
        rows = [e for e in rows if Path(e["file"]).stem in keep]
    llm = llm or OllamaLLM()
    out = Path(a.out); (out / "fixes").mkdir(parents=True, exist_ok=True)

    results, ok_n, t0 = [], 0, time.time()
    for e in rows:
        stem = Path(e["file"]).stem
        cands = [c for c in cf.get_candidates(e["file"], e["bug_type"])["candidates"] if c["line"] in e["accepted_lines"]]
        if not cands:
            print(f"{stem}  {e['bug_type']}  NO MATCHING CANDIDATE (detector gap, not a fixer problem)")
            results.append({"file": e["file"], "skipped": "no matching candidate"})
            continue
        t = time.time()
        try:
            r = fix_finding(llm, e["file"], cands[0])
        except LLMError as err:
            sys.exit(f"LLM problem: {err}")
        ok_n += r.success
        extra = f" introduced={r.introduced_suspects}" if r.introduced_suspects else ""
        print(f"{stem}  {e['bug_type']:<7} {'FIXED ' if r.success else 'FAILED'} attempts={r.attempts} "
              f"compiles={r.compiles} removed={r.bug_removed} new_warn={r.new_warnings} changed={r.changed_lines}"
              f"{extra}  ({time.time()-t:.0f}s)" + ("" if r.success else f"\n      why: {r.failure[:160]}"), flush=True)
        if r.patched_source:
            (out / "fixes" / f"{stem}_{r.bug_type}.c").write_bytes(r.patched_source.encode("utf-8"))
        d = r.to_dict(); d.pop("patched_source")
        results.append(d)

    tried = sum(1 for r in results if "skipped" not in r)
    print(f"\nsplit={a.split}  fix success {ok_n}/{tried}   LLM calls: {llm.calls}  "
          f"tokens: {llm.prompt_tokens + llm.completion_tokens}  time: {time.time()-t0:.0f}s")
    (out / f"fixer_{a.split}.json").write_text(json.dumps(results, indent=1), encoding="utf-8")
    print(f"details -> {out / ('fixer_' + a.split + '.json')}   patched files -> {out / 'fixes'}")
    print("NOW READ the diffs in runs/fixer_dev.json ('diff' field): passing the rule is not proof the fix is right.")


if __name__ == "__main__":
    main()
