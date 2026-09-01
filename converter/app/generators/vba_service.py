"""VBA module -> Spring service semantic converter (plan §9-11).

Walks the AST produced by `analyzers.vba_ast` and emits Java.  Design rules:

* Procedures become methods on one service class per VBA module (§10),
  named dynamically from the module name (`modMathCumulative` ->
  `MathCumulativeService`).  Nothing is keyed off specific object names.
* `Static` locals become an explicit per-invocation context class (§11):
  callers iterating an ordered row stream create ONE instance and reuse it,
  matching the Access semantics where Static persists across query rows.
* VBA control flow (labels / GoTo / On Error GoTo) compiles to a labelled
  dispatch loop with a signal exception, preserving arbitrary jumps without
  restructuring the source.
* Unconvertible constructs generate ACCESS-MIGRATION markers plus
  MANUAL_REVIEW status, never silent drops (plan §28).
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

from ..analyzers.vba_ast import (
    Assignment, CallStatement, DoLoop, ExitConstruct, ForEach, ForNext,
    GotoStatement, IfBlock, LabelDef, Node, OnError, ProcedureAST,
    RedimStatement, ReturnAssignment, RawStatement, SeqNode, SelectCase,
    SingleLineIf, VarDecl, WithBlock, parse_procedure,
)
from .java_compat import RuntimeUsage


# ------------------------------------------------------------------ naming

def _camel(name: str) -> str:
    name = name.strip()
    # strip VBA array-parameter parens and any stray non-word characters
    name = re.sub(r"[^A-Za-z0-9_]", "", name)
    if not name:
        return "_"
    if re.match(r"^[A-Za-z_]\w*$", name):
        return name[0].lower() + name[1:]
    parts = re.split(r"[\s_\-]+", name)
    joined = "".join(p[:1].lower() + p[1:] for p in parts if p)
    return joined or "_"


def _pascal(name: str) -> str:
    parts = re.split(r"[\s_\-]+", name.strip())
    return "".join(p[:1].upper() + p[1:] for p in parts if p)


def service_class_name(module_name: str) -> str:
    """modFooBar -> FooBarService; derived purely from the source name.

    Digit-leading names (Leszynski conventions like 'Form_001_About_frm')
    get an 'N' prefix so the result is a valid Java identifier.
    """
    stem = module_name
    m = re.match(r"^mod(?=[A-Z])(.+)$", stem)
    if m:
        stem = m.group(1)
    elif re.match(r"^cls(?=[A-Z])(.+)$", stem):
        stem = m.group(1)
    elif re.match(r"^bas_(.+)$", stem):
        stem = m.group(1)
    else:
        stem = re.sub(r"^(Form_|Report_)", "", stem)
    camel = _pascal(stem)
    if camel and camel[0].isdigit():
        camel = "N" + camel
    return camel + "Service"


# ------------------------------------------------------------------ types

JAVA_TYPE_MAP = {
    "STRING": "String",
    "INTEGER": "int",
    "LONG": "long",
    "DOUBLE": "double",
    "SINGLE": "float",
    "BOOLEAN": "boolean",
    "BYTE": "byte",
    "CURRENCY": "java.math.BigDecimal",
    "DATE": "java.time.LocalDateTime",
    "VARIANT": "Object",
    "OBJECT": "Object",
}

_BOXED = {"int": "Integer", "long": "Long", "double": "Double",
          "float": "Float", "boolean": "Boolean", "byte": "Byte"}


def java_type(vba_type: str | None, boxed: bool = False) -> str:
    t = (vba_type or "").strip()
    base = JAVA_TYPE_MAP.get(t.upper())
    if base is None:
        return "Object"
    if boxed:
        return _BOXED.get(base, base)
    return base


# ------------------------------------------------------------------ context

@dataclass
class ProcContext:
    """Scope knowledge used while translating expressions."""
    func_name: str
    params: list[dict] = field(default_factory=list)
    local_types: dict[str, str] = field(default_factory=dict)      # lower -> type
    static_scalars: dict[str, str] = field(default_factory=dict)   # lower -> type
    static_arrays: dict[str, list[str]] = field(default_factory=dict)
    local_arrays: dict[str, list[str]] = field(default_factory=dict)
    return_type: str | None = None
    in_module_funcs: set[str] = field(default_factory=set)
    uses_runtime: bool = False
    uses_query_functions: bool = False
    uses_strings: bool = False
    has_unresolved_calls: bool = False

    def type_of(self, name_lower: str) -> str | None:
        if name_lower in self.static_scalars:
            return self.static_scalars[name_lower]
        if name_lower in self.local_types:
            return self.local_types[name_lower]
        for p in self.params:
            if p["name"].lower() == name_lower:
                return p.get("type")
        return None

    def is_param(self, name_lower: str) -> bool:
        return any(p["name"].lower() == name_lower for p in self.params)


# ------------------------------------------------------------------ expression translation

_FUNC_MAP = {
    "nz": "AccessRuntime.nz",
    "isnull": "AccessRuntime.isNull",
    "isnumeric": "AccessRuntime.isNumeric",
    "iif": "AccessRuntime.iif",
    "cdbl": "AccessRuntime.cDbl",
    "clng": "AccessRuntime.cLng",
    "cint": "AccessRuntime.cInt",
    "cstr": "AccessRuntime.cStr",
    "cbool": "AccessRuntime.cBool",
    "cdate": "AccessRuntime.cDate",
    "cvdate": "AccessRuntime.cDate",
    "int": "AccessRuntime.intFloor",
    "fix": "AccessRuntime.fix",
    "now": "AccessDateFunctions.now",
    "dateadd": "AccessDateFunctions.dateAdd",
    "datediff": "AccessDateFunctions.dateDiff",
    "datepart": "AccessDateFunctions.datePart",
    "year": "AccessDateFunctions.year",
    "month": "AccessDateFunctions.month",
    "day": "AccessDateFunctions.day",
}

_ARITH_NATIVE = {"+": "+", "-": "-", "*": "*", "/": "/"}
_ARITH_RUNTIME = {"+": "add", "-": "sub", "*": "mul", "/": "div",
                  "&": "concat", "\\": "idiv", "Mod": "mod"}


class ExprTranslator:
    """Translates a VBA expression string into a Java expression."""

    def __init__(self, ctx: ProcContext, usage: RuntimeUsage):
        self.ctx = ctx
        self.usage = usage

    # public ---------------------------------------------------------

    def translate(self, expr: str) -> str:
        s = expr.strip()
        if not s:
            return '""'
        # Strip redundant outer parens so operators inside are reachable
        # (VBA authors often wrap sub-expressions: (a = b And c)).
        while s.startswith("(") and s.endswith(")") and \
                self._matching_close(s, 0) == len(s) - 1:
            s = s[1:-1].strip()
            if not s:
                return '""'
        # VBA precedence, lowest first — each split recurses on its sides:
        #   Or -> And -> Not -> comparisons -> & -> +- -> \ Mod -> */
        for word, java_op in (("Or", "||"), ("And", "&&")):
            hit = self._top_word_op(s, word)
            if hit:
                pos, op = hit
                lhs = self.translate(s[:pos])
                rhs = self.translate(s[pos + len(op):])
                return f"({lhs} {java_op} {rhs})"
        if re.match(r"(?i)Not\s+", s):
            inner = re.sub(r"(?i)^Not\s+", "", s)
            return f"!({self.translate(inner)})"
        cmp_at = self._top_comparison(s)
        if cmp_at:
            pos, op = cmp_at
            lhs = self.translate(s[:pos])
            rhs = self.translate(s[pos + len(op):])
            return self._combine_comparison(lhs, rhs, op)
        # Arithmetic splits route possibly-Variant operands through
        # AccessRuntime helpers so Object-typed values always compile.
        ar_at = self._top_arith(s)
        if ar_at:
            pos, op = ar_at
            lhs_raw = s[:pos]
            rhs_raw = s[pos + len(op):]
            lhs = self.translate(lhs_raw)
            rhs = self.translate(rhs_raw)
            return self._combine_arith(lhs, rhs, op,
                                       self._possibly_variant(lhs_raw),
                                       self._possibly_variant(rhs_raw))
        s = self._rewrite_static_refs(s)
        s = self._map_functions(s)
        s = self._fix_literals(s)
        return s

    def split_args(self, inner: str) -> list[str]:
        parts, depth, cur = [], 0, ""
        for ch in inner:
            if ch == "(":
                depth += 1
            elif ch == ")":
                depth -= 1
            if ch == "," and depth == 0:
                parts.append(cur)
                cur = ""
            else:
                cur += ch
        if cur.strip():
            parts.append(cur)
        return parts

    # internals ------------------------------------------------------

    def _known_array(self, lowered: str) -> tuple[str | None, list[str]]:
        """Return ('$state.'|''|None, dims) for array-valued identifiers."""
        if lowered in self.ctx.static_arrays:
            return "$state.", self.ctx.static_arrays[lowered]
        if lowered in self.ctx.local_arrays:
            return "", self.ctx.local_arrays[lowered]
        return None, []

    def _rewrite_static_refs(self, s: str) -> str:
        """Rewrite Static-state scalars/arrays and Err references."""
        out = []
        i = 0
        n = len(s)
        while i < n:
            ch = s[i]
            if ch == '"':
                jm = re.match(r'"(?:[^"]|"")*"', s[i:])
                if jm:
                    out.append(self._vlit(jm.group(0)))
                    i += jm.end()
                    continue
            im = re.match(r"[A-Za-z_]\w*", s[i:])
            if im:
                name = im.group(0)
                low = name.lower()
                j = i + len(name)
                # already qualified / synthetic? ($state.x, $ret, ...)
                prev = s[i - 1] if i > 0 else ""
                if i > 0 and (prev == "." or prev == "$"):
                    out.append(name)
                    i = j
                    continue

                # Err / Erl pseudo-objects
                if low == "err":
                    rest = s[j:]
                    if rest.startswith(".Number"):
                        out.append("$errNum")
                        i = j + len(".Number")
                        continue
                    if rest.startswith(".Description"):
                        out.append("$errDesc")
                        i = j + len(".Description")
                        continue
                    out.append("$errNum /* Err */")
                    i = j
                    continue
                if low == "erl":
                    out.append("0 /* Erl */")
                    i = j
                    continue
                arr_owner, dims = self._known_array(low)
                if arr_owner is not None and j < n and s[j] == "(":
                    depth = 1
                    k = j + 1
                    while k < n and depth:
                        if s[k] == "(":
                            depth += 1
                        elif s[k] == ")":
                            depth -= 1
                        k += 1
                    inner = s[j + 1:k - 1]
                    idx_parts = [self.translate(p.strip())
                                 for p in self.split_args(inner)]
                    lowers = [_parse_dim(d)[1] for d in dims]
                    indexes = ""
                    for pos, ix in enumerate(idx_parts):
                        off = lowers[pos] if pos < len(lowers) else 0
                        indexes += f"[({ix}){' - ' + str(off) if off else ''}]"
                    out.append(f"{arr_owner}{_camel(name)}{indexes}")
                    i = k
                    continue

                if low in self.ctx.static_scalars and \
                        not (j < n and s[j:j + 1] == "("):
                    out.append(f"$state.{_camel(name)}")
                    i = j
                    continue

                out.append(name)
                i = j
                continue
            out.append(ch)
            i += 1
        return "".join(out)

    def _map_functions(self, s: str) -> str:
        out = []
        i = 0
        n = len(s)
        while i < n:
            if s[i] == '"':
                # already Java-escaped by _rewrite_static_refs; verbatim
                jm = re.match(r'"(?:[^"]|"")*"', s[i:])
                if jm:
                    out.append(jm.group(0))
                    i += jm.end()
                    continue
            m = re.match(r"([A-Za-z_]\w*)\s*\(", s[i:])
            if m:
                name = m.group(1)
                low = name.lower()
                j = i + m.end()
                depth = 1
                k = j
                while k < n and depth:
                    if s[k] == "(":
                        depth += 1
                    elif s[k] == ")":
                        depth -= 1
                    k += 1
                inner = s[j:k - 1]
                tail = s[k:]

                special = self._rewrite_string_call(name, inner)
                if special is not None:
                    out.append(special)
                    out.append(self._map_functions(tail))
                    return "".join(out)

                mapped = _FUNC_MAP.get(low)
                if mapped:
                    if low in ("now", "date", "dateadd", "datediff", "datepart",
                               "year", "month", "day"):
                        self.usage.date_functions = True
                    self.ctx.uses_runtime = True
                    args_j = [self.translate(a) for a in self.split_args(inner)]
                    out.append(f"{mapped}({', '.join(args_j)})")
                    out.append(self._map_functions(tail))
                    return "".join(out)

                if low in ("dlookup", "dcount", "dmax", "dmin"):
                    self.ctx.uses_query_functions = True
                    args_j = [self.translate(a) for a in self.split_args(inner)]
                    out.append(f"accessQueryFunctions.{low}"
                               f"({', '.join(args_j)})")
                    out.append(self._map_functions(tail))
                    return "".join(out)

                if low in self.ctx.in_module_funcs:
                    args_j = [self.translate(a) for a in self.split_args(inner)]
                    out.append(f"{_camel(name)}({', '.join(args_j)})")
                    out.append(self._map_functions(tail))
                    return "".join(out)
                # unknown call: keep compiling via the runtime marker and
                # flag the procedure for manual review (plan §28)
                self.ctx.has_unresolved_calls = True
                args_j = [self.translate(a) for a in self.split_args(inner)]
                quoted = '"' + name.replace('"', '') + '"'
                out.append(f"AccessRuntime.unsupported({quoted}"
                           + (", " + ", ".join(args_j) if args_j else "")
                           + ")")
                i = k
                continue
            out.append(s[i])
            i += 1
        return "".join(out)

    def _rewrite_string_call(self, name: str, inner: str) -> str | None:
        low = name.lower()
        args = self.split_args(inner)
        # single-argument math functions -> java.lang.Math on cDbl()
        math1 = {"sqr": "Math.sqrt", "abs": "Math.abs", "sin": "Math.sin",
                 "cos": "Math.cos", "tan": "Math.tan", "atn": "Math.atan",
                 "exp": "Math.exp", "log": "Math.log"}
        if low in math1 and len(args) == 1:
            self.ctx.uses_runtime = True
            return (f"{math1[low]}(AccessRuntime.cDbl("
                    f"{self.translate(args[0])}))")
        if low == "val" and len(args) == 1:
            self.ctx.uses_runtime = True
            return f"AccessRuntime.val({self.translate(args[0])})"
        if low == "left" and len(args) == 2:
            self.ctx.uses_strings = True
            return (f"{self.translate(args[0])}.substring(0, "
                    f"AccessRuntime.cInt({self.translate(args[1])}))")
        if low == "right" and len(args) == 2:
            self.ctx.uses_strings = True
            return (f"AccessStrings.right({self.translate(args[0])}, "
                    f"AccessRuntime.cInt({self.translate(args[1])}))")
        if low == "mid":
            if len(args) == 2:
                self.ctx.uses_strings = True
                return (f"{self.translate(args[0])}.substring("
                        f"AccessRuntime.cInt({self.translate(args[1])}) - 1)")
            if len(args) >= 3:
                self.ctx.uses_strings = True
                return (f"{self.translate(args[0])}.substring("
                        f"AccessRuntime.cInt({self.translate(args[1])}) - 1, "
                        f"AccessRuntime.cInt({self.translate(args[1])}) - 1 + "
                        f"AccessRuntime.cInt({self.translate(args[2])}))")
        if low == "len" and len(args) == 1:
            self.ctx.uses_strings = True
            return f"{self.translate(args[0])}.toString().length()"
        if low == "trim" and len(args) == 1:
            self.ctx.uses_strings = True
            return f"{self.translate(args[0])}.toString().trim()"
        if low == "instr" and len(args) >= 2:
            self.ctx.uses_strings = True
            hay, needle = args[-2], args[-1]
            return f"({hay}.toString().indexOf({needle}) + 1)"
        return None

    def _concat_amp(self, s: str) -> str:
        parts = []
        i = 0
        n = len(s)
        while i < n:
            if s[i] == '"':
                jm = re.match(r'"(?:[^"]|"")*"', s[i:])
                if jm:
                    parts.append(jm.group(0))
                    i += jm.end()
                    continue
            if s[i] == "&":
                if s[i + 1:i + 2] == "=":
                    parts.append("&=")
                    i += 2
                    continue
                parts.append("+")
                i += 1
                continue
            parts.append(s[i])
            i += 1
        return "".join(parts)

    _LIT_RE = re.compile(r"\b(True|False|Null|Nothing|Empty)\b", re.I)

    @staticmethod
    def _vlit(raw: str) -> str:
        """Convert a raw VBA string literal (with its quotes) to Java."""
        inner = raw[1:-1]
        # VBA doubles quotes for escaping: "" -> literal quote
        inner = inner.replace('""', '"')
        inner = inner.replace("\\", "\\\\").replace('"', '\\"')
        return f'"{inner}"'

    def _fix_literals(self, s: str) -> str:
        out = []
        i = 0
        n = len(s)
        while i < n:
            # date/time literal: #m/d/yyyy[ h:mm[:ss] [AM|PM]]# (date optional)
            tm = re.match(r"#\s*(\d{1,2}):(\d{2})(?::(\d{2}))?\s*([AaPp])?[Mm]?\s*#", s[i:])
            if tm:
                hh = int(tm.group(1))
                mi = int(tm.group(2))
                ss = int(tm.group(3) or 0)
                pm = (tm.group(4) or "").lower() == "p"
                am = (tm.group(4) or "").lower() == "a"
                if pm and hh < 12:
                    hh += 12
                if am and hh == 12:
                    hh = 0
                out.append(f"java.time.LocalTime.of({hh}, {mi}, {ss})")
                i += tm.end()
                continue
            dm = re.match(r"#\s*(\d{1,2})/(\d{1,2})/(\d{2,4})"
                          r"(?:\s+(\d{1,2}):(\d{2})(?::(\d{2}))?"
                          r"\s*([AaPp])?[Mm]?)?\s*#", s[i:])
            if dm:
                mon, day = int(dm.group(1)), int(dm.group(2))
                yr = int(dm.group(3))
                if yr < 100:
                    yr += 2000
                hh = int(dm.group(4) or 0)
                mi = int(dm.group(5) or 0)
                ss = int(dm.group(6) or 0)
                pm = (dm.group(7) or "").lower() == "p"
                if pm and hh < 12:
                    hh += 12
                out.append(f"java.time.LocalDateTime.of({yr}, {mon}, {day}, "
                           f"{hh}, {mi}, {ss})")
                i += dm.end()
                continue
            if s[i] == '"':
                # string literals already escaped upstream; verbatim
                jm = re.match(r'"(?:[^"]|"")*"', s[i:])
                if jm:
                    out.append(jm.group(0))
                    i += jm.end()
                    continue
            # numeric literal with VBA type suffix: 1# 2& 3! 4@ 5% 6$
            nm = re.match(r"(\d+(?:\.\d+)?(?:[eE][+-]?\d+)?)"
                          r"(?=[#&!@$%])([#&!@$%])", s[i:])
            if nm:
                out.append(nm.group(1))
                i += nm.end()
                continue
            wm = self._LIT_RE.match(s, i)
            if wm:
                word = wm.group(1).lower()
                out.append({"true": "true", "false": "false",
                            "null": "null", "nothing": "null",
                            "empty": '""'}[word])
                i += wm.end()
                continue
            out.append(s[i])
            i += 1
        return "".join(out)

    _WORD_OPS = {
        "or": "Or", "and": "And", "mod": "Mod",
    }

    @staticmethod
    def _matching_close(s: str, open_pos: int) -> int:
        depth = 0
        i = open_pos
        n = len(s)
        while i < n:
            ch = s[i]
            if ch == '"':
                jm = re.match(r'"(?:[^"]|"")*"', s[i:])
                if jm:
                    i += jm.end()
                    continue
            if ch == "(":
                depth += 1
            elif ch == ")":
                depth -= 1
                if depth == 0:
                    return i
            i += 1
        return -1

    def _top_word_op(self, s: str, word: str) -> tuple[int, str] | None:
        """Top-level VBA word operator (And/Or/Mod) outside strings/parens."""
        depth = 0
        i = 0
        n = len(s)
        wlen = len(word)
        while i < n:
            ch = s[i]
            if ch == '"':
                jm = re.match(r'"(?:[^"]|"")*"', s[i:])
                if jm:
                    i += jm.end()
                    continue
            if ch == "(":
                depth += 1
            elif ch == ")":
                depth -= 1
            elif depth == 0:
                seg = s[i:i + wlen + 1]
                if re.match(rf"(?i){word}\b", seg) and (
                        i == 0 or not re.match(r"\w", s[i - 1])):
                    return (i, s[i:i + wlen])
            i += 1
        return None

    def _top_arith(self, s: str) -> tuple[int, str] | None:
        """Find the lowest-precedence top-level arithmetic operator.

        Passes: & (concat) -> + - -> \\ Mod -> * /   giving VBA precedence
        when combined with recursive translation of each side.
        """
        for kind in ("&", "+-", "intdiv", "*/"):
            depth = 0
            i = 0
            n = len(s)
            while i < n:
                ch = s[i]
                if ch == '"':
                    jm = re.match(r'"(?:[^"]|"")*"', s[i:])
                    if jm:
                        i += jm.end()
                        continue
                if ch == "(":
                    depth += 1
                elif ch == ")":
                    depth -= 1
                elif depth == 0:
                    if kind == "intdiv":
                        if ch == "\\" and s[i + 1:i + 2] != "\\":
                            return (i, "\\")
                        hm = re.match(r"(?i)Mod\b", s[i:])
                        if hm and not re.match(r"\w", s[i - 1] if i else ""):
                            return (i, hm.group(0))
                    elif ch in ("&", "+-"):
                        if ch == "&" and s[i + 1:i + 2] == "=":
                            i += 2
                            continue
                        if ch in "+-":
                            prev = s[:i].rstrip()[-1:] if s[:i].rstrip() else ""
                            if prev == "" or prev in "+-*/(<>=,&\\":
                                i += 1
                                continue
                        if ch in kind:
                            return (i, ch)
                    elif ch in "*/" and ch in kind:
                        return (i, ch)
                i += 1
        return None

    def _combine_arith(self, lhs: str, rhs: str, op: str,
                       l_variant: bool, r_variant: bool) -> str:
        self.ctx.uses_runtime = True
        if op == "&":
            if l_variant or r_variant:
                return f"AccessRuntime.concat({lhs}, {rhs})"
            return f"({lhs} + {rhs})"
        # integer division and Mod always route through the runtime (VBA
        # rounds operands before dividing; Java operators don't)
        if op in ("\\", "Mod"):
            return f"AccessRuntime.{_ARITH_RUNTIME[op]}({lhs}, {rhs})"
        if l_variant or r_variant:
            return f"AccessRuntime.{_ARITH_RUNTIME[op]}({lhs}, {rhs})"
        return f"({lhs} {_ARITH_NATIVE[op]} {rhs})"

    def _possibly_variant(self, s: str) -> bool:
        """Heuristic: does this raw operand reference non-primitive data?"""
        t = s.strip()
        if not t:
            return False
        if re.fullmatch(r'[+-]?\d+(\.\d+)?', t):
            return False
        if t.startswith('"') and t.endswith('"') and len(t) >= 2:
            return False
        stripped = re.sub(r'"(?:[^"]|"")*"', '""', t)
        idents = re.findall(r"[A-Za-z_]\w*", stripped)
        if not idents:
            return False
        for ident in idents:
            low = ident.lower()
            if low in ("true", "false", "null", "nothing", "empty", "me"):
                continue
            if low in ("isnull", "eq", "compare", "cdbl", "cint", "clng",
                       "cdbo", "cstr", "cbool"):
                continue
            # array element read is always Object-typed
            if re.search(rf"\b{re.escape(ident)}\s*\(", stripped) and (
                    low in self.ctx.static_arrays
                    or low in self.ctx.local_arrays):
                return True
            if low in ("nz", "iif"):
                return True
            vtype = self.ctx.type_of(low)
            if not vtype:
                return True          # undeclared/param without type -> Variant
            u = vtype.upper()
            if u in ("VARIANT", "OBJECT", "STRING", "DATE"):
                return True
        return False

    def _top_comparison(self, s: str) -> tuple[int, str] | None:
        depth = 0
        i = 0
        while i < len(s):
            ch = s[i]
            if ch == '"':
                jm = re.match(r'"(?:[^"]|"")*"', s[i:])
                if jm:
                    i += jm.end()
                    continue
            if ch == "(":
                depth += 1
            elif ch == ")":
                depth -= 1
            elif depth == 0 and ch in "<>=!":
                two = s[i:i + 2]
                if two in ("<=", ">=", "<>", "=="):
                    return (i, "<>" if two == "<>" else two.replace("==", "="))
                if ch in "<>=":
                    return (i, ch)
                break
            i += 1
        return None

    def _combine_comparison(self, lhs: str, rhs: str, op: str) -> str:
        self.ctx.uses_runtime = True
        if op in ("<", ">"):
            sym = "<" if op == "<" else ">"
            return f"(AccessRuntime.compare({lhs}, {rhs}) {sym} 0)"
        if op == ">=":
            return f"(AccessRuntime.compare({lhs}, {rhs}) >= 0)"
        if op == "<=":
            return f"(AccessRuntime.compare({lhs}, {rhs}) <= 0)"
        if op == "=":
            return f"AccessRuntime.eq({lhs}, {rhs})"
        if op == "<>":
            return f"(!AccessRuntime.eq({lhs}, {rhs}))"
        return f"({lhs}) {op} ({rhs})"


# ------------------------------------------------------------------ dimensions

def _parse_dim(spec: str) -> tuple[int, int]:
    """Return (java_size, vba_lower_bound) for one array dimension spec.

    'a To b' -> size b-a+1 (indices shifted); 'n' -> upper bound with
    lower bound 0 -> size n+1.
    """
    m = re.match(r"^(-?\d+)\s+[Tt]o\s+(-?\d+)$", spec.strip())
    if m:
        lo, hi = int(m.group(1)), int(m.group(2))
        return (max(hi - lo + 1, 0), lo)
    return (int(spec.strip()) + 1, 0)


def _build_multiarray_init(sizes: list[int]) -> str:
    return "new Object[" + "][".join(str(max(s, 0)) for s in sizes) + "]"


# ------------------------------------------------------------------ emitter

class JavaSemanticEmitter:
    """Emits Java for one procedure AST."""

    def __init__(self, ast: ProcedureAST, usage: RuntimeUsage,
                 module_func_names: set[str]):
        self.ast = ast
        self.usage = usage
        self.return_var = "$ret"
        self.lines_for_state: list[str] = []
        ctx = ProcContext(func_name=ast.name, params=ast.params,
                          return_type=ast.return_type,
                          in_module_funcs=module_func_names)
        for node in ast.body:
            if isinstance(node, VarDecl):
                for spec in node.names:
                    lname = spec["name"].lower()
                    if spec.get("array_dims"):
                        target = (ctx.static_arrays if node.static
                                  else ctx.local_arrays)
                        target[lname] = spec["array_dims"]
                    else:
                        if node.static:
                            ctx.static_scalars[lname] = spec.get("type") or "Variant"
                        else:
                            ctx.local_types[lname] = spec.get("type") or "Variant"
        self.ctx = ctx
        self.translator = ExprTranslator(ctx, usage)
        self._declared_locals: set[str] = {
            spec["name"].lower()
            for nd in ast.body if isinstance(nd, VarDecl)
            for spec in nd.names
        }
        self.param_names = {p["name"].lower() for p in ast.params}

    @property
    def static_decls(self) -> list[VarDecl]:
        return [nd for nd in self.ast.body
                if isinstance(nd, VarDecl) and nd.static]

    def state_type(self) -> str:
        return _pascal(self.ast.name) + "State"

    # -------------------------------------------------- method rendering

    def render_method(self) -> list[str]:
        ast = self.ast
        has_static = bool(self.static_decls)
        sig_params: list[str] = []
        if has_static:
            sig_params.append(f"{self.state_type()} $state")
        for p in ast.params:
            if p.get("array"):
                sig_params.append(f"Object[] {_camel(p['name'])}")
                continue
            ptype = java_type(p.get("type"), boxed=bool(p.get("default"))
                              or bool(p.get("optional")))
            sig_params.append(f"{ptype} {_camel(p['name'])}")

        ret_java = "void" if ast.kind.upper() != "FUNCTION" \
            else java_type(ast.return_type)
        method_name = _camel(ast.name)

        out = [
            "/**",
            f" * Converted from VBA '{ast.name}' ({ast.kind}).",
            " * ACCESS-SOURCE trace: see conversion manifest entry for this object.",
            " * Unconvertible constructs appear as ACCESS-MIGRATION markers below.",
            " */",
        ]
        visibility = "public"
        out.append(f"{visibility} {ret_java} {method_name}({', '.join(sig_params)}) {{")

        # counter names never Dim'd need their own slot (values survive
        # 'Exit For' exactly like VBA)
        counter_names = self._collect_counter_names(ast.body)
        for cn in sorted(counter_names):
            if cn not in self._declared_locals and cn not in self.param_names \
                    and cn not in self.ctx.static_scalars \
                    and cn not in self.ctx.static_arrays:
                out.append(f"    int {_camel(cn)} = 0;")
                self.ctx.local_types[cn.lower()] = "Integer"

        # optional-parameter defaults: reassign the boxed parameter itself
        for p in ast.params:
            dv = p.get("default")
            if dv is not None:
                pname = _camel(p["name"])
                default = self.translator.translate(str(dv))
                out.append(f"    if ({pname} == null) {{ {pname} = {default}; }}")

        # error variables
        err_mode = next((nd for nd in ast.body if isinstance(nd, OnError)), None)
        out.append("    long $errNum = 0;")
        out.append('    String $errDesc = "";')

        if ret_java != "void":
            prim_default = {"double": "0d", "int": "0", "long": "0L",
                            "float": "0f", "boolean": "false"}.get(ret_java)
            default_expr = prim_default if prim_default is not None else (
                "null" if ret_java in ("Object", "String") else prim_default or "null")
            out.append(f"    {ret_java} {self.return_var} = {default_expr};")

        # VBA Dim locals are procedure-scoped and start with VBA default
        # values (numbers 0, booleans false, objects null); Java case blocks
        # would hide them from other dispatch segments AND fail definite
        # assignment, so hoist every declaration pre-initialized.
        _TYPE_DEFAULTS = {"int": "0", "long": "0L", "double": "0d",
                          "float": "0f", "boolean": "false"}
        for node in ast.body:
            if not isinstance(node, VarDecl) or node.static:
                continue
            for spec in node.names:
                lname = spec["name"].lower()
                if lname in self.ctx.static_scalars or \
                        lname in self.ctx.static_arrays:
                    continue
                jn = _camel(spec["name"])
                dims = spec.get("array_dims")
                if dims:
                    sizes = [_parse_dim(d)[0] for d in dims]
                    out.append(f"    Object[]{'[]' * (len(sizes)-1)} {jn} = "
                               f"{_build_multiarray_init(sizes)};")
                else:
                    jt = java_type(spec.get("type"))
                    default = _TYPE_DEFAULTS.get(jt, "null")
                    out.append(f"    {jt} {jn} = {default};")

        body_blocks, complete = self._render_control_flow(has_static, err_mode)
        out.extend(body_blocks)

        if ret_java != "void":
            out.append(f"    return {self.return_var};")
        out.append("}")
        return out

    @staticmethod
    def _collect_counter_names(nodes: list[Node]) -> set[str]:
        found: set[str] = set()

        def walk(ns: list[Node]) -> None:
            for nd in ns:
                if isinstance(nd, ForNext):
                    found.add(nd.var_name.lower())
                    walk(nd.body)
                elif isinstance(nd, (IfBlock, SingleLineIf)):
                    walk(getattr(nd, "then_stmts", []) or [])
                    walk(getattr(nd, "else_stmts", []) or [])
                    for _, lst in getattr(nd, "elseifs", []) or []:
                        walk(lst)
                elif isinstance(nd, DoLoop):
                    walk(nd.body)
                elif isinstance(nd, SelectCase):
                    for _, lst in nd.cases:
                        walk(lst)
                elif isinstance(nd, WithBlock):
                    walk(nd.body)

        walk(nodes)
        return found

    # -------------------------------------------------- control flow

    def _segment_plan(self) -> tuple[list[Node], list[tuple[str, list[Node]]]]:
        main: list[Node] = []
        segs: list[tuple[str, list[Node]]] = []
        current = main
        seen_label = False
        for node in self.ast.body:
            if isinstance(node, LabelDef):
                seen_label = True
                current = []
                segs.append((node.name, current))
                continue
            current.append(node)
        del seen_label
        return main, segs

    def _render_control_flow(self, has_static: bool,
                             err_mode: OnError | None) -> tuple[list[str], bool]:
        main, segs = self._segment_plan()

        if not segs and (err_mode is None
                         or getattr(err_mode, "mode", "") != "GOTO_LABEL"):
            lines, ok = self._emit_stmts(main, 8)
            return lines, ok

        seg_names = ["__MAIN__"] + [s[0] for s in segs]
        guard_target = max(len(seg_names) * 100, 200)

        out: list[str] = []
        out.append('    String $label = "__MAIN__";')
        out.append(f"    for (int $__guard = 0; $__guard < {guard_target}; $__guard++) {{")
        out.append("        try {")
        out.append("            switch ($label) {")

        # ---- main segment
        out.append('            case "__MAIN__": {')
        main_lines, _ = self._emit_stmts(main, 16)
        out.extend(main_lines)
        if _ends_with_jump(main_lines):
            pass                        # segment already returns/throws
        elif segs:
            nxt = segs[0][0]
            out.append(f'                $label = "{_jstr(nxt)}";')
            out.append("                break;")
        elif self.ast.kind.upper() == "FUNCTION":
            out.append(f"                return {self.return_var};")
        else:
            out.append("                return;")
        out.append("            }")

        # ---- labelled segments
        for si, (seg_name, stmts) in enumerate(segs):
            out.append(f'            case "{_jstr(seg_name)}": {{')
            stmt_list = list(stmts)
            if stmt_list and isinstance(stmt_list[0], OnError) \
                    and stmt_list[0].mode == "RESUME_NEXT":
                stmt_list = stmt_list[1:]
                out.append("                // On Error Resume Next at this label:")
                out.append("                // per-statement suppression not modelled (see report).")
            seg_lines, _ = self._emit_stmts(stmt_list, 16)
            out.extend(seg_lines)
            if _ends_with_jump(seg_lines):
                pass                    # unreachable fallthrough avoided
            elif si + 1 < len(segs):
                nxt = segs[si + 1][0]
                out.append(f'                $label = "{_jstr(nxt)}";')
                out.append("                break;")
            elif self.ast.kind.upper() == "FUNCTION":
                out.append(f"                return {self.return_var};")
            else:
                out.append("                return;")
            out.append("            }")

        out.append("            default:")
        if self.ast.kind.upper() == "FUNCTION":
            out.append(f"                return {self.return_var};")
        else:
            out.append("                return;")
        out.append("            }")     # switch
        out.append("        }")

        out.append("        catch (com.generated.app.access.VbaGotoSignal $g) {")
        out.append("            $label = $g.label;")
        out.append("        }")

        if err_mode is not None and err_mode.mode == "GOTO_LABEL" and any(
                s[0].lower() == err_mode.label.lower() for s in segs):
            self.usage.error_handling = True
            out.append("        catch (RuntimeException $err) {")
            out.append('            com.generated.app.access.AccessError.log("'
                       + _jstr(self.ast.name) + '", $err);')
            out.append("            $errNum = com.generated.app.access."
                       "AccessError.number($err);")
            out.append('            $errDesc = String.valueOf($err.getMessage());')
            out.append(f'            $label = "{_jstr(err_mode.label)}";')
            out.append("        }")
        else:
            self.usage.error_handling = True
            out.append("        catch (RuntimeException $err) {")
            out.append("            $errNum = com.generated.app.access."
                       "AccessError.number($err);")
            out.append('            $errDesc = String.valueOf($err.getMessage());')
            out.append("            throw $err;")
            out.append("        }")
        out.append("    }")
        return out, True

    # -------------------------------------------------- statements

    def _emit_stmts(self, stmts: list[Node],
                    indent: int) -> tuple[list[str], bool]:
        lines: list[str] = []
        ok = True
        for st in stmts:
            emitted, complete = self._emit_stmt(st, indent)
            lines.extend(emitted)
            if not complete:
                ok = False
        return lines, ok

    def _pad(self, indent: int) -> str:
        return " " * indent

    def _emit_stmt(self, node: Node,
                   ind: int) -> tuple[list[str], bool]:
        pad = " " * ind
        T = self.translator
        lines: list[str] = []

        if isinstance(node, SeqNode):
            ok_all = True
            for sub in node.stmts:
                ln2, ok2 = self._emit_stmt(sub, ind)
                lines.extend(ln2)
                ok_all = ok_all and ok2
            return lines, ok_all

        if isinstance(node, RawStatement):
            src = (node.source_line or node.text or "").rstrip()
            lines.append(pad + "// ACCESS-MIGRATION: manual review required "
                               "(construct not recognised)")
            lines.append(pad + "// SOURCE-VBA: " + _jstr(src))
            return lines, False

        if isinstance(node, VarDecl):
            # declarations were hoisted to method scope (or live in $state)
            return lines, True

        if isinstance(node, Assignment):
            lines.append(pad + self._translate_assignment(node) + ";")
            return lines, True

        if isinstance(node, CallStatement):
            expr = node.expression.rstrip(":").strip()
            if expr.lower().startswith("debug.print"):
                self.usage.error_handling = True
                rest = expr[len("debug.print"):].strip()
                # VBA Debug.Print separates args with , or ;
                parts = re.split(r"[;,]", rest) if rest else []
                args = [T.translate(p) for p in parts if p.strip()]
                if args:
                    joined = ", ".join(f'AccessRuntime.cStr({a})' for a in args)
                    lines.append(pad + f"System.out.println({joined});")
                else:
                    lines.append(pad + "System.out.println();")
                return lines, True
            cm = re.match(r"^([A-Za-z_]\w*)\s*\((.*)\)\s*$", expr, re.S)
            if cm and cm.group(1).lower() in self.ctx.in_module_funcs:
                args = [T.translate(a) for a in T.split_args(cm.group(2))]
                lines.append(pad + f"{_camel(cm.group(1))}({', '.join(args)});")
                return lines, True
            # bare sub call without parens: Foo arg1, arg2
            sm = re.match(r"^([A-Za-z_]\w*)\s+([^()=][^\n]*)$", expr)
            if sm and sm.group(1).lower() in self.ctx.in_module_funcs:
                args = [T.translate(a) for a in T.split_args(sm.group(2))]
                lines.append(pad + f"{_camel(sm.group(1))}({', '.join(args)});")
                return lines, True
            lines.append(pad + "// ACCESS-MIGRATION: unsupported statement kept for review")
            lines.append(pad + "// SOURCE-VBA: " + _jstr(expr))
            return lines, False

        if isinstance(node, ExitConstruct):
            what = (node.what or "").split()[0].upper() if node.what else ""
            if what in ("FUNCTION", "SUB", "PROPERTY"):
                if self.ast.kind.upper() == "FUNCTION":
                    lines.append(pad + f"return {self.return_var};")
                else:
                    lines.append(pad + "return;")
                return lines, True
            if what in ("FOR", "DO"):
                lines.append(pad + "break;")
                return lines, True
            lines.append(pad + f"// ACCESS-MIGRATION: Exit {what} unsupported here")
            return lines, False

        if isinstance(node, GotoStatement):
            lines.append(pad +
                         f'throw new com.generated.app.access.VbaGotoSignal('
                         f'"{_jstr(node.label)}");')
            return lines, True

        if isinstance(node, LabelDef):
            return lines, True

        if isinstance(node, OnError):
            lines.append(pad + "// (On Error handled by the generated dispatcher)")
            return lines, True

        if isinstance(node, ReturnAssignment):
            val = T.translate(node.value)
            lines.append(pad + f"{self.return_var} = {val};")
            return lines, True

        if isinstance(node, SingleLineIf):
            cond = T.translate(node.condition)
            lines.append(pad + f"if ({cond}) {{")
            ln, _ = self._emit_stmts(node.then_stmts, ind + 4)
            lines.extend(ln)
            if node.else_stmts:
                lines.append(pad + "} else {")
                ln2, _ = self._emit_stmts(node.else_stmts, ind + 4)
                lines.extend(ln2)
            lines.append(pad + "}")
            return lines, True

        if isinstance(node, IfBlock):
            cond = T.translate(node.condition)
            lines.append(pad + f"if ({cond}) {{")
            ln, ok = self._emit_stmts(node.then_stmts, ind + 4)
            lines.extend(ln)
            complete = ok
            for ei_cond, ei_body in node.elseifs:
                ec = T.translate(ei_cond)
                lines.append(pad + f"}} else if ({ec}) {{")
                ln, ok_ei = self._emit_stmts(ei_body, ind + 4)
                lines.extend(ln)
                complete = complete and ok_ei
            if node.else_stmts:
                lines.append(pad + "} else {")
                ln, ok_else = self._emit_stmts(node.else_stmts, ind + 4)
                lines.extend(ln)
                complete = complete and ok_else
            lines.append(pad + "}")
            return lines, complete

        if isinstance(node, ForNext):
            var = _camel(node.var_name)
            declared_here = node.var_name.lower() in self._declared_locals \
                or node.var_name.lower() in self.param_names
            start = T.translate(node.start_expr)
            end = T.translate(node.end_expr)
            step = T.translate(node.step_expr) if node.step_expr else ""
            negative_step = bool(step) and step.lstrip("+").startswith("-")
            if step in ("", "1"):
                incr = f"{var}++"
                cmp_op = "<="
            else:
                incr = f"{var} += ({step})"
                cmp_op = ">=" if negative_step else "<="
            decl = "" if declared_here else "int "
            lines.append(pad + f"for ({decl}{var} = {start}; {var} {cmp_op} {end}; {incr}) {{")
            ln, ok = self._emit_stmts(node.body, ind + 4)
            lines.extend(ln)
            lines.append(pad + "}")
            return lines, ok

        if isinstance(node, ForEach):
            item = _camel(node.item_var)
            coll = T.translate(node.collection_expr)
            self.ctx.uses_runtime = True
            lines.append(pad + f"for (Object {item} : AccessRuntime.iterate({coll})) {{")
            ln, ok = self._emit_stmts(node.body, ind + 4)
            lines.extend(ln)
            lines.append(pad + "}")
            return lines, ok

        if isinstance(node, DoLoop):
            cond = T.translate(node.condition) if node.condition else "true"
            tail = node.kind in ("DO_WHILE_TAIL", "DO_UNTIL_TAIL")
            if node.kind == "WHILE":
                lines.append(pad + f"while ({cond}) {{")
            elif node.kind == "UNTIL":
                lines.append(pad + f"while (!({cond})) {{")
            else:
                lines.append(pad + "do {")
            ln, ok = self._emit_stmts(node.body, ind + 4)
            lines.extend(ln)
            if tail:
                if node.kind == "DO_WHILE_TAIL":
                    lines.append(pad + f"}} while ({cond});")
                else:
                    lines.append(pad + f"}} while (!({cond}));")
            else:
                lines.append(pad + "}")
            return lines, ok

        if isinstance(node, SelectCase):
            subj = T.translate(node.subject_expr)
            first = True
            complete = True
            open_needed = False
            for case_val, body in node.cases:
                cv = case_val.strip()
                if cv.lower() == "else":
                    if open_needed:
                        lines.append(pad + "} else {")
                    else:
                        lines.append(pad + "if (true) {")
                    ln, ok_b = self._emit_stmts(body, ind + 4)
                    lines.extend(ln)
                    complete &= ok_b
                    open_needed = True
                    continue
                test = self._select_case_test(subj, cv)
                kw = "if" if not open_needed else "} else if"
                lines.append(pad + f"{kw} ({test}) {{")
                ln, ok_b = self._emit_stmts(body, ind + 4)
                lines.extend(ln)
                complete &= ok_b
                open_needed = True
            if open_needed:
                lines.append(pad + "}")
            return lines, complete

        if isinstance(node, WithBlock):
            lines.append(pad + "// ACCESS-MIGRATION: With block flattened; verify member access")
            lines.append(pad + "{")
            lines.append(pad + f"    Object $with = {T.translate(node.object_expr)};")
            ln, ok = self._emit_stmts(node.body, ind + 4)
            lines.extend(ln)
            lines.append(pad + "}")
            return lines, ok

        if isinstance(node, RedimStatement):
            lines.append(pad + "// ACCESS-MIGRATION: ReDim requires sizing adapter")
            lines.append(pad + "// SOURCE-VBA: " + _jstr(node.source_line or ""))
            return lines, False

        lines.append(pad + "// ACCESS-MIGRATION: unrecognized construct")
        return lines, False

    def _select_case_test(self, subject: str, case_val: str) -> str:
        self.ctx.uses_runtime = True
        if case_val.lower().startswith("is "):
            rest = case_val[3:].strip()
            for op in (">=", "<=", "<>", ">", "<", "="):
                if rest.startswith(op):
                    rhs = self.translator.translate(rest[len(op):].strip())
                    if op == "=":
                        return f"AccessRuntime.eq({subject}, {rhs})"
                    if op == "<>":
                        return f"(!AccessRuntime.eq({subject}, {rhs}))"
                    return f"AccessRuntime.compare({subject}, {rhs}) {op} 0"
            return f"/* bad case clause {case_val} */ true"
        if re.search(r"\bto\b", case_val, re.I):
            lo, hi = re.split(r"\bto\b", case_val, maxsplit=1, flags=re.I)
            lot = self.translator.translate(lo.strip())
            hit = self.translator.translate(hi.strip())
            return (f"(AccessRuntime.compare({subject}, {lot}) >= 0 && "
                    f"AccessRuntime.compare({subject}, {hit}) <= 0)")
        tests = [f"AccessRuntime.eq({subject}, {self.translator.translate(p.strip())})"
                 for p in case_val.split(",") if p.strip()]
        return " || ".join(tests) if tests else "true"

    # -------------------------------------------------- assignments

    def _translate_assignment(self, node: Assignment) -> str:
        T = self.translator
        target = node.target.strip().rstrip(":")
        value = T.translate(node.value)
        lowered = target.lower()

        # function-name slot?
        if self.ast.kind.upper() == "FUNCTION" and lowered == self.ast.name.lower():
            if self.translator._possibly_variant(node.value):
                ret_jt = java_type(self.ast.return_type)
                coerce = {"double": "cDbl", "float": "cDbl", "int": "cInt",
                          "long": "cLng"}.get(ret_jt)
                if coerce:
                    self.ctx.uses_runtime = True
                    return f"{self.return_var} = AccessRuntime.{coerce}({value})"
            return f"{self.return_var} = {value}"

        am = re.match(
            r"^([A-Za-z_]\w*)\s*\((.*)\)$", target, re.S)
        if am:
            arr_name = am.group(1)
            dims = (self.ctx.static_arrays.get(arr_name.lower())
                    or self.ctx.local_arrays.get(arr_name.lower()))
            idx_parts = [T.translate(p.strip()) for p in T.split_args(am.group(2))]
            indexes = ""
            if dims:
                lowers = [_parse_dim(d)[1] for d in dims]
                for pos, ix in enumerate(idx_parts):
                    off = lowers[pos] if pos < len(lowers) else 0
                    indexes += f"[({ix}){' - ' + str(off) if off else ''}]"
            else:
                indexes = "".join(f"[{ix}]" for ix in idx_parts)
            owner = "$state." if arr_name.lower() in self.ctx.static_arrays else ""
            return f"{owner}{_camel(arr_name)}{indexes} = {value}"

        if lowered in self.ctx.static_scalars:
            return f"$state.{_camel(target)} = {value}"

        if re.match(r"^[A-Za-z_]\w*$", target):
            # primitive numeric targets need coercion when the RHS is
            # Variant-typed (array reads, untyped params, ...)
            if self.translator._possibly_variant(node.value):
                jt = java_type(self.ctx.type_of(lowered))
                coerce = {"double": "cDbl", "float": "cDbl", "int": "cInt",
                          "long": "cLng"}.get(jt)
                if coerce:
                    self.ctx.uses_runtime = True
                    return f"{_camel(target)} = AccessRuntime.{coerce}({value})"
            return f"{_camel(target)} = {value}"
        return f"/* bad assignment target: {target} */"


def _ends_with_jump(lines: list[str]) -> bool:
    """True when the last emitted statement already returns/throws."""
    for raw in reversed(lines):
        stripped = raw.strip()
        if not stripped or stripped.startswith("//"):
            continue
        return stripped.startswith(("return", "throw", "$label"))
    return False


def _terminates_block(stmts: list[Node]) -> bool:
    """Does this segment always exit via jump/return at its end?"""
    if not stmts:
        return False
    last = stmts[-1]
    if isinstance(last, (ExitConstruct, GotoStatement)):
        return True
    return False


def _jstr(s: str) -> str:
    return s.replace("\\", "\\\\").replace('"', '\\"')


def _state_class_source(proc: ProcedureAST, decls: list[VarDecl]) -> list[str]:
    cls = _pascal(proc.name) + "State"
    out = [
        "    /**",
        f"     * Holds Static-local state of converted '{proc.name}'.",
        "     * Plan §11: callers processing an ordered record stream share ONE",
        "     * instance so accumulations behave exactly like Access.",
        "     */",
        f"    public static class {cls} {{",
    ]
    for decl in decls:
        for spec in decl.names:
            jn = _camel(spec["name"])
            dims = spec.get("array_dims")
            if dims:
                sizes = [_parse_dim(d)[0] for d in dims]
                out.append(f"        private Object[]{'[]' * (len(sizes)-1)} {jn} = "
                           f"{_build_multiarray_init(sizes)};")
            else:
                out.append(f"        private Object {jn};")
    out.append("")
    out.append("        void reset() {")
    for decl in decls:
        for spec in decl.names:
            jn = _camel(spec["name"])
            dims = spec.get("array_dims")
            if dims:
                sizes = [_parse_dim(d)[0] for d in dims]
                out.append(f"            this.{jn} = {_build_multiarray_init(sizes)};")
            else:
                out.append(f"            this.{jn} = null;")
    out.append("        }")
    out.append("    }")
    return out


# ------------------------------------------------------------------ module entry

@dataclass
class ModuleConversionResult:
    module_name: str
    class_name: str
    java_source: str
    converted_procedures: list[str]
    manual_review_procedures: list[str]
    # procedure name -> inner state class name ('' when no Static state)
    procedure_states: dict[str, str] = field(default_factory=dict)
    notes: list[str] = field(default_factory=list)


def convert_module(module_ir,
                   usage: RuntimeUsage | None = None) -> ModuleConversionResult:
    """Convert a VbaModuleIR into a Spring service source string.

    When `usage` is provided, runtime-need flags accumulate onto it so the
    caller can emit exactly the compatibility classes required.
    """
    usage = usage or RuntimeUsage()
    proc_results: list[tuple[object, ProcedureAST]] = []
    func_names: set[str] = set()

    for proc in module_ir.procedures:
        ast = parse_procedure(proc.name, proc.parameters, proc.return_type,
                              proc.kind, proc.body or "")
        func_names.add(proc.name.lower())
        proc_results.append((proc, ast))

    class_name = service_class_name(module_ir.name)
    src: list[str] = []
    src.append("// ACCESS-SOURCE:")
    src.append(f"// Module: {module_ir.name}")
    src.append("// Strategy: SPRING_SERVICE")
    src.append("")
    src.append("package com.generated.app.service;")
    src.append("")
    src.append("import org.springframework.stereotype.Service;")
    src.append("import com.generated.app.access.AccessRuntime;")
    src.append("import com.generated.app.access.AccessDateFunctions;")
    src.append("import com.generated.app.access.AccessStrings;")
    src.append("import com.generated.app.access.VbaGotoSignal;")
    src.append("")
    src.append("/**")
    src.append(f" * Converted from VBA module '{module_ir.name}'.")
    src.append(" * Generated dynamically from IR + dependency graph; no hardcoded")
    src.append(" * source object names. ACCESS-MIGRATION markers require review.")
    src.append(" */")
    src.append("@Service")
    src.append(f"public class {class_name} {{")

    converted: list[str] = []
    review: list[str] = []
    notes: list[str] = []
    state_blocks: list[str] = []
    procedure_states: dict[str, str] = {}

    for proc, ast in proc_results:
        emitter = JavaSemanticEmitter(ast, usage, func_names)
        state_decls = emitter.static_decls
        if ast.unsupported_lines:
            review.append(proc.name)
            notes.append(f"{proc.name}: {len(ast.unsupported_lines)} "
                         f"unconverted construct(s)")
        elif emitter.ctx.has_unresolved_calls:
            review.append(proc.name)
            notes.append(f"{proc.name}: unresolved call(s) routed through "
                         f"AccessRuntime.unsupported()")
        else:
            converted.append(proc.name)

        if state_decls:
            state_blocks.append((ast, state_decls))
            procedure_states[proc.name] = _pascal(ast.name) + "State"
        else:
            procedure_states[proc.name] = ""
        src.extend(emitter.render_method())
        src.append("")

    for ast, decls in state_blocks:
        src.extend(_state_class_source(ast, decls))
        src.append("")

    src.append("}")

    result = ModuleConversionResult(
        module_name=module_ir.name,
        class_name=class_name,
        java_source="\n".join(src),
        converted_procedures=converted,
        manual_review_procedures=review,
        procedure_states=procedure_states,
        notes=notes,
    )
    return result
