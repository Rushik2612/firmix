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
