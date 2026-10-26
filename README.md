# Firmix 2.0

Tool-grounded multi-agent bug finder for STM32F4 firmware. This folder currently
holds the **spec and benchmark scaffolding** (no detector yet).

## Quick start (Windows PowerShell or any shell)

```
python tools/setup_deps.py                       # one-time: fetch HAL / CMSIS / FreeRTOS
python tools/check_compile.py benchmark/dev      # every benchmark file must compile (0 errors)
python tools/validate_gt.py                      # ground truth matches files; shows progress
```

## Layout

| Path | What |
|---|---|
| `SPEC.md` | scope, 10 bug-type definitions, benchmark and evaluation rules |
| `benchmark/PLAN.md` | which neutral slot name (fNNN) holds which bug type |
| `benchmark/files/` | the 50 test files (write here; never tune against them) |
| `benchmark/dev/` | dev files; d01 (buggy) and d02 (near-miss clean) are worked examples |
| `benchmark/ground_truth.json` | answer key: file, line, bug type |
| `include/` | shared `stm32f4xx_hal_conf.h` and `FreeRTOSConfig.h` (max syscall priority 5) |
| `tools/` | `check_compile.py`, `validate_gt.py`, `make_plan.py`, `setup_deps.py` |
| `tools/selftest/smoke.c` | toolchain smoke test |

## Workflow per benchmark file

1. Pick a slot from `benchmark/PLAN.md`; create `benchmark/files/fNNN.c`.
2. `python tools/check_compile.py benchmark/files/fNNN.c`
3. Add its entry to `benchmark/ground_truth.json` (copy the d01/d02 pattern).
4. `python tools/validate_gt.py`
