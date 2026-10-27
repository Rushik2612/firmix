# Firmix 2.0

**GCC compiles it. ChatGPT explains it. Firmix catches it before it crashes your device.**

Firmix 2.0 is a tool-grounded multi-agent bug finder for **STM32F4 firmware**. It finds ten kinds of embedded bugs that compile
cleanly and pass basic tests (ISR/main data races, missing `volatile`, FreeRTOS misuse, wrong GPIO or clock setup, buffer overflows),
backs every finding with tool evidence, and proposes a fix that is checked to compile.

> **Demo:** _live link and demo GIF are added at the end of Step 10._

## The problem

These bugs compile, pass a quick test, and then crash devices in the field; finding them takes days with a debugger.
General static analyzers do not understand embedded semantics (interrupt context, RTOS rules, peripheral registers), and general
LLMs explain code well but invent bugs and line numbers. On the benchmark below, GCC + cppcheck found **2 of 40** seeded bugs and a
single local LLM with the same rules found **0 of 40** (best prompt variant: 9 of 40, with 42 false alarms).

## Results

Frozen test set: **40 buggy + 10 clean near-miss files**, ground truth fixed before any detector existed (git tag `benchmark-frozen`).
One local model for every LLM row: `qwen3:8b` via Ollama, temperature 0, seed 42. Run once, at git tag `pre-test-eval`, with the
predictions written down first ([CHANGELOG entry 25](CHANGELOG.md)). Recall counts a bug only if the right type is reported on the
right line.

| Setup | Precision | Recall (40 bugs) | 95% CI for recall | LLM calls | Tokens |
|---|---|---|---|---|---|
| GCC `-Wall -Wextra` + cppcheck (lenient: type not checked) | n/a | 5% (2/40) | 1-17% | 0 | 0 |
| Single LLM, no tools, v1 prompt (pre-registered) | 0% (0/17) | 0% (0/40) | 0-9% | 50 | 133k |
| Single LLM, no tools, one call per bug type *(post-hoc, tuned on dev)* | 18% (9/51) | 22% (9/40) | 12-38% | 500 | 698k |
| Rules only (code-facts, no LLM) | 84% (38/45) | 95% (38/40) | 83-99% | 0 | 0 |
| Agents, no verifier | 90% (37/41) | 92% (37/40) | 80-97% | 98 | 106k |
| **Full Firmix** (planner, reasoning, verifier) | **100% (33/33)** | **82% (33/40)** | 68-91% | 142 | 145k |

Full Firmix with temperature 0.3 over three seeds: precision 99% +- 2, recall 78% +- 4 (31, 30, 33 of 40). The single LLM stays at
0 of 40 in all three sampled runs.

**What this shows, and what it does not.**

- **The tools are what works.** Tool-grounded setups find 33-38 bugs; the best tool-free LLM design finds 9, at 4.8x the tokens.
  Even with line anchoring ignored (right bug type anywhere in the file) the best tool-free variant reaches only 38%.
- **The LLM stages trade recall for precision; they do not improve both.** Rules alone: 84% precision, 95% recall. Full Firmix:
  100% precision, 82% recall. On F1 the three are about equal (0.89, 0.91, 0.90), and their recall confidence intervals overlap, so
  at 40 bugs the recall differences among them are **not statistically significant**. What the verifier does buy is **zero false
  alarms on the 10 clean files** and a written, line-cited reason for every finding.
- **Where the bugs are lost** (test set): 2 never became candidates (f029, f036), the reasoning agent dropped 1 (f004), the
  verifier refuted 4 real bugs (f003, f024, f037, f041) and correctly removed all 4 remaining false positives.

### Per bug group (exact-line recall; test set, pinned run)

| Group (bugs) | Rules only | Agents, no verifier | Full Firmix recall | Full Firmix recall, sampled | Full Firmix precision | Single LLM (one call per type) |
|---|---|---|---|---|---|---|
| Interrupts (12) | 92% | 92% | 83% | 81% +- 13 | 100% | 33% |
| RTOS (12) | 100% | 100% | 100% | 89% +- 5 | 100% | 25% |
| Peripherals / HAL (8) | 100% | 88% | 62% | 58% +- 14 | 100% | 0% |
| Memory (8) | 88% | 88% | 75% | 79% +- 14 | 100% | 25% |

Peripherals/HAL is the weakest group for the full system: the verifier refuted 2 of its 7 candidates that were true bugs.

### Fixes

The fixer proposes line-range edits for each correctly found bug. **Code, not the model, decides success**: the patch must be well
formed, compile with no new warnings, make the detector rule stop flagging the bug, and stay small.

| Measure (35 attempts on true positives) | Result |
|---|---|
| Patch compiles | 25 / 35 |
| Compiles + rule no longer flags the bug + small diff | 20 / 35 |
| **Fully correct on author review of the code** | **16 / 35 (46%)**, plus 1 partial |

Three of the 20 rule-successful fixes were **wrong although they pass every automated check**: f048 moved a label so both validation
failures now fall through to the save (and left the mutex release in dead code); f006 turned an ADC input pin into an output to
silence the rule; f025 deleted a busy-wait and left a comment asking someone to fix it. By bug type, INT-02 was fixed 0 of 4 times,
INT-03 1 of 4, RTOS-01 1 of 4. The lesson: "compiles and the rule is satisfied" can be gamed, so fix correctness needs a human read.
Per-fix verdicts: `results/test_main/fix_review.json`.

## How it works

```
        STM32 C file
             |
   [ code-facts MCP server ]  tree-sitter AST, macro table, ISR context, shared variables,
             |                NVIC priorities, GPIO/clock configs  ->  deterministic CANDIDATES (file, line, type, evidence)
             v
   Planner (code)        groups candidates; an LLM triage variant was tested and rejected (see below)
             v
   Reasoning agent       one candidate at a time; rule text from [ knowledge MCP server ] (BM25 over STM32 docs + the SPEC)
             |            schema-forced verdict + exact code quote; the LINE always comes from the tool, never the model
             v
   Verifier              stage 1 (code): does the quote match the line, does the suspect reproduce?
             |            stage 2 (LLM): try to refute with a cited guard; the refutation only counts if code confirms
             v            the quote, and code rejects hedged reasoning or a "guard" that is the suspect line itself
   Fixer                 minimal edits -> [ build MCP server ] compile + warnings check -> re-run the rule -> retry (max 2)
```

- **Three MCP servers:** code facts (14 tools), knowledge (4 tools, 1,460 chunks), build (5 tools: arm-none-eabi-gcc, cppcheck).
- **Four agents:** planner, reasoning, verifier, fixer.
- **Hallucination control:** every finding carries tool evidence; code validates line numbers and quotes; an LLM refutation or fix
  is never trusted without a code check. Candidate recall is the ceiling for everything downstream (38/40 on test).
- **Retrieval check:** 17 of 25 hand-written queries return a correct chunk in the top 3 (BM25, exact API names).

### The ten bug types (`SPEC.md`)

Interrupts: INT-01 missing `volatile` on an ISR-shared variable, INT-02 non-atomic read-modify-write shared with an ISR,
INT-03 blocking call in an ISR. RTOS: RTOS-01 non-ISR-safe API from an ISR, RTOS-02 mutex not released on every path,
RTOS-03 `FromISR` call at priority < 5. Peripherals: PER-01 peripheral used without its clock enable, PER-02 GPIO mode contradicts
use. Memory: MEM-01 fixed-size buffer overflow, MEM-02 stack buffer passed to an async HAL transfer.

## Evaluation integrity

- **Benchmark frozen** before any detector ran (`benchmark-frozen`). Prompts, rules and thresholds were developed on a separate
  **dev set only** (20 files: d01-d12, then d13-d20 written later to measure out-of-sample behaviour); the test split is refused by
  every script unless `--allow-test` is passed.
- **Pre-registered**: the test run was logged with predictions first. They held: recall 60-85% (82%), precision 85-100% (100%),
  single LLM < 15% (0%), fixer rule success < 90% (57%).
- **Every change is in [CHANGELOG.md](CHANGELOG.md)** (30 entries), including mistakes: a verifier rule I over-generalized from one
  file (caught by fresh dev files), a fixer prompt that showed two stacked line labels, a baseline harness bug.
- **Post-hoc rows are labelled.** The single-LLM v1 result (0/40) is pre-registered and weak evidence, because that prompt made the
  model answer with an empty list for every dev file. A fairer tool-free baseline was tuned on dev afterwards and run once on test.
- **Out-of-sample check:** the first run on d13-d20 found 11/13 bugs with 1 false positive before any change; that false positive
  exposed the over-general verifier rule above.

## Limitations

- **One 8B local model for every LLM row.** A stronger model could narrow the gap to the tool-grounded setups; this was not tested.
- **Small benchmark.** 40 bugs: confidence intervals are wide (recall 68-91%), and the three tool-grounded setups cannot be told
  apart on recall.
- **Synthetic benchmark by the same author as the detector.** Files were frozen before the detector existed and audited, but the
  same person's mental model shaped both. Files are 40-150 lines with one seeded bug; real firmware is larger and messier.
- **Scope:** STM32F4 only, ten bug types, HAL + FreeRTOS style. The pin-to-alternate-function table covers one chip.
- **Known detector gaps:** f029 and f036 (test), and d14 (dev: a `memcpy` length taken from a received byte). The MEM-01 rule
  covers `i <= N` and constant sizes, not lengths from received data. Candidate rules are frozen as v1.
- **Recall cost of the verifier:** it removed 4 real bugs to remove 4 false alarms. Dev numbers (92% recall) overstated test recall (82%).
- **Fix correctness is the weakest part** (46% fully correct), and "bug removed" is judged by the same rule that found the bug.
- **"Hallucination" for tool-grounded setups (16-17%)** counts findings whose model-written quote is not on the line; the line itself
  is tool-proposed, so this is a sloppy quote, not an invented location. In Full Firmix the displayed quote is replaced by the real line.
- **Planner:** candidates per file average about 1 on this benchmark (49 over 50 test files), so an LLM planner could save at most
  about 7 of 49 reasoning calls while risking recall. The planner therefore stays in code; the LLM triage variant is kept as an experiment.

## Reproduce

```
python tools/setup_deps.py                    # fetch HAL / CMSIS / FreeRTOS headers
python tools/check_compile.py benchmark       # every benchmark file compiles
python tools/validate_gt.py                   # ground truth matches the files
python tools/build_knowledge.py               # build the BM25 index
python tools/run_baseline.py                  # GCC + cppcheck baseline
python tools/run_eval.py --split dev          # dev evaluation (test split needs --allow-test)
python tools/run_fixer.py --split dev         # fixer on dev
```
Requires Ollama with `qwen3:8b`, `arm-none-eabi-gcc` and `cppcheck`. Plumbing tests (no model needed): `tools/test_*_plumbing.py`.

## Repository map

| Path | What |
|---|---|
| `SPEC.md` | scope, the ten bug definitions, benchmark and evaluation rules |
| `benchmark/` | 50 frozen test files, 20 dev files, `ground_truth.json` |
| `src/codefacts/` | tree-sitter facts, candidate rules, pin map, API (14 tools) |
| `src/knowledge/` | chunker, BM25 store, API (4 tools) |
| `src/buildtools/` | compile and cppcheck runner, fix check (5 tools) |
| `src/servers/` | the three MCP servers |
| `src/agents/` | planner, reasoning, verifier, fixer, single-LLM baselines, pipeline |
| `tools/` | evaluation harness, baseline, plumbing tests |
| `results/` | baseline, dev, test (main, robustness, post-hoc) tables and raw JSON |
