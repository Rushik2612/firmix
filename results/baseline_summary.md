# Baseline: GCC + cppcheck on the frozen 50-file test set

Detected = at least one warning on an accepted line of the buggy file (type not checked; lenient to the baseline).
False alarm = clean file with any warning.

'Any' counts every warning, including cppcheck style hints. 'Serious' counts only GCC warnings and cppcheck error/warning severity.

| Tool | Detected, any (of 40) | Detected, serious (of 40) | Clean files flagged, any (of 10) | Clean files flagged, serious (of 10) | Warnings total |
|---|---|---|---|---|---|
| GCC -Wall -Wextra (-O0/-O2) | 1/40 (2%, 95% CI 0-13%) | 1/40 (2%, 95% CI 0-13%) | 0/10 | 0/10 | 2 |
| cppcheck | 2/40 (5%, 95% CI 1-17%) | 1/40 (2%, 95% CI 0-13%) | 7/10 | 0/10 | 43 |
| GCC + cppcheck | 2/40 (5%, 95% CI 1-17%) | 1/40 (2%, 95% CI 0-13%) | 7/10 | 0/10 | 45 |

## Per bug group (GCC + cppcheck combined)

| Group | Detected |
|---|---|
| RTOS | 0/12 (0%, 95% CI 0-24%) |
| interrupts | 1/12 (8%, 95% CI 1-35%) |
| memory | 1/8 (12%, 95% CI 2-47%) |
| peripherals/HAL | 0/8 (0%, 95% CI 0-32%) |

## Files detected

- gcc: f028
- cppcheck: f015, f028

## Clean files that drew a warning

- gcc: none
- cppcheck: f001, f005, f007, f008, f020, f030, f034
