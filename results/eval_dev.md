# Evaluation on the dev split (13 buggy, 7 clean files), repeats=3

mean ± sd across repeats. Precision = TP/(TP+FP); recall = TP/(TP+FN); hallucination = reported findings whose quoted code is not on the line they name (for the tool-grounded setups the line is tool-proposed, so this only measures a sloppy quote, not an invented location).

## interrupts

| Setup | Precision | Recall (exact line) | Recall (right type anywhere in file) | Hallucination |
|---|---|---|---|---|
| Single LLM (no tools) |    6% ±5 |   17% ±14 |   17% ±14 |   18% ±1 |
| Full Firmix |  100% ±0 |   92% ±14 |   92% ±14 |    0% ±0 |

## RTOS

| Setup | Precision | Recall (exact line) | Recall (right type anywhere in file) | Hallucination |
|---|---|---|---|---|
| Single LLM (no tools) |   n/a   |    0% ±0 |    0% ±0 |   n/a   |
| Full Firmix |  100% ±0 |  100% ±0 |  100% ±0 |   25% ±0 |

## peripherals/HAL

| Setup | Precision | Recall (exact line) | Recall (right type anywhere in file) | Hallucination |
|---|---|---|---|---|
| Single LLM (no tools) |    0% ±0 |    0% ±0 |    0% ±0 |    0% ±0 |
| Full Firmix |  100% ±0 |   83% ±29 |   83% ±29 |    0% ±0 |

## memory

| Setup | Precision | Recall (exact line) | Recall (right type anywhere in file) | Hallucination |
|---|---|---|---|---|
| Single LLM (no tools) |   n/a   |    0% ±0 |    0% ±0 |   n/a   |
| Full Firmix |  100% ±0 |   44% ±19 |   44% ±19 |    0% ±0 |

## All groups

| Setup | Precision | Recall (exact line) | Recall (right type anywhere in file) | Hallucination |
|---|---|---|---|---|
| Single LLM (no tools) |    4% ±3 |    5% ±4 |    5% ±4 |   12% ±1 |
| Full Firmix |  100% ±0 |   82% ±12 |   82% ±12 |   10% ±1 |

## Cost (mean per run)

| Setup | LLM calls | Tokens |
|---|---|---|
| Single LLM (no tools) | 20 | 51880 |
| Full Firmix | 50 | 50201 |
