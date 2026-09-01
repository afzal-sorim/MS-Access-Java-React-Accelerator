"""Report generation entry points (spec section 20).

The report pipeline is split into three modules:

    sql_translate.py   Access SQL -> PostgreSQL, with explicit refusals
    model.py           ReportIR   -> ReportDefinition (semantic model)
    spring_reports.py  ReportDefinition -> Spring Boot report package

This module ties them together and provides the migration-report payload.

Note on history: an earlier version of this file carried its own report model
that read ``ReportIR`` fields which do not exist (``group.field``,
``report.status``, ``header_section``) and would have raised ``AttributeError``
on the first report it saw. It was never wired into a generator. The working
implementation lives in the three modules above.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any, Optional

from .model import (
    ReportDefinition,
    ReportField,
    ReportFieldType,
    ReportGroupSpec,
    ReportTotal,
    build_report_definitions,
)
from .spring_reports import (
    PDF_DEPENDENCY,
    SpringReportGenerator,
    generate_report_sources,
)
from .sql_translate import TranslatedSql, translate_access_sql

__all__ = [
    "PDF_DEPENDENCY",
    "ReportDefinition",
    "ReportField",
    "ReportFieldType",
    "ReportGroupSpec",
    "ReportTotal",
    "SpringReportGenerator",
    "TranslatedSql",
    "build_report_definitions",
    "generate_report_sources",
    "report_migration_summary",
    "translate_access_sql",
    "write_report_manifest",
]


def report_migration_summary(definitions: list[ReportDefinition]) -> dict[str, Any]:
    """Build the reports section of the migration report (spec section 66)."""
    generatable = [d for d in definitions if d.generatable]
    skipped = [d for d in definitions if not d.generatable]

    total = len(definitions)
    coverage = round(100.0 * len(generatable) / total, 1) if total else 0.0
    confidence = (
        round(sum(d.confidence for d in generatable) / len(generatable), 2)
        if generatable else 0.0
    )

    return {
        "total": total,
        "generated": len(generatable),
        "unsupported": len(skipped),
        "coverage_pct": coverage,
        "average_confidence": confidence,
        "reports": [d.to_dict() for d in definitions],
        "unsupported_reports": [
            {"name": d.name, "source": d.source, "blockers": list(d.blockers)}
            for d in skipped
        ],
    }


def write_report_manifest(
    definitions: list[ReportDefinition],
    output_path: str | Path,
) -> dict[str, Any]:
    """Write migration-report/reports.json and return the payload."""
    import json

    summary = report_migration_summary(definitions)
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    return summary
