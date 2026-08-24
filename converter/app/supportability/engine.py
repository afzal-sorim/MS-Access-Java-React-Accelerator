"""Supportability Engine - classifies objects for conversion feasibility.

Spec section 12: Before generation, classify every object into:
- SUPPORTED
- SUPPORTED_WITH_TRANSFORMATION
- SUPPORTED_WITH_REVIEW
- UNSUPPORTED
- FAILED_EXTRACTION

Each object receives status, complexity, risk, conversion strategy, confidence, and reason.
"""
from __future__ import annotations

from typing import Optional

from ..ir.models import (
    ApplicationIR, TableIR, QueryIR, FormIR, ReportIR, MacroIR, VbaModuleIR,
    ObjectSupport, SupportStatus, QueryKind, TableRole,
)


# Feature support matrices (spec section 62 - MVP scope)
SUPPORTED_TABLE_FEATURES = {
    "basic_columns": True,
    "autonumber": True,
    "primary_key": True,
    "foreign_key": True,
    "indexes": True,
    "validation_rules": True,
    "default_values": True,
    "required_fields": True,
    "lookup_fields": True,  # Supported with transformation
    "hyperlink": False,
    "attachment": False,
    "multivalue": False,
    "calculated": False,
    "ole": False,
    "replication_id": False,
}

SUPPORTED_QUERY_FEATURES = {
    "select": True,
    "parameter": True,
    "insert": True,
    "update": True,
    "delete": True,
    "join": True,
    "aggregate": True,
    "group_by": True,
    "order_by": True,
    "union": False,  # Phase 2
    "crosstab": False,  # Phase 2
    "pass_through": False,
    "make_table": False,
    "ddl": False,
    "nested": True,
    # Access functions
    "nz": True,
    "iif": True,
    "date_functions": True,
    "format": True,
    "dlookup": False,  # Domain aggregates need transformation
    "dcount": False,
    "dsum": False,
}

SUPPORTED_FORM_FEATURES = {
    "bound_form": True,
    "unbound_form": True,
    "textbox": True,
    "combobox": True,
    "checkbox": True,
    "command_button": True,
    "subform": True,
    "tab_control": True,
    "date_picker": True,
    "listbox": True,
    "option_group": True,
    "image": True,
    "webbrowser": False,
    "attachment": False,
    "custom_control": False,
    "form_events": True,
    "control_events": True,
    "conditional_formatting": False,  # Phase 2
}

SUPPORTED_REPORT_FEATURES = {
    "tabular": True,
    "grouping": True,
    "sorting": True,
    "totals": True,
    "parameters": True,
    "subreports": False,  # Phase 2
    "charts": False,
    "vba_module": False,
    "complex_formatting": False,
}

SUPPORTED_MACRO_ACTIONS = {
    "OpenForm": True,
    "OpenReport": True,
    "RunQuery": True,
    "RunCode": True,
    "SetValue": True,
    "SendObject": False,  # Email - needs review
    "TransferSpreadsheet": False,
    "TransferText": False,
    "OutputTo": True,
    "Quit": True,
    "RunMacro": True,
    "GoToRecord": True,
    "ApplyFilter": True,
    "ShowAllRecords": True,
    "MsgBox": True,
    "SetWarnings": True,
}

SUPPORTED_VBA_PATTERNS = {
    "simple_condition": True,
    "loops": True,
    "function_call": True,
    "recordset_dao": True,
    "docmd": True,
    "currentdb": True,
    "forms_bang": True,
    "me_reference": True,
    "error_handling": True,
    "external_automation": False,  # Outlook, Excel, etc.
    "windows_api": False,
    "activex": False,
}


class SupportabilityEngine:
    """Analyzes ApplicationIR and classifies each object's convertibility."""

    def __init__(self, app: ApplicationIR):
        self.app = app
        self.results: list[ObjectSupport] = []

    def analyze(self) -> list[ObjectSupport]:
        """Analyze all objects and return support classifications."""
        self.results = []

        # Analyze tables
        for table in self.app.tables:
            self.results.append(self._analyze_table(table))

        # Analyze queries
        for query in self.app.queries:
            self.results.append(self._analyze_query(query))

        # Analyze forms
        for form in self.app.forms:
            self.results.append(self._analyze_form(form))

        # Analyze reports
        for report in self.app.reports:
            self.results.append(self._analyze_report(report))

        # Analyze macros
        for macro in self.app.macros:
            self.results.append(self._analyze_macro(macro))

        # Analyze VBA modules
        for module in self.app.vba_modules:
            self.results.append(self._analyze_module(module))

        # Analyze external dependencies
        for dep in self.app.external_dependencies:
            self.results.append(self._analyze_external(dep.kind, dep.target))

        return self.results

    # ---------------------------------------------------------------- tables

    def _analyze_table(self, table: TableIR) -> ObjectSupport:
        """Analyze a table's convertibility."""
        issues: list[str] = []
        complexity = "LOW"
        confidence = 0.99

        # Check for unsupported column types
        for col in table.columns:
            if col.is_attachment:
                issues.append(f"Column {col.name}: attachment type unsupported")
            if col.is_multivalue:
                issues.append(f"Column {col.name}: multivalue type unsupported")
            if col.is_ole:
                issues.append(f"Column {col.name}: OLE type unsupported")
            if col.is_calculated and col.calculated_expression:
                issues.append(f"Column {col.name}: calculated field needs review")

        # Check for linked tables
        if table.is_linked:
            if table.external_kind == "ACCESS_BE":
                return ObjectSupport(
                    object=table.name,
                    category="TABLE",
                    status=SupportStatus.SUPPORTED_WITH_REVIEW,
                    complexity="MEDIUM",
                    risk="LOW",
                    conversion="LINKED_ACCESS_TABLE",
                    confidence=0.90,
                    reason="Linked Access backend table - needs migration path",
                )
            else:
                return ObjectSupport(
                    object=table.name,
                    category="TABLE",
                    status=SupportStatus.SUPPORTED_WITH_REVIEW,
                    complexity="HIGH",
                    risk="HIGH",
                    conversion="EXTERNAL_SOURCE",
                    confidence=0.70,
                    reason=f"External {table.external_kind} linked table",
                )

        # Determine status based on issues
        if not issues:
            return ObjectSupport(
                object=table.name,
                category="TABLE",
                status=SupportStatus.SUPPORTED,
                complexity=complexity,
                risk="LOW",
                conversion="JPA_ENTITY",
                confidence=confidence,
                reason="Standard table structure",
            )

        has_unsupported = any("unsupported" in i for i in issues)
        if has_unsupported:
            status = SupportStatus.SUPPORTED_WITH_REVIEW
            complexity = "HIGH"
            confidence = 0.75
        else:
            status = SupportStatus.SUPPORTED_WITH_TRANSFORMATION
            complexity = "MEDIUM"
            confidence = 0.85

        return ObjectSupport(
            object=table.name,
            category="TABLE",
            status=status,
            complexity=complexity,
            risk="MEDIUM" if issues else "LOW",
            conversion="JPA_ENTITY_WITH_WARNINGS",
            confidence=confidence,
            reason="; ".join(issues) if issues else "Standard table",
        )

    # ---------------------------------------------------------------- queries

    def _analyze_query(self, query: QueryIR) -> ObjectSupport:
        """Analyze a query's convertibility."""
        complexity = "LOW"
        issues: list[str] = []
        confidence = 0.98

        # Check query type
        kind_support = {
            QueryKind.SELECT: (True, "SELECT"),
            QueryKind.PARAMETER: (True, "PARAMETER"),
            QueryKind.INSERT: (True, "INSERT"),
            QueryKind.UPDATE: (True, "UPDATE"),
            QueryKind.DELETE: (True, "DELETE"),
            QueryKind.APPEND: (True, "APPEND"),
            QueryKind.UNION: (False, "UNION"),
            QueryKind.CROSSTAB: (False, "CROSSTAB"),
            QueryKind.PASS_THROUGH: (False, "PASS_THROUGH"),
            QueryKind.MAKE_TABLE: (False, "MAKE_TABLE"),
            QueryKind.DDL: (False, "DDL"),
            QueryKind.UNKNOWN: (True, "UNKNOWN"),
        }

        supported, kind_name = kind_support.get(query.kind, (False, "UNKNOWN"))
        if not supported:
            return ObjectSupport(
                object=query.name,
                category="QUERY",
                status=SupportStatus.UNSUPPORTED,
                complexity="HIGH",
                risk="HIGH",
                conversion="MANUAL",
                confidence=0.50,
                reason=f"{kind_name} queries not supported in V1",
            )

        # Check for Access-specific functions that need transformation
        unsupported_funcs = []
        for func in query.access_functions:
            if func in ("DLookup", "DCount", "DSum", "DMax", "DMin", "DAvg"):
                unsupported_funcs.append(func)

        if unsupported_funcs:
            issues.append(f"Domain aggregate functions: {', '.join(unsupported_funcs)}")
            complexity = "MEDIUM"
            confidence = 0.80

        # Check for nested query references
        if query.references_queries:
            complexity = "MEDIUM"
            confidence = 0.90

        # Determine conversion strategy
        if query.kind in (QueryKind.SELECT, QueryKind.PARAMETER):
            conversion = "JPA_QUERY"
        elif query.kind in (QueryKind.INSERT, QueryKind.UPDATE, QueryKind.DELETE):
            conversion = "SERVICE_METHOD"
        else:
            conversion = "REVIEW"

        status = SupportStatus.SUPPORTED if not issues else SupportStatus.SUPPORTED_WITH_TRANSFORMATION

        return ObjectSupport(
            object=query.name,
            category="QUERY",
            status=status,
            complexity=complexity,
            risk="LOW",
            conversion=conversion,
            confidence=confidence,
            reason="; ".join(issues) if issues else "Standard query",
        )

    # ---------------------------------------------------------------- forms

    def _analyze_form(self, form: FormIR) -> ObjectSupport:
        """Analyze a form's convertibility."""
        complexity = "LOW"
        issues: list[str] = []
        confidence = 0.95

        # Check for record source
        if not form.record_source:
            # Unbound form
            complexity = "MEDIUM"
            confidence = 0.85

        # Check controls
        for ctrl in form.controls:
            ctrl_type = ctrl.control_type
            if ctrl_type in ("WebBrowser", "Attachment", "CustomControl"):
                issues.append(f"Control {ctrl.name}: {ctrl_type} not supported")
                complexity = "HIGH"
                confidence = 0.70

        # Check for VBA module
        if form.module_name:
            complexity = "HIGH"
            issues.append("Form has VBA module - requires analysis")
            confidence = 0.75

        # Check events
        if form.events:
            complexity = "MEDIUM"
            confidence = 0.85

        # Subforms add complexity
        subform_controls = [c for c in form.controls if c.control_type == "Subform"]
        if subform_controls:
            complexity = "MEDIUM" if complexity == "LOW" else complexity
            issues.append(f"Form has {len(subform_controls)} subform(s)")

        if any("not supported" in i for i in issues):
            status = SupportStatus.SUPPORTED_WITH_REVIEW
        elif issues:
            status = SupportStatus.SUPPORTED_WITH_TRANSFORMATION
        else:
            status = SupportStatus.SUPPORTED

        return ObjectSupport(
            object=form.name,
            category="FORM",
            status=status,
            complexity=complexity,
            risk="LOW" if complexity == "LOW" else "MEDIUM",
            conversion="REACT_PAGE",
            confidence=confidence,
            reason="; ".join(issues) if issues else "Standard form",
        )

    # ---------------------------------------------------------------- reports

    def _analyze_report(self, report: ReportIR) -> ObjectSupport:
        """Analyze a report's convertibility."""
        complexity = "LOW"
        issues: list[str] = []
        confidence = 0.90

        # Check for record source
        if not report.record_source:
            issues.append("Report has no record source")
            confidence = 0.70

        # Check groups
        if report.groups:
            complexity = "MEDIUM"
            confidence = 0.85

        # Check summary fields
        if report.summary_fields:
            complexity = "MEDIUM"
            confidence = 0.85

        # Check for VBA module
        if report.module_name:
            issues.append("Report has VBA module")
            complexity = "HIGH"
            confidence = 0.70
            status = SupportStatus.SUPPORTED_WITH_REVIEW
        elif issues:
            status = SupportStatus.SUPPORTED_WITH_TRANSFORMATION
        else:
            status = SupportStatus.SUPPORTED

        return ObjectSupport(
            object=report.name,
            category="REPORT",
            status=status,
            complexity=complexity,
            risk="LOW",
            conversion="REPORT_ENDPOINT",
            confidence=confidence,
            reason="; ".join(issues) if issues else "Standard report",
        )

    # ---------------------------------------------------------------- macros

    def _analyze_macro(self, macro: MacroIR) -> ObjectSupport:
        """Analyze a macro's convertibility."""
        complexity = "LOW"
        issues: list[str] = []
        confidence = 0.85

        # Check for AutoExec
        if macro.is_autoexec:
            complexity = "MEDIUM"
            confidence = 0.80

        # Analyze macro actions
        for action in macro.actions:
            action_name = action.action
            if action_name not in SUPPORTED_MACRO_ACTIONS:
                issues.append(f"Action {action_name} not supported")
                confidence = 0.60
            elif not SUPPORTED_MACRO_ACTIONS[action_name]:
                issues.append(f"Action {action_name} needs review")

        if any("not supported" in i for i in issues):
            status = SupportStatus.SUPPORTED_WITH_REVIEW
        elif issues:
            status = SupportStatus.SUPPORTED_WITH_TRANSFORMATION
        else:
            status = SupportStatus.SUPPORTED

        return ObjectSupport(
            object=macro.name,
            category="MACRO",
            status=status,
            complexity=complexity,
            risk="LOW" if not issues else "MEDIUM",
            conversion="SERVICE_METHOD",
            confidence=confidence,
            reason="; ".join(issues) if issues else "Standard macro",
        )

    # ---------------------------------------------------------------- VBA

    def _analyze_module(self, module: VbaModuleIR) -> ObjectSupport:
        """Analyze a VBA module's convertibility."""
        complexity = "MEDIUM"
        issues: list[str] = []
        confidence = 0.75

        # Check for external references
        if module.uses_external:
            for ext in module.uses_external:
                issues.append(f"Uses external: {ext}")
                complexity = "HIGH"
                confidence = 0.50

        if module.references_com:
            issues.append(f"COM references: {', '.join(module.references_com)}")
            complexity = "HIGH"
            confidence = 0.55

        if module.declares_api:
            issues.append(f"API declarations: {len(module.declares_api)}")
            complexity = "HIGH"
            confidence = 0.45

        # Form/report modules are analyzed with their parent objects
        if module.module_type in ("FORM", "REPORT"):
            return ObjectSupport(
                object=module.name,
                category="VBA",
                status=SupportStatus.SUPPORTED_WITH_TRANSFORMATION,
                complexity=complexity,
                risk="MEDIUM",
                conversion="SPRING_SERVICE",
                confidence=confidence,
                reason=f"{module.module_type} module - analyzed with parent",
            )

        # Standard modules
        if issues:
            if any("external" in i.lower() or "api" in i.lower() for i in issues):
                status = SupportStatus.SUPPORTED_WITH_REVIEW
            else:
                status = SupportStatus.SUPPORTED_WITH_TRANSFORMATION
        else:
            status = SupportStatus.SUPPORTED

        return ObjectSupport(
            object=module.name,
            category="VBA",
            status=status,
            complexity=complexity,
            risk="HIGH" if "external" in str(issues).lower() else "MEDIUM",
            conversion="SPRING_SERVICE",
            confidence=confidence,
            reason="; ".join(issues) if issues else "Standard VBA module",
        )

    # ---------------------------------------------------------------- external

    def _analyze_external(self, kind: str, target: str) -> ObjectSupport:
        """Analyze an external dependency."""
        support_map = {
            "ACCESS_BE": (SupportStatus.SUPPORTED_WITH_REVIEW, "MEDIUM", 0.85),
            "SQL_SERVER": (SupportStatus.SUPPORTED_WITH_REVIEW, "MEDIUM", 0.80),
            "EXCEL": (SupportStatus.SUPPORTED_WITH_REVIEW, "HIGH", 0.70),
            "TEXT": (SupportStatus.SUPPORTED_WITH_REVIEW, "MEDIUM", 0.75),
            "CSV": (SupportStatus.SUPPORTED_WITH_REVIEW, "MEDIUM", 0.75),
            "POSTGRESQL": (SupportStatus.SUPPORTED, "LOW", 0.95),
            "MYSQL": (SupportStatus.SUPPORTED_WITH_REVIEW, "MEDIUM", 0.85),
            "ODBC": (SupportStatus.SUPPORTED_WITH_REVIEW, "HIGH", 0.65),
            "UNKNOWN": (SupportStatus.UNSUPPORTED, "HIGH", 0.50),
        }

        status, risk, confidence = support_map.get(kind, support_map["UNKNOWN"])

        return ObjectSupport(
            object=target,
            category="EXTERNAL",
            status=status,
            complexity="HIGH",
            risk=risk,
            conversion="INTEGRATION_LAYER",
            confidence=confidence,
            reason=f"External dependency: {kind}",
        )

    # ---------------------------------------------------------------- coverage

    def calculate_coverage(self) -> dict:
        """Calculate coverage statistics."""
        if not self.results:
            self.analyze()

        categories = {
            "TABLE": [],
            "QUERY": [],
            "FORM": [],
            "REPORT": [],
            "MACRO": [],
            "VBA": [],
            "EXTERNAL": [],
        }

        for result in self.results:
            categories[result.category].append(result)

        coverage = {}
        for cat, items in categories.items():
            if not items:
                coverage[f"{cat.lower()}_coverage"] = 0.0
                continue

            supported = sum(1 for i in items if i.status in (
                SupportStatus.SUPPORTED,
                SupportStatus.SUPPORTED_WITH_TRANSFORMATION,
            ))
            coverage[f"{cat.lower()}_coverage"] = round(supported / len(items) * 100, 1)

        # Overall
        total = len(self.results)
        if total > 0:
            fully_supported = sum(1 for r in self.results if r.status == SupportStatus.SUPPORTED)
            with_transform = sum(1 for r in self.results if r.status == SupportStatus.SUPPORTED_WITH_TRANSFORMATION)
            with_review = sum(1 for r in self.results if r.status == SupportStatus.SUPPORTED_WITH_REVIEW)
            unsupported = sum(1 for r in self.results if r.status == SupportStatus.UNSUPPORTED)

            coverage["overall"] = round(
                (fully_supported + with_transform + with_review) / total * 100, 1
            )
            coverage["fully_supported_pct"] = round(fully_supported / total * 100, 1)
            coverage["supported_with_review_pct"] = round(
                (with_transform + with_review) / total * 100, 1
            )
            coverage["unsupported_pct"] = round(unsupported / total * 100, 1)

        return coverage


def analyze_supportability(app: ApplicationIR) -> list[ObjectSupport]:
    """Entry point to analyze application supportability."""
    return SupportabilityEngine(app).analyze()
