#!/usr/bin/env python3
"""
run_agents.py -- run an agent setup over a benchmark split and print a quick score.

DEV SET ONLY by default. The test split is the frozen 50-file benchmark: it is refused unless you
pass --allow-test, and every test run must be logged in CHANGELOG.md. Never edit prompts, rules or
settings after looking at test output.

Usage (from the firmix folder, Ollama running):
    python tools/run_agents.py --setup reasoning --split dev
    python tools/run_agents.py --setup reasoning --split dev --files d05,d06
"""
import argparse, json, sys, time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from agents.llm import OllamaLLM, LLMError          # noqa: E402
from agents.pipeline import run_setup, run_planned               # noqa: E402


def score(entry, findings):
    bugs = list(findings)            # run_setup returns only the findings that survive
    if entry["label"] == "clean":
        return {"tp": 0, "fn": 0, "fp": len(bugs)}
    hit = any(f.bug_type == entry["bug_type"] and f.line in entry["accepted_lines"] for f in bugs)
    fp = sum(1 for f in bugs if not (f.bug_type == entry["bug_type"] and f.line in entry["accepted_lines"]))
    return {"tp": int(hit), "fn": int(not hit), "fp": fp}


def main(argv=None, llm=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--setup", default="reasoning", choices=["reasoning", "verified", "planned", "planned_llm"])
    ap.add_argument("--split", default="dev", choices=["dev", "test"])
    ap.add_argument("--files", default=None, help="comma list of file stems, e.g. d05,d06")
    ap.add_argument("--allow-test", action="store_true")
    ap.add_argument("--out", default=str(ROOT / "runs"))
    a = ap.parse_args(argv)

    if a.split == "test" and not a.allow_test:
        sys.exit("Refusing to run on the frozen TEST split. If this is the deliberate final run, add "
                 "--allow-test and log it in CHANGELOG.md first.")
    gt = json.loads((ROOT / "benchmark" / "ground_truth.json").read_text(encoding="utf-8"))["entries"]
    rows = [e for e in gt if e["split"] == a.split]
    if a.files:
        keep = set(a.files.split(","))
        rows = [e for e in rows if Path(e["file"]).stem in keep]
    llm = llm or OllamaLLM()

    results, tot = [], {"tp": 0, "fn": 0, "fp": 0}
    t0 = time.time()
    for e in rows:
        stem = Path(e["file"]).stem
        t = time.time()
        try:
            if a.setup in ("planned", "planned_llm"):
                findings, log = run_planned(llm, e["file"], use_verifier=True, triage=(a.setup == "planned_llm"))
            else:
                findings, log = run_setup(llm, e["file"], use_verifier=(a.setup == "verified"))
        except LLMError as err:
            sys.exit(f"LLM problem: {err}\nIs Ollama running and the model pulled (ollama pull qwen3:8b)?")
        s = score(e, findings)
        for k in tot:
            tot[k] += s[k]
        want = "clean" if e["label"] == "clean" else e["bug_type"]
        bugs = [(f.bug_type, f.line) for f in findings]
        print(f"{stem}  expect={want:<7} bugs_reported={bugs}  tp={s['tp']} fn={s['fn']} fp={s['fp']}  ({time.time()-t:.0f}s)", flush=True)
        results.append({"file": e["file"], "score": s, "findings": [f.to_dict() for f in findings], "log": log})

    buggy = sum(1 for e in rows if e["label"] != "clean")
    print(f"\nsetup={a.setup} split={a.split}  found {tot['tp']}/{buggy} buggy files   false positives: {tot['fp']}"
          f"   LLM calls: {llm.calls}  tokens: {llm.prompt_tokens + llm.completion_tokens}  time: {time.time()-t0:.0f}s")
    out = Path(a.out)
    out.mkdir(exist_ok=True)
    (out / f"{a.setup}_{a.split}.json").write_text(json.dumps(results, indent=1), encoding="utf-8")
    print(f"details -> {out / (a.setup + '_' + a.split + '.json')}")


if __name__ == "__main__":
    main()
