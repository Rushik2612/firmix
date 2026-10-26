#!/usr/bin/env python3
"""
setup_deps.py -- fetch the four header/source repos Firmix compiles against
into ./deps (shallow clones, ~100 MB total). Safe to re-run.

Needs: git and Python 3. Works on Windows, macOS and Linux.
You also need arm-none-eabi-gcc on PATH (Arm GNU Toolchain, or the copy that
ships with STM32CubeIDE).
"""
import shutil
import subprocess
import sys
from pathlib import Path

DEPS = Path(__file__).resolve().parent.parent / "deps"
REPOS = {
    "cmsis_device_f4":       "https://github.com/STMicroelectronics/cmsis_device_f4.git",
    "stm32f4xx_hal_driver":  "https://github.com/STMicroelectronics/stm32f4xx_hal_driver.git",
    "cmsis_core":            "https://github.com/STMicroelectronics/cmsis_core.git",
    "FreeRTOS-Kernel":       "https://github.com/FreeRTOS/FreeRTOS-Kernel.git",
}

if shutil.which("git") is None:
    sys.exit("git not found on PATH")
DEPS.mkdir(exist_ok=True)
for name, url in REPOS.items():
    target = DEPS / name
    if target.exists():
        print(f"skip   {name} (already there)")
        continue
    print(f"clone  {name} ...")
    subprocess.run(["git", "clone", "--depth", "1", url, str(target)], check=True)

if shutil.which("arm-none-eabi-gcc") is None:
    print("\nWARNING: arm-none-eabi-gcc is not on PATH. Install the Arm GNU Toolchain "
          "and tick 'add to PATH'.")
else:
    print("\narm-none-eabi-gcc found. Next: python tools/check_compile.py benchmark/dev")
