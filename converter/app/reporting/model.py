"""Semantic report model built from ReportIR (spec section 20).

Spec section 20 is explicit about scope:

    V1 report scope: basic tabular reports, grouping, sorting, totals,
    filters, parameters, PDF output, CSV output.
    Do not promise perfect pixel-level Access report reproduction.
    Represent the report semantically: data source, fields, grouping,
    aggregation, sorting, display rules.

So this module does **not** model Access report sections, twips, or fonts. It
extracts what a modern tabular report actually needs and classifies anything
it cannot faithfully carry over, rather than emitting a report that silently
shows the wrong data (spec sections 61, 71).
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Optional

from ..ir.models import ReportIR, SupportStatus, TableIR
from .sql_translate import (
    SqlParameter,
    to_camel,
    to_snake,
    translate_access_sql,
)

__all__ = [
    "ReportFieldType",
    "ReportField",
    "ReportGroupSpec",
    "ReportTotal",
    "ReportDefinition",
    "build_report_definitions",
]


# Access control types that carry report data.
_BOUND_CONTROLS = {"TextBox", "ComboBox", "ListBox", "CheckBox"}

# Aggregate parsed out of an Access summary expression, e.g. "=Sum([Days])".
_SUMMARY_RE = re.compile(
    r"=\s*(Sum|Count|Avg|Min|Max)\s*\(\s*\[?([A-Za-z_][A-Za-z_0-9 ]*)\]?\s*\)",
    re.IGNORECASE,
)


class ReportFieldType(str, Enum):
    TEXT = "TEXT"
    NUMBER = "NUMBER"
    CURRENCY = "CURRENCY"
    DATE = "DATE"
    BOOLEAN = "BOOLEAN"


@dataclass
class ReportField:
    """One column of the generated report.

    ``key`` is the result-set column label the SQL actually returns, so the
    renderer can read it straight out of the row map.
    """
    key: str
    label: str
    field_type: ReportFieldType = ReportFieldType.TEXT

    @property
    def numeric(self) -> bool:
        return self.field_type in (ReportFieldType.NUMBER, ReportFieldType.CURRENCY)

    @property
    def align(self) -> str:
        if self.numeric:
            return "right"
        if self.field_type in (ReportFieldType.DATE, ReportFieldType.BOOLEAN):
            return "center"
        return "left"


@dataclass
class ReportGroupSpec:
    """A grouping level: break rows whenever this column's value changes."""
    key: str
    label: str
    direction: str = "ASC"


@dataclass
class ReportTotal:
    """An aggregate shown in a group footer and/or the report footer."""
    key: str
    function: str        # SUM | COUNT | AVG | MIN | MAX
    label: str


@dataclass
class ReportDefinition:
    """A fully-resolved, generatable report."""
    name: str                                   # Access report name
    title: str
    endpoint: str                               # URL slug
    method_name: str                            # Java/JS identifier
    sql: str = ""
    parameters: list[SqlParameter] = field(default_factory=list)
    fields: list[ReportField] = field(default_factory=list)
    groups: list[ReportGroupSpec] = field(default_factory=list)
    totals: list[ReportTotal] = field(default_factory=list)
    source: str = ""                            # Access record source
    source_kind: str = "QUERY"                  # TABLE | QUERY
    status: SupportStatus = SupportStatus.SUPPORTED
    blockers: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)
    confidence: float = 1.0

    @property
    def generatable(self) -> bool:
        """True when this report can be emitted into the target project."""
        return self.status != SupportStatus.UNSUPPORTED and bool(self.sql)

    def to_dict(self) -> dict[str, Any]:
        """Serializable form for the migration report (spec section 66)."""
        return {
            "name": self.name,
            "title": self.title,
            "endpoint": self.endpoint,
            "source": self.source,
            "source_kind": self.source_kind,
            "status": self.status.value,
            "confidence": round(self.confidence, 2),
            "fields": [
                {"key": f.key, "label": f.label, "type": f.field_type.value}
                for f in self.fields
            ],
            "groups": [{"key": g.key, "direction": g.direction} for g in self.groups],
            "totals": [
                {"key": t.key, "function": t.function} for t in self.totals
            ],
            "parameters": [
                {
                    "name": p.bind_name,
                    "access_name": p.access_name,
                    "sql_type": p.sql_type,
                    "java_type": p.java_type,
                }
                for p in self.parameters
            ],
            "blockers": list(self.blockers),
            "notes": list(self.notes),
            "sql": self.sql,
        }


# ---------------------------------------------------------------- builder

class ReportDefinitionBuilder:
    """Turns one ReportIR into a ReportDefinition."""

    def __init__(self, app_ir):
        self.app = app_ir
        self._tables = {t.name.lower(): t for t in app_ir.tables}
        self._queries = {q.name.lower(): q for q in app_ir.queries}
        self._table_names = set(self._tables)
        self._query_names = set(self._queries)

    # ------------------------------------------------------------ entry

    def build(self, report: ReportIR) -> ReportDefinition:
        title = (report.caption or self._humanize(report.name)).strip()
        definition = ReportDefinition(
            name=report.name,
            title=title or report.name,
            endpoint=self._slug(report.name),
            method_name=to_camel(self._strip_prefix(report.name)) or "report",
            source=report.record_source or "",
        )

        if not report.record_source:
            definition.status = SupportStatus.UNSUPPORTED
            definition.blockers.append(
                "report has no record source — nothing to query"
            )
            definition.confidence = 0.0
            return definition

        # Resolve the record source, then derive fields from the bound controls.
        self._resolve_source(report, definition)
        self._collect_fields(report, definition)
        self._collect_groups(report, definition)
        self._collect_totals(report, definition)
        self._apply_ordering(definition)
        self._classify(report, definition)
        return definition

    # ------------------------------------------------------------ source

    def _resolve_source(self, report: ReportIR, definition: ReportDefinition) -> None:
        """Produce PostgreSQL for the report's record source."""
        source = (report.record_source or "").strip()

        # An inline SELECT typed straight into the RecordSource property.
        if source.upper().startswith(("SELECT", "PARAMETERS")):
            definition.source_kind = "SQL"
            self._translate(source, definition, declared=None)
            return

        bare = source.strip("[]")

        # A saved query: translate that query's SQL inline (the schema
        # generator does not emit queries as views).
        query = self._queries.get(bare.lower())
        if query is not None:
            definition.source_kind = "QUERY"
            if not (query.sql or "").strip():
                definition.blockers.append(
                    f"record source query [{bare}] has no SQL to translate"
                )
                return
            self._translate(query.sql, definition, declared=query.parameters)
            return

        # A table: build the SELECT ourselves — fully deterministic, no
        # translation risk.
        table = self._tables.get(bare.lower())
        if table is not None:
            definition.source_kind = "TABLE"
            definition.sql = ""   # filled by _collect_fields, which knows the columns
            definition._table = table  # type: ignore[attr-defined]
            return

        definition.blockers.append(
            f"record source [{bare}] matches no extracted table or query"
        )

    def _translate(
        self,
        sql: str,
        definition: ReportDefinition,
        *,
        declared: Optional[list[dict]],
    ) -> None:
        result = translate_access_sql(
            sql,
            known_tables=self._table_names,
            known_queries=self._query_names,
            declared_parameters=declared,
        )
        definition.sql = result.sql
        definition.parameters = list(result.parameters)
        definition.blockers.extend(result.blockers)
        definition.notes.extend(result.notes)
        definition._aliases = set(result.select_aliases)  # type: ignore[attr-defined]

    # ------------------------------------------------------------ fields

    def _collect_fields(self, report: ReportIR, definition: ReportDefinition) -> None:
        """Derive report columns from the report's bound controls."""
        bound = [
            c for c in report.controls
            if c.control_type in _BOUND_CONTROLS
            and c.control_source
            and c.visible
        ]

        # Controls bound to an expression (=Sum(...), =[A] & [B]) are computed
        # in the Access report, not in the query. We cannot evaluate them
        # without a full expression compiler, so they are recorded as notes and
        # skipped rather than rendered wrong.
        expression_controls = [c for c in bound if c.control_source.startswith("=")]
        data_controls = [c for c in bound if not c.control_source.startswith("=")]

        for ctrl in expression_controls:
            # Aggregates are picked up separately as report totals.
            if not _SUMMARY_RE.match(ctrl.control_source.strip()):
                definition.notes.append(
                    f"control {ctrl.name} shows a calculated expression "
                    f"({ctrl.control_source}) — not rendered as a column"
                )

        table: Optional[TableIR] = getattr(definition, "_table", None)

        # A table source: we author the SELECT from the bound columns.
        if definition.source_kind == "TABLE" and table is not None:
            columns = {c.name.lower(): c for c in table.columns}
            selected: list[str] = []
            for ctrl in data_controls:
                col = columns.get(ctrl.control_source.strip("[]").lower())
                if col is None:
                    definition.notes.append(
                        f"control {ctrl.name} is bound to "
                        f"[{ctrl.control_source}], which table {table.name} "
                        "does not define — column skipped"
                    )
                    continue
                key = to_snake(col.name)
                selected.append(key)
                definition.fields.append(
                    ReportField(
                        key=key,
                        label=self._humanize(col.name),
                        field_type=self._type_from_column(col),
                    )
                )
            if not definition.fields:
                # No usable bound control: fall back to the table's own columns
                # so the report still shows its data.
                for col in table.columns:
                    key = to_snake(col.name)
                    selected.append(key)
                    definition.fields.append(
                        ReportField(
                            key=key,
                            label=self._humanize(col.name),
                            field_type=self._type_from_column(col),
                        )
                    )
                definition.notes.append(
                    "report has no bound controls — all columns of "
                    f"{table.name} are included"
                )
            cols = ", ".join(f'"{c}"' for c in selected) or "*"
            definition.sql = f'SELECT {cols} FROM "{to_snake(table.name)}"'
        else:
            # A query/SQL source: the translated SQL already selects the right
            # columns; the field list decides what gets rendered.
            for ctrl in data_controls:
                key = to_snake(ctrl.control_source.strip("[]"))
                definition.fields.append(
                    ReportField(
                        key=key,
                        label=self._humanize(ctrl.control_source.strip("[]")),
                        field_type=self._type_from_source(
                            ctrl, definition, key
                        ),
                    )
                )

        # Access lays labels out above the detail row; when the counts line up,
        # the Nth label is the Nth column's caption. This only affects the
        # header text, never which data is read.
        self._apply_label_captions(report, definition)

        if not definition.fields and not definition.blockers:
            definition.blockers.append(
                "report has no bound controls and no resolvable columns"
            )

    def _apply_label_captions(
        self, report: ReportIR, definition: ReportDefinition
    ) -> None:
        labels = [
            c.caption.strip()
            for c in report.controls
            if c.control_type == "Label" and c.caption and c.caption.strip()
        ]
        if len(labels) == len(definition.fields) and labels:
            for f, caption in zip(definition.fields, labels):
                f.label = caption

    # ------------------------------------------------------------ grouping

    def _collect_groups(self, report: ReportIR, definition: ReportDefinition) -> None:
        valid_keys = {f.key for f in definition.fields}
        for group in report.groups:
            expression = (group.expression or "").strip()
            if not expression:
                continue
            if expression.startswith("="):
                definition.notes.append(
                    f"group level on expression {expression} is not applied — "
                    "only column grouping is supported"
                )
                continue
            key = to_snake(expression.strip("[]"))
            label = self._humanize(expression.strip("[]"))
            if key not in valid_keys:
                # Grouping on a column the report does not display is valid in
                # Access; the group header still shows it. Add it as a field so
                # the value is available to the renderer.
                definition.fields.insert(
                    0, ReportField(key=key, label=label, field_type=ReportFieldType.TEXT)
                )
                valid_keys.add(key)
                definition.notes.append(
                    f"group column {label} was not a visible control — "
                    "included so group headers can be rendered"
                )
            direction = "DESC" if str(group.sort_order).upper().startswith("D") else "ASC"
            definition.groups.append(
                ReportGroupSpec(key=key, label=label, direction=direction)
            )

    def _collect_totals(self, report: ReportIR, definition: ReportDefinition) -> None:
        """Read Access summary expressions into explicit totals."""
        for expression in report.summary_fields:
            m = _SUMMARY_RE.match((expression or "").strip())
            if not m:
                definition.notes.append(
                    f"summary expression {expression} is not a simple "
                    "aggregate — no total generated"
                )
                continue
            func, column = m.group(1).upper(), m.group(2).strip()
            key = to_snake(column)
            definition.totals.append(
                ReportTotal(key=key, function=func, label=self._humanize(column))
            )
            # A total needs its column in the result set.
            if key not in {f.key for f in definition.fields}:
                definition.notes.append(
                    f"total {func}({column}) refers to a column the report does "
                    "not display — total omitted"
                )
                definition.totals.pop()

        # A numeric column under a grouping level is the classic Access
        # group-footer subtotal. Only infer this when the report explicitly
        # groups, and record it as a note so it is never a silent guess.
        if definition.groups and not definition.totals:
            group_keys = {g.key for g in definition.groups}
            for f in definition.fields:
                if f.numeric and f.key not in group_keys:
                    definition.totals.append(
                        ReportTotal(key=f.key, function="SUM", label=f.label)
                    )
            if definition.totals:
                names = ", ".join(t.label for t in definition.totals)
                definition.notes.append(
                    f"subtotals inferred for numeric columns ({names}) because "
                    "the report defines grouping levels"
                )

    def _apply_ordering(self, definition: ReportDefinition) -> None:
        """Wrap the source SQL so report grouping drives row order."""
        if not definition.groups or not definition.sql:
            return
        order = ", ".join(f'"{g.key}" {g.direction}' for g in definition.groups)
        # The source may already carry its own ORDER BY; wrapping makes the
        # report's grouping the outer, authoritative sort.
        definition.sql = (
            f"SELECT * FROM ({definition.sql}) AS report_source ORDER BY {order}"
        )
        definition.notes.append(
            "rows ordered by the report's grouping levels"
        )

    # ------------------------------------------------------------ status

    def _classify(self, report: ReportIR, definition: ReportDefinition) -> None:
        """Assign support status, confidence and reasons (spec sections 12, 49)."""
        if definition.blockers or not definition.sql:
            definition.status = SupportStatus.UNSUPPORTED
            definition.confidence = 0.0
            if not definition.blockers:
                definition.blockers.append("no report SQL could be produced")
            return

        review_reasons: list[str] = []

        if report.subreports:
            review_reasons.append(
                "subreport(s) " + ", ".join(report.subreports) +
                " are not rendered (spec section 20 defers subreports)"
            )
        if report.module_name:
            review_reasons.append(
                f"report VBA module {report.module_name} may alter presentation "
                "at runtime; only the data layout was converted"
            )

        if review_reasons:
            definition.status = SupportStatus.SUPPORTED_WITH_REVIEW
            definition.notes.extend(review_reasons)
            definition.confidence = 0.70
            return

        if definition.source_kind == "TABLE":
            # We authored the SQL from extracted columns: highest confidence.
            definition.status = SupportStatus.SUPPORTED
            definition.confidence = 0.97
            return

        # Query-sourced: SQL was translated, so confidence reflects that.
        definition.status = (
            SupportStatus.SUPPORTED_WITH_TRANSFORMATION
            if definition.parameters or definition.groups
            else SupportStatus.SUPPORTED
        )
        definition.confidence = 0.88 if definition.parameters else 0.92

    # ------------------------------------------------------------ typing

    def _type_from_column(self, column) -> ReportFieldType:
        access = (column.access_type or "").lower()
        if "currency" in access:
            return ReportFieldType.CURRENCY
        if any(k in access for k in ("integer", "byte", "long", "double",
                                     "single", "decimal", "numeric", "number")):
            return ReportFieldType.NUMBER
        if "date" in access or "time" in access:
            return ReportFieldType.DATE
        if "yes/no" in access or "bool" in access or "bit" in access:
            return ReportFieldType.BOOLEAN
        return ReportFieldType.TEXT

    def _type_from_source(self, ctrl, definition: ReportDefinition, key: str) -> ReportFieldType:
        """Infer a query column's type from the schema, then from its name."""
        # Prefer a real column definition when any table declares this column.
        for table in self.app.tables:
            for col in table.columns:
                if to_snake(col.name) == key:
                    return self._type_from_column(col)

        # A control Format property is authoritative for currency/date.
        fmt = (getattr(ctrl, "format", None) or "").lower()
        if "currency" in fmt:
            return ReportFieldType.CURRENCY
        if any(t in fmt for t in ("date", "time")):
            return ReportFieldType.DATE

        # Aggregate aliases produced by the query are numeric.
        if re.search(r"(count|total|sum|amount|qty|quantity|days|num|number)$", key):
            return ReportFieldType.NUMBER
        if re.search(r"(date|time)$", key):
            return ReportFieldType.DATE
        return ReportFieldType.TEXT

    # ------------------------------------------------------------ naming

    @staticmethod
    def _strip_prefix(name: str) -> str:
        return re.sub(r"^(rpt|report)[_\s]*", "", name, flags=re.IGNORECASE) or name

    @classmethod
    def _humanize(cls, name: str) -> str:
        """'rptLeaveSummary' -> 'Leave Summary'; 'total_days' -> 'Total Days'."""
        base = cls._strip_prefix(name)
        spaced = re.sub(r"(?<=[a-z0-9])(?=[A-Z])", " ", base)
        spaced = spaced.replace("_", " ").replace("-", " ")
        return " ".join(w.capitalize() if w.islower() else w
                        for w in spaced.split()).strip() or name

    @classmethod
    def _slug(cls, name: str) -> str:
        return to_snake(cls._strip_prefix(name)).replace("_", "-") or "report"


def build_report_definitions(app_ir) -> list[ReportDefinition]:
    """Build a ReportDefinition for every report in the IR."""
    builder = ReportDefinitionBuilder(app_ir)
    return [builder.build(r) for r in app_ir.reports]
