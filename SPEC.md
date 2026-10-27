# Firmix 2.0 — SPEC (v0.2, DRAFT — not frozen)

Status: **DRAFT.** Freeze it only after you have read every section and
checked the open items at the bottom. After the freeze, edits need an entry in
`CHANGELOG.md` with a reason, and are forbidden once any detector has been run
on the test set.

## 1. Scope

- **Target:** STM32F4, reference chip STM32F411RE (`-DSTM32F411xE`), STM32CubeF4 HAL
  (`stm32f4xx_hal_driver`), native FreeRTOS API, Cortex-M4F.
- **Unit of analysis:** one self-contained C file that includes the real HAL and
  FreeRTOS headers. Compile-checked with `arm-none-eabi-gcc -fsyntax-only`
  (`tools/check_compile.py`). No linking, no flashing, no hardware.
- **In scope** only if decidable from that one file plus the knowledge tables
  (ISR names, ISR-safe APIs, clock macros, pin/AF table).
- **Out of scope:** other MCU families, multi-file projects, C++, CMSIS-RTOS
  wrappers, binaries, security/taint vulnerabilities, dynamic analysis, timing
  bugs (priority inversion, deadlines), MISRA compliance.

## 2. Global definitions

- **ISR context:** `SysTick_Handler`; any function named `*_IRQHandler`; any HAL
  callback matching `HAL_*Callback` (excluding `*MspInit`, `*MspDeInit`, which
  run at init time); any function in the file called from those. A function
  reachable from both ISR and task code is **both**.
- **Task context:** `main()`, functions passed to `xTaskCreate`, and everything else.
- **NVIC rules:** 4 priority bits, grouping 4. **Lower number = more urgent.** An
  ISR can be preempted only by a strictly lower number; equal priority never preempts.
- **FreeRTOS config:** `configLIBRARY_MAX_SYSCALL_INTERRUPT_PRIORITY = 5`
  (`include/FreeRTOSConfig.h`). An ISR may call `FromISR` APIs only if its
  priority number is **>= 5**.
- **Anchor line:** the single line recorded in ground truth. `accepted_lines`
  lists alternates, fixed when the file is written, never after a detector has run.

## 3. The 10 bug types

### Interrupts

**INT-01 Missing `volatile` on ISR-shared variable**
- *Bug:* file-scope or static non-const variable accessed in both ISR and task
  context, at least one write, not `volatile`.
- *Not a bug:* single-context variable; `const` data; `*_HandleTypeDef`; a variable
  whose task-side accesses all sit inside critical sections (`__disable_irq()`
  has a memory clobber, so the compiler must reload); RTOS object handles
  (`SemaphoreHandle_t`, `QueueHandle_t`, `TaskHandle_t`, …) and any variable
  written only during initialization, before its interrupt is enabled or before
  `vTaskStartScheduler()`; a variable whose only task-side use is passing its
  address to a HAL function (e.g. the byte given to `HAL_UART_Receive_IT`).
  *(v0.2: last two exemptions added after writing d05, d07 and d03.)*
- *Anchor:* declaration line. *Alternate:* the task-side polling read.
- *Candidate rule:* shared-variable table, non-volatile entries.
- *Judge asks:* does the task side rely on seeing the ISR's update?

**INT-02 Non-atomic access to ISR-shared data**
- *Bug:* plain read-modify-write (`x++`, `x--`, `x |= m`, `x = x + n`), read
  followed by a write of the same variable (read-and-reset: `n = c; c = 0;`),
  multi-word access (`uint64_t`, `double`, struct copy) or check-then-act on
  related variables, while another context that can preempt it also writes the
  data; no critical section or IRQ masking. *(v0.2: read-and-reset added; it is
  the same lost-update failure.)*
- *Not a bug:* a single aligned load or store of <= 32 bits; two ISRs of equal priority. A read-modify-write (`x++`, `x--`, `x |= m`, `x = x + n`) is NOT a single load/store, even on a `uint8_t`.
- *Anchor:* the unprotected access (the lower-priority side for ISR-vs-ISR).
- *Candidate rule:* RMW / multi-word access to a shared variable outside any
  critical-section region, with the preemption check applied.

**INT-03 Blocking or non-reentrant call in ISR**
- *Bug:* ISR-context call to `HAL_Delay`; a polling HAL transfer
  (`HAL_UART_Transmit`, `HAL_I2C_Master_Transmit`, `HAL_SPI_Transmit`,
  `HAL_ADC_PollForConversion`, …); `printf`/`sprintf` family; `malloc`/`free`;
  an unbounded `while` on a peripheral flag. (`HAL_Delay` and polling calls need
  the HAL tick: they hang unless SysTick is strictly more urgent than the caller.)
- *Not a bug:* FreeRTOS calls (RTOS-01); `_IT`/`_DMA` start calls (re-arming
  `HAL_UART_Receive_IT` in a callback is normal); bounded loops.
- *Anchor:* the call line.

### RTOS

**RTOS-01 Non-ISR-safe FreeRTOS API called from ISR**
- *Bug:* ISR-context call to a FreeRTOS API that has a `FromISR` variant, or to
  `vTaskDelay` / `vTaskDelayUntil`.
- *Not a bug:* `FromISR` APIs, `portYIELD_FROM_ISR`, or the same calls from task context.
- *Anchor:* the call line. *Precedence:* FreeRTOS call ⇒ RTOS-01, never INT-03.

**RTOS-02 Mutex not released on every exit path**
- *Bug:* successful take of a mutex (`xSemaphoreCreateMutex` / recursive), then a
  path to function exit (`return`, `goto`) with no matching give.
- *Not a bug:* binary/counting semaphores used for signaling; a give in another
  function (avoided in the benchmark).
- *Anchor:* the leaking `return`; if no give exists in the function, the take line.

**RTOS-03 `FromISR` call from an ISR more urgent than the allowed priority**
- *Bug:* ISR calls a `FromISR` API and its priority number (a compile-time constant
  passed to `HAL_NVIC_SetPriority`) is **< 5**.
- *Not a bug:* priority >= 5; non-constant priority (undecidable; avoided).
- *Anchor:* the `FromISR` call line. *Alternate:* the `HAL_NVIC_SetPriority` line.

### Peripherals / HAL

**PER-01 Peripheral used without clock enable**
- *Bug:* peripheral or GPIO port initialized/accessed with no matching
  `__HAL_RCC_*_CLK_ENABLE()` anywhere in the file, **or** the enable comes after
  first use in straight-line code.
- *Not a bug:* enable inside the file's own `HAL_*_MspInit`; peripherals not used.
- *Anchor:* the first `HAL_*_Init` call for that peripheral (or its first direct
  register access). *Alternate:* the line that assigns `.Instance`.
  *(v0.2: pinned down after d08; "first init line" was ambiguous.)*

**PER-02 GPIO configuration contradicts use**
- *Bug (a):* `HAL_GPIO_WritePin`/`TogglePin` on a pin configured input or analog.
  *(b):* pin used as a peripheral signal but not `GPIO_MODE_AF_*`, or given an AF
  macro belonging to a different peripheral.
- *Not a bug:* reading an output pin; EXTI pins read with `ReadPin`.
- *Anchor:* the write line for (a); the `HAL_GPIO_Init` line for (b).

### Memory

**MEM-01 Fixed-size buffer overflow**
- *Bug:* write to a fixed-size array with an index/length that is out of range at
  compile time (`i <= N`, constant `memcpy` size > buffer) or taken from received
  data with no bounds check.
- *Not a bug:* guarded writes; bounded `snprintf`/`strncpy`.
- *Anchor:* the write line.

**MEM-02 Stack buffer passed to async HAL transfer**
- *Bug:* local non-static array passed to an `_IT`/`_DMA` HAL call and the
  function can return before the transfer completes.
- *Not a bug:* static/global buffer; polling HAL call; function that waits for
  completion (flag loop, or semaphore given by the callback). `HAL_Delay` is **not**
  proof of completion.
- *Anchor:* the HAL call line.

## 4. Benchmark rules

- **Test set:** 40 buggy (4 per type: 12 interrupts, 12 RTOS, 8 peripherals,
  8 memory) + 10 clean = 50 files, in `benchmark/files/`, named `fNNN.c`
  (slots in `benchmark/PLAN.md`). Names are neutral and shuffled so a path never
  reveals the bug type.
- **Dev set:** `benchmark/dev/dNN.c`, 12 files, **already written** (d01–d12: one
  buggy per type + 2 clean near-misses). Rules and prompts may be developed against
  these **only**. Every dev file compiles with zero errors and zero warnings
  (`-Wall -Wextra`, also at `-O2 -Warray-bounds`), so GCC reports none of the
  12 seeded situations. cppcheck has not been run yet.
- **One seeded bug per buggy file**, 40–150 lines of realistic code. The file
  must contain **none of the other 9 bug types**. Self-review every file against
  all 10 definitions before listing it.
- **Clean files are near-misses:** each one is a hard negative for one bug type
  (e.g. equal-priority ISRs sharing a counter for INT-02, `FromISR` at priority 6
  for RTOS-03). A clean file must be clean for **all 10** types.
- **No hints:** no comment that mentions the bug, the fix, or "seeded/TODO/FIXME"
  (`validate_gt.py` warns). Do not name variables `bug_*`.
- **Vary the four files per type:** different peripherals, structure and variable
  names. Four near-copies with one renamed variable measure memorization, not detection.
- **Compile rule:** zero **errors** (`tools/check_compile.py`). Warnings are fine
  and are **recorded**: if GCC already warns about a seeded bug, that is a real
  result for the GCC baseline, not a defect of the file.
- **Prove the bug is real.** Write one line in the ground-truth `note` saying why
  it fails. For INT-01 check the `-O2` disassembly (see `d01`/`d02`).
- **Frozen before any detector exists.** Test files and `ground_truth.json` are
  never edited after the first detector run. A mistake found later is logged in
  `CHANGELOG.md`, the file is excluded **for all setups**, and the exclusion is
  reported in the README.

## 5. Ground truth format

`benchmark/ground_truth.json`: one entry per file, validated by `tools/validate_gt.py`.

```json
{ "file": "files/f014.c", "split": "test", "label": "buggy", "bug_type": "INT-01",
  "anchor_line": 10, "accepted_lines": [10, 57],
  "anchor_snippet": "static uint8_t button_pressed;", "note": "why this fails" }
{ "file": "files/f034.c", "split": "test", "label": "clean",
  "near_miss_of": "INT-01", "note": "why this is safe" }
```

`anchor_snippet` must appear on the anchor line; it keeps line numbers honest if
you later add or remove a line.

## 6. Evaluation protocol

- **Setups (5):** GCC + cppcheck · candidate rules only (no LLM) · single LLM ·
  agents without verifier · full Firmix. Same LLM, temperature 0 and seed fixed
  for every LLM setup; model version recorded in the results table.
- **Match:** a finding is a **true positive** if it has the same file, same bug
  type, and a line in `accepted_lines`. Any other finding is a **false positive**.
  A buggy file with no matching finding is a **false negative**. Every finding
  on a clean file is a false positive.
- **Hallucination:** a reported finding that cites a line, construct or evidence
  ID that does not exist. Counted separately from false positives (a real
  construct wrongly judged).
- **Metrics per bug group:** precision, recall, hallucination rate; fix success
  rate = fix compiles, the finding's rule no longer fires, no new finding appears,
  diff under a size limit. All with Wilson 95% confidence intervals.
- **Honesty rules:** report `uncertain` verdicts separately; no prompt or rule edits
  after the test set is first run; dev-set results are never reported as test results.

## 7. Open items (resolve before freezing)

1. Approve the 10 types (RTOS-03 and MEM-02 are the least conventional).
2. Check `INT-01 'not a bug'` (critical-section reads) against your own view.
3. PER-02 needs a hand-curated pin→AF table; decide its source (datasheet table 9).
4. Decide whether fixed twins (bug-free copy of each buggy file) happen on Nov 3.

## 8. Notes for the code-facts server (found while writing the dev set)

- **Resolve `#define` constants.** d03, d08, d09, d10 use macros for ports, pins,
  sizes and thresholds (`DOOR_PIN`, `SAMPLE_COUNT`). tree-sitter does not expand
  macros, so the server needs a table built from `preproc_def` nodes, or
  PER-02 and MEM-01 will fail on realistic code.
- **Map IRQ numbers to handler names** (`USART2_IRQn` ↔ `USART2_IRQHandler`, from the
  startup file's vector table) so `HAL_NVIC_SetPriority(USART2_IRQn, 2, 0)` can be
  joined to the ISR that RTOS-03 and INT-02 reason about (d07, d12).
- **Callback list:** `HAL_*Callback` functions reached from `*_IRQHandler` via the
  HAL's own IRQ handler (d01–d05, d07, d11, d12). Treat them as ISR context by name.
- **Constant-priority extraction** must also accept the two-value form
  `HAL_NVIC_SetPriority(irq, preempt, sub)`; only `preempt` matters (grouping 4).
