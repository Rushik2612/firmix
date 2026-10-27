# Evaluation on the dev split (13 buggy, 7 clean files), repeats=1

mean ± sd across repeats. Precision = TP/(TP+FP); recall = TP/(TP+FN); hallucination = reported findings whose quoted code is not on the line they name (for the tool-grounded setups the line is tool-proposed, so this only measures a sloppy quote, not an invented location).

## interrupts

| Setup | Precision | Recall (exact line) | Recall (right type anywhere in file) | Hallucination |
|---|---|---|---|---|
| Single LLM, open prompt (no tools) |    6% ±0 |   75% ±0 |   75% ±0 |    4% ±0 |
| Single LLM, per-type checklist (no tools) |    6% ±0 |   50% ±0 |   75% ±0 |   48% ±0 |
| Single LLM, one call per bug type (no tools) |   13% ±0 |   50% ±0 |   75% ±0 |    7% ±0 |

## RTOS

| Setup | Precision | Recall (exact line) | Recall (right type anywhere in file) | Hallucination |
|---|---|---|---|---|
| Single LLM, open prompt (no tools) |   n/a   |    0% ±0 |    0% ±0 |   n/a   |
| Single LLM, per-type checklist (no tools) |    0% ±0 |    0% ±0 |   25% ±0 |   25% ±0 |
| Single LLM, one call per bug type (no tools) |   33% ±0 |   25% ±0 |   50% ±0 |    0% ±0 |

## peripherals/HAL

| Setup | Precision | Recall (exact line) | Recall (right type anywhere in file) | Hallucination |
|---|---|---|---|---|
| Single LLM, open prompt (no tools) |    0% ±0 |    0% ±0 |    0% ±0 |   12% ±0 |
| Single LLM, per-type checklist (no tools) |    0% ±0 |    0% ±0 |    0% ±0 |   60% ±0 |
| Single LLM, one call per bug type (no tools) |    0% ±0 |    0% ±0 |    0% ±0 |   33% ±0 |

## memory

| Setup | Precision | Recall (exact line) | Recall (right type anywhere in file) | Hallucination |
|---|---|---|---|---|
| Single LLM, open prompt (no tools) |   n/a   |    0% ±0 |    0% ±0 |   n/a   |
| Single LLM, per-type checklist (no tools) |   30% ±0 |  100% ±0 |  100% ±0 |   40% ±0 |
| Single LLM, one call per bug type (no tools) |   67% ±0 |   67% ±0 |   67% ±0 |    0% ±0 |

## All groups

| Setup | Precision | Recall (exact line) | Recall (right type anywhere in file) | Hallucination |
|---|---|---|---|---|
| Single LLM, open prompt (no tools) |    4% ±0 |   23% ±0 |   23% ±0 |    6% ±0 |
| Single LLM, per-type checklist (no tools) |    9% ±0 |   38% ±0 |   54% ±0 |   47% ±0 |
| Single LLM, one call per bug type (no tools) |   21% ±0 |   38% ±0 |   54% ±0 |    8% ±0 |

## Cost (mean per run)

| Setup | LLM calls | Tokens |
|---|---|---|
| Single LLM, open prompt (no tools) | 20 | 55584 |
| Single LLM, per-type checklist (no tools) | 20 | 63738 |
| Single LLM, one call per bug type (no tools) | 200 | 261481 |
