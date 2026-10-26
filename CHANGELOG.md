# Changelog

- 2026-10-26: SPEC v0.1 drafted (not frozen).
- 2026-10-26: SPEC v0.2. INT-01: exempt RTOS handles/init-once variables and address-only HAL use. INT-02: read-and-reset added. PER-01: anchor pinned to first HAL_*_Init. Dev set d01-d12 written. Added section 8 (code-facts server notes). Not frozen.
- 2026-10-26: Test files f001-f050 drafted (40 buggy + 10 clean near-misses) with ground-truth entries. DRAFT: not yet reviewed or frozen by the owner. 50/50 compile with zero errors; validator clean.

2026-10-26: accepted_lines widened before any detector ran, after an external review: f004 +27, f041 +18, f015 +56, f023 +45. Rejected review claims: GPIO_AF8_USART6 missing (it exists in the HAL header), SYSCFG clock missing (HAL_GPIO_Init enables it). No other ground-truth changes.

2026-10-26 (2): second review round. accepted_lines widened: f006 +18,+20,+72; f049 +24,+26 (config-defining lines / same statement). Rejected as too loose: f018 +49,+69; f033 +6; f043 +58,+63; f013/f017/f038 buffer declarations; f027 +79; f044 +75 (symptom or call-site lines, not the bug itself). f011 RTOS-01 vs INT-03 stays as is: SPEC precedence rule already settles it. f015 as INT-02 rejected: 32-bit aligned read is atomic, so no torn read. Clean files unchanged.

2026-10-26 (3): STEP 4 DONE. Owner confirmed the 50 test files (f001-f050) and ground_truth.json. FROZEN from now on: no edits to benchmark/files or ground truth. Any later change must be logged here with the reason. Rules, prompts and tuning use the dev set (d01-d12) only.

2026-10-26 (4): Step 6 code-facts v1 (src/codefacts: facts.py, rules.py, pinmap.py, api.py; src/servers/codefacts_server.py = MCP server 1 of 3, 14 tools; tools/measure_candidates.py). Rules written from SPEC section 3 and developed on the dev set only (d01-d12: 10/10 candidate recall). Test set run ONCE for measurement, no rule changed afterwards: candidate recall 38/40 (95%, Wilson 95% CI 83-99%). Misses: f029 (MEM-01, length taken from received data; v1 handles only constant sizes/indices), f036 (INT-02, two-field struct read as separate field reads; v1 handles RMW/multi-word/read-then-write only). Both are gaps against the SPEC definitions, not test-specific. Decision: v1 kept as is; the two gaps are documented limitations. Any rule change from here is POST-HOC and must be logged as such, with the v1 number kept in the README.

2026-10-26 (5): Step 7a build MCP server (src/buildtools, src/servers/build_server.py; tools/test_build_mcp.py). 5 tools: compile_file, compile_source, cppcheck_file, cppcheck_source, check_fix. Deterministic, no LLM. Compiles with arm-none-eabi-gcc -Wall -Wextra at -O0 and -O2; check_fix reports compiles / new warnings / changed lines. Untrusted source is restricted to plain #include names. "Bug removed" is NOT decided here; the evaluation harness re-runs the detector on the patched source.
