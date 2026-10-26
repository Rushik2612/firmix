"""
facts.py -- deterministic fact extraction from one STM32 C file (tree-sitter).

No LLM here. Everything in this module is computed from the syntax tree, so every
fact has an exact line number and can be re-checked by a human with a text editor.

Public entry point:  Facts(path_or_source)  ->  object with .functions, .calls,
.globals, .macros, .isr_context, .accesses, ... (all plain data, JSON-friendly).
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

import tree_sitter_c as _tsc
from tree_sitter import Language, Parser

_LANG = Language(_tsc.language())
_PARSER = Parser(_LANG)

# ---------------------------------------------------------------------------
# small knowledge tables (STM32F4 / FreeRTOS / Cortex-M facts, not benchmark-specific)
# ---------------------------------------------------------------------------
ELEM_SIZE = {
    "uint8_t": 1, "int8_t": 1, "char": 1, "unsigned char": 1, "signed char": 1,
    "uint16_t": 2, "int16_t": 2, "short": 2, "unsigned short": 2,
    "uint32_t": 4, "int32_t": 4, "int": 4, "unsigned": 4, "unsigned int": 4,
    "long": 4, "unsigned long": 4, "float": 4,
    "uint64_t": 8, "int64_t": 8, "double": 8, "long long": 8, "unsigned long long": 8,
}
RTOS_HANDLE_TYPES = {
    "SemaphoreHandle_t", "QueueHandle_t", "TaskHandle_t", "TimerHandle_t",
    "EventGroupHandle_t", "StreamBufferHandle_t", "MessageBufferHandle_t",
    "QueueSetHandle_t",
}
CRIT_ENTER = {"__disable_irq", "taskENTER_CRITICAL", "portENTER_CRITICAL",
              "vPortEnterCritical", "taskENTER_CRITICAL_FROM_ISR"}
CRIT_EXIT = {"__enable_irq", "taskEXIT_CRITICAL", "portEXIT_CRITICAL",
             "vPortExitCritical", "taskEXIT_CRITICAL_FROM_ISR"}

# FreeRTOS APIs that have a *FromISR variant (plus the delay calls the SPEC lists).
RTOS_PLAIN_APIS = {
    "xQueueSend", "xQueueSendToBack", "xQueueSendToFront", "xQueueOverwrite",
    "xQueueReceive", "xQueuePeek", "uxQueueMessagesWaiting",
    "xSemaphoreGive", "xSemaphoreTake", "xSemaphoreGiveRecursive", "xSemaphoreTakeRecursive",
    "xTaskNotifyGive", "ulTaskNotifyTake", "xTaskNotify", "xTaskNotifyWait",
    "xTaskNotifyAndQuery", "vTaskNotifyGiveFromISR_",  # placeholder never matches
    "xTaskResumeAll", "vTaskSuspend", "xTaskResume", "xTaskAbortDelay",
    "xEventGroupSetBits", "xEventGroupClearBits", "xEventGroupGetBits",
    "xTimerStart", "xTimerStop", "xTimerReset", "xTimerChangePeriod",
    "xStreamBufferSend", "xStreamBufferReceive", "xMessageBufferSend",
    "vTaskDelay", "vTaskDelayUntil", "xTaskDelayUntil",
}
RTOS_ANY_PREFIXES = ("x", "v", "ul", "ux")  # FreeRTOS naming; used with a known-API test

# INT-03: blocking / non-reentrant calls
BLOCKING_EXACT = {"HAL_Delay", "printf", "sprintf", "snprintf", "vsprintf", "vsnprintf",
                  "puts", "malloc", "calloc", "realloc", "free", "scanf", "fprintf"}
POLLING_HAL = re.compile(
    r"^HAL_(UART|USART|I2C|SPI|ADC|CAN|SD|QSPI|TIM)_?[A-Za-z_]*"
    r"(Transmit|Receive|TransmitReceive|PollForConversion|PollForEvent|Mem_Write|Mem_Read|IsDeviceReady)$")
ASYNC_SUFFIX = re.compile(r"_(IT|DMA)$")

# ---------------------------------------------------------------------------


def _text(node) -> str:
    return node.text.decode("utf-8", "replace") if node is not None else ""


def _line(node) -> int:
    return node.start_point[0] + 1


def _walk(node):
    stack = [node]
    while stack:
        n = stack.pop()
        yield n
        stack.extend(reversed(n.children))


@dataclass
class Call:
    name: str
    line: int
    args: list[str]
    function: str | None       # enclosing function (None = file scope)
    text: str
    node: object = field(repr=False, default=None)


@dataclass
class Function:
    name: str
    start: int
    end: int
    is_static: bool
    params: list[str]
    node: object = field(repr=False, default=None)
    locals: dict = field(default_factory=dict)   # name -> {type, array, static, line}
    callees: set = field(default_factory=set)


@dataclass
class Global:
    name: str
    line: int
    type: str
    volatile: bool
    const: bool
    static: bool
    array: str | None          # size expression text, or None
    pointer: bool
    init_text: str | None


@dataclass
class Access:
    var: str
    line: int
    function: str
    kind: str                  # read | write | rmw | address
    in_loop_cond: bool
    in_critical: bool
    text: str                  # source line text


class Facts:
    def __init__(self, source):
        if isinstance(source, (str, Path)) and Path(str(source)).exists():
            self.path = str(source)
            data = Path(source).read_bytes()
        else:
            self.path = "<memory>"
            data = source if isinstance(source, bytes) else str(source).encode()
        self.src = data
        self.lines = data.decode("utf-8", "replace").splitlines()
        self.tree = _PARSER.parse(data)
        self.root = self.tree.root_node

        self.macros: dict[str, str] = {}
        self.macro_lines: dict[str, int] = {}
        self.functions: dict[str, Function] = {}
        self.globals: dict[str, Global] = {}
        self.calls: list[Call] = []
        self.accesses: list[Access] = []
        self.isr_context: dict[str, list[str]] = {}   # function -> call chain from an ISR root
        self.isr_roots: set[str] = set()

        self._collect_macros()
        self._collect_top_level()
        self._collect_calls_and_locals()
        self._compute_isr_context()
        self._collect_accesses()

    # ------------------------------------------------------------------ macros
    def _collect_macros(self):
        for n in _walk(self.root):
            if n.type == "preproc_def":
                name = n.child_by_field_name("name")
                val = n.child_by_field_name("value")
                if name is not None:
                    self.macros[_text(name)] = _text(val).strip() if val is not None else ""
                    self.macro_lines[_text(name)] = _line(n)

    def expand(self, text: str, _depth: int = 0) -> str:
        """Replace known object-like macros by their bodies until a fixpoint."""
        if _depth > 8:
            return text

        def sub(m):
            w = m.group(0)
            return "(" + self.macros[w] + ")" if w in self.macros and self.macros[w] else m.group(0)

        new = re.sub(r"\b[A-Za-z_]\w*\b", sub, text)
        return new if new == text else self.expand(new, _depth + 1)

    def eval_int(self, text: str, func: str | None = None):
        """Evaluate a compile-time integer expression, or return None."""
        t = self.expand(text.strip())
        # sizeof(x)/sizeof(x[0]) and sizeof(x)
        def sz(m):
            name = m.group(1)
            info = self.array_info(name, func)
            if info is None:
                return m.group(0)
            return str(info[0] * info[1])
        t = re.sub(r"sizeof\s*\(\s*(\w+)\s*\)", sz, t)
        t = re.sub(r"sizeof\s*\(\s*\w+\s*\[\s*0\s*\]\s*\)", "1", t)
        t = re.sub(r"\b(0[xX][0-9a-fA-F]+|\d+)[uUlL]+\b", r"\1", t)
        t = re.sub(r"\(\s*(?:uint\d+_t|int\d+_t|unsigned|int)\s*\)", "", t)
        if re.search(r"[A-Za-z_]", t):
            return None
        if not re.fullmatch(r"[\d\s+\-*/%()<>|&^x0-9a-fA-F]*", t):
            return None
        try:
            return int(eval(t, {"__builtins__": {}}, {}))   # only digits/operators here
        except Exception:
            return None

    # --------------------------------------------------------------- top level
    def _declarator_name(self, d):
        """Return (name, array_size_text|None, is_pointer, is_function) for a declarator."""
        array, ptr = None, False
        while d is not None:
            if d.type == "identifier":
                return _text(d), array, ptr, False
            if d.type == "function_declarator":
                inner = d.child_by_field_name("declarator")
                nm = _text(inner) if inner is not None and inner.type == "identifier" else None
                return nm, array, ptr, True
            if d.type == "pointer_declarator":
                ptr = True
            if d.type == "array_declarator":
                sz = d.child_by_field_name("size")
                array = _text(sz) if sz is not None else ""
            d = d.child_by_field_name("declarator")
        return None, array, ptr, False

    def _decl_info(self, decl):
        """Parse a `declaration` node into a list of dicts (one per declarator)."""
        quals, storage, tparts = set(), set(), []
        for c in decl.children:
            if c.type == "type_qualifier":
                quals.add(_text(c))
            elif c.type == "storage_class_specifier":
                storage.add(_text(c))
            elif c.type in ("primitive_type", "type_identifier", "sized_type_specifier",
                            "struct_specifier", "enum_specifier", "union_specifier"):
                tparts.append(_text(c))
        out = []
        for c in decl.children:
            if c.type in ("init_declarator", "identifier", "array_declarator", "pointer_declarator",
                          "function_declarator"):
                init = None
                dn = c
                if c.type == "init_declarator":
                    dn = c.child_by_field_name("declarator")
                    v = c.child_by_field_name("value")
                    init = _text(v) if v is not None else None
                name, arr, ptr, is_fn = self._declarator_name(dn)
                if name and not is_fn:
                    out.append(dict(name=name, array=arr, pointer=ptr, init=init,
                                    type=" ".join(tparts), volatile="volatile" in quals,
                                    const="const" in quals, static="static" in storage,
                                    line=_line(c)))
        return out

    def _collect_top_level(self):
        for n in self.root.children:
            if n.type == "declaration":
                for d in self._decl_info(n):
                    self.globals[d["name"]] = Global(
                        d["name"], d["line"], d["type"], d["volatile"], d["const"], d["static"],
                        d["array"], d["pointer"], d["init"])
            elif n.type == "function_definition":
                decl = n.child_by_field_name("declarator")
                name, _, _, _ = self._declarator_name(decl)
                if not name:
                    continue
                is_static = any(c.type == "storage_class_specifier" and _text(c) == "static"
                                for c in n.children)
                params = []
                fd = decl
                while fd is not None and fd.type != "function_declarator":
                    fd = fd.child_by_field_name("declarator")
                if fd is not None:
                    pl = fd.child_by_field_name("parameters")
                    if pl is not None:
                        for p in pl.children:
                            if p.type == "parameter_declaration":
                                pn, _, _, _ = self._declarator_name(p.child_by_field_name("declarator"))
                                if pn:
                                    params.append(pn)
                self.functions[name] = Function(name, _line(n), n.end_point[0] + 1, is_static,
                                                params, n)

    # ------------------------------------------------------------ calls / locals
    def func_at(self, line: int) -> str | None:
        for f in self.functions.values():
            if f.start <= line <= f.end:
                return f.name
        return None

    def _collect_calls_and_locals(self):
        for f in self.functions.values():
            body = f.node.child_by_field_name("body")
            for n in _walk(body):
                if n.type == "declaration":
                    for d in self._decl_info(n):
                        f.locals[d["name"]] = dict(type=d["type"], array=d["array"],
                                                   static=d["static"], line=d["line"],
                                                   pointer=d["pointer"])
                elif n.type == "call_expression":
                    fn = n.child_by_field_name("function")
                    args = n.child_by_field_name("arguments")
                    if fn is not None and fn.type == "identifier":
                        arglist = [_text(a) for a in args.children
                                   if a.type not in ("(", ")", ",")] if args is not None else []
                        c = Call(_text(fn), _line(n), arglist, f.name, _text(n), n)
                        self.calls.append(c)
                        f.callees.add(c.name)
            for p in f.params:
                f.locals.setdefault(p, dict(type="param", array=None, static=False,
                                            line=f.start, pointer=False))

    def array_info(self, name: str, func: str | None):
        """(element_count, element_size) of a fixed array visible as `name`, else None."""
        info = None
        if func and func in self.functions and name in self.functions[func].locals:
            l = self.functions[func].locals[name]
            if l["array"] not in (None, ""):
                info = (l["array"], l["type"])
        elif name in self.globals and self.globals[name].array not in (None, ""):
            g = self.globals[name]
            info = (g.array, g.type)
        if info is None:
            return None
        cnt = self.eval_int(info[0], func)
        if cnt is None:
            return None
        return cnt, ELEM_SIZE.get(info[1], 1)

    # --------------------------------------------------------------- ISR context
    HAL_IRQ_TO_CALLBACK = re.compile(r"^HAL_(?P<p>[A-Za-z0-9]+)(?:_[A-Za-z0-9]+)?_IRQHandler$")

    def _compute_isr_context(self):
        roots = set()
        for name in self.functions:
            if name == "SysTick_Handler" or name.endswith("_IRQHandler"):
                roots.add(name)
            elif re.fullmatch(r"HAL_\w+Callback", name) and "MspInit" not in name \
                    and "MspDeInit" not in name:
                roots.add(name)
        self.isr_roots = roots
        chain: dict[str, list[str]] = {r: [r] for r in roots}
        frontier = list(roots)
        while frontier:
            cur = frontier.pop()
            for callee in sorted(self.functions[cur].callees):
                if callee in self.functions and callee not in chain:
                    chain[callee] = chain[cur] + [callee]
                    frontier.append(callee)
        self.isr_context = chain

    def is_isr(self, func: str | None) -> bool:
        return func in self.isr_context

    def handler_callbacks(self, handler: str) -> set[str]:
        """Callbacks the HAL IRQ handler called from `handler` will run (by HAL naming)."""
        out = set()
        for callee in self.functions[handler].callees if handler in self.functions else []:
            m = re.match(r"^HAL_([A-Za-z0-9]+)_(?:[A-Za-z0-9]+_)?IRQHandler$", callee)
            if not m:
                continue
            periph = m.group(1)
            for fn in self.functions:
                if re.fullmatch(rf"HAL_{periph}_\w*Callback", fn) and "Msp" not in fn:
                    out.add(fn)
                if periph == "GPIO" and fn == "HAL_GPIO_EXTI_Callback":
                    out.add(fn)
        return out

    def reach_from(self, root: str) -> set[str]:
        seen, stack = set(), [root]
        while stack:
            cur = stack.pop()
            if cur in seen or cur not in self.functions:
                continue
            seen.add(cur)
            stack.extend(self.functions[cur].callees)
        return seen

    # ------------------------------------------------------------ critical sections
    def critical_ranges(self, func: str):
        """List of (start_line, end_line) inside __disable_irq/taskENTER_CRITICAL ... pairs."""
        events = sorted((c.line, 1 if c.name in CRIT_ENTER else -1)
                        for c in self.calls
                        if c.function == func and (c.name in CRIT_ENTER or c.name in CRIT_EXIT))
        ranges, start = [], None
        for ln, kind in events:
            if kind == 1 and start is None:
                start = ln
            elif kind == -1 and start is not None:
                ranges.append((start, ln))
                start = None
        if start is not None:
            ranges.append((start, self.functions[func].end))
        return ranges

    # ------------------------------------------------------------------ accesses
    def _in_sizeof(self, n) -> bool:
        p = n.parent
        while p is not None:
            if p.type == "sizeof_expression":
                return True
            p = p.parent
        return False

    def _collect_accesses(self):
        gnames = {g for g, v in self.globals.items()}
        for f in self.functions.values():
            body = f.node.child_by_field_name("body")
            crit = self.critical_ranges(f.name)
            for n in _walk(body):
                if n.type != "identifier":
                    continue
                name = _text(n)
                if name not in gnames or name in f.locals or self._in_sizeof(n):
                    continue
                # skip the callee name of a call and field names
                par = n.parent
                if par.type == "call_expression" and par.child_by_field_name("function") == n:
                    continue
                if par.type == "field_expression" and par.child_by_field_name("field") == n:
                    continue
                # climb an lvalue chain: x.f, x[i], x.f[i]
                top = n
                while top.parent is not None and (
                        (top.parent.type == "field_expression" and top.parent.child_by_field_name("argument") == top)
                        or (top.parent.type == "subscript_expression" and top.parent.child_by_field_name("argument") == top)):
                    top = top.parent
                kind = "read"
                p = top.parent
                if p is not None and p.type == "assignment_expression" and p.child_by_field_name("left") == top:
                    op = _text(p.child_by_field_name("operator")) if p.child_by_field_name("operator") is not None else "="
                    kind = "write" if op == "=" else "rmw"
                elif p is not None and p.type == "update_expression":
                    kind = "rmw"
                elif p is not None and p.type == "pointer_expression" and _text(p).startswith("&"):
                    kind = "address"
                elif p is not None and p.type == "unary_expression" and _text(p).startswith("&"):
                    kind = "address"
                # in a loop condition?
                in_cond = False
                q = n
                while q is not None and q != body:
                    pp = q.parent
                    if pp is not None and pp.type in ("while_statement", "do_statement", "for_statement"):
                        cond = pp.child_by_field_name("condition")
                        if cond is not None and cond.start_byte <= n.start_byte < cond.end_byte:
                            in_cond = True
                    q = pp
                ln = _line(n)
                in_crit = any(a <= ln <= b for a, b in crit)
                txt = self.lines[ln - 1].strip() if ln - 1 < len(self.lines) else ""
                self.accesses.append(Access(name, ln, f.name, kind, in_cond, in_crit, txt))

    # -------------------------------------------------------------------- helpers
    def decl_line(self, func, name: str) -> int:
        if func and func in self.functions and name in self.functions[func].locals:
            return self.functions[func].locals[name]["line"]
        return self.globals[name].line if name in self.globals else 1

    def line_text(self, ln: int) -> str:
        return self.lines[ln - 1].rstrip() if 1 <= ln <= len(self.lines) else ""

    def snippet(self, start: int, end: int) -> str:
        start, end = max(1, start), min(len(self.lines), end)
        return "\n".join(f"{i}: {self.lines[i-1]}" for i in range(start, end + 1))

    def calls_in(self, func: str):
        return [c for c in self.calls if c.function == func]

    def to_summary(self) -> dict:
        return {
            "file": self.path,
            "functions": {n: {"start": f.start, "end": f.end, "static": f.is_static,
                              "isr_chain": self.isr_context.get(n)} for n, f in self.functions.items()},
            "globals": {n: g.__dict__ for n, g in self.globals.items()},
            "macros": self.macros,
        }
