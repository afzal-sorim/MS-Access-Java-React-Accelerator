"""Access expression parser and multi-target translator (PHASE 6).

Access forms and reports embed expressions in control sources, default
values, and validation rules.  This module:

1. Classifies an expression (simple field reference, known function,
   complex/unsupported).
2. Translates to PostgreSQL, Java, and JSX fragments.
3. Produces a safe JavaScript identifier for use as a React state key.
4. Never emits invalid target syntax — unsupported expressions become
   explicit placeholders or comments.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from enum import Enum
from typing import Optional


class ExprKind(str, Enum):
    FIELD_REF = "FIELD_REF"           # bare column name
    ACCESS_FUNC = "ACCESS_FUNC"        # known built-in
    STRING_LITERAL = "STRING_LITERAL"
    NUMERIC_LITERAL = "NUMERIC_LITERAL"
    COMPLEX = "COMPLEX"                # multi-function, nested, operator exprs
    UNSUPPORTED = "UNSUPPORTED"        # no safe translation


# ---------------------------------------------------------------- known builtins

ACCESS_BUILTINS: dict[str, dict] = {
    # function -> {postgresql, java, js, description}
    "Now()": {
        "postgresql": "CURRENT_TIMESTAMP",
        "java": "java.time.LocalDateTime.now()",
        "js": "new Date().toISOString()",
    },
    "Date()": {
        "postgresql": "CURRENT_DATE",
        "java": "java.time.LocalDate.now()",
        "js": "new Date().toISOString().slice(0, 10)",
    },
    "Time()": {
        "postgresql": "LOCALTIME",
        "java": "java.time.LocalTime.now()",
        "js": "new Date().toISOString().slice(11, 19)",
    },
    "CurrentUser()": {
        "postgresql": "CURRENT_USER",
        "java": "securityContext.getAuthentication().getName()",
        "js": "null /* TODO: replace with auth identity */",
    },
    "Environ(USERNAME)": {
        "postgresql": "CURRENT_USER",
        "java": "System.getenv(\"USERNAME\")",
        "js": "process.env.USERNAME || null",
    },
    "Nz": {
        "description": "Null coalescing — must be expanded per call",
    },
    "IIf": {
        "description": "Inline conditional — must be expanded per call",
    },
    "Format": {
        "description": "Format string differs per locale — needs per-call mapping",
    },
    "DatePart": {
        "description": "Interval constants differ — needs per-call mapping",
    },
}


@dataclass
class TranslatedExpression:
    """Result of translating an Access expression."""
    original: str
    kind: ExprKind
    postgresql: Optional[str] = None
    java: Optional[str] = None
    js: Optional[str] = None
    js_identifier: str = "unknownField"  # safe camelCase key for React state
    is_unsupported: bool = False
    reason: str = ""


def classify(source: str) -> ExprKind:
    """Classify an Access expression string (with or without leading =)."""
    if not source or not source.strip():
        return ExprKind.FIELD_REF

    s = source.strip()
    if s.startswith("="):
        s = s[1:].strip()

    # String literal: ="text"
    if (s.startswith('"') and s.endswith('"')) or (s.startswith("'") and s.endswith("'")):
        return ExprKind.STRING_LITERAL

    # Numeric literal: =2, =3.14
    if re.match(r'^[+-]?(\d+\.?\d*)$', s):
        return ExprKind.NUMERIC_LITERAL

    # Simple identifier (field reference)
    if re.match(r'^[A-Za-z_][A-Za-z0-9_]*$', s):
        return ExprKind.FIELD_REF

    # Known built-in function call (match by root name)
    func_match = re.match(r'^([A-Za-z_][A-Za-z0-9_]*)\s*\(', s)
    if func_match:
        fname = func_match.group(1)
        for key in ACCESS_BUILTINS:
            root = key.split("(")[0]
            if fname.lower() == root.lower():
                return ExprKind.ACCESS_FUNC

    return ExprKind.COMPLEX


def translate(source: str) -> TranslatedExpression:
    """Translate an Access expression into PostgreSQL / Java / JS forms."""
    result = TranslatedExpression(
        original=source,
        kind=classify(source),
        js_identifier=_to_js_identifier(source),
    )

    s = source.strip()
    if s.startswith("="):
        s = s[1:].strip()

    # --- field reference ---
    if result.kind == ExprKind.FIELD_REF:
        result.postgresql = f'"{_to_snake(s)}"'
        result.java = _to_camel(s)
        result.js = f'formData.{_to_camel(s)}'
        return result

    # --- numeric literal ---
    if result.kind == ExprKind.NUMERIC_LITERAL:
        result.postgresql = s
        result.java = s
        result.js = s
        return result

    # --- string literal ---
    if result.kind == ExprKind.STRING_LITERAL:
        inner = s[1:-1].replace("'", "''")
        result.postgresql = f"'{inner}'"
        result.java = f'"{inner}"'
        result.js = f'"{s[1:-1]}"'
        return result

    # --- known built-in ---
    func_name = re.match(r'^([A-Za-z_][A-Za-z0-9_]*)', s)
    if func_name:
        for bkey, mapping in ACCESS_BUILTINS.items():
            root = bkey.split("(")[0]
            if func_name.group(1).lower() == root.lower():
                result.postgresql = mapping.get("postgresql")
                result.java = mapping.get("java")
                result.js = mapping.get("js")
                if "description" in mapping:
                    result.reason = mapping["description"]
                return result

    # --- complex / unsupported ---
    result.is_unsupported = True
    result.reason = f"Access expression could not be translated: {source[:80]}"
    return result


def _to_js_identifier(source: str) -> str:
    """Produce a safe camelCase JS identifier for an Access expression.

    Reused by the React generator so the logic lives in one place.
    """
    from .naming import to_camel

    if not source or not source.strip():
        return "unknownField"

    s = source.strip()
    if s.startswith("="):
        s = s[1:].strip()

    # String literal
    if (s.startswith('"') and s.endswith('"')) or (s.startswith("'") and s.endswith("'")):
        clean = re.sub(r'[^a-zA-Z0-9]', '', s.strip("'\""))
        return f'literal{clean[:20].capitalize()}' if clean else 'literalValue'

    # Numeric literal
    if s.isdigit():
        return f'calculatedField{s}'

    # Simple identifier
    if re.match(r'^[A-Za-z_][A-Za-z0-9_]*$', s):
        return s

    # Known functions -> readable names (lowercase canonical keys)
    _func_names = {
        'currentuser()': 'currentUser',
        'now()': 'currentDateTime',
        'date()': 'currentDate',
        'time()': 'currentTime',
    }
    if s.lower() in _func_names:
        return _func_names[s.lower()]

    # Environ("USERNAME") -> environUsername
    if s.lower().startswith('environ('):
        m = re.search(r'"([^"]*)"', s) or re.search(r"'([^']*)'", s)
        if m and m.group(1):
            return 'environ' + m.group(1).capitalize()
        return 'environValue'

    # GetProperties("X") -> propertyX
    if s.lower().startswith('getproperties('):
        m = re.search(r'"([^"]*)"', s) or re.search(r"'([^']*)'", s)
        if m and m.group(1):
            parts = m.group(1).replace('_', ' ').replace('-', ' ').split()
            return 'property' + ''.join(p.capitalize() for p in parts)
        return 'propertyValue'

    # Extract function name if present
    func_match = re.match(r'([a-zA-Z_]\w*)\s*\(', s)
    if func_match:
        return f'computed{func_match.group(1).capitalize()}'

    # Last resort: sanitize the whole thing
    clean = re.sub(r'[^a-zA-Z0-9_]', '', s)
    if clean and clean[0].isdigit():
        clean = 'field_' + clean
    return to_camel(clean) if clean else 'computedField'


def _to_snake(name: str) -> str:
    from .naming import to_snake
    return to_snake(name)


def _to_camel(name: str) -> str:
    from .naming import to_camel
    return to_camel(name)


# Keys accepted for user-identity defaults, compared case-insensitively.
_USER_DEFAULT_KEYS = (
    'environ("username")',
    "environ('username')",
    'currentuser()',
)


def _is_user_default(expr_lower: str) -> bool:
    return expr_lower in _USER_DEFAULT_KEYS


def translate_postgres_default(source: str, access_type: str) -> Optional[str]:
    """Translate an Access column default to a PostgreSQL DEFAULT clause.

    This is the canonical location for default-value translation;
    the Postgres generator delegates here.
    """
    if not source:
        return None

    stripped = source.strip()

    if stripped.startswith("="):
        expr = stripped[1:].strip()
        expr_lower = expr.lower()
        if _is_user_default(expr_lower):
            return "CURRENT_USER"
        if expr_lower in ('now()', 'date()', 'time()', 'currentdate()'):
            return "CURRENT_TIMESTAMP"
        if expr.startswith('"') and expr.endswith('"'):
            val = expr[1:-1].replace("'", "''")
            return f"'{val}'"
        if expr.startswith("'") and expr.endswith("'"):
            val = expr[1:-1].replace("'", "''")
            return f"'{val}'"
        if re.match(r'^[+-]?(\d+\.?\d*)$', expr):
            return expr
        # Untranslatable expression
        return None

    clean = stripped.strip("'\"")

    if clean.lower() == "true":
        return "TRUE"
    if clean.lower() == "false":
        return "FALSE"
    if clean.lower() in ("now()", "date()", "time()"):
        return "CURRENT_TIMESTAMP"
    if _is_user_default(clean.lower()):
        return "CURRENT_USER"

    if access_type in ("Short Text", "Long Text", "Hyperlink"):
        escaped = clean.replace("'", "''")
        return f"'{escaped}'"

    try:
        float(clean)
        return clean
    except ValueError:
        pass

    escaped = clean.replace("'", "''")
    return f"'{escaped}'"
