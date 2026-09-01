"""VBA statement-level parser producing an AST (plan §6-7).

The existing `analyzers/vba.py` extracts procedures and call graphs; this
module parses each procedure *body* into structured statements so the Java
generator can emit semantically equivalent code instead of translating text
line-by-line.

Supported constructs (plan §7): Dim/Static/ReDim, If/ElseIf/Else (block and
single-line), For..Next, For Each..Next, Do While/Until/Loop variants,
Select Case, With, assignment (including array element targets), Exit
For/Do/Function/Sub/Property, GoTo + labels, On Error GoTo/Resume Next,
Debug.Print, ReDim, Set, and plain expression statements.

Anything unrecognised becomes `RawStatement` — never silently dropped; the
generator marks it MANUAL_REVIEW.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Optional


# ------------------------------------------------------------------ AST nodes

@dataclass
class Node:
    """Base for all statement nodes."""
    line: int = 0
    source_line: str = ""


@dataclass
class VarDecl(Node):
    names: list[dict] = field(default_factory=list)  # {name,type,array_dims}
    static: bool = False

    @property
    def is_array(self) -> bool:
        return any(v.get("array_dims") for v in self.names)


@dataclass
class Assignment(Node):
    target: str = ""                    # variable or array-element expression
    value: str = ""
    is_set: bool = False                # VBA 'Set' object assignment


@dataclass
class CallStatement(Node):
    expression: str = ""                # e.g. Debug.Print "x", y


@dataclass
class SingleLineIf(Node):
    condition: str = ""
    then_stmts: list["Node"] = field(default_factory=list)
    else_stmts: list["Node"] = field(default_factory=list)


@dataclass
class IfBlock(Node):
    condition: str = ""
    then_stmts: list["Node"] = field(default_factory=list)
    elseifs: list[tuple[str, list["Node"]]] = field(default_factory=list)
    else_stmts: list["Node"] = field(default_factory=list)


@dataclass
class ForNext(Node):
    var_name: str = ""
    start_expr: str = ""
    end_expr: str = ""
    step_expr: str = ""                 # '' = 1
    body: list["Node"] = field(default_factory=list)


@dataclass
class ForEach(Node):
    item_var: str = ""
    collection_expr: str = ""
    body: list["Node"] = field(default_factory=list)


@dataclass
class DoLoop(Node):
    kind: str = "WHILE"                 # WHILE | UNTIL | DO_WHILE_TAIL | DO_UNTIL_TAIL
    condition: str = ""
    body: list["Node"] = field(default_factory=list)


@dataclass
class SelectCase(Node):
    subject_expr: str = ""
    cases: list[tuple[str, list["Node"]]] = field(default_factory=list)  # ('1,2'|'Is > x'|'Else', stmts)


@dataclass
class WithBlock(Node):
    object_expr: str = ""
    body: list["Node"] = field(default_factory=list)


@dataclass
class LabelDef(Node):
    name: str = ""


@dataclass
class GotoStatement(Node):
    label: str = ""
    is_error_resume_next_marker: bool = False


@dataclass
class OnError(Node):
    mode: str = ""                      # GOTO_LABEL | RESUME_NEXT | GOTO_0
    label: str = ""


@dataclass
class ExitConstruct(Node):
    what: str = ""                      # FOR | DO | FUNCTION | SUB | PROPERTY


@dataclass
class ReturnAssignment(Node):
    """`FunctionName = expr` — sets the VBA return slot."""
    function_name: str = ""
    value: str = ""


@dataclass
class RedimStatement(Node):
    target: str = ""
    bounds: str = ""


@dataclass
class SeqNode(Node):
    """Several statements that shared one physical line via ':'."""
    stmts: list["Node"] = field(default_factory=list)


@dataclass
class RawStatement(Node):
    text: str = ""
    reason: str = "unparsed construct"


@dataclass
class ProcedureAST:
    name: str
    params: list[dict] = field(default_factory=list)
    return_type: Optional[str] = None
    kind: str = "SUB"
    body: list[Node] = field(default_factory=list)
    labels: list[str] = field(default_factory=list)
    unsupported_lines: list[str] = field(default_factory=list)

    @property
    def fully_supported(self) -> bool:
        return not self.unsupported_lines


_LINE_CONTINUATION = re.compile(r"_\s*(?:'[^']*)?$")


def _strip_comment(line: str) -> str:
    """Remove a trailing 'comment, respecting doubled-quote literals."""
    in_string = False
    for i, ch in enumerate(line):
        if ch == '"':
            in_string = not in_string
        elif ch == "'" and not in_string:
            return line[:i].rstrip()
    return line


def _join_continuations(text: str) -> list[tuple[int, str]]:
    """Merge ` _` continuation lines; return (first_lineno, logical_line)."""
    raw_lines = text.split("\n")
    merged: list[tuple[int, str]] = []
    buf = ""
    start_ln = 0
    for idx, raw in enumerate(raw_lines):
        ln = idx + 1
        stripped = _strip_comment(raw.strip())
        if not buf:
            if not stripped:
                continue
            start_ln = ln
            buf = stripped
        else:
            buf += " " + stripped
        if _LINE_CONTINUATION.search(buf):
            buf = _LINE_CONTINUATION.sub("", buf).rstrip()
            continue
        merged.append((start_ln, buf))
        buf = ""
    if buf:
        merged.append((start_ln, buf))
    return merged


_ARRAY_DECL_DIMS = re.compile(
    r"^(?P<name>[A-Za-z_]\w*)\s*\((?P<dims>[^)]+)\)")
_DECL_NAME_TYPE = re.compile(r"^([A-Za-z_]\w*)(?:\s+As\s+(.+))?$", re.I)


def _parse_decl_names(rest: str) -> list[dict]:
    out: list[dict] = []
    # split on commas outside parens
    parts, depth, cur = [], 0, ""
    for ch in rest:
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
    for part in parts:
        part = part.strip()
        m = _ARRAY_DECL_DIMS.match(part)
        entry: dict = {"array_dims": None, "type": None}
        if m:
            name_part = m.group("name")
            entry["name"] = name_part.strip()
            entry["array_dims"] = [d.strip() for d in m.group("dims").split(",")]
            trailing = part[m.end():]
            tm = re.search(r"\bAs\s+(.+)$", trailing, re.I)
            entry["type"] = tm.group(1).strip() if tm else None
        else:
            nm = _DECL_NAME_TYPE.match(part)
            if nm:
                entry["name"] = nm.group(1)
                entry["type"] = (nm.group(2) or "").strip() or None
            else:
                entry["name"] = part
        out.append(entry)
    return out


def _split_single_line_if(rest: str) -> tuple[str, str]:
    """Split 'cond Then code [Else code]' respecting nested If-in-Then."""
    depth = 0
    idx = len(rest)
    low = rest.lower()
    for m in re.finditer(r"(?<!(\w))(then|else)(?!(\w))", low):
        kw = m.group(0)
        if kw == "then":
            depth += 1
            continue
        # an 'else' with no open single-line 'then'
        if depth <= 1 and "end if" not in low[m.start():m.start()+8]:
            idx = m.start()
            break
    head_then = rest[:idx]
    else_part = rest[idx:].strip()
    tm = re.search(r"\bthen\b", head_then, re.I)
    cond = head_then[:tm.start()].strip() if tm else head_then
    tail_then = head_then[tm.end():].strip() if tm else ""
    return cond, tail_then, else_part[4:].strip() if else_part.lower().startswith("else") else None or "", else_part


def _split_first_keyword(line: str, keyword: str) -> Optional[tuple[str, str]]:
    m = re.search(rf"(?<![\w!])(?:\b|^){keyword}\b", line, re.I)
    if not m:
        return None
    prefix = line[:m.start()].strip()
    rest = line[m.end():].strip()
    return prefix, rest


class StatementParser:
    """Parses one logical VBA statement stream into a Node tree."""

    def __init__(self, proc_name: str):
        self.proc_name = proc_name

    # public ------------------------------------------------------------

    def parse_body(self, lines: list[str]) -> tuple[list[Node], list[str]]:
        """Parse raw procedure-body lines into nodes.

        Returns (nodes, unsupported_source_lines).
        """
        merged = _join_continuations("\n".join(lines))
        parsed_pairs = [(ln, l) for ln, l in merged]
        stmts, unsupported = self._parse_seq(parsed_pairs, 0)
        return stmts, unsupported

    # internals ----------------------------------------------------------

    @staticmethod
    def _top_level_colon(line: str) -> int:
        """Position of a statement-separating colon outside strings/parens."""
        depth = 0
        in_string = False
        for i, ch in enumerate(line):
            if in_string:
                if ch == '"':
                    in_string = False
                continue
            if ch == '"':
                in_string = True
            elif ch == "(":
                depth += 1
            elif ch == ")":
                depth -= 1
            elif ch == ":" and depth == 0:
                return i
        return -1

    def _parse_seq(self, pairs: list[tuple[int, str]],
                   depth: int) -> tuple[list[Node], list[str]]:
        nodes: list[Node] = []
        unsupported: list[str] = []
        i = 0
        n = len(pairs)
        while i < n:
            ln, line = pairs[i]
            low = line.lower()

            # skip empty / pure comments
            if not low or low.startswith("'"):
                i += 1
                continue

            node, consumed = self._parse_one(pairs, i)
            if node is None:
                unsupported.append(line)
                nodes.append(RawStatement(line=ln, source_line=line,
                                          text=line))
                i += 1
                continue
            nodes.append(node)
            i += consumed
        return nodes, unsupported

    # individual statements ------------------------------------------------

    def _parse_one(self, pairs, i) -> tuple[Optional[Node], int]:
        ln, line = pairs[i]
        low = line.lower().strip()

        # colon-separated statements on one line: `x = 1: foo bar`
        # (a whole-line label was already handled below)
        colon = self._top_level_colon(line)
        if colon != -1 and not re.match(r"^([A-Za-z_]\w*):\s*$", line.strip()):
            left = line[:colon].strip()
            right = line[colon + 1:].strip()
            # `1:` numeric statement labels behave like no-ops here
            if left:
                sub_pairs = [(ln, left), (ln, right)] if \
                    not re.fullmatch(r"\d+", left) else [(ln, right)]
                node, consumed = self._parse_seq(sub_pairs, 0)
                if len(node) == 1:
                    return node[0], 1
                seq = SeqNode(line=ln, source_line=line, stmts=node)
                return seq, 1

        # labels: Identifier:
        lm = re.match(r"^([A-Za-z_]\w*):\s*$", line.strip())
        if lm:
            return LabelDef(line=ln, source_line=line, name=lm.group(1)), 1

        if low.startswith("on error"):
            return self._parse_on_error(ln, line), 1

        if low.startswith(("exit for", "exit do", "exit function",
                           "exit sub", "exit property")):
            what = line.strip()[5:].strip().upper()
            return ExitConstruct(line=ln, source_line=line, what=what), 1

        if low.startswith("goto ") or low.startswith("resume next") \
                or low == "resume":
            if low.startswith("goto"):
                return GotoStatement(line=ln, source_line=line,
                                     label=line.strip()[5:].strip()), 1
            return RawStatement(line=ln, source_line=line, text=line,
                                reason="bare Resume"), 1

        if low.startswith(("dim ", "static ", "public ", "private ")) \
                and (" as " in low or "(" in low or low.endswith("static")):
            static_kw = low.startswith("static ")
            rest = line.strip()
            for kw in ("dim", "static", "private", "public"):
                split = _split_first_keyword(rest, kw)
                if split is not None and split[0] == "":
                    rest = split[1]
                    break
            return VarDecl(line=ln, source_line=line, static=static_kw,
                           names=_parse_decl_names(rest)), 1

        if low.startswith("redim"):
            _, rest = _split_first_keyword(line.strip(), "redim")
            return RedimStatement(line=ln, source_line=line, target=rest), 1

        # block-level constructs consume multiple pairs
        if re.match(r"^if\b", low) :
            node, consumed = self._parse_if(pairs, i)
            return node, consumed

        if low.startswith("for each"):
            return self._parse_for_each(pairs, i)
        if low.startswith("for "):
            return self._parse_for(pairs, i)

        if low.startswith("do"):
            return self._parse_do(pairs, i)

        if low.startswith("select case"):
            return self._parse_select(pairs, i)

        if low.startswith("with "):
            return self._parse_with(pairs, i)

        # assignment vs call
        assign = self._try_assignment(ln, line)
        if assign is not None:
            return assign, 1
        return CallStatement(line=ln, source_line=line,
                             expression=line.strip()), 1

    # helpers -----------------------------------------------------------------

    @staticmethod
    def _try_assignment(ln: int, line: str) -> Optional[Node]:
        text = line.strip()
        if text.startswith("set "):
            m = re.match(r"^set\s+([^=]+?)\s*=\s*(.+)$", text, re.I)
            if m:
                return Assignment(line=ln, source_line=line,
                                  target=m.group(1).strip(),
                                  value=m.group(2).strip(), is_set=True)
        m = re.match(r"^([\w!.()\s,'\"+\-*/&]+?)\s*=\s*(.+)$", text)
        if m and not text.startswith(("==",)):
            target = m.group(1).strip()
            if target and not target.startswith("'"):
                # distinguish CallStatement like 'x(1)' with bare compare ops?
                return Assignment(line=ln, source_line=line,
                                  target=target, value=m.group(2).strip())
        return None

    def _parse_on_error(self, ln: int, line: str) -> Node:
        low = line.lower().strip()
        m = re.match(r"^on\s+error\s+goto\s+(\w+)", low)
        if m:
            # preserve the label's original case for emission
            om = re.match(r"^on\s+error\s+goto\s+(\w+)", line.strip(), re.I)
            return OnError(line=ln, source_line=line, mode="GOTO_LABEL",
                           label=om.group(1) if om else m.group(1))
        if re.search(r"resume\s+next", low):
            return OnError(line=ln, source_line=line, mode="RESUME_NEXT")
        if re.search(r"goto\s+0", low):
            return OnError(line=ln, source_line=line, mode="GOTO_0")
        return RawStatement(line=ln, source_line=line, text=line,
                            reason="unrecognized On Error form")

    def _parse_if(self, pairs, i) -> tuple[Optional[Node], int]:
        ln, line = pairs[i]
        text = line.strip()
        # single-line IF?
        body_openers = (
            ("then$", True),
        )
        # find whether this is block IF: nothing after first THEN
        m = re.match(r"^if\s+(.+)$", text, re.I)
        if not m:
            return None, 1
        after = m.group(1)
        tm = re.search(r"\bthen\b", after, re.I)
        if not tm:
            return RawStatement(line=ln, source_line=line, text=text,
                                reason="IF without THEN"), 1
        cond = after[:tm.start()].strip()
        tail = after[tm.end():].strip()
        if tail:
            # single-line IF / IF...THEN...ELSE
            tail_low = tail.lower()
            em = re.search(r"(?<!\w)else(?!\w)", tail_low)
            if em and "end if" not in tail_low:
                then_txt = tail[:em.start()].strip()
                else_txt = tail[em.end():].strip()
            else:
                then_txt, else_txt = tail, ""
            p_then = [(ln, then_txt)] if then_txt else []
            p_else = [(ln, else_txt)] if else_txt else []
            tn, u1 = self._parse_seq(p_then, 0)
            en, u2 = self._parse_seq(p_else, 0)
            unsup = u1 + u2
            node = SingleLineIf(line=ln, source_line=line, condition=cond,
                                then_stmts=tn, else_stmts=en)
            node_unsup = getattr(node, "_unsupported", [])
            if unsup:
                node._unsupported = unsup  # type: ignore[attr-defined]
            return node, 1

        # block IF — scan to matching ELSEIF / ELSE / END IF at same nesting.
        # Block-if openers inside nested constructs are consumed by
        # _parse_one; we only track depth so their terminators aren't stolen.
        then_stmts, elseifs, else_stmts, consumed, unsup = [], [], [], 1, []
        current = then_stmts
        j = i + 1
        n = len(pairs)
        if_depth = 0
        while j < n:
            cjln, cline = pairs[j]
            clow = cline.strip().lower()
            dm = re.match(r"^end\s+if\b", clow)
            eim = re.match(r"^elseif\s+(.+)$", clow)
            em = re.match(r"^else\b", clow)
            opener = bool(re.match(r"^(if\b.*then$|if\b.*then\s+if\b)", clow))
            if dm and if_depth == 0:
                consumed = j - i + 1
                break
            if eim and if_depth == 0:
                cm = re.match(r"^elseif\s+(.+)\s+then$", cline.strip(), re.I)
                new_list: list[Node] = []
                elseifs.append((cm.group(1).strip() if cm else cline.strip(), new_list))
                current = new_list
                j += 1
                continue
            if em and if_depth == 0:
                new_list = []
                else_stmts = new_list
                current = new_list
                j += 1
                continue
            sub_node, sub_consumed = self._parse_one(pairs, j)
            if sub_node is None:
                unsup.append(cline)
                current.append(RawStatement(line=cjln, source_line=cline,
                                            text=cline))
                j += 1
            else:
                current.append(sub_node)
                span_end = j + sub_consumed
                for k in range(j, span_end):
                    klow = pairs[k][1].strip().lower()
                    if re.match(r"^(if\b.*\bthen$)", klow):
                        if_depth += 1
                    elif re.match(r"^end\s+if\b", klow):
                        if_depth -= 1
                j = span_end
        else:
            # unterminated IF
            return RawStatement(line=ln, source_line=line, text=text,
                                reason="unclosed block IF"), 1
        node = IfBlock(line=ln, source_line=line, condition=cond,
                       then_stmts=then_stmts, elseifs=elseifs,
                       else_stmts=else_stmts)
        node._unsupported = unsup  # type: ignore[attr-defined]
        return node, consumed

    def _parse_for(self, pairs, i) -> tuple[Optional[Node], int]:
        ln, line = pairs[i]
        m = re.match(r"^for\s+([A-Za-z_]\w*)\s*=\s*(.+?)\s+to\s+(.+?)(\s+step\s+(.+))?$",
                     line.strip(), re.I)
        if not m:
            return RawStatement(line=ln, source_line=line, text=line.strip(),
                                reason="unrecognized FOR"), 1
        var_name = m.group(1)
        start_expr = m.group(2).strip()
        end_expr = m.group(3).strip()
        step_expr = (m.group(5) or "").strip()
        body, consumed, unsup = [], 1, []
        j = i + 1
        n = len(pairs)
        depth_nest = 0
        while j < n:
            _, cline = pairs[j]
            clow = cline.strip().lower()
            if re.match(r"^for\b", clow):
                depth_nest += 1
            elif re.match(r"^next\b", clow):
                if depth_nest == 0:
                    consumed = j - i + 1
                    break
                depth_nest -= 1
            sub_node, sub_consumed = self._parse_one(pairs, j)
            if sub_node is None:
                unsup.append(cline)
                body.append(RawStatement(line=pairs[j][0],
                                         source_line=cline, text=cline))
                j += 1
            else:
                body.append(sub_node)
                j += sub_consumed
        else:
            return RawStatement(line=ln, source_line=line, text=line.strip(),
                                reason="FOR without NEXT"), 1
        node = ForNext(line=ln, source_line=line, var_name=var_name,
                       start_expr=start_expr, end_expr=end_expr,
                       step_expr=step_expr, body=body)
        node._unsupported = unsup  # type: ignore[attr-defined]
        return node, consumed

    def _parse_for_each(self, pairs, i) -> tuple[Optional[Node], int]:
        ln, line = pairs[i]
        m = re.match(r"^for\s+each\s+([A-Za-z_]\w*)\s+in\s+(.+)$", line.strip(), re.I)
        if not m:
            return RawStatement(line=ln, source_line=line, text=line.strip(),
                                reason="unrecognized FOR EACH"), 1
        body, consumed, unsup = [], 1, []
        j = i + 1
        depth_nest = 0
        while j < len(pairs):
            _, cline = pairs[j]
            clow = cline.strip().lower()
            if re.match(r"^for\b", clow):
                depth_nest += 1
            elif re.match(r"^next\b", clow):
                if depth_nest == 0:
                    consumed = j - i + 1
                    break
                depth_nest -= 1
            sub_node, sub_consumed = self._parse_one(pairs, j)
            if sub_node is None:
                unsup.append(cline)
                body.append(RawStatement(line=pairs[j][0],
                                         source_line=cline, text=cline))
                j += 1
            else:
                body.append(sub_node)
                j += sub_consumed
        else:
            return RawStatement(line=ln, source_line=line, text=line.strip(),
                                reason="FOR EACH without NEXT"), 1
        node = ForEach(line=ln, source_line=line, item_var=m.group(1),
                       collection_expr=m.group(2).strip(), body=body)
        node._unsupported = unsup  # type: ignore[attr-defined]
        return node, consumed

    def _parse_do(self, pairs, i) -> tuple[Optional[Node], int]:
        ln, line = pairs[i]
        low = line.strip().lower()
        body, consumed, unsup = [], 1, []
        pre_condition = ""
        post_kind = None
        if re.match(r"^do\s+(while|until)\b", low):
            km = re.match(r"^do\s+(while|until)\s+(.+)$", line.strip(), re.I)
            if km:
                pre_condition = km.group(2).strip()
        elif low != "do":
            return RawStatement(line=ln, source_line=line, text=line.strip(),
                                reason="unrecognized DO"), 1
        j = i + 1
        while j < len(pairs):
            _, cline = pairs[j]
            clow = cline.strip().lower()
            lm = re.match(r"^loop(\s+(while|until)\s+(.+))?\s*$", clow)
            if lm:
                consumed = j - i + 1
                if lm.group(2):
                    post_kind = ("DO_WHILE_TAIL" if lm.group(2).lower() == "while"
                                 else "DO_UNTIL_TAIL")
                    pre_condition = lm.group(3).strip()
                break
            sub_node, sub_consumed = self._parse_one(pairs, j)
            if sub_node is None:
                unsup.append(cline)
                body.append(RawStatement(line=pairs[j][0],
                                         source_line=cline, text=cline))
                j += 1
            else:
                body.append(sub_node)
                j += sub_consumed
        else:
            return RawStatement(line=ln, source_line=line, text=line.strip(),
                                reason="DO without LOOP"), 1
        kind = post_kind or ("UNTIL" if low.startswith("do until") else "WHILE")
        node = DoLoop(line=ln, source_line=line, kind=kind,
                      condition=pre_condition, body=body)
        node._unsupported = unsup  # type: ignore[attr-defined]
        return node, consumed

    def _parse_select(self, pairs, i) -> tuple[Optional[Node], int]:
        ln, line = pairs[i]
        m = re.match(r"^select\s+case\s+(.+)$", line.strip(), re.I)
        if not m:
            return RawStatement(line=ln, source_line=line, text=line.strip(),
                                reason="bad SELECT CASE"), 1
        subject = m.group(1).strip()
        cases: list[tuple[str, list[Node]]] = []
        consumed, unsup = 1, []
        j = i + 1
        current: list[Node] = []
        while j < len(pairs):
            _, cline = pairs[j]
            cst = cline.strip()
            clow = cst.lower()
            cm = re.match(r"^case\s+(.+)$", cst, re.I)
            if cm:
                current = []
                cases.append((cm.group(1).strip(), current))
                j += 1
                continue
            if clow == "end select":
                consumed = j - i + 1
                break
            sub_node, sub_consumed = self._parse_one(pairs, j)
            if sub_node is None:
                unsup.append(cst)
                current.append(RawStatement(line=pairs[j][0],
                                            source_line=cline, text=cst))
                j += 1
            else:
                current.append(sub_node)
                j += sub_consumed
        else:
            return RawStatement(line=ln, source_line=line, text=line.strip(),
                                reason="SELECT CASE without END SELECT"), 1
        node = SelectCase(line=ln, source_line=line, subject_expr=subject,
                          cases=cases)
        node._unsupported = unsup  # type: ignore[attr-defined]
        return node, consumed

    def _parse_with(self, pairs, i) -> tuple[Optional[Node], int]:
        ln, line = pairs[i]
        m = re.match(r"^with\s+(.+)$", line.strip(), re.I)
        if not m:
            return RawStatement(line=ln, source_line=line, text=line.strip(),
                                reason="bad WITH"), 1
        body, consumed, unsup = [], 1, []
        j = i + 1
        while j < len(pairs):
            _, cline = pairs[j]
            clow = cline.strip().lower()
            if clow == "end with":
                consumed = j - i + 1
                break
            sub_node, sub_consumed = self._parse_one(pairs, j)
            if sub_node is None:
                unsup.append(cline)
                body.append(RawStatement(line=pairs[j][0],
                                         source_line=cline, text=cline))
                j += 1
            else:
                if isinstance(sub_node, Assignment):
                    sub_node.target = re.sub(r"^\.!", ".", sub_node.target)
                body.append(sub_node)
                j += sub_consumed
        else:
            return RawStatement(line=ln, source_line=line, text=line.strip(),
                                reason="WITH without END WITH"), 1
        node = WithBlock(line=ln, source_line=line,
                         object_expr=m.group(1).strip(), body=body)
        node._unsupported = unsup  # type: ignore[attr-defined]
        return node, consumed


def collect_unsupported(nodes: list[Node]) -> list[str]:
    """Recursively gather every unparsed / flagged construct."""
    out: list[str] = []

    def visit(n: Node) -> None:
        unsup = getattr(n, "_unsupported", None)
        if isinstance(n, RawStatement):
            out.append(f"{n.text}   ({n.reason})")
        elif unsup:
            out.extend(unsup)
        for attr in ("then_stmts", "else_stmts", "body", "cases", "stmts"):
            val = getattr(n, attr, None)
            if attr == "cases" and isinstance(val, list):
                for _, stmts in val:
                    for s in stmts:
                        visit(s)
            elif isinstance(val, list):
                for child in val:
                    if isinstance(child, Node):
                        visit(child)
        elseifs = getattr(n, "elseifs", None)
        if elseifs:
            for _, stmts in elseifs:
                for s in stmts:
                    visit(s)

    for n in nodes:
        visit(n)
    return out


def parse_procedure(name: str, params: list[dict], return_type: Optional[str],
                    kind: str, body_text: str) -> ProcedureAST:
    """Public entry: parse a procedure body string into a ProcedureAST."""
    parser = StatementParser(name)
    lines = body_text.split("\n") if body_text else []
    try:
        body_nodes, _inline_unsup = parser.parse_body(lines)
    except RecursionError:
        body_nodes = [RawStatement(source_line="", text="<too deeply nested>",
                                   reason="parser recursion limit")]
        _inline_unsup = []
    ast = ProcedureAST(
        name=name,
        params=params,
        return_type=return_type,
        kind=kind,
        body=body_nodes,
        labels=[n.name for n in body_nodes if isinstance(n, LabelDef)],
    )
    ast.unsupported_lines = collect_unsupported(body_nodes)
    return ast
