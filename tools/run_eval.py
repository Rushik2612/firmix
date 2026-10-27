#!/usr/bin/env python3
"""
run_eval.py -- Step 9: run the evaluation setups, several times, and report mean and spread.

Setups
  rules    code-facts candidates reported as findings, no LLM (what the tools alone give)
  single   one LLM call per file: whole file + all rules, no tools                (single LLM)
  agents   planner -> reasoning agent, NO verifier                                (agents without verifier)
  full     planner -> reasoning -> verifier                                       (full Firmix)
The GCC + cppcheck baseline is already in results/baseline_raw.json (tools/run_baseline.py).

Per bug group and overall, per run:  precision = TP/(TP+FP),  recall = TP/(TP+FN),
  hallucination rate = (reported findings whose quoted code is NOT on the line they name) / (reported findings).
A finding is a TP if its bug type matches a buggy file's ground truth and its line is in accepted_lines; every other
reported finding is a FP (including anything reported on a clean file).
LLM setups are repeated --repeats times (default 3); results are mean (sd) across repeats.

DEV by default. The TEST split needs --allow-test and a CHANGELOG entry; run it ONCE, deliberately, never tune after.

    python tools/run_eval.py --split dev --setups rules,single,agents,full --repeats 3
    python tools/run_eval.py --split test --allow-test --setups rules,single,agents,full --repeats 3 --fix
"""
import argparse, json, statistics as st, sys, time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from agents.llm import OllamaLLM, LLMError                 # noqa: E402
from agents.findings import Finding                         # noqa: E402
from agents.pipeline import run_planned                     # noqa: E402
from agents.single import run_single                         # noqa: E402
from agents.fixer import fix_finding                         # noqa: E402
from codefacts import api as cf                              # noqa: E402

GROUPS = {"INT": "interrupts", "RTOS": "RTOS", "PER": "peripherals/HAL", "MEM": "memory"}
LLM_SETUPS = ("single", "agents", "full")
LABEL = {"rules": "Rules only (code-facts, no LLM)", "single": "Single LLM (no tools)",
         "agents": "Agents, no verifier", "full": "Full Firmix"}


def group(bt): return GROUPS[bt.split("-")[0]]


def run_rules(file):
    out = []
    for c in cf.get_candidates(file)["candidates"]:
        v = cf.validate_line(file, c["line"], cf.load(file).line_text(c["line"]).strip())
        out.append(Finding(file=file, bug_type=c["bug_type"], line=c["line"], verdict="bug", reason=c["summary"],
                           candidate_rule=c["rule"], quote_on_line=v["valid"], grounded=v["valid"]))
    return out


def run_one(setup, llm, file):
    if setup == "rules":
        return run_rules(file)
    if setup == "single":
        return run_single(llm, file)[0]
    return run_planned(llm, file, use_verifier=(setup == "full"))[0]


def score_run(rows, per_file):
    """rows: ground-truth entries; per_file: {file: [Finding]} -> counts per group + overall."""
    z = lambda: {"tp": 0, "fn": 0, "fp": 0, "reported": 0, "halluc": 0, "loose": 0}
    c = {g: z() for g in list(GROUPS.values()) + ["ALL"]}
    for e in rows:
        fs = per_file.get(e["file"], [])
        if e["label"] == "buggy":
            g = group(e["bug_type"])
            hit = any(f.bug_type == e["bug_type"] and f.line in e["accepted_lines"] for f in fs)
            loose = any(f.bug_type == e["bug_type"] for f in fs)       # right type anywhere in the file
            for k in (g, "ALL"):
                c[k]["tp" if hit else "fn"] += 1
                c[k]["loose"] += int(loose)
        for f in fs:
            is_tp = (e["label"] == "buggy" and f.bug_type == e["bug_type"] and f.line in e["accepted_lines"])
            for k in (group(f.bug_type), "ALL"):
                c[k]["reported"] += 1
                c[k]["halluc"] += int(not f.quote_on_line)
                if not is_tp:
                    c[k]["fp"] += 1
    return c


def rates(c):
    tp, fn, fp, rep, h = c["tp"], c["fn"], c["fp"], c["reported"], c["halluc"]
    return {"recall": tp / (tp + fn) if tp + fn else None,
            "recall_loose": c["loose"] / (tp + fn) if tp + fn else None,
            "precision": tp / (tp + fp) if tp + fp else None,
            "halluc": h / rep if rep else None}


def ms(vals):
    v = [x for x in vals if x is not None]
    if not v:
        return "  n/a  "
    return f"{100*st.mean(v):4.0f}% ±{100*(st.stdev(v) if len(v) > 1 else 0):.0f}"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--split", default="dev", choices=["dev", "test"])
    ap.add_argument("--setups", default="rules,single,agents,full")
    ap.add_argument("--repeats", type=int, default=3)
    ap.add_argument("--files", default=None)
    ap.add_argument("--fix", action="store_true", help="also run the fixer on each true positive of the 'full' setup")
    ap.add_argument("--allow-test", action="store_true")
    ap.add_argument("--temperature", type=float, default=None, help="sampling temperature for a robustness study (default: pinned 0)")
    ap.add_argument("--vary-seed", action="store_true", help="repeat with seeds 42,43,... instead of the pinned seed")
    ap.add_argument("--out", default=str(ROOT / "results"))
    a = ap.parse_args()
    if a.split == "test" and not a.allow_test:
        sys.exit("Refusing to run on the frozen TEST split without --allow-test (and a CHANGELOG entry first).")
    gt = json.loads((ROOT / "benchmark" / "ground_truth.json").read_text(encoding="utf-8"))["entries"]
    rows = [e for e in gt if e["split"] == a.split]
    if a.files:
        keep = set(a.files.split(","))
        rows = [e for e in rows if Path(e["file"]).stem in keep]
    setups = a.setups.split(",")
    results, fixes, t0 = {}, [], time.time()

    for s in setups:
        runs = []
        n = 1 if s == "rules" else a.repeats
        for r in range(n):
            llm = None if s == "rules" else OllamaLLM(seed=(42 + r) if a.vary_seed else None, temperature=a.temperature)
            per_file = {}
            for e in rows:
                try:
                    per_file[e["file"]] = run_one(s, llm, e["file"])
                except LLMError as err:
                    sys.exit(f"LLM problem: {err}\nIs Ollama running?")
            c = score_run(rows, per_file)
            runs.append({"counts": c, "findings": {f: [(x.bug_type, x.line, bool(x.quote_on_line)) for x in fs] for f, fs in per_file.items()}, "calls": getattr(llm, "calls", 0),
                         "tokens": (llm.prompt_tokens + llm.completion_tokens) if llm else 0})
            print(f"[{s} run {r+1}/{n}] ALL: tp={c['ALL']['tp']} fn={c['ALL']['fn']} fp={c['ALL']['fp']} "
                  f"reported={c['ALL']['reported']} halluc={c['ALL']['halluc']}  ({time.time()-t0:.0f}s)", flush=True)
            if a.fix and s == "full":
                for e in rows:
                    for f in per_file[e["file"]]:
                        if e["label"] == "buggy" and f.bug_type == e["bug_type"] and f.line in e["accepted_lines"]:
                            cand = next((x for x in cf.get_candidates(e["file"], f.bug_type)["candidates"] if x["line"] == f.line), None)
                            if cand:
                                fr = fix_finding(llm, e["file"], cand)
                                d = fr.to_dict(); d["run"] = r + 1
                                fixes.append(d)
        results[s] = runs

    # ---- table ----
    lines = [f"# Evaluation on the {a.split} split ({len([e for e in rows if e['label']=='buggy'])} buggy, "
             f"{len([e for e in rows if e['label']=='clean'])} clean files), repeats={a.repeats}", "",
             "mean ± sd across repeats. Precision = TP/(TP+FP); recall = TP/(TP+FN); "
             "hallucination = reported findings whose quoted code is not on the line they name (for the tool-grounded setups the line is "
             "tool-proposed, so this only measures a sloppy quote, not an invented location).", ""]
    for g in list(GROUPS.values()) + ["ALL"]:
        lines += [f"## {'All groups' if g == 'ALL' else g}", "", "| Setup | Precision | Recall (exact line) | Recall (right type anywhere in file) | Hallucination |", "|---|---|---|---|---|"]
        for s in setups:
            rr = [rates(r["counts"][g]) for r in results[s]]
            lines.append(f"| {LABEL[s]} | {ms([x['precision'] for x in rr])} | {ms([x['recall'] for x in rr])} | {ms([x['recall_loose'] for x in rr])} | {ms([x['halluc'] for x in rr])} |")
        lines.append("")
    lines += ["## Cost (mean per run)", "", "| Setup | LLM calls | Tokens |", "|---|---|---|"]
    for s in setups:
        rs = results[s]
        lines.append(f"| {LABEL[s]} | {st.mean(r['calls'] for r in rs):.0f} | {st.mean(r['tokens'] for r in rs):.0f} |")
    if fixes:
        ok = [f for f in fixes if f["success"]]
        lines += ["", "## Fixer (on true positives of the full setup, all runs)", "",
                  f"- attempted: {len(fixes)}", f"- compiles: {sum(f['compiles'] for f in fixes)}/{len(fixes)}",
                  f"- bug removed by the rule + compiles + small diff (rule-based success): {len(ok)}/{len(fixes)}",
                  "- hand-verified correct: fill results/fix_review.json ({\"file|bug_type\": true/false}) after reading each diff"]
    out = Path(a.out); out.mkdir(exist_ok=True)
    text = "\n".join(lines) + "\n"
    (out / f"eval_{a.split}.md").write_text(text, encoding="utf-8")
    (out / f"eval_{a.split}.json").write_text(json.dumps({"results": results, "fixes": fixes}, indent=1), encoding="utf-8")
    if fixes:
        rv = ["# Fixes to review by hand", "", "For each: does it fix the real cause, or only silence the rule?", ""]
        seen = set()
        for f in fixes:
            k = (f["file"], f["bug_type"], f["diff"])
            if k in seen: continue
            seen.add(k)
            rv += [f"## {f['file']} {f['bug_type']}  rule-success={f['success']}", "```diff", f["diff"], "```", ""]
        (out / "fixes_to_review.md").write_text("\n".join(rv), encoding="utf-8")
    print("\n" + text)
    print(f"-> {out / ('eval_' + a.split + '.md')}")


if __name__ == "__main__":
    main()
