# Evaluation on the test split (40 buggy, 10 clean files), repeats=1

mean ± sd across repeats. Precision = TP/(TP+FP); recall = TP/(TP+FN); hallucination = reported findings whose quoted code is not on the line they name (for the tool-grounded setups the line is tool-proposed, so this only measures a sloppy quote, not an invented location).

## interrupts

| Setup | Precision | Recall (exact line) | Recall (right type anywhere in file) | Hallucination |
|---|---|---|---|---|
| Rules only (code-facts, no LLM) |   92% ±0 |   92% ±0 |   92% ±0 |    0% ±0 |
| Single LLM (no tools) |    0% ±0 |    0% ±0 |    0% ±0 |   10% ±0 |
| Agents, no verifier |  100% ±0 |   92% ±0 |   92% ±0 |    8% ±0 |
| Full Firmix |  100% ±0 |   83% ±0 |   83% ±0 |    9% ±0 |

## RTOS

| Setup | Precision | Recall (exact line) | Recall (right type anywhere in file) | Hallucination |
|---|---|---|---|---|
| Rules only (code-facts, no LLM) |  100% ±0 |  100% ±0 |  100% ±0 |    0% ±0 |
| Single LLM (no tools) |   n/a   |    0% ±0 |    0% ±0 |   n/a   |
| Agents, no verifier |  100% ±0 |  100% ±0 |  100% ±0 |   31% ±0 |
| Full Firmix |  100% ±0 |  100% ±0 |  100% ±0 |   31% ±0 |

## peripherals/HAL

| Setup | Precision | Recall (exact line) | Recall (right type anywhere in file) | Hallucination |
|---|---|---|---|---|
| Rules only (code-facts, no LLM) |   80% ±0 |  100% ±0 |  100% ±0 |    0% ±0 |
| Single LLM (no tools) |    0% ±0 |    0% ±0 |    0% ±0 |    0% ±0 |
| Agents, no verifier |   78% ±0 |   88% ±0 |   88% ±0 |   22% ±0 |
| Full Firmix |  100% ±0 |   62% ±0 |   62% ±0 |   20% ±0 |

## memory

| Setup | Precision | Recall (exact line) | Recall (right type anywhere in file) | Hallucination |
|---|---|---|---|---|
| Rules only (code-facts, no LLM) |   64% ±0 |   88% ±0 |   88% ±0 |    0% ±0 |
| Single LLM (no tools) |   n/a   |    0% ±0 |    0% ±0 |   n/a   |
| Agents, no verifier |   78% ±0 |   88% ±0 |   88% ±0 |    0% ±0 |
| Full Firmix |  100% ±0 |   75% ±0 |   75% ±0 |    0% ±0 |

## All groups

| Setup | Precision | Recall (exact line) | Recall (right type anywhere in file) | Hallucination |
|---|---|---|---|---|
| Rules only (code-facts, no LLM) |   84% ±0 |   95% ±0 |   95% ±0 |    0% ±0 |
| Single LLM (no tools) |    0% ±0 |    0% ±0 |    0% ±0 |    6% ±0 |
| Agents, no verifier |   90% ±0 |   92% ±0 |   92% ±0 |   16% ±0 |
| Full Firmix |  100% ±0 |   82% ±0 |   82% ±0 |   17% ±0 |

## Cost (mean per run)

| Setup | LLM calls | Tokens |
|---|---|---|
| Rules only (code-facts, no LLM) | 0 | 0 |
| Single LLM (no tools) | 50 | 133166 |
| Agents, no verifier | 98 | 106166 |
| Full Firmix | 142 | 144962 |

## Fixer (on true positives of the full setup, all runs)

- attempted: 35
- compiles: 25/35
- bug removed by the rule + compiles + small diff (rule-based success): 20/35
- hand-verified correct: fill results/fix_review.json ({"file|bug_type": true/false}) after reading each diff
