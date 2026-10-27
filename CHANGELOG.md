# Changelog

- 2026-10-26: SPEC v0.1 drafted (not frozen).
- 2026-10-26: SPEC v0.2. INT-01: exempt RTOS handles/init-once variables and address-only HAL use. INT-02: read-and-reset added. PER-01: anchor pinned to first HAL_*_Init. Dev set d01-d12 written. Added section 8 (code-facts server notes). Not frozen.
- 2026-10-26: Test files f001-f050 drafted (40 buggy + 10 clean near-misses) with ground-truth entries. DRAFT: not yet reviewed or frozen by the owner. 50/50 compile with zero errors; validator clean.

2026-10-26: accepted_lines widened before any detector ran, after an external review: f004 +27, f041 +18, f015 +56, f023 +45. Rejected review claims: GPIO_AF8_USART6 missing (it exists in the HAL header), SYSCFG clock missing (HAL_GPIO_Init enables it). No other ground-truth changes.

2026-10-26 (2): second review round. accepted_lines widened: f006 +18,+20,+72; f049 +24,+26 (config-defining lines / same statement). Rejected as too loose: f018 +49,+69; f033 +6; f043 +58,+63; f013/f017/f038 buffer declarations; f027 +79; f044 +75 (symptom or call-site lines, not the bug itself). f011 RTOS-01 vs INT-03 stays as is: SPEC precedence rule already settles it. f015 as INT-02 rejected: 32-bit aligned read is atomic, so no torn read. Clean files unchanged.

2026-10-26 (3): STEP 4 DONE. Owner confirmed the 50 test files (f001-f050) and ground_truth.json. FROZEN from now on: no edits to benchmark/files or ground truth. Any later change must be logged here with the reason. Rules, prompts and tuning use the dev set (d01-d12) only.

2026-10-26 (4): Step 6 code-facts v1 (src/codefacts: facts.py, rules.py, pinmap.py, api.py; src/servers/codefacts_server.py = MCP server 1 of 3, 14 tools; tools/measure_candidates.py). Rules written from SPEC section 3 and developed on the dev set only (d01-d12: 10/10 candidate recall). Test set run ONCE for measurement, no rule changed afterwards: candidate recall 38/40 (95%, Wilson 95% CI 83-99%). Misses: f029 (MEM-01, length taken from received data; v1 handles only constant sizes/indices), f036 (INT-02, two-field struct read as separate field reads; v1 handles RMW/multi-word/read-then-write only). Both are gaps against the SPEC definitions, not test-specific. Decision: v1 kept as is; the two gaps are documented limitations. Any rule change from here is POST-HOC and must be logged as such, with the v1 number kept in the README.

2026-10-26 (5): Step 7a build MCP server (src/buildtools, src/servers/build_server.py; tools/test_build_mcp.py). 5 tools: compile_file, compile_source, cppcheck_file, cppcheck_source, check_fix. Deterministic, no LLM. Compiles with arm-none-eabi-gcc -Wall -Wextra at -O0 and -O2; check_fix reports compiles / new warnings / changed lines. Untrusted source is restricted to plain #include names. "Bug removed" is NOT decided here; the evaluation harness re-runs the detector on the patched source.

2026-10-26 (6): Step 7b knowledge MCP server (src/knowledge, src/servers/knowledge_server.py; tools/build_knowledge.py, eval_retrieval.py, test_knowledge_mcp.py; knowledge/queries.json). Corpus = doc comments from the real repos in deps/ (FreeRTOS, STM32 HAL, CMSIS) + SPEC.md + FreeRTOSConfig.h, every chunk cited as file:line. Search = BM25 (exact API names matter; offline; deterministic). Retrieval eval, 25 queries written before the first run: v1 recall@3 14/25, MRR 0.55; v2 (added HAL i2c/spi/adc/tim/rcc/dma .c sources and FreeRTOS \defgroup names as symbols, queries unchanged) recall@3 17/25 (68%), MRR 0.61. Embeddings NOT added; revisit only if the agent evaluation shows retrieval is the bottleneck.

2026-10-26 (7): Step 8 start. LLM pinned for ALL LLM-based setups: Ollama, qwen3:8b (supports tools, 5.2 GB, 40K ctx per ollama.com/library/qwen3), temperature 0, seed 42, num_ctx 8192, thinking off. Fallback llama3.1:8b only if tool calling proves unreliable; switching means re-running every LLM setup. Settings live in src/agents/config.py.

2026-10-26 (8): Step 8a reasoning agent (src/agents: llm.py, toolbox.py, findings.py, reasoning.py; tools/run_agents.py, test_agents_plumbing.py). Design: the LLM judges ONE code-facts candidate at a time with the SPEC rule text, evidence excerpts and function source in the prompt, up to 2 rounds of read-only tool calls, then a schema-constrained JSON verdict (exemption_checked, reason, code_quote, line, verdict). It cannot report a bug at a line no tool proposed. run_agents.py refuses the frozen test split unless --allow-test is passed. Prompts are developed on the dev set only.

2026-10-26 (9): Reasoning agent, first real-model run on DEV only (qwen3:8b): 9/10 buggy files found, 0 false alarms on clean dev files, 26 LLM calls, 89 s. The one miss (d06) was the LLM moving the line from the tool-proposed return (50) to the mutex take (45). Dev-driven fix, generic by design: the finding's line is ALWAYS the tool-proposed candidate line; the LLM's own line and quote are only checked by code (model_line, quote_on_line). No test-set run yet.

2026-10-26 (10): Dev-driven prompt/spec fixes after run 2 (dev only; no test run). Run 2 flipped d01 and d03 to misses although only the line anchor had changed: (a) the model treated the tool fact task_read_in_loop_condition=True as an exemption because the prompt called all flags "hints about possible exemptions" (my prompt bug) -> prompt now separates recorded facts from possible exemptions; (b) the model applied "single aligned load/store <= 32 bits" to rx_count-- (a read-modify-write) -> SPEC.md INT-02 'Not a bug' clause now states explicitly that a read-modify-write is not a single load/store (wording clarification, same intent). Knowledge index rebuilt. Also learned: results vary between identical runs; final evaluation will repeat each LLM setup several times.

2026-10-26 (11): Reasoning agent FROZEN on dev after prompt fix: 3 repeat runs on dev gave 10/10 buggy files found with 1 false positive (d03 MEM-01 line 59, a ring-buffer index kept in range by a modulo on line 60 that the 8B model failed to credit). Deliberately NOT patched in rules or prompt: it is the case the verifier exists for. Step 8b verifier (src/agents/verifier.py, pipeline.py; tools/test_verifier_plumbing.py): stage 1 code check (the model's quote is on the proposed line; the suspect reproduces on rule re-run), stage 2 adversarial LLM that tries to refute using the rule's exemptions or a guard in the code; a refutation counts ONLY if it cites a line and quote that code confirms. Setups in run_agents.py: reasoning (no verifier), verified.

(12) Verifier tightened (dev set only; test split untouched). First real run: verifier kept only 4/10 true bugs
because the LLM's refutations were bad (cited the suspect line itself as the "guard", or hedged/self-contradicting
reasoning: "may imply", "however"). Added code-side `refutation_defect`: reject a refutation if guard_line == suspect
line, or the reason contains hedge words. Quote-on-line check is unchanged. Not tuned to any test file.

(13) Verifier stage 1 relaxed (dev only). d06 was dropped as "ungrounded" only because the model's quote did not match
the line text. The LINE is always tool-proposed, so a sloppy quote does not make a finding unreal; the quote is now
replaced by the real source line, and the finding must still reproduce under the deterministic rule. Plumbing test updated.
Known remaining miss: d09 (verifier misapplies the PER-02 exemption "reading an output pin" to a pin that is an input).

(14) Verifier (dev only): d06 still missed after (13) because the verifier cited the xSemaphoreGive at line 54 as a
"guard" for an early return at line 50 that skips it. Added a code rule: a cited guard that comes AFTER the suspect
line cannot protect it, so the refutation is rejected. Plumbing-test fixture corrected (its guard was after the suspect).
Also noted: d09 and d10 flicker between runs (model nondeterminism); final eval must repeat runs.

(15) Step 8c: fixer agent added (src/agents/fixer.py, tools/run_fixer.py, tools/test_fixer_plumbing.py). LLM proposes
line-range edits; code decides success: edits well formed, compiles, no new warnings, rule no longer flags the bug type
in that function, small diff. Up to 2 retries with the exact failure fed back. Dev set only so far.

(16) Fixer hardening (dev only). First real run: the model's d01 fix was correct but it copied the prompt's line-number
label into the code ("  10: static volatile ..."), so it never compiled. Code now strips 'NN|' / 'NN:' labels from new_text
(not valid C anyway) and the prompt tells the model not to copy them. Patched files are saved as bytes (Windows was adding CRs).

(17) Fixer prompt (dev only). Hand review of the first dev run found one WRONG fix that passed all code checks:
d09 PER-02 -- the model turned the door-sensor input (DOOR_PIN) into a push-pull output to silence the rule, which would
break the sensor; the right fix is to remove the stray write. d03: the model proposed a mutex against an ISR race (a mutex
cannot protect against an interrupt). Added two general principles to the prompt: fix the faulty use, not the setup other
code relies on; use a critical section (not a mutex) against ISRs. Lesson for README: "bug removed" is judged by the same
rule that found it, so hand review of fixes is part of the evaluation. Reported dev fix success 8/10 is really 7/10.

(18) Fixer FROZEN on dev after entry 17. Two identical runs: 9/10 by the rule, 8/10 by hand review. d01 correct (volatile).
d03 fails all 3 attempts (the model picks the right idea, a critical section, but its edit deletes an opening brace, so it
does not compile). d09 still WRONG (changes the door-sensor input pin to an output); it passes every code check, so it is
documented as a known wrong fix and is why the final evaluation reports hand-verified correctness next to the rule-based number.
No further fixer tuning.

(19) Step 8d: planner added (src/agents/planner.py, run_planned in pipeline.py, setups 'planned' and 'planned_llm').
Code planner (default): deterministic grouping/ordering of tool-found candidates; cannot lose a bug the candidate stage found.
LLM triage (variant): may only DROP existing candidates. Design finding BEFORE measuring: candidates per file are ~1.0
(dev 13 over 12 files; test 49 over 50 files, only 7 files with >1, 8 with none), so an LLM planner could save at most ~7 of
49 reasoning calls on the whole test set while every skip risks a real bug. Kept deterministic as the default; triage is
reported as an experiment. Limitation to state: the benchmark files are small and single-bug; on real multi-file firmware
with many suspects a planner would matter more. (Only candidate COUNTS were read from the test split, no labels or results.)

(20) Dev set extended from 12 to 20 files (d13-d20: 3 buggy + 5 clean near-misses), written AFTER all four agents were tuned
on d01-d12, to measure out-of-sample behaviour. Test split untouched; test ground-truth entries verified byte-identical.
All 8 compile with 0 errors and 0 warnings. d13 RTOS-02 (I2C mutex leaked on an error return), d14 MEM-01 (memcpy length
from a received frame byte), d15 INT-03 (HAL_Delay in an EXTI callback); clean near-misses: d16 RTOS-02 (goto-out cleanup
gives the mutex), d17 MEM-01 (modulo-guarded ring buffer), d18 MEM-02 (waits on a completion flag), d19 PER-01 (clock enable
inside HAL_SPI_MspInit), d20 RTOS-03 (FromISR at the boundary priority 5).
FIRST out-of-sample candidate-stage result, recorded BEFORE any change: buggy 2/3 (d13, d15 found; d14 MISSED -- the MEM-01
rule covers 'i <= N' and constant sizes but not 'length taken from received data'). Clean: d16, d19, d20 give 0 suspects;
d17 (2 suspects) and d18 (1 suspect) must be dismissed by reasoning+verifier. Decision: candidate rules stay FROZEN (v1);
d14 is documented as a known coverage gap, not patched, because the v1 candidate recall on the test split is already measured.

(21) OUT-OF-SAMPLE RESULT on d13-d20 (agents tuned on d01-d12 only), recorded BEFORE the change below:
verified setup, dev (20 files): found 11/13 buggy (misses: d10 = the known verifier flicker, d14 = the known MEM-01 candidate
gap), 1 false positive: d17 MEM-01 (clean near-miss). Fixer: 10/12 by rule (d03 and d15 failed: d03 broken edit as before;
d15 needed 5 edits, over the 3-edit cap), d14 had no candidate.
Cause of the d17 false positive: MY OWN entry-(14) rule. The verifier gave the correct refutation (head is kept in range by
'head = (head + 1U) % RING_LEN' on the next line) and code rejected it because "a guard after the suspect line cannot protect
it". That is only true for exit paths (RTOS-02); an index invariant or a completion wait (d18) legitimately comes after.
I over-generalised from d06. Change: the 'guard after suspect' rejection now applies to RTOS-02 only. Plumbing tests added.
From here d17 is no longer out-of-sample; the pre-fix numbers above are the honest out-of-sample record.

(22) Step 9 harness added (dev only so far): src/agents/single.py (single-LLM baseline: whole file + all SPEC rules, no tools,
same pinned model), tools/run_eval.py (setups rules / single / agents / full, repeated, per-group precision, recall,
hallucination as mean +- sd; optional --fix), tools/test_eval_plumbing.py (12 checks of the scoring), OllamaLLM(seed=...) for
variation studies. Hallucination = reported finding whose quoted code is not on the line it names. TEST split still refused
without --allow-test.
PLUMBING BUG FIXED in the fixer prompt: get_snippet text already carries 'NN: ' prefixes and the fixer added its own 'NN| ',
so the model saw 'NN| NN: code' and copied the label into its edits. That, not model weakness, was the real cause of the
'10: static volatile ...' failures that entry (16) patched around. Fixer now shows raw lines with ONE label. The earlier fixer dev
numbers (9/10 and 10/12) were produced with the confusing prompt, so the fixer dev run is repeated before the test run.
Also fixed: rules-only setup validated the wrong text (reported 100% hallucination); now 0%, as it must be.

(23) FIRST FULL DEV EVALUATION (20 files: 13 buggy, 7 clean; 3 in-process repeats, pinned temp 0 / seed 42). All repeats were
IDENTICAL (sd 0), so in-process repeats do not measure run-to-run variation (separate invocations did differ earlier).
All groups: rules-only P 67% R 92% H 0%; single LLM P 6% R 8% H 25% (tp 1/13, 15 false positives); agents without verifier
P 86% R 92% H 7%; full Firmix P 100% R 92% H 8%. Remaining miss: d14 (known MEM-01 candidate gap). Verifier: 86% -> 100% precision,
no recall cost. Hallucination for the tool-grounded setups is a sloppy QUOTE (the line itself is tool-proposed), not an invented
location. Fixer 10/12 (d03 broken edit; d15 needs 4-5 edits, cap is 3).
Added to the harness (no change to any agent): lenient column "right bug type anywhere in the file" (so the single-LLM baseline is
not judged only on exact line), per-file findings stored in the results JSON, --temperature for a sampled-robustness study.

(24) ROBUSTNESS RESULT (dev, 20 files, temperature 0.3, seeds 42/43/44): full Firmix precision 100% in all three runs (0 false
positives each), recall 82% +- 12 (11, 12, 9 of 13 found); misses = d14 every time (known candidate gap), d10 sometimes, d04 and d09
in one run. Single LLM: precision 4% +- 3, recall 5% +- 4, and its lenient recall (right bug type anywhere in the file) is the same
5%, so the baseline is not merely being punished for off-by-one lines. Full Firmix's 'hallucination' is one finding per run: d06
RTOS-02, correct tool-proposed line with a sloppy model quote.

(25) PRE-REGISTRATION OF THE TEST-SET RUN (written BEFORE any agent has seen a test file). From this entry on, NOTHING in src/,
SPEC.md, prompts, config.py or the benchmark is changed because of test results. Run once, at the git tag `pre-test-eval`:
  A) python tools/run_eval.py --split test --allow-test --setups rules,single,agents,full --repeats 1 --fix --out results/test_main
  B) python tools/run_eval.py --split test --allow-test --setups single,full --repeats 3 --vary-seed --temperature 0.3 --out results/test_robust
  (A = pinned deterministic configuration, the main table; B = sampled run-to-run spread. GCC + cppcheck: results/baseline_summary.md.)
Predictions, stated in advance: candidate stage ceiling is 38/40 = 95% recall on test (measured earlier); full Firmix exact-line
recall will land between 60% and 85%; precision between 85% and 100%, lower than on dev because the agents were tuned on dev; the
single LLM stays below 15% recall; the fixer's rule-based success rate is below 90% and the hand-verified rate is lower still.
Whatever comes out is what the README reports, including anything worse than predicted.

(26) TEST-SET RESULT, main run (pinned, 40 buggy + 10 clean, run at tag pre-test-eval; nothing changed after seeing it).
Exact-line recall / precision: rules-only 95% (38/40) / 84%; single LLM 0% (0/40) / 0%; agents without verifier 92% (37/40) / 90%;
full Firmix 82% (33/40) / 100%. Predictions made in entry (25): recall 60-85% (held), precision 85-100% (held), single LLM <15% (held),
fixer rule-based success <90% (held). Stage accounting on test: candidate gaps f029 and f036 (2 bugs); the judge dropped 1 true bug
(f004); the verifier dropped 4 true bugs (f003, f024, f037, f041) and removed all 4 remaining false positives (f001 x2, f012 x2). On
F1 the three non-baseline setups are about equal (rules 0.89, agents 0.91, full 0.90): the LLM stages TRADE recall for precision.
Fixer on the 35 true-positive attempts: compiles 25/35, rule-based success 20/35; hand review of the 20 (results/test_main/
fix_review.json, DRAFT verdicts to be spot-checked): 16 correct, 1 partial (f028), 3 wrong although they pass every code check:
f048 (label moved inside the if, both validation failures now fall through; give is dead code), f006 (turns the ADC input PA1
into an output), f025 (deletes the wait and leaves a comment). By type: INT-02 0/4, INT-03 1/4, RTOS-01 1/4 fixed.
Hallucination for the tool-grounded setups (16-17%) is a sloppy model quote on a tool-proposed line, not an invented location.
OPEN: the single-LLM baseline reported 17 findings in only two files (f001, f005, both clean) and nothing elsewhere. Possible silent
parse failures or truncation in my harness; tools/diagnose_single.py (dev only, read-only) added to check. llm.chat now also returns
done_reason (instrumentation only, no behaviour change). Robustness run (temperature 0.3, 3 seeds) still pending.

(27) TEST-SET ROBUSTNESS RUN (temperature 0.3, seeds 42/43/44, same tag pre-test-eval). Full Firmix: precision 99% +- 2 (one
false positive in one of three runs, zero in the other two), exact-line recall 78% +- 4 (31, 30, 33 of 40 found); the pinned run's
33/40 (82%) sits inside that range. Per group (mean +- sd): interrupts 81% +- 13, RTOS 89% +- 5, peripherals/HAL 58% +- 14 (weakest;
precision 93% +- 12), memory 79% +- 14. Single LLM: 0/40 in all three runs (5, 6 and 6 false positives), so its 0% is stable, not a
fluke of one sample. Tokens: single 133k, full 145k per run (about the same cost; full Firmix makes 142 calls vs 50).
Reporting rule for the README: headline numbers are the pinned run; the sampled run is the stability statement.

(28) SINGLE-LLM BASELINE DIAGNOSIS. tools/diagnose_single.py on dev: 0 parse failures, 0 truncated answers, but the v1 baseline returned
the empty list ({"findings":[]}, 6-7 tokens) for ALL 20 dev files in that run. So the pre-registered 0/40 on test is real but weak
evidence: the v1 prompt ('report only what you are confident about, empty list if none') under schema-constrained decoding makes the
8B model say nothing, and in earlier runs it was unstable (sometimes ~16 findings, sometimes none). v1's test result stays in the README
as the pre-registered result.
Equal-effort fix: three tool-free variants (all with the same SPEC rule text and the same pinned model), developed and chosen on the
DEV split only: single_open (same single call, no 'only if confident'), single_checklist (one call, one forced yes/no entry per bug type),
single_pertype (ten calls per file, one rule each). The best-on-dev variant will be run ONCE on test as an extra row, clearly labelled
POST-HOC (decided after seeing the v1 test result). Agents, verifier, fixer, rules, prompts and benchmark are NOT changed.

(29) SINGLE-LLM VARIANTS ON DEV (20 files, 13 buggy, pinned): open P 4% / R 23% / 69 reported (66 false); checklist P 9% / R 38% (54% right-type-anywhere)
/ 55 reported, hallucination 47%; one-call-per-bug-type P 21% / R 38% (54%) / 24 reported, hallucination 8%, 200 calls and 261k tokens
(Full Firmix on the same dev set: P 100%, R 92%, 50 calls, 50k tokens). Best on dev by precision with equal recall: single_pertype.
POST-HOC DECISION (made after seeing the v1 test result, so it is labelled post-hoc in the README): run single_pertype ONCE on the
test split, pinned settings, as an extra baseline row. Command:
  python tools/run_eval.py --split test --allow-test --setups single_pertype --repeats 1 --out results/test_posthoc
The pre-registered v1 result (0/40) stays in the README unchanged. Nothing else changes.

(30) POST-HOC BASELINE ROW ON TEST (single_pertype, chosen on dev in entry 29, run once, pinned): precision 18% (9 TP, 42 FP), exact-line
recall 22% (9/40), right-type-anywhere-in-file recall 38%, hallucination 6%, 500 LLM calls, 698k tokens. Prediction (precision < 30%, recall
< 50%) held. Full Firmix on the same split: precision 100%, recall 82%, 142 calls, 145k tokens. Per group, single_pertype exact-line recall:
interrupts 33%, RTOS 25%, peripherals/HAL 0%, memory 25%. LABEL IN README: post-hoc (decided after the v1 result). The evaluation is now
COMPLETE; no further test-split runs.
