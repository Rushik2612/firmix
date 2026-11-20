#!/usr/bin/env python3
"""
export_demo.py -- build app/demo_data.json for the demo's "Benchmark replay" tab.

NO NEW TEST-SET MODEL RUN. Two tiers, labelled the same way in the UI:
  * dev files d01-d20: the full pipeline is run here (needs Ollama, ~10-15 min) and every step is recorded
    (candidate, reasoning verdict, verifier verdict, fix). Dev was tuned on, so the UI says it is not a result.
  * test files f001-f050: nothing is re-run with a model. The PINNED findings and fixes are copied from
    results/test_main/eval_test.json (the one pre-registered run). The deterministic rule candidates are
    re-computed (no LLM, same output as always).

    python tools/export_demo.py              # dev (runs the LLM) + test (copy)
    python tools/export_demo.py --no-dev     # test copy only, no LLM needed
"""
import argparse, json, sys, time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from codefacts import api as cf          # noqa: E402

OUT = ROOT / "app" / "demo_data.json"


def src_of(rel: str) -> str:
    return (ROOT / "benchmark" / rel).read_bytes().decode("utf-8", errors="replace").replace("\r\n", "\n")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--no-dev", action="store_true")
    a = ap.parse_args()

    gt = json.loads((ROOT / "benchmark" / "ground_truth.json").read_text(encoding="utf-8"))["entries"]
    by_file = {e["file"]: e for e in gt}
    test_res = json.loads((ROOT / "results" / "test_main" / "eval_test.json").read_text(encoding="utf-8"))
    full = test_res["results"]["full"][0]["findings"]          # {"files/f001.c": [[type, line, flag], ...]}
    fixes = {}
    for f in test_res["fixes"]:
        fixes[(f["file"], f["bug_type"], f["line"])] = f

    items = []

    # ---- test tier: copy pinned results, no model
    for e in gt:
        if e["split"] != "test":
            continue
        rel = e["file"]
        rep = []
        for t, ln, *_ in full.get(rel, []):
            ok = e["label"] == "buggy" and t == e["bug_type"] and ln in e["accepted_lines"]
            fx = fixes.get((rel, t, ln))
            rep.append({"bug_type": t, "line": ln, "correct": ok,
                        "fix": ({k: fx[k] for k in ("success", "compiles", "bug_removed", "changed_lines",
                                                     "attempts", "explanation", "diff")} if fx else None)})
        items.append({"id": Path(rel).stem, "split": "test", "label": e["label"], "truth": {
            "bug_type": e.get("bug_type"), "line": e.get("anchor_line"), "accepted_lines": e.get("accepted_lines"),
            "note": e.get("note", "")}, "source": src_of(rel),
            "candidates": cf.get_candidates(rel)["candidates"], "reported": rep, "trace": None})

    # ---- dev tier: run the full pipeline and record every step
    if not a.no_dev:
        from agents.llm import OllamaLLM
        from agents.pipeline import run_planned
        from agents.fixer import fix_finding
        llm = OllamaLLM()
        for e in gt:
            if e["split"] != "dev":
                continue
            rel = e["file"]
            t0 = time.time()
            kept, log = run_planned(llm, rel, use_verifier=True)
            trace, rep = [], []
            for row in log:
                if "candidate" not in row:
                    continue
                c, f = row["candidate"], row["finding"]
                trace.append({"candidate": {k: c[k] for k in ("bug_type", "line", "function", "rule", "summary")},
                              "verdict": f["verdict"], "reason": f["reason"], "grounded": f["grounded"],
                              "verified": f["verified"], "verifier_reason": f["verifier_reason"],
                              "reported": row["reported"]})
                if row["reported"]:
                    ok = e["label"] == "buggy" and c["bug_type"] == e["bug_type"] and c["line"] in e["accepted_lines"]
                    fr = fix_finding(llm, rel, c)
                    rep.append({"bug_type": c["bug_type"], "line": c["line"], "correct": ok,
                                "fix": {"success": fr.success, "compiles": fr.compiles, "bug_removed": fr.bug_removed,
                                        "changed_lines": fr.changed_lines, "attempts": fr.attempts,
                                        "explanation": fr.explanation, "diff": fr.diff}})
            print(f"{Path(rel).stem}: {len(trace)} candidates, {len(rep)} reported ({time.time()-t0:.0f}s)", flush=True)
            items.append({"id": Path(rel).stem, "split": "dev", "label": e["label"], "truth": {
                "bug_type": e.get("bug_type"), "line": e.get("anchor_line"), "accepted_lines": e.get("accepted_lines"),
                "note": e.get("note", "")}, "source": src_of(rel),
                "candidates": cf.get_candidates(rel)["candidates"], "reported": rep, "trace": trace})

    items.sort(key=lambda x: (x["split"] != "test", x["id"]))
    OUT.parent.mkdir(exist_ok=True)
    OUT.write_text(json.dumps({"model": "qwen3:8b (Ollama), temperature 0, seed 42", "items": items}, indent=1),
                   encoding="utf-8")
    print(f"{len(items)} files -> {OUT}")


if __name__ == "__main__":
    main()
