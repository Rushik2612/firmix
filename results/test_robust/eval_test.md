# Evaluation on the test split (40 buggy, 10 clean files), repeats=3

mean ± sd across repeats. Precision = TP/(TP+FP); recall = TP/(TP+FN); hallucination = reported findings whose quoted code is not on the line they name (for the tool-grounded setups the line is tool-proposed, so this only measures a sloppy quote, not an invented location).

## interrupts

| Setup | Precision | Recall (exact line) | Recall (right type anywhere in file) | Hallucination |
|---|---|---|---|---|
| Single LLM (no tools) |    0% ±0 |    0% ±0 |    0% ±0 |    0% ±0 |
| Full Firmix |  100% ±0 |   81% ±13 |   81% ±13 |    6% ±6 |

## RTOS

| Setup | Precision | Recall (exact line) | Recall (right type anywhere in file) | Hallucination |
|---|---|---|---|---|
| Single LLM (no tools) |   n/a   |    0% ±0 |    0% ±0 |   n/a   |
| Full Firmix |  100% ±0 |   89% ±5 |   89% ±5 |   29% ±4 |

## peripherals/HAL

| Setup | Precision | Recall (exact line) | Recall (right type anywhere in file) | Hallucination |
|---|---|---|---|---|
| Single LLM (no tools) |    0% ±0 |    0% ±0 |    0% ±0 |    0% ±0 |
| Full Firmix |   93% ±12 |   58% ±14 |   58% ±14 |   21% ±4 |

## memory

| Setup | Precision | Recall (exact line) | Recall (right type anywhere in file) | Hallucination |
|---|---|---|---|---|
| Single LLM (no tools) |   n/a   |    0% ±0 |    0% ±0 |   n/a   |
| Full Firmix |  100% ±0 |   79% ±14 |   79% ±14 |    0% ±0 |

## All groups

| Setup | Precision | Recall (exact line) | Recall (right type anywhere in file) | Hallucination |
|---|---|---|---|---|
| Single LLM (no tools) |    0% ±0 |    0% ±0 |    0% ±0 |    0% ±0 |
| Full Firmix |   99% ±2 |   78% ±4 |   78% ±4 |   15% ±3 |

## Cost (mean per run)

| Setup | LLM calls | Tokens |
|---|---|---|
| Single LLM (no tools) | 50 | 132847 |
| Full Firmix | 142 | 144749 |
