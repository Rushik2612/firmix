# Evaluation on the test split (40 buggy, 10 clean files), repeats=1

mean ± sd across repeats. Precision = TP/(TP+FP); recall = TP/(TP+FN); hallucination = reported findings whose quoted code is not on the line they name (for the tool-grounded setups the line is tool-proposed, so this only measures a sloppy quote, not an invented location).

## interrupts

| Setup | Precision | Recall (exact line) | Recall (right type anywhere in file) | Hallucination |
|---|---|---|---|---|
| Single LLM, one call per bug type (no tools) |   15% ±0 |   33% ±0 |   50% ±0 |    4% ±0 |

## RTOS

| Setup | Precision | Recall (exact line) | Recall (right type anywhere in file) | Hallucination |
|---|---|---|---|---|
| Single LLM, one call per bug type (no tools) |   27% ±0 |   25% ±0 |   58% ±0 |    9% ±0 |

## peripherals/HAL

| Setup | Precision | Recall (exact line) | Recall (right type anywhere in file) | Hallucination |
|---|---|---|---|---|
| Single LLM, one call per bug type (no tools) |    0% ±0 |    0% ±0 |    0% ±0 |   12% ±0 |

## memory

| Setup | Precision | Recall (exact line) | Recall (right type anywhere in file) | Hallucination |
|---|---|---|---|---|
| Single LLM, one call per bug type (no tools) |   40% ±0 |   25% ±0 |   25% ±0 |    0% ±0 |

## All groups

| Setup | Precision | Recall (exact line) | Recall (right type anywhere in file) | Hallucination |
|---|---|---|---|---|
| Single LLM, one call per bug type (no tools) |   18% ±0 |   22% ±0 |   38% ±0 |    6% ±0 |

## Cost (mean per run)

| Setup | LLM calls | Tokens |
|---|---|---|
| Single LLM, one call per bug type (no tools) | 500 | 698080 |
