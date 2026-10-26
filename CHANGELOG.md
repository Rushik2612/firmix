# Changelog

- 2026-10-26: SPEC v0.1 drafted (not frozen).
- 2026-10-26: SPEC v0.2. INT-01: exempt RTOS handles/init-once variables and address-only HAL use. INT-02: read-and-reset added. PER-01: anchor pinned to first HAL_*_Init. Dev set d01-d12 written. Added section 8 (code-facts server notes). Not frozen.
- 2026-10-26: Test files f001-f050 drafted (40 buggy + 10 clean near-misses) with ground-truth entries. DRAFT: not yet reviewed or frozen by the owner. 50/50 compile with zero errors; validator clean.

2026-10-26: accepted_lines widened before any detector ran, after an external review: f004 +27, f041 +18, f015 +56, f023 +45. Rejected review claims: GPIO_AF8_USART6 missing (it exists in the HAL header), SYSCFG clock missing (HAL_GPIO_Init enables it). No other ground-truth changes.

2026-10-26 (2): second review round. accepted_lines widened: f006 +18,+20,+72; f049 +24,+26 (config-defining lines / same statement). Rejected as too loose: f018 +49,+69; f033 +6; f043 +58,+63; f013/f017/f038 buffer declarations; f027 +79; f044 +75 (symptom or call-site lines, not the bug itself). f011 RTOS-01 vs INT-03 stays as is: SPEC precedence rule already settles it. f015 as INT-02 rejected: 32-bit aligned read is atomic, so no torn read. Clean files unchanged.

2026-10-26 (3): STEP 4 DONE. Owner confirmed the 50 test files (f001-f050) and ground_truth.json. FROZEN from now on: no edits to benchmark/files or ground truth. Any later change must be logged here with the reason. Rules, prompts and tuning use the dev set (d01-d12) only.
