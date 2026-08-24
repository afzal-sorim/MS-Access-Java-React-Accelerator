"""Report generation package (spec section 20).

Public surface:

    build_report_definitions(app_ir)      -> list[ReportDefinition]
    generate_report_sources(definitions)  -> (java files, needs_pdf_dependency)
    report_migration_summary(definitions) -> migration-report payload
    translate_access_sql(sql)             -> TranslatedSql
"""
from __future__ import annotations

from .model import (
    ReportDefinition,
    ReportField,
    ReportFieldType,
    ReportGroupSpec,
    ReportTotal,
    build_report_definitions,
)
from .report import report_migration_summary, write_report_manifest
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
