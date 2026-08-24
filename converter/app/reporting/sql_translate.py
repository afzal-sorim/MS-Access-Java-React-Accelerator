"""Access SQL → PostgreSQL translator for report record sources.

Spec section 16: "Do not perform naive string replacement. Build a query AST or
structured query representation."

This module tokenizes Access SQL and rewrites it token-by-token so that the
result runs against the snake_case schema emitted by the PostgreSQL generator.
It is deliberately conservative: anything it cannot prove it can translate
becomes a *blocker*, and the caller must classify that report UNSUPPORTED
rather than emit SQL that would fail or silently return the wrong rows
(spec sections 19, 61, 71).

Handled deterministically:
  * identifier folding to snake_case, incl. ``[Bracketed Names]``
  * ``&`` string concatenation → ``||``
  * ``[Parameter]`` references → named binds (``:paramName``)
  * ``Nz`` → ``COALESCE``, ``IIf`` → ``CASE WHEN``, ``Switch`` → ``CASE``
  * scalar function renames (``UCase`` → ``UPPER``, ``Len`` → ``LENGTH``, ...)
  * ``SELECT TOP n`` → ``LIMIT n``
  * ``<>`` → ``!=`` (both are valid PostgreSQL; normalized for readability)
  * ``LIKE`` wildcards ``*``/``?`` → ``%``/``_`` inside string literals only
  * Access outer-join keyword forms and parenthesized join chains

Refused (recorded as blockers, never guessed):
  * domain aggregates (``DLookup``/``DCount``/``DSum``/...) — need subquery
    rewriting with knowledge of the domain expression
  * crosstab (``TRANSFORM``/``PIVOT``), ``IN 'external.mdb'`` clauses
  * ``PARAMETERS`` declaring a type the mapper does not know
  * unbalanced quotes/parens (i.e. SQL we failed to tokenize)
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Optional

__all__ = [
    "TranslatedSql",
    "SqlParameter",
    "AccessSqlTranslator",
    "translate_access_sql",
    "to_snake",
    "to_camel",
]


# ---------------------------------------------------------------- naming

def to_snake(name: str) -> str:
    """CamelCase → snake_case.

    Mirrors PostgresSchemaGenerator._to_snake so report SQL addresses the
    exact identifiers the schema generator emitted.
    """
    s1 = re.sub(r"(.)([A-Z][a-z]+)", r"\1_\2", name)
    s2 = re.sub(r"([a-z0-9])([A-Z])", r"\1_\2", s1).lower()
    # Collapse whitespace/punctuation that Access allows in [Bracketed Names]
    s2 = re.sub(r"[^a-z0-9_]+", "_", s2)
    return re.sub(r"_+", "_", s2).strip("_")


def to_camel(name: str) -> str:
    """Any casing → camelCase, for Java/JSON facing names."""
    parts = [p for p in re.split(r"[^A-Za-z0-9]+", to_snake(name)) if p]
    if not parts:
        return "value"
    head, *rest = parts
    out = head + "".join(p.capitalize() for p in rest)
    if out[0].isdigit():
        out = "p" + out
    return out


# ---------------------------------------------------------------- tables

# Access scalar functions that map 1:1 onto a PostgreSQL function name.
SCALAR_FUNCTIONS = {
    "ucase": "UPPER",
    "lcase": "LOWER",
    "len": "LENGTH",
    "trim": "BTRIM",
    "ltrim": "LTRIM",
    "rtrim": "RTRIM",
    "abs": "ABS",
    "sgn": "SIGN",
    "sqr": "SQRT",
    "replace": "REPLACE",
    "left": "LEFT",
    "right": "RIGHT",
    "nz": "COALESCE",
    "cstr": "CAST_TEXT",   # rewritten structurally below
    "clng": "CAST_BIGINT",
    "cint": "CAST_INT",
    "cdbl": "CAST_DOUBLE",
}

# Aggregates pass through unchanged (name is identical in PostgreSQL).
AGGREGATES = {"sum", "count", "avg", "min", "max", "stddev", "variance"}

# Zero-argument / keyword-like Access constructs.
LITERAL_FUNCTIONS = {
    "date": "CURRENT_DATE",
    "now": "CURRENT_TIMESTAMP",
    "time": "CURRENT_TIME",
}

# Access aggregates that Access spells differently from PostgreSQL.
AGGREGATE_RENAMES = {
    "stdev": "STDDEV",
    "var": "VARIANCE",
    "first": None,   # no PostgreSQL equivalent -> blocker
    "last": None,
}

# Refused outright: correct translation needs the domain expression rewritten
# into a correlated subquery, which we will not guess.
DOMAIN_AGGREGATES = {
    "dlookup", "dcount", "dsum", "davg", "dmax", "dmin", "dfirst", "dlast",
    "dstdev", "dvar",
}

# Access PARAMETERS types → (PostgreSQL cast, Java type)
PARAM_TYPES = {
    "long": ("bigint", "Long"),
    "long integer": ("bigint", "Long"),
    "integer": ("integer", "Integer"),
    "short": ("smallint", "Integer"),
    "byte": ("smallint", "Integer"),
    "double": ("double precision", "Double"),
    "single": ("real", "Float"),
    "currency": ("numeric(19,4)", "java.math.BigDecimal"),
    "decimal": ("numeric", "java.math.BigDecimal"),
    "text": ("text", "String"),
    "string": ("text", "String"),
    "char": ("text", "String"),
    "date": ("timestamp", "java.time.LocalDateTime"),
    "datetime": ("timestamp", "java.time.LocalDateTime"),
    "date/time": ("timestamp", "java.time.LocalDateTime"),
    "bit": ("boolean", "Boolean"),
    "yesno": ("boolean", "Boolean"),
    "boolean": ("boolean", "Boolean"),
    "guid": ("uuid", "String"),
}

# Reserved words that must not be snake_cased as if they were identifiers.
SQL_KEYWORDS = {
    "select", "from", "where", "group", "by", "having", "order", "asc", "desc",
    "inner", "left", "right", "outer", "full", "cross", "join", "on", "as",
    "and", "or", "not", "in", "is", "null", "like", "between", "exists",
    "union", "all", "distinct", "distinctrow", "top", "case", "when", "then",
    "else", "end", "cast", "limit", "offset", "true", "false", "insert",
    "update", "delete", "into", "values", "set", "with", "parameters",
}


@dataclass
class SqlParameter:
    """A report parameter surfaced as a named JDBC bind."""
    access_name: str          # as written in Access, e.g. "DeptID"
    bind_name: str            # named-parameter key, e.g. "deptId"
    sql_type: str             # PostgreSQL type, e.g. "bigint"
    java_type: str            # e.g. "Long"
    required: bool = True


@dataclass
class TranslatedSql:
    """Outcome of translating one Access statement."""
    sql: str = ""
    parameters: list[SqlParameter] = field(default_factory=list)
    blockers: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)
    select_aliases: list[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        """True when the SQL is safe to emit into a generated project."""
        return not self.blockers and bool(self.sql.strip())


# ---------------------------------------------------------------- tokenizer

@dataclass
class _Token:
    kind: str   # IDENT | NUMBER | STRING | BRACKET | PUNCT | WS | PARAM
    text: str


class _Tokenizer:
    """Splits Access SQL into tokens, preserving string/bracket boundaries."""

    _NUMBER = re.compile(r"\d+(?:\.\d+)?")
    _IDENT = re.compile(r"[A-Za-z_][A-Za-z_0-9]*")
    _WS = re.compile(r"\s+")

    def __init__(self, sql: str):
        self.sql = sql
        self.i = 0
        self.errors: list[str] = []

    def tokens(self) -> list[_Token]:
        out: list[_Token] = []
        s, n = self.sql, len(self.sql)
        while self.i < n:
            ch = s[self.i]

            # whitespace
            m = self._WS.match(s, self.i)
            if m:
                out.append(_Token("WS", " "))
                self.i = m.end()
                continue

            # line comments
            if s.startswith("--", self.i):
                nl = s.find("\n", self.i)
                self.i = n if nl == -1 else nl
                continue

            # string literal: Access accepts both ' and "
            if ch in ("'", '"'):
                lit, ok = self._read_string(ch)
                if not ok:
                    self.errors.append("unterminated string literal")
                    return out
                out.append(_Token("STRING", lit))
                continue

            # date literal  #1/2/2024#
            if ch == "#":
                end = s.find("#", self.i + 1)
                if end == -1:
                    self.errors.append("unterminated date literal (#)")
                    return out
                out.append(_Token("DATE", s[self.i + 1:end]))
                self.i = end + 1
                continue

            # [Bracketed Name] or [Parameter]
            if ch == "[":
                end = s.find("]", self.i + 1)
                if end == -1:
                    self.errors.append("unterminated [bracketed identifier]")
                    return out
                out.append(_Token("BRACKET", s[self.i + 1:end]))
                self.i = end + 1
                continue

            m = self._NUMBER.match(s, self.i)
            if m:
                out.append(_Token("NUMBER", m.group(0)))
                self.i = m.end()
                continue

            m = self._IDENT.match(s, self.i)
            if m:
                out.append(_Token("IDENT", m.group(0)))
                self.i = m.end()
                continue

            # multi-char operators
            for op in ("<>", "<=", ">=", "!=", "||"):
                if s.startswith(op, self.i):
                    out.append(_Token("PUNCT", op))
                    self.i += len(op)
                    break
            else:
                out.append(_Token("PUNCT", ch))
                self.i += 1
        return out

    def _read_string(self, quote: str) -> tuple[str, bool]:
        """Read a quoted literal, honouring doubled-quote escapes."""
        s, n = self.sql, len(self.sql)
        j = self.i + 1
        buf: list[str] = []
        while j < n:
            c = s[j]
            if c == quote:
                if j + 1 < n and s[j + 1] == quote:   # escaped quote
                    buf.append(quote)
                    j += 2
                    continue
                self.i = j + 1
                return "".join(buf), True
            buf.append(c)
            j += 1
        return "".join(buf), False


# ---------------------------------------------------------------- translator

class AccessSqlTranslator:
    """Translates one Access SELECT statement into PostgreSQL.

    ``known_tables`` lets the translator distinguish a table reference from a
    bare column, and a ``[Bracket]`` that names a saved query (unsupported as
    an inline source) from one that names a parameter.
    """

    _PARAMETERS_RE = re.compile(r"^\s*PARAMETERS\s+(.*?);", re.IGNORECASE | re.DOTALL)
    _TOP_RE = re.compile(r"\bTOP\s+(\d+)\b", re.IGNORECASE)

    def __init__(
        self,
        sql: str,
        *,
        known_tables: Optional[set[str]] = None,
        known_queries: Optional[set[str]] = None,
        declared_parameters: Optional[list[dict]] = None,
    ):
        self.raw = sql or ""
        self.known_tables = {t.lower() for t in (known_tables or set())}
        self.known_queries = {q.lower() for q in (known_queries or set())}
        self.declared = declared_parameters or []
        self.blockers: list[str] = []
        self.notes: list[str] = []
        self._params: dict[str, SqlParameter] = {}
        # Identifiers introduced by AS aliases -- these must NOT be folded to
        # snake_case as if they were source columns, and they are what the
        # report's field list keys off.
        self._aliases: list[str] = []

    # ------------------------------------------------------------ public

    def translate(self) -> TranslatedSql:
        sql = self.raw.strip()
        if not sql:
            return TranslatedSql(blockers=["report has no record source SQL"])

        # Refuse constructs we will not guess at, before any rewriting.
        self._reject_unsupported_shapes(sql)

        # PARAMETERS ... ; prologue is metadata, not part of the statement.
        sql, declared = self._strip_parameters_clause(sql)
        for name, type_name in declared:
            self._register_parameter(name, type_name)

        # Parameters can also be declared out-of-band by the extractor (DAO).
        for p in self.declared:
            if isinstance(p, dict) and p.get("name"):
                self._register_parameter(p["name"], p.get("type"))

        # Access ends statements with ';' -- drop it so we can append LIMIT.
        sql = sql.rstrip().rstrip(";").rstrip()

        # SELECT TOP n  ->  ... LIMIT n
        sql, limit = self._extract_top(sql)

        tokenizer = _Tokenizer(sql)
        tokens = tokenizer.tokens()
        if tokenizer.errors:
            for err in tokenizer.errors:
                self.blockers.append(f"could not parse Access SQL: {err}")
            return self._result("")

        out = self._rewrite(tokens)

        if limit is not None:
            out = f"{out} LIMIT {limit}"

        return self._result(out)

    # ------------------------------------------------------------ guards

    def _reject_unsupported_shapes(self, sql: str) -> None:
        """Record blockers for whole-statement shapes we refuse to translate."""
        upper = sql.upper()

        if re.search(r"^\s*TRANSFORM\b", upper) or re.search(r"\bPIVOT\b", upper):
            self.blockers.append(
                "crosstab query (TRANSFORM/PIVOT) — needs manual pivot design"
            )
        if re.search(r"\bIN\s+['\"][^'\"]*\.(MDB|ACCDB)['\"]", upper):
            self.blockers.append(
                "query reads from an external Access file (IN '<file>') — "
                "migrate that data source first"
            )
        if re.search(r"^\s*(INSERT|UPDATE|DELETE)\b", upper):
            self.blockers.append(
                "record source is an action query — reports must read, not write"
            )
        if re.search(r"\bINTO\b", upper) and re.search(r"^\s*SELECT", upper):
            self.blockers.append(
                "make-table query (SELECT ... INTO) is not a valid report source"
            )
        # Detect domain aggregates up front for a clearer message.
        for fn in sorted(DOMAIN_AGGREGATES):
            if re.search(rf"\b{fn}\s*\(", sql, re.IGNORECASE):
                self.blockers.append(
                    f"domain aggregate {fn.upper()}() must be rewritten as a "
                    "subquery — not translated automatically"
                )

    def _strip_parameters_clause(self, sql: str) -> tuple[str, list[tuple[str, str]]]:
        """Pull the ``PARAMETERS name Type, ...;`` prologue off the statement."""
        m = self._PARAMETERS_RE.match(sql)
        if not m:
            return sql, []

        decls: list[tuple[str, str]] = []
        body = m.group(1)
        for chunk in self._split_top_level(body, ","):
            chunk = chunk.strip()
            if not chunk:
                continue
            # e.g. "DeptID Long"  |  "[Start Date] DateTime"
            pm = re.match(r"^\[([^\]]+)\]\s+(.*)$", chunk) or \
                 re.match(r"^(\S+)\s+(.*)$", chunk)
            if not pm:
                self.blockers.append(f"unparsable PARAMETERS declaration: {chunk!r}")
                continue
            decls.append((pm.group(1).strip(), pm.group(2).strip()))

        return sql[m.end():].strip(), decls

    @staticmethod
    def _split_top_level(text: str, sep: str) -> list[str]:
        """Split on ``sep`` ignoring separators inside quotes/brackets/parens."""
        parts, buf, depth = [], [], 0
        quote: Optional[str] = None
        for ch in text:
            if quote:
                buf.append(ch)
                if ch == quote:
                    quote = None
                continue
            if ch in ("'", '"'):
                quote = ch
                buf.append(ch)
                continue
            if ch in "([":
                depth += 1
            elif ch in ")]":
                depth -= 1
            if ch == sep and depth <= 0:
                parts.append("".join(buf))
                buf = []
                continue
            buf.append(ch)
        parts.append("".join(buf))
        return parts

    def _extract_top(self, sql: str) -> tuple[str, Optional[int]]:
        """``SELECT TOP 10 ...`` → (``SELECT ...``, 10)."""
        m = self._TOP_RE.search(sql)
        if not m:
            return sql, None
        if re.search(r"\bTOP\s+\d+\s+PERCENT\b", sql, re.IGNORECASE):
            self.blockers.append("TOP n PERCENT has no direct PostgreSQL form")
            return sql, None
        n = int(m.group(1))
        self.notes.append(f"SELECT TOP {n} translated to LIMIT {n}")
        return (sql[:m.start()] + sql[m.end():]), n

    # ------------------------------------------------------------ params

    def _register_parameter(self, access_name: str, type_name: Optional[str]) -> SqlParameter:
        """Map an Access parameter to a named bind, deduplicating by bind name."""
        bind = to_camel(access_name)
        if bind in self._params:
            return self._params[bind]

        key = (type_name or "").strip().lower()
        sql_type, java_type = PARAM_TYPES.get(key, ("", ""))
        if not sql_type:
            if key:
                self.notes.append(
                    f"parameter {access_name}: unmapped Access type {type_name!r}, "
                    "bound as text"
                )
            else:
                self.notes.append(
                    f"parameter {access_name}: no declared type, bound as text"
                )
            sql_type, java_type = "text", "String"

        param = SqlParameter(
            access_name=access_name,
            bind_name=bind,
            sql_type=sql_type,
            java_type=java_type,
        )
        self._params[bind] = param
        return param

    # ------------------------------------------------------------ rewrite

    def _rewrite(self, tokens: list[_Token]) -> str:
        """Walk tokens, emitting PostgreSQL text."""
        out: list[str] = []
        i = 0
        n = len(tokens)
        # Track whether we are in the SELECT list (to collect aliases) and
        # whether the previous meaningful token was `AS`.
        prev_kw: Optional[str] = None

        while i < n:
            tok = tokens[i]

            if tok.kind == "WS":
                if out and not out[-1].endswith(" "):
                    out.append(" ")
                i += 1
                continue

            if tok.kind == "STRING":
                out.append(self._string_literal(tok.text, out))
                prev_kw = None
                i += 1
                continue

            if tok.kind == "DATE":
                out.append(f"TIMESTAMP '{tok.text}'")
                prev_kw = None
                i += 1
                continue

            if tok.kind == "NUMBER":
                out.append(tok.text)
                prev_kw = None
                i += 1
                continue

            if tok.kind == "BRACKET":
                consumed = self._emit_bracket(tok.text, tokens, i, out, prev_kw)
                i += consumed
                prev_kw = None
                continue

            if tok.kind == "IDENT":
                consumed = self._emit_ident(tokens, i, out, prev_kw)
                low = tok.text.lower()
                prev_kw = low if low in SQL_KEYWORDS else None
                i += consumed
                continue

            # PUNCT
            out.append(self._punct(tok.text, tokens, i))
            prev_kw = None
            i += 1

        text = "".join(out)
        # Tidy spacing: collapse runs, tighten before commas/parens.
        text = re.sub(r"\s+", " ", text).strip()
        text = re.sub(r"\s+,", ",", text)
        text = re.sub(r"\(\s+", "(", text)
        text = re.sub(r"\s+\)", ")", text)
        return text

    def _string_literal(self, value: str, out: list[str]) -> str:
        """Emit a quoted literal, converting LIKE wildcards where applicable."""
        # Access uses * and ? as LIKE wildcards; PostgreSQL uses % and _.
        # Only rewrite when this literal is the operand of LIKE, otherwise a
        # legitimate '*' in data would be corrupted.
        tail = "".join(out[-6:]).upper()
        if re.search(r"\bLIKE\s*$", tail):
            value = value.replace("%", r"\%").replace("_", r"\_")
            value = value.replace("*", "%").replace("?", "_")
            # Access [A-Z] char classes are not supported by LIKE.
            if "[" in value:
                self.blockers.append(
                    "LIKE pattern uses an Access character class ([...]) — "
                    "needs a regular expression rewrite"
                )
        escaped = value.replace("'", "''")
        return f"'{escaped}'"

    def _emit_bracket(
        self,
        name: str,
        tokens: list[_Token],
        i: int,
        out: list[str],
        prev_kw: Optional[str],
    ) -> int:
        """Emit a ``[Bracketed]`` token: parameter, qualified name, or column."""
        # Forms!/Reports! references cannot be resolved server-side.
        next_meaningful = i + 1
        while next_meaningful < len(tokens) and tokens[next_meaningful].kind == "WS":
            next_meaningful += 1
        is_access_ui_reference = (
            name.lower() in {"forms", "reports"}
            and next_meaningful < len(tokens)
            and tokens[next_meaningful].kind == "PUNCT"
            and tokens[next_meaningful].text == "!"
        )
        if "!" in name or name.lower().startswith(("forms.", "reports.")) or is_access_ui_reference:
            self.blockers.append(
                f"record source references the Access UI ([{name}]) — "
                "value must be passed in as a report parameter"
            )
            return 1

        # A bracketed name that matches a declared parameter is a bind.
        bind = to_camel(name)
        if bind in self._params:
            out.append(f":{bind}")
            return 1

        # A bracketed name matching a saved query is a nested source.
        if name.lower() in self.known_queries:
            self.blockers.append(
                f"record source depends on saved query [{name}] — "
                "nested query sources are not inlined"
            )
            return 1

        # Dotted bracket, e.g. [Order Details].[Unit Price]
        if "." in name:
            parts = [to_snake(p) for p in name.split(".")]
            out.append(".".join(f'"{p}"' for p in parts))
            return 1

        # A bracket immediately followed by `.` is a qualifier.
        if name.lower() in self.known_tables:
            out.append(f'"{to_snake(name)}"')
            return 1

        # Otherwise: undeclared [Name] in a WHERE/HAVING position is Access's
        # implicit parameter prompt. Treat it as a parameter -- that is the
        # documented Access behavior, and leaving it as a column would produce
        # a query that fails at runtime.
        if self._looks_like_predicate_position(out):
            param = self._register_parameter(name, None)
            self.notes.append(
                f"[{name}] treated as an implicit report parameter "
                "(Access would prompt for it)"
            )
            out.append(f":{param.bind_name}")
            return 1

        out.append(f'"{to_snake(name)}"')
        return 1

    @staticmethod
    def _looks_like_predicate_position(out: list[str]) -> bool:
        """True if the emitted text so far ends in a comparison operator."""
        tail = "".join(out[-4:]).rstrip().upper()
        return bool(re.search(r"(=|<>|!=|<|>|<=|>=|LIKE|IN|BETWEEN|AND|OR)\s*$", tail))

    def _emit_ident(
        self,
        tokens: list[_Token],
        i: int,
        out: list[str],
        prev_kw: Optional[str],
    ) -> int:
        """Emit an identifier or function call. Returns tokens consumed."""
        tok = tokens[i]
        word = tok.text
        low = word.lower()

        # Keywords are never function names.  In particular, Access permits
        # parenthesized JOIN chains immediately after FROM, which must not be
        # misclassified as a fictitious FROM() call.
        if low in SQL_KEYWORDS and low != "cast":
            out.append(word.upper())
            return 1

        # Is this a function call?  IDENT followed by optional WS then '('
        j = i + 1
        while j < len(tokens) and tokens[j].kind == "WS":
            j += 1
        is_call = j < len(tokens) and tokens[j].kind == "PUNCT" and tokens[j].text == "("

        if is_call:
            return self._emit_call(tokens, i, j, out)

        # Zero-arg Access literals used bare: Date, Now, Time
        if low in LITERAL_FUNCTIONS:
            out.append(LITERAL_FUNCTIONS[low])
            return 1

        # Keywords pass through upper-cased.
        if low in SQL_KEYWORDS:
            # Access spells the inner-join-less FROM list fine; normalize case.
            out.append(word.upper())
            return 1

        if low in ("yes", "no") and self._looks_like_predicate_position(out):
            out.append("TRUE" if low == "yes" else "FALSE")
            return 1

        # An identifier right after AS is an output alias: keep it stable and
        # record it so the report field list can bind to it.
        if prev_kw == "as":
            alias = to_snake(word)
            self._aliases.append(alias)
            out.append(f'"{alias}"')
            return 1

        # Plain identifier: table or column reference → snake_case, quoted.
        out.append(f'"{to_snake(word)}"')
        return 1

    def _emit_call(self, tokens: list[_Token], i: int, paren: int, out: list[str]) -> int:
        """Emit a function call. Returns the number of tokens consumed."""
        name = tokens[i].text
        low = name.lower()

        # Locate the matching close paren so we can rewrite argument-wise.
        args, end = self._read_call_args(tokens, paren)
        consumed = end - i + 1

        if low in DOMAIN_AGGREGATES:
            # Already recorded as a blocker in _reject_unsupported_shapes;
            # emit a placeholder so tokenizing continues.
            out.append("NULL")
            return consumed

        if low in AGGREGATE_RENAMES:
            target = AGGREGATE_RENAMES[low]
            if target is None:
                self.blockers.append(
                    f"aggregate {name}() has no PostgreSQL equivalent"
                )
                out.append("NULL")
                return consumed
            out.append(f"{target}({self._join_args(args)})")
            return consumed

        if low == "iif":
            if len(args) != 3:
                self.blockers.append(f"IIf() expects 3 arguments, found {len(args)}")
                out.append("NULL")
                return consumed
            cond, t, f = (self._rewrite(a) for a in args)
            out.append(f"CASE WHEN {cond} THEN {t} ELSE {f} END")
            return consumed

        if low == "switch":
            if len(args) < 2 or len(args) % 2 != 0:
                self.blockers.append(
                    "Switch() expects an even number of condition/value arguments"
                )
                out.append("NULL")
                return consumed
            pieces = []
            rendered = [self._rewrite(a) for a in args]
            for k in range(0, len(rendered), 2):
                pieces.append(f"WHEN {rendered[k]} THEN {rendered[k + 1]}")
            out.append("CASE " + " ".join(pieces) + " END")
            return consumed

        if low == "choose":
            # Choose(idx, a, b, ...) -> CASE idx WHEN 1 THEN a ...
            if len(args) < 2:
                self.blockers.append("Choose() expects an index and at least one value")
                out.append("NULL")
                return consumed
            rendered = [self._rewrite(a) for a in args]
            idx, values = rendered[0], rendered[1:]
            whens = " ".join(
                f"WHEN {k + 1} THEN {v}" for k, v in enumerate(values)
            )
            out.append(f"CASE {idx} {whens} END")
            return consumed

        if low == "mid":
            # Mid(s, start[, len]) -> SUBSTRING(s FROM start FOR len)
            rendered = [self._rewrite(a) for a in args]
            if len(rendered) == 2:
                out.append(f"SUBSTRING({rendered[0]} FROM {rendered[1]})")
            elif len(rendered) == 3:
                out.append(
                    f"SUBSTRING({rendered[0]} FROM {rendered[1]} FOR {rendered[2]})"
                )
            else:
                self.blockers.append("Mid() expects 2 or 3 arguments")
                out.append("NULL")
            return consumed

        if low == "instr":
            rendered = [self._rewrite(a) for a in args]
            if len(rendered) == 2:
                out.append(f"POSITION({rendered[1]} IN {rendered[0]})")
            else:
                self.blockers.append(
                    "InStr() with a start position or compare mode is not translated"
                )
                out.append("NULL")
            return consumed

        if low in ("cstr", "clng", "cint", "cdbl", "ccur"):
            cast_to = {
                "cstr": "text", "clng": "bigint", "cint": "integer",
                "cdbl": "double precision", "ccur": "numeric(19,4)",
            }[low]
            if len(args) != 1:
                self.blockers.append(f"{name}() expects 1 argument")
                out.append("NULL")
                return consumed
            out.append(f"CAST({self._rewrite(args[0])} AS {cast_to})")
            return consumed

        if low in ("year", "month", "day", "hour", "minute", "second"):
            if len(args) != 1:
                self.blockers.append(f"{name}() expects 1 argument")
                out.append("NULL")
                return consumed
            out.append(f"EXTRACT({low.upper()} FROM {self._rewrite(args[0])})")
            return consumed

        if low in ("datediff", "dateadd", "datepart", "format", "partition", "eval"):
            self.blockers.append(
                f"{name}() semantics differ from PostgreSQL — needs explicit review"
            )
            out.append("NULL")
            return consumed

        if low in SCALAR_FUNCTIONS:
            out.append(f"{SCALAR_FUNCTIONS[low]}({self._join_args(args)})")
            return consumed

        if low in AGGREGATES:
            out.append(f"{low.upper()}({self._join_args(args)})")
            return consumed

        if low in ("count",):
            out.append(f"COUNT({self._join_args(args)})")
            return consumed

        # Unknown function: refuse rather than emit something that won't exist.
        self.blockers.append(
            f"unknown function {name}() — no verified PostgreSQL equivalent"
        )
        out.append("NULL")
        return consumed

    def _read_call_args(
        self, tokens: list[_Token], paren: int
    ) -> tuple[list[list[_Token]], int]:
        """Read a call's arguments. Returns (args, index_of_closing_paren)."""
        depth = 0
        args: list[list[_Token]] = []
        cur: list[_Token] = []
        k = paren
        while k < len(tokens):
            t = tokens[k]
            if t.kind == "PUNCT" and t.text == "(":
                depth += 1
                if depth == 1:
                    k += 1
                    continue
            elif t.kind == "PUNCT" and t.text == ")":
                depth -= 1
                if depth == 0:
                    if cur or args:
                        args.append(cur)
                    return args, k
            elif t.kind == "PUNCT" and t.text == "," and depth == 1:
                args.append(cur)
                cur = []
                k += 1
                continue
            cur.append(t)
            k += 1

        self.blockers.append("unbalanced parentheses in Access SQL")
        return args, len(tokens) - 1

    def _join_args(self, args: list[list[_Token]]) -> str:
        return ", ".join(self._rewrite(a) for a in args)

    def _punct(self, ch: str, tokens: list[_Token], i: int) -> str:
        """Translate an operator token."""
        if ch == "&":
            # Access string concatenation. `+` is ambiguous so only & is mapped.
            return " || "
        if ch == "<>":
            return " != "
        if ch == "*":
            # `*` is SELECT-star here; LIKE wildcards live inside literals and
            # are handled in _string_literal.
            return "*"
        if ch in ("=", "<", ">", "<=", ">=", "!="):
            return f" {ch} "
        if ch == ",":
            return ", "
        if ch == ";":
            return ""
        return ch

    # ------------------------------------------------------------ finish

    def _result(self, sql: str) -> TranslatedSql:
        # Deduplicate blockers while preserving order.
        seen: set[str] = set()
        blockers = [b for b in self.blockers if not (b in seen or seen.add(b))]
        return TranslatedSql(
            sql=sql,
            parameters=list(self._params.values()),
            blockers=blockers,
            notes=list(dict.fromkeys(self.notes)),
            select_aliases=list(dict.fromkeys(self._aliases)),
        )


def translate_access_sql(
    sql: str,
    *,
    known_tables: Optional[set[str]] = None,
    known_queries: Optional[set[str]] = None,
    declared_parameters: Optional[list[dict]] = None,
) -> TranslatedSql:
    """Translate one Access statement to PostgreSQL. Never raises."""
    try:
        return AccessSqlTranslator(
            sql,
            known_tables=known_tables,
            known_queries=known_queries,
            declared_parameters=declared_parameters,
        ).translate()
    except Exception as exc:  # defensive: a crash must not fail the whole run
        return TranslatedSql(
            blockers=[f"internal translator error: {type(exc).__name__}: {exc}"]
        )
