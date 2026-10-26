"""
chunker.py -- turn real primary-source documentation into small citable chunks.

Sources are the open-source files already in deps/ (FreeRTOS-Kernel headers, STM32 HAL
driver, CMSIS core) plus this project's own SPEC.md and FreeRTOSConfig.h. Nothing is
hand-written from memory: every chunk carries its file and line, so a finding can cite
"queue.h:123" and a human can open that exact place.
"""
from __future__ import annotations

import re
from pathlib import Path

MAX_CHARS = 1800

# (path relative to repo root, label shown in citations)
DOC_FILES = [
    # FreeRTOS: queue / semaphore / task / event APIs and which are ISR-safe
    "deps/FreeRTOS-Kernel/include/queue.h", "deps/FreeRTOS-Kernel/include/semphr.h",
    "deps/FreeRTOS-Kernel/include/task.h", "deps/FreeRTOS-Kernel/include/event_groups.h",
    "deps/FreeRTOS-Kernel/include/timers.h", "deps/FreeRTOS-Kernel/include/stream_buffer.h",
    "deps/FreeRTOS-Kernel/portable/GCC/ARM_CM4F/portmacro.h",
    # STM32 HAL: peripheral APIs
    "deps/stm32f4xx_hal_driver/Inc/stm32f4xx_hal_gpio.h",
    "deps/stm32f4xx_hal_driver/Inc/stm32f4xx_hal_gpio_ex.h",
    "deps/stm32f4xx_hal_driver/Inc/stm32f4xx_hal_uart.h",
    "deps/stm32f4xx_hal_driver/Inc/stm32f4xx_hal_i2c.h",
    "deps/stm32f4xx_hal_driver/Inc/stm32f4xx_hal_spi.h",
    "deps/stm32f4xx_hal_driver/Inc/stm32f4xx_hal_adc.h",
    "deps/stm32f4xx_hal_driver/Inc/stm32f4xx_hal_tim.h",
    "deps/stm32f4xx_hal_driver/Inc/stm32f4xx_hal_rcc.h",
    "deps/stm32f4xx_hal_driver/Inc/stm32f4xx_hal_rcc_ex.h",
    "deps/stm32f4xx_hal_driver/Inc/stm32f4xx_hal_cortex.h",
    "deps/stm32f4xx_hal_driver/Inc/stm32f4xx_hal_dma.h",
    "deps/stm32f4xx_hal_driver/Inc/stm32f4xx_hal.h",
    "deps/stm32f4xx_hal_driver/Src/stm32f4xx_hal_cortex.c",
    "deps/stm32f4xx_hal_driver/Src/stm32f4xx_hal.c",
    "deps/stm32f4xx_hal_driver/Src/stm32f4xx_hal_gpio.c",
    "deps/stm32f4xx_hal_driver/Src/stm32f4xx_hal_uart.c",
    "deps/stm32f4xx_hal_driver/Src/stm32f4xx_hal_i2c.c",
    "deps/stm32f4xx_hal_driver/Src/stm32f4xx_hal_spi.c",
    "deps/stm32f4xx_hal_driver/Src/stm32f4xx_hal_adc.c",
    "deps/stm32f4xx_hal_driver/Src/stm32f4xx_hal_tim.c",
    "deps/stm32f4xx_hal_driver/Src/stm32f4xx_hal_rcc.c",
    "deps/stm32f4xx_hal_driver/Src/stm32f4xx_hal_dma.c",
    # CMSIS: NVIC and interrupt masking
    "deps/cmsis_core/CMSIS/Core/Include/core_cm4.h",
    "deps/cmsis_core/CMSIS/Core/Include/cmsis_gcc.h",
    # project config
    "include/FreeRTOSConfig.h",
]

COMMENT = re.compile(r"/\*(\*|!).*?\*/", re.S)
SYMBOL_FN = re.compile(r"\b([A-Za-z_][A-Za-z0-9_]*)\s*\(")
SYMBOL_DEF = re.compile(r"#\s*define\s+([A-Za-z_][A-Za-z0-9_]*)")
SYMBOL_TYPEDEF = re.compile(r"\}\s*([A-Za-z_][A-Za-z0-9_]*)\s*;")
KEYWORDS = {"if", "while", "for", "return", "sizeof", "defined", "switch", "__attribute__", "__ASM",
            "__STATIC_INLINE", "__STATIC_FORCEINLINE"}


def _clean_comment(c: str) -> str:
    c = re.sub(r"^/\*[*!]?", "", c)
    c = re.sub(r"\*/$", "", c)
    lines = [re.sub(r"^\s*\*\s?", "", l).rstrip() for l in c.splitlines()]
    text = "\n".join(lines)
    text = re.sub(r"<[^>\n]{1,40}>", "", text)          # html-ish doxygen tags
    text = re.sub(r"\n{3,}", "\n\n", text).strip()
    return text


def _symbol(decl: str, comment: str) -> str | None:
    # FreeRTOS names each public API on a "\\defgroup <name> <name>" line: that is the API users search for
    g = re.search(r"[\\@]defgroup\s+([A-Za-z_][A-Za-z0-9_]*)", comment)
    if g:
        return g.group(1)
    m = SYMBOL_DEF.search(decl)
    if m:
        return m.group(1)
    m = SYMBOL_TYPEDEF.search(decl)
    if m:
        return m.group(1)
    # function declaration/definition: last identifier before '(' on the first line with one
    for line in decl.splitlines():
        for mm in SYMBOL_FN.finditer(line):
            if mm.group(1) not in KEYWORDS:
                return mm.group(1)
    m = re.search(r"@(?:brief|defgroup)\s+(\S+)", comment)
    return m.group(1) if m else None


def chunk_c_file(path: Path, rel: str):
    text = path.read_text(encoding="utf-8", errors="replace")
    out = []
    for m in COMMENT.finditer(text):
        raw = m.group(0)
        body = _clean_comment(raw)
        if len(body) < 80 or re.search(r"Copyright|SPDX|All rights reserved|Licensed under", body[:400]):
            continue
        if re.match(r"\s*(@file|@defgroup|@addtogroup|@}|\*+$)", body) and "@brief" not in body:
            continue
        end = m.end()
        decl_lines = []
        for ln in text[end:end + 600].splitlines()[1:6]:
            if not ln.strip():
                if decl_lines:
                    break
                continue
            decl_lines.append(ln.rstrip())
            if ln.rstrip().endswith((";", "{")) or ln.lstrip().startswith("#define"):
                break
        decl = "\n".join(decl_lines)
        sym = _symbol(decl, body)
        line = text.count("\n", 0, m.start()) + 1
        full = (body + ("\n\nDeclaration:\n" + decl if decl else ""))[:MAX_CHARS]
        out.append({"source": rel, "line": line, "symbol": sym, "text": full})
    return out


def chunk_config(path: Path, rel: str):
    """FreeRTOSConfig.h: one chunk per commented #define group around priority settings."""
    text = path.read_text(encoding="utf-8", errors="replace").splitlines()
    out = []
    for i, l in enumerate(text, start=1):
        m = re.match(r"\s*#\s*define\s+(config\w+)\s+(.*)", l)
        if m and re.search(r"PRIORIT|PRIO_BITS|TICK_RATE|HEAP|MAX_PRIORITIES", m.group(1)):
            ctx = "\n".join(text[max(0, i - 4):i]).strip()
            out.append({"source": rel, "line": i, "symbol": m.group(1), "text": ctx[:MAX_CHARS]})
    return out


def chunk_spec(path: Path, rel: str):
    text = path.read_text(encoding="utf-8").splitlines()
    out, cur, start, sym = [], [], 0, None
    for i, l in enumerate(text, start=1):
        m = re.match(r"\*\*((?:INT|RTOS|PER|MEM)-\d\d)\b", l)
        if m or l.startswith("## ") or l.startswith("### "):
            if cur and sym:
                out.append({"source": rel, "line": start, "symbol": sym, "text": "\n".join(cur)[:MAX_CHARS]})
            cur, start, sym = ([l], i, m.group(1)) if m else ([], i, None)
            if not m and l.startswith("## 2"):
                cur, sym = [l], "GLOBAL-DEFINITIONS"
        elif cur is not None:
            cur.append(l)
    if cur and sym:
        out.append({"source": rel, "line": start, "symbol": sym, "text": "\n".join(cur)[:MAX_CHARS]})
    return out


def build_chunks(root: Path):
    chunks, missing = [], []
    for rel in DOC_FILES:
        p = root / rel
        if not p.exists():
            missing.append(rel)
            continue
        chunks += chunk_config(p, rel) if rel.endswith("FreeRTOSConfig.h") else chunk_c_file(p, rel)
    spec = root / "SPEC.md"
    if spec.exists():
        chunks += chunk_spec(spec, "SPEC.md")
    for i, c in enumerate(chunks):
        c["id"] = i
    return chunks, missing
