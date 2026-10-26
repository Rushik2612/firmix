"""
rules.py -- deterministic CANDIDATE generation for the 10 bug types.

A candidate is a suspect, not a verdict: the rule found a code pattern that the
SPEC (section 3) says can be a bug. Each candidate carries the facts that triggered
it (`evidence`) and facts that argue for an exemption (`flags`), so the later LLM
judge and the verifier have something concrete to check. Candidate rules are
deliberately recall-oriented. Precision comes from the judge + verifier, and the
evaluation measures it.

Every rule here was written from the SPEC definitions and developed against the
dev set only (benchmark/dev). The frozen test set was never used to adjust a rule.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field, asdict

from .facts import (Facts, RTOS_HANDLE_TYPES, RTOS_PLAIN_APIS, BLOCKING_EXACT,
                    POLLING_HAL, ASYNC_SUFFIX, CRIT_ENTER, CRIT_EXIT, ELEM_SIZE)
from .pinmap import AF_TABLE, ANALOG_ONLY

MAX_SYSCALL_PRIO = 5   # configLIBRARY_MAX_SYSCALL_INTERRUPT_PRIORITY (include/FreeRTOSConfig.h)


@dataclass
class Candidate:
    bug_type: str
    line: int                       # proposed anchor line
    function: str | None
    rule: str                       # which rule fired
    summary: str                    # one-line human description
    evidence: list = field(default_factory=list)   # [{"line": n, "fact": "..."}]
    flags: dict = field(default_factory=dict)      # exemption hints for the judge
    alt_lines: list = field(default_factory=list)

    def to_dict(self):
        return asdict(self)


# =============================================================================
# helpers
# =============================================================================
def _ev(line, fact):
    return {"line": line, "fact": fact}


def _is_rtos_handle(g) -> bool:
    return g.type in RTOS_HANDLE_TYPES or g.type.endswith("HandleTypeDef")


def _shared_vars(F: Facts):
    """var -> {'isr': [accesses], 'task': [accesses]} for file-scope non-const variables
    touched from both contexts. A function reachable from ISR *and* task counts as both."""
    called_from_task = set()
    for c in F.calls:
        if c.function and c.function not in F.isr_context and c.name in F.functions:
            called_from_task.add(c.name)
    out = {}
    for a in F.accesses:
        g = F.globals[a.var]
        if g.const or _is_rtos_handle(g) or g.array is not None and a.kind == "address":
            continue
        isr_side = F.is_isr(a.function)
        task_side = (not isr_side) or (a.function in called_from_task)
        d = out.setdefault(a.var, {"isr": [], "task": []})
        if isr_side:
            d["isr"].append(a)
        if task_side:
            d["task"].append(a)
    return {k: v for k, v in out.items() if v["isr"] and v["task"]}


# =============================================================================
# INT-01  missing volatile on ISR-shared variable
# =============================================================================
def int01(F: Facts):
    cands = []
    for var, d in _shared_vars(F).items():
        g = F.globals[var]
        if g.volatile:
            continue
        accs = d["isr"] + d["task"]
        if not any(a.kind in ("write", "rmw") for a in accs):
            continue
        # exemption hint: every task-side access is inside a critical section
        task_unprot = [a for a in d["task"] if not a.in_critical and a.kind != "address"]
        task_addr_only = d["task"] and all(a.kind == "address" for a in d["task"])
        if task_addr_only:
            continue
        flags = {"all_task_accesses_in_critical_section": not task_unprot,
                 "task_read_in_loop_condition": any(a.in_loop_cond for a in d["task"])}
        evid = [_ev(g.line, f"'{var}' declared '{g.type}' without volatile")]
        evid += [_ev(a.line, f"{a.kind} of '{var}' in ISR context ({a.function})") for a in d["isr"][:2]]
        evid += [_ev(a.line, f"{a.kind} of '{var}' in task context ({a.function})"
                     + (" inside loop condition" if a.in_loop_cond else "")
                     + (" inside critical section" if a.in_critical else ""))
                 for a in d["task"][:3]]
        poll = [a.line for a in d["task"] if a.in_loop_cond]
        alt = poll or [a.line for a in task_unprot[:1]]
        cands.append(Candidate("INT-01", g.line, None, "shared-nonvolatile",
                               f"'{var}' is shared between ISR and task code but not volatile",
                               evid, flags, alt))
    return cands


# =============================================================================
# INT-02  non-atomic access to ISR-shared data
# =============================================================================
def int02(F: Facts):
    cands = []
    for var, d in _shared_vars(F).items():
        g = F.globals[var]
        multiword = ELEM_SIZE.get(g.type, 4) > 4 and not g.pointer and g.array is None
        is_struct = g.type.startswith("struct") or (g.type not in ELEM_SIZE and g.array is None
                                                    and not g.pointer and not g.type.endswith("_t"))
        # which side writes
        isr_writes = [a for a in d["isr"] if a.kind in ("write", "rmw")]
        task_writes = [a for a in d["task"] if a.kind in ("write", "rmw")]
        if not isr_writes and not task_writes:
            continue
        # task-side RMW, or read followed by write of the same var in one function
        by_func = {}
        for a in d["task"]:
            by_func.setdefault(a.function, []).append(a)
        for fn, accs in by_func.items():
            accs = sorted(accs, key=lambda a: a.line)
            for a in accs:
                if a.in_critical:
                    continue
                reason = None
                if a.kind == "rmw":
                    reason = "read-modify-write"
                elif multiword and a.kind in ("read", "write"):
                    reason = f"{ELEM_SIZE.get(g.type)*8}-bit access (not a single load/store)"
                elif is_struct and a.kind == "read":
                    reason = "struct/multi-field access"
                if reason and isr_writes:
                    cands.append(Candidate(
                        "INT-02", a.line, fn, "nonatomic-shared",
                        f"'{var}' {reason} in {fn} while an ISR also writes it",
                        [_ev(a.line, f"{a.kind} of '{var}' in {fn}, outside any critical section: {a.text}")]
                        + [_ev(w.line, f"ISR-context write of '{var}' in {w.function}") for w in isr_writes[:2]],
                        {"type": g.type, "volatile": g.volatile}))
            # read-then-write (read-and-reset) in same function
            reads = [a for a in accs if a.kind == "read" and not a.in_critical]
            writes = [a for a in accs if a.kind == "write" and not a.in_critical]
            for r in reads:
                for w in writes:
                    if r.line < w.line and w.line - r.line <= 4 and isr_writes \
                            and not any(c.kind == "rmw" and c.line == r.line for c in accs):
                        cands.append(Candidate(
                            "INT-02", r.line, fn, "read-then-write",
                            f"'{var}' read at line {r.line} then overwritten at {w.line} in {fn}; "
                            f"an ISR update between them is lost",
                            [_ev(r.line, f"read of '{var}': {r.text}"),
                             _ev(w.line, f"write of '{var}': {w.text}")]
                            + [_ev(x.line, f"ISR-context write in {x.function}") for x in isr_writes[:1]],
                            {}, [w.line]))
        # two-ISR RMW with unequal priority is left to the judge (needs priorities)
    # dedupe by (line, var-rule)
    seen, out = set(), []
    for c in cands:
        k = (c.line, c.rule)
        if k not in seen:
            seen.add(k)
            out.append(c)
    return out


# =============================================================================
# INT-03  blocking / non-reentrant call in ISR
# =============================================================================
def int03(F: Facts):
    cands = []
    for c in F.calls:
        if not F.is_isr(c.function):
            continue
        name = c.name
        why = None
        if name in BLOCKING_EXACT:
            why = f"'{name}' blocks or is not reentrant"
        elif POLLING_HAL.match(name) and not ASYNC_SUFFIX.search(name):
            why = f"'{name}' is a polling HAL transfer (needs the HAL tick / waits for hardware)"
        elif name == "HAL_ADC_PollForConversion":
            why = "polling ADC conversion"
        if why:
            chain = " -> ".join(F.isr_context[c.function])
            cands.append(Candidate("INT-03", c.line, c.function, "blocking-call-in-isr",
                                   f"{why}, reached from ISR via {chain}",
                                   [_ev(c.line, f"call: {c.text}"),
                                    _ev(F.functions[c.function].start, f"ISR path: {chain}")],
                                   {"also_called_from_task": _also_task(F, c.function)}))
    # unbounded while on a peripheral flag inside ISR context
    for fn in F.isr_context:
        node = F.functions[fn].node
        stack = [node]
        while stack:
            n = stack.pop()
            stack.extend(n.children)
            if n.type == "while_statement":
                cond = n.child_by_field_name("condition")
                ctxt = cond.text.decode() if cond is not None else ""
                if re.search(r"(->|\.)\s*(SR|ISR|CR\d?|DR|SR1|SR2)\b|__HAL_\w+_GET_FLAG|\bGET_FLAG\b", ctxt) \
                        and not re.search(r"(timeout|tick|count|retry|spins|limit|<)", ctxt, re.I):
                    ln = n.start_point[0] + 1
                    chain = " -> ".join(F.isr_context[fn])
                    cands.append(Candidate("INT-03", ln, fn, "unbounded-flag-wait-in-isr",
                                           f"unbounded wait on a peripheral flag in ISR path {chain}",
                                           [_ev(ln, f"loop: while {ctxt.strip()}")], {}))
    return cands


def _also_task(F, func):
    return any(c.name == func and c.function and c.function not in F.isr_context for c in F.calls)


# =============================================================================
# RTOS-01  non-ISR-safe FreeRTOS API in ISR
# =============================================================================
def rtos01(F: Facts):
    cands = []
    for c in F.calls:
        if c.name in RTOS_PLAIN_APIS and F.is_isr(c.function):
            chain = " -> ".join(F.isr_context[c.function])
            cands.append(Candidate("RTOS-01", c.line, c.function, "plain-rtos-api-in-isr",
                                   f"'{c.name}' has a FromISR variant but is called from ISR context ({chain})",
                                   [_ev(c.line, f"call: {c.text}"),
                                    _ev(F.functions[c.function].start, f"ISR path: {chain}")],
                                   {"also_called_from_task": _also_task(F, c.function)}))
    return cands


# =============================================================================
# RTOS-02  mutex not released on every exit path
# =============================================================================
TAKE = {"xSemaphoreTake", "xSemaphoreTakeRecursive"}
GIVE = {"xSemaphoreGive", "xSemaphoreGiveRecursive"}


def _creates_mutex(F: Facts, handle: str) -> bool:
    for c in F.calls:
        if c.name in ("xSemaphoreCreateMutex", "xSemaphoreCreateRecursiveMutex"):
            # created by assignment to this handle: look at the source line
            if handle in F.line_text(c.line):
                return True
    return False


def rtos02(F: Facts):
    cands = []
    for fn, f in F.functions.items():
        takes = [c for c in F.calls_in(fn) if c.name in TAKE]
        gives = [c for c in F.calls_in(fn) if c.name in GIVE]
        if not takes:
            continue
        for t in takes:
            handle = t.args[0].lstrip("&") if t.args else ""
            # only mutexes: created with xSemaphoreCreateMutex somewhere, or unknown
            mutex = _creates_mutex(F, handle)
            if not mutex and any(c.name in ("xSemaphoreCreateBinary", "xSemaphoreCreateCounting")
                                 and handle in F.line_text(c.line) for c in F.calls):
                continue
            g_lines = sorted(g.line for g in gives if g.args and g.args[0].lstrip("&") == handle)
            if not g_lines:
                cands.append(Candidate("RTOS-02", t.line, fn, "take-without-give",
                                       f"mutex '{handle}' taken in {fn} but never given in the same function",
                                       [_ev(t.line, f"take: {t.text}")], {"mutex_confirmed": mutex}))
                continue
            # find exits (return / goto) after the take
            exits = []
            stack = [f.node]
            while stack:
                n = stack.pop()
                stack.extend(n.children)
                if n.type in ("return_statement", "goto_statement") and n.start_point[0] + 1 > t.line:
                    exits.append(n)
            labels = {}
            stack = [f.node]
            while stack:
                n = stack.pop()
                stack.extend(n.children)
                if n.type == "labeled_statement":
                    lab = n.child_by_field_name("label")
                    labels[lab.text.decode()] = n.start_point[0] + 1
            for e in sorted(exits, key=lambda n: n.start_point):
                ln = e.start_point[0] + 1
                if e.type == "goto_statement":
                    target = e.child_by_field_name("label").text.decode()
                    tl = labels.get(target)
                    if tl and any(gl >= tl for gl in g_lines):
                        continue          # jumps to a label that gives the mutex
                    kind = f"goto {target}"
                else:
                    kind = "return"
                    # a return that sits in the take's own failure branch holds nothing
                    if _in_failed_take_branch(e, t):
                        continue
                if any(t.line < gl < ln for gl in g_lines):
                    continue              # a give lies between take and this exit
                cands.append(Candidate("RTOS-02", ln, fn, "exit-without-give",
                                       f"{kind} at line {ln} after taking '{handle}' (line {t.line}) "
                                       f"with no give on the way out",
                                       [_ev(t.line, f"take: {t.text}"),
                                        _ev(ln, f"exit: {e.text.decode().strip()}"),
                                        _ev(g_lines[0], f"first give is at line {g_lines[0]}")],
                                       {"mutex_confirmed": mutex}, [t.line]))
    return cands


def _in_failed_take_branch(ret, take: "Call") -> bool:
    n = ret.parent
    while n is not None:
        if n.type == "if_statement":
            cond = n.child_by_field_name("condition")
            ctext = cond.text.decode() if cond is not None else ""
            if take.name in ctext:
                failing = bool(re.search(r"!=\s*pdTRUE|!=\s*pdPASS|==\s*pdFALSE|==\s*pdFAIL|!\s*xSemaphore", ctext))
                cons = n.child_by_field_name("consequence")
                in_cons = cons is not None and cons.start_byte <= ret.start_byte < cons.end_byte
                if failing and in_cons:
                    return True
        n = n.parent
    return False


# =============================================================================
# RTOS-03  FromISR call from an ISR more urgent than the allowed priority
# =============================================================================
def priorities(F: Facts):
    """[(irq_name, preempt_priority|None, line, raw_text)] for HAL_NVIC_SetPriority calls."""
    out = []
    for c in F.calls:
        if c.name in ("HAL_NVIC_SetPriority", "NVIC_SetPriority") and len(c.args) >= 2:
            irq = c.args[0].strip()
            pre = F.eval_int(c.args[1], c.function) if c.name == "HAL_NVIC_SetPriority" \
                else F.eval_int(c.args[1], c.function)
            out.append((irq, pre, c.line, c.text))
    return out


def irq_handler_name(irq: str) -> str:
    return re.sub(r"_IRQn$", "_IRQHandler", irq)


def rtos03(F: Facts):
    cands = []
    for irq, pre, line, text in priorities(F):
        if pre is None or pre >= MAX_SYSCALL_PRIO:
            continue
        handler = irq_handler_name(irq)
        scope = set()
        if handler in F.functions:
            scope |= F.reach_from(handler)
            for cb in F.handler_callbacks(handler):
                scope |= F.reach_from(cb)
        # EXTI lines shared between handlers: also accept the EXTI callback when the handler is an EXTI one
        for fn in scope:
            for c in F.calls_in(fn):
                if c.name.endswith("FromISR") or c.name == "portYIELD_FROM_ISR":
                    if c.name == "portYIELD_FROM_ISR":
                        continue
                    cands.append(Candidate(
                        "RTOS-03", c.line, fn, "fromisr-above-max-syscall-priority",
                        f"{irq} has priority {pre} (< {MAX_SYSCALL_PRIO}) and its handler path calls '{c.name}'",
                        [_ev(line, f"priority set: {text} (resolves to preempt priority {pre})"),
                         _ev(c.line, f"call: {c.text}"),
                         _ev(1, f"configLIBRARY_MAX_SYSCALL_INTERRUPT_PRIORITY = {MAX_SYSCALL_PRIO}")],
                        {"priority_given_via_macro": not re.search(r"SetPriority\(\s*\w+\s*,\s*\d+U?\s*,", text)},
                        [line]))
    return cands


# =============================================================================
# PER-01  peripheral used without clock enable
# =============================================================================
INSTANCE_RE = re.compile(r"\.Instance\s*=\s*(\w+)")
PERIPH_RE = re.compile(r"^(USART|UART|SPI|I2C|TIM|ADC|DMA|CAN|SDIO|RTC)(\d*)$")
CLK_RE = re.compile(r"__HAL_RCC_(\w+?)_CLK_ENABLE$")
INIT_FOR = {"UART": "HAL_UART_Init", "USART": "HAL_UART_Init", "SPI": "HAL_SPI_Init",
            "I2C": "HAL_I2C_Init", "ADC": "HAL_ADC_Init", "TIM": None}


def resolve_port(F: Facts, expr: str):
    e = F.expand(expr.strip())
    m = re.search(r"\bGPIO([A-K])\b", e)
    return m.group(1) if m else None


def clock_enables(F: Facts):
    """name (e.g. 'GPIOA', 'USART2') -> list of (line, function)"""
    out = {}
    for c in F.calls:
        m = CLK_RE.match(c.name)
        if m:
            out.setdefault(m.group(1), []).append((c.line, c.function))
    return out


def per01(F: Facts):
    cands = []
    clocks = clock_enables(F)

    def check(periph, use_line, use_func, label):
        # an enable inside a *MspInit counts, anywhere in file
        en = clocks.get(periph, [])
        if not en:
            cands.append(Candidate("PER-01", use_line, use_func, "no-clock-enable",
                                   f"{label}: no __HAL_RCC_{periph}_CLK_ENABLE() anywhere in the file",
                                   [_ev(use_line, f"{label} at line {use_line}"),
                                    _ev(1, f"calls to __HAL_RCC_*_CLK_ENABLE in file: {sorted(clocks)}")], {}))
            return
        # enable after first use in straight-line code of the same function
        same = [ln for ln, fn in en if fn == use_func]
        if same and all(ln > use_line for ln in same) and not any(fn != use_func for _, fn in en):
            cands.append(Candidate("PER-01", use_line, use_func, "enable-after-use",
                                   f"{label}: clock enabled at line {min(same)} after first use at line {use_line}",
                                   [_ev(use_line, f"first use: {label}"),
                                    _ev(min(same), f"__HAL_RCC_{periph}_CLK_ENABLE() comes later")], {}))

    # GPIO ports touched by Init / Write / Toggle / Read
    first_gpio = {}
    for c in F.calls:
        if c.name in ("HAL_GPIO_Init", "HAL_GPIO_WritePin", "HAL_GPIO_TogglePin",
                      "HAL_GPIO_ReadPin", "HAL_GPIO_DeInit") and c.args:
            port = resolve_port(F, c.args[0])
            if port and (port not in first_gpio or c.line < first_gpio[port][0]):
                first_gpio[port] = (c.line, c.function, c.name)
    for port, (ln, fn, nm) in first_gpio.items():
        check(f"GPIO{port}", ln, fn, f"GPIO{port} used via {nm}")

    # peripherals by `.Instance = X`
    for fn, f in F.functions.items():
        body = F.snippet(f.start, f.end)
        for i, line in enumerate(F.lines[f.start - 1:f.end], start=f.start):
            m = INSTANCE_RE.search(line)
            if not m:
                continue
            inst = m.group(1)
            pm = PERIPH_RE.match(inst)
            if not pm:
                continue
            kind = pm.group(1)
            # first HAL_xxx_Init for this handle (or this kind) at/after the Instance line in this function
            hname = line.split(".Instance")[0].strip()
            init_names = {INIT_FOR.get(kind)} if INIT_FOR.get(kind) else {"HAL_TIM_Base_Init", "HAL_TIM_PWM_Init",
                                                                          "HAL_TIM_IC_Init", "HAL_TIM_OC_Init"}
            init_calls = [c for c in F.calls_in(fn) if c.name in init_names and c.line >= i]
            use = init_calls[0].line if init_calls else i
            check(inst, use if init_calls else i, fn, f"{inst} initialized (handle {hname})")
            cands[-1:] and None
    # alternates: the .Instance line for each PER-01 candidate (SPEC: alternate)
    for cnd in cands:
        for i, line in enumerate(F.lines, start=1):
            if INSTANCE_RE.search(line) and cnd.rule and re.search(rf"\b{re.escape(cnd.summary.split(':')[0].split()[0])}\b", line):
                if i != cnd.line:
                    cnd.alt_lines.append(i)
    return cands


# =============================================================================
# PER-02  GPIO configuration contradicts use
# =============================================================================
def gpio_configs(F: Facts):
    """Reconstruct each HAL_GPIO_Init(port,&cfg) configuration from the preceding field writes
    in the same function: [{'line','function','port','pins':set,'mode','alt','pull'}]."""
    out = []
    for c in F.calls:
        if c.name != "HAL_GPIO_Init" or len(c.args) < 2:
            continue
        port = resolve_port(F, c.args[0])
        cfg = c.args[1].lstrip("&").strip()
        pins, mode, alt = None, None, None
        # scan earlier assignments to cfg.* in the same function, nearest wins
        for i in range(c.line - 1, F.functions[c.function].start - 1, -1) if c.function else []:
            text = F.line_text(i)
            m = re.match(rf"\s*{re.escape(cfg)}\.(\w+)\s*=\s*(.+?);", text)
            if not m:
                continue
            field_, val = m.group(1), m.group(2)
            if field_ == "Pin" and pins is None:
                pins = val
            elif field_ == "Mode" and mode is None:
                mode = val
            elif field_ == "Alternate" and alt is None:
                alt = val
            if pins and mode and (alt or (mode and "AF" not in mode)):
                break
        pin_nums = sorted({int(x) for x in re.findall(r"GPIO_PIN_(\d+)", F.expand(pins or ""))})
        out.append(dict(line=c.line, function=c.function, port=port, pins=pin_nums,
                        mode=F.expand(mode or "").strip("() "), alt=F.expand(alt or "").strip("() "),
                        raw_mode=mode, raw_alt=alt))
    return out


def per02(F: Facts):
    cands = []
    cfgs = gpio_configs(F)
    used_periph = set()
    for f in F.functions.values():
        for line in F.lines[f.start - 1:f.end]:
            m = INSTANCE_RE.search(line)
            if m:
                used_periph.add(m.group(1))

    # (a) write/toggle on a pin configured input or analog (static view over whole file)
    modes_by_pin = {}
    for cfg in cfgs:
        for p in cfg["pins"]:
            modes_by_pin.setdefault((cfg["port"], p), []).append(cfg)
    for c in F.calls:
        if c.name in ("HAL_GPIO_WritePin", "HAL_GPIO_TogglePin") and len(c.args) >= 2:
            port = resolve_port(F, c.args[0])
            pins = sorted({int(x) for x in re.findall(r"GPIO_PIN_(\d+)", F.expand(c.args[1]))})
            for p in pins:
                confs = modes_by_pin.get((port, p), [])
                if not confs:
                    continue
                bad = [x for x in confs if "ANALOG" in x["mode"] or "INPUT" in x["mode"]]
                good = [x for x in confs if "OUTPUT" in x["mode"]]
                if bad:
                    runtime_switch = bool(good)
                    cands.append(Candidate(
                        "PER-02", c.line, c.function, "write-to-input-or-analog-pin",
                        f"P{port}{p} is configured {bad[0]['mode']} (line {bad[0]['line']}) but written by {c.name}",
                        [_ev(bad[0]["line"], f"HAL_GPIO_Init config: mode={bad[0]['mode']} pins={bad[0]['pins']}"),
                         _ev(c.line, f"{c.name} on P{port}{p}: {c.text}")],
                        {"pin_also_configured_output_elsewhere": runtime_switch},
                        sorted({x["line"] for x in bad} | {bad[0]["line"] - 1 if False else bad[0]["line"]})))
    # (b) peripheral signal pins must be AF, and the AF number must belong to that pin
    af_ports = {}
    for cfg in cfgs:
        if "AF_" in cfg["mode"]:
            for p in cfg["pins"]:
                sig = AF_TABLE.get((cfg["port"], p), {}).get(int((re.search(r"AF(\d+)_", cfg["alt"] or "") or [0, 0])[1]), "")
                m = re.match(r"([A-Z]+\d*)_", sig)
                if m:
                    af_ports.setdefault(m.group(1), set()).add(cfg["port"])
    for cfg in cfgs:
        for p in cfg["pins"]:
            key = (cfg["port"], p)
            m_af = re.search(r"GPIO_AF(\d+)_(\w+)", cfg["alt"] or "")
            if "AF_" in cfg["mode"] or cfg["mode"].endswith("AF_PP") or "AF_OD" in cfg["mode"]:
                if m_af and key in AF_TABLE:
                    afn = int(m_af.group(1))
                    valid = AF_TABLE[key]
                    if afn not in valid:
                        cands.append(Candidate(
                            "PER-02", cfg["line"], cfg["function"], "af-not-valid-for-pin",
                            f"P{cfg['port']}{p} configured with AF{afn} ({m_af.group(2)}), but that pin offers "
                            f"{ {k: v for k, v in sorted(valid.items())} }",
                            [_ev(cfg["line"], f"HAL_GPIO_Init: mode={cfg['mode']} alternate={cfg['alt']}"),
                             _ev(1, f"pin map for P{cfg['port']}{p}: {valid}")], {},
                            [l for l in range(cfg["line"] - 3, cfg["line"] + 1)]))
                    else:
                        periph = valid[afn]
                        want = m_af.group(2)
                        if not periph.startswith(want.split("_")[0]) and not want.startswith(periph.split("_")[0]):
                            cands.append(Candidate(
                                "PER-02", cfg["line"], cfg["function"], "af-belongs-to-other-peripheral",
                                f"P{cfg['port']}{p}: AF{afn} is {periph} on this pin, but macro names {want}",
                                [_ev(cfg["line"], f"alternate={cfg['alt']}"),
                                 _ev(1, f"pin map: AF{afn} -> {periph}")], {}))
            else:
                # not AF: is this pin a data/clock signal of a peripheral the file uses?
                if key in AF_TABLE:
                    for afn, sig in AF_TABLE[key].items():
                        base = re.match(r"([A-Z]+\d*)_(SCK|MISO|MOSI|SCL|SDA|TX|RX)$", sig)
                        if not base or base.group(1) not in used_periph:
                            continue
                        periph = base.group(1)
                        if periph[:3] not in ("SPI", "I2C", "USA", "UAR"):
                            continue
                        # skip if this peripheral's pins are AF-configured on a different port
                        if af_ports.get(periph) and cfg["port"] not in af_ports[periph]:
                            continue
                        cands.append(Candidate(
                            "PER-02", cfg["line"], cfg["function"], "signal-pin-not-af",
                            f"P{cfg['port']}{p} is {sig} of {periph} (used in this file) but configured "
                            f"'{cfg['mode']}', not an alternate-function mode",
                            [_ev(cfg["line"], f"HAL_GPIO_Init: mode={cfg['mode']} pins={cfg['pins']}"),
                             _ev(1, f"pin map: AF{afn} -> {sig}; file initializes {periph}")],
                            {"pin_may_be_gpio_by_design": True},
                            [l for l in range(cfg["line"] - 4, cfg["line"] + 1)]))
                        break
    # dedupe
    seen, out = set(), []
    for c in cands:
        k = (c.line, c.rule, c.summary)
        if k not in seen:
            seen.add(k)
            out.append(c)
    return out


# =============================================================================
# MEM-01  fixed-size buffer overflow
# =============================================================================
COPY_FUNCS = {"memcpy": (0, 2), "memmove": (0, 2), "memset": (0, 2), "strncpy": (0, 2),
              "strncat": (0, 2), "HAL_UART_Receive": (1, 2)}
UNBOUNDED = {"strcpy", "strcat", "sprintf", "gets"}


def mem01(F: Facts):
    cands = []
    # (1) constant-size copy > destination, (2) unbounded string copies
    for c in F.calls:
        if c.name in COPY_FUNCS and len(c.args) >= 3:
            di, si = COPY_FUNCS[c.name]
            dest = re.sub(r"^&", "", c.args[di]).split("[")[0].strip()
            info = F.array_info(dest, c.function)
            n = F.eval_int(c.args[si], c.function)
            if info and n is not None and n > info[0] * info[1]:
                cands.append(Candidate(
                    "MEM-01", c.line, c.function, "const-copy-exceeds-buffer",
                    f"{c.name} writes {n} bytes into '{dest}' which holds {info[0]*info[1]}",
                    [_ev(c.line, f"call: {c.text}"),
                     _ev(F.decl_line(c.function, dest), f"'{dest}' is {info[0]} element(s) of {info[1]} byte(s)")], {}))
        if c.name in UNBOUNDED and c.args:
            dest = re.sub(r"^&", "", c.args[0]).split("[")[0].strip()
            info = F.array_info(dest, c.function)
            if info:
                cands.append(Candidate(
                    "MEM-01", c.line, c.function, "unbounded-string-copy",
                    f"{c.name} into fixed buffer '{dest}' ({info[0]*info[1]} bytes) with no length limit",
                    [_ev(c.line, f"call: {c.text}")], {"source_is_external": True}))
    # (3) subscripts on fixed arrays with non-constant index, and (4) off-by-one loops
    for fn, f in F.functions.items():
        body = f.node.child_by_field_name("body")
        stack = [body]
        while stack:
            n = stack.pop()
            stack.extend(n.children)
            if n.type == "subscript_expression":
                arg = n.child_by_field_name("argument")
                idx = n.child_by_field_name("indices") or (n.children[2] if len(n.children) > 2 else None)
                if arg is None or arg.type != "identifier" or idx is None:
                    continue
                name = arg.text.decode()
                info = F.array_info(name, fn)
                if not info:
                    continue
                itext = idx.text.decode().strip()
                const = F.eval_int(itext, fn)
                ln = n.start_point[0] + 1
                is_write = _is_write_target(n)
                if const is not None:
                    if const >= info[0] or const < 0:
                        cands.append(Candidate("MEM-01", ln, fn, "const-index-out-of-range",
                                               f"'{name}[{itext}]' index {const} is outside 0..{info[0]-1}",
                                               [_ev(ln, f"access: {n.text.decode()}")], {"is_write": is_write}))
                    continue
                if not _index_guarded(F, fn, itext, info[0], ln):
                    cands.append(Candidate(
                        "MEM-01", ln, fn, "unguarded-index",
                        f"'{name}[{itext}]' (array has {info[0]} elements): no bound check on the index found "
                        f"before line {ln}",
                        [_ev(ln, f"access: {n.text.decode()}")],
                        {"is_write": is_write, "array_size": info[0]}))
    return cands


def _is_write_target(n) -> bool:
    p = n.parent
    return p is not None and p.type == "assignment_expression" and p.child_by_field_name("left") == n


def _index_guarded(F: Facts, fn: str, itext: str, size: int, upto_line: int) -> bool:
    """True if some condition before `upto_line` bounds the identifier(s) in the index,
    or the index is a for-loop variable with a bound <= size."""
    ids = set(re.findall(r"[A-Za-z_]\w*", itext))
    ids -= {"uint8_t", "uint16_t", "uint32_t", "int"}
    f = F.functions[fn]
    # for-loop variable: check the loop bound
    stack = [f.node]
    while stack:
        n = stack.pop()
        stack.extend(n.children)
        if n.type == "for_statement":
            cond = n.child_by_field_name("condition")
            if cond is None:
                continue
            start, end = n.start_point[0] + 1, n.end_point[0] + 1
            if not (start <= upto_line <= end):
                continue
            ctext = cond.text.decode()
            m = re.match(r"\s*(\w+)\s*(<=|<)\s*(.+)$", ctext)
            if m and m.group(1) in ids:
                bound = F.eval_int(m.group(3), fn)
                if bound is not None:
                    top = bound if m.group(2) == "<" else bound + 1
                    return top <= size
                return True  # non-constant bound: leave it to the judge, not flagged here
    # comparison guard before the access: if/while/ternary condition mentioning the id with a relational op
    for i in range(f.start, upto_line):
        t = F.line_text(i)
        if re.search(r"\b(if|while)\b|\?", t) and any(re.search(rf"\b{re.escape(v)}\b", t) for v in ids) \
                and re.search(r"[<>]=?|!=|==", t):
            return True
    # clamped via modulo / mask / ternary on the same expression
    if re.search(r"%\s*\w+|&\s*(0x[0-9a-fA-F]+|\d+)", itext):
        return True
    return False


# =============================================================================
# MEM-02  stack buffer passed to async HAL transfer
# =============================================================================
def mem02(F: Facts):
    cands = []
    for c in F.calls:
        if not c.name.startswith("HAL_") or not ASYNC_SUFFIX.search(c.name) or not c.function:
            continue
        fn = F.functions[c.function]
        for a in c.args[1:]:
            base = re.sub(r"\(.*?\)", "", a)         # drop casts like (uint8_t *)
            base = re.sub(r"^[\s&*]+", "", base).split("[")[0].strip()
            loc = fn.locals.get(base)
            if loc and not loc["static"] and not loc["pointer"] and loc["type"] != "param" \
                    and (loc["array"] is not None):
                waits = _waits_for_completion(F, c)
                cands.append(Candidate(
                    "MEM-02", c.line, c.function, "stack-buffer-to-async-hal",
                    f"local array '{base}' (declared line {loc['line']}) passed to {c.name}; "
                    f"function may return before the transfer completes",
                    [_ev(loc["line"], f"'{base}' is a non-static local array"),
                     _ev(c.line, f"call: {c.text}")],
                    {"function_waits_for_completion": waits["waits"],
                     "wait_evidence": waits["evidence"],
                     "uses_HAL_Delay_only": waits["delay_only"]}, [loc["line"]]))
    return cands


def _waits_for_completion(F: Facts, call: "Call"):
    """Look for a loop after the call whose condition reads a global written in ISR context,
    or a semaphore/notification take. HAL_Delay is NOT proof (SPEC)."""
    fn = call.function
    ev, waits, delay_only = [], False, False
    for a in F.accesses:
        if a.function == fn and a.line > call.line and a.in_loop_cond:
            if any(w.var == a.var and F.is_isr(w.function) and w.kind in ("write", "rmw") for w in F.accesses):
                waits = True
                ev.append(f"line {a.line}: loop waits on '{a.var}', written in ISR context")
    for c in F.calls_in(fn):
        if c.line > call.line and c.name in ("xSemaphoreTake", "ulTaskNotifyTake", "xQueueReceive",
                                               "xEventGroupWaitBits"):
            waits = True
            ev.append(f"line {c.line}: {c.name}")
    if not waits and any(c.name == "HAL_Delay" and c.line > call.line for c in F.calls_in(fn)):
        delay_only = True
    return {"waits": waits, "evidence": ev, "delay_only": delay_only}


# =============================================================================
ALL_RULES = [int01, int02, int03, rtos01, rtos02, rtos03, per01, per02, mem01, mem02]


def all_candidates(F: Facts):
    out = []
    for r in ALL_RULES:
        out.extend(r(F))
    out.sort(key=lambda c: (c.line, c.bug_type))
    return out
