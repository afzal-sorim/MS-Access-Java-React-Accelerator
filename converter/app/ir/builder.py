"""IR Builder - transforms raw extraction JSON into ApplicationIR model instances.

This is the bridge between the extractor's raw JSON output and the canonical
intermediate representation. All downstream processing uses this IR.
"""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Optional

from .models import (
    ApplicationIR, TableIR, ColumnIR, IndexIR, RelationshipIR,
    QueryIR, QueryKind, FormIR, ControlIR, ReportIR, ReportGroupIR,
    MacroIR, MacroActionIR, VbaModuleIR, VbaProcedureIR,
    BusinessRuleIR, ExternalDependencyIR, ObjectSupport, SupportStatus,
    CoverageReport, StartupConfigIR, TableRole, KnowledgeOrigin,
)


class IRBuilder:
    """Transforms raw extraction payload into ApplicationIR."""

    def __init__(self, extraction_path: str | Path):
        self.extraction_path = Path(extraction_path)
        self.raw: dict = {}
        self.warnings: list[str] = []

    def load(self) -> "IRBuilder":
        """Load the extraction JSON file."""
        with open(self.extraction_path, "r", encoding="utf-8") as f:
            self.raw = json.load(f)
        return self

    def build(self) -> ApplicationIR:
        """Build the full ApplicationIR from the raw extraction."""
        if not self.raw:
            raise ValueError("No extraction data loaded. Call load() first.")

        app = ApplicationIR(
            application_name=self._get("database.name", "AccessApplication"),
            source_file=self.raw.get("source_file", ""),
            access_version=self._get("database.access_version"),
            file_format=self._get("database.file_format"),
            split_role=self._detect_split_role(),
            origin_facts=KnowledgeOrigin.FACT,
        )

        # Build tables
        for table_data in self.raw.get("tables", []):
            app.tables.append(self._build_table(table_data))

        # Build relationships
        for rel_data in self.raw.get("relationships", []):
            if not rel_data["name"].startswith("MSys"):  # Skip system relationships
                app.relationships.append(self._build_relationship(rel_data))

        # Build queries
        for query_data in self.raw.get("queries", []):
            app.queries.append(self._build_query(query_data))

        # Build forms
        for form_data in self.raw.get("forms", []):
            app.forms.append(self._build_form(form_data))

        # Build reports
        for report_data in self.raw.get("reports", []):
            app.reports.append(self._build_report(report_data))

        # Build macros
        for macro_data in self.raw.get("macros", []):
            app.macros.append(self._build_macro(macro_data))

        # Build VBA modules
        for module_data in self.raw.get("modules", []):
            app.vba_modules.append(self._build_module(module_data))

        # Build startup config
        app.startup = self._build_startup()

        # Discover external dependencies
        app.external_dependencies = self._discover_external_dependencies()

        # Transfer warnings
        app.warnings = self.raw.get("warnings", [])
        app.warnings.extend(self.warnings)

        return app

    # ---------------------------------------------------------------- helpers

    def _get(self, path: str, default: Any = None) -> Any:
        """Get nested value from raw dict using dot notation."""
        parts = path.split(".")
        value = self.raw
        for part in parts:
            if isinstance(value, dict):
                value = value.get(part)
            else:
                return default
            if value is None:
                return default
        return value

    def _detect_split_role(self) -> str:
        """Detect if this is a frontend, backend, or standalone database."""
        connect = self._get("database.connect")
        if connect:
            return "FRONTEND"

        # Check if any tables are linked
        has_linked = any(t.get("is_linked") for t in self.raw.get("tables", []))
        if has_linked:
            return "FRONTEND"

        # Check if this appears to be a backend (tables only, no forms)
        has_forms = len(self.raw.get("forms", [])) > 0
        has_tables = len(self.raw.get("tables", [])) > 0
        if has_tables and not has_forms:
            return "BACKEND"

        return "STANDALONE"

    # ---------------------------------------------------------------- table

    def _build_table(self, data: dict) -> TableIR:
        """Build TableIR from raw table data."""
        table = TableIR(
            name=data["name"],
            is_linked=data.get("is_linked", False),
            connect_string=data.get("connect"),
            source_table_name=data.get("source_table_name"),
            row_count=data.get("row_count"),
            description=data.get("description"),
            role=self._determine_table_role(data),
        )

        # Build columns
        for col_data in data.get("columns", []):
            table.columns.append(self._build_column(col_data))

        # Build indexes
        for idx_data in data.get("indexes", []):
            table.indexes.append(IndexIR(
                name=idx_data["name"],
                columns=idx_data["columns"],
                primary=idx_data.get("primary", False),
                unique=idx_data.get("unique", False),
            ))

        # Detect external kind for linked tables
        if table.is_linked and table.connect_string:
            table.external_kind = self._detect_external_kind(table.connect_string)

        return table

    def _build_column(self, data: dict) -> ColumnIR:
        """Build ColumnIR from raw column data."""
        return ColumnIR(
            name=data["name"],
            access_type=data.get("access_type", "Unknown"),
            size=data.get("size"),
            precision=data.get("precision"),
            scale=data.get("scale"),
            required=data.get("required", False),
            allow_null=data.get("allow_null", True),
            primary_key=False,  # Set by index analysis
            auto_number=data.get("auto_number", False),
            default_value=data.get("default_value"),
            validation_rule=data.get("validation_rule"),
            validation_text=data.get("validation_text"),
            is_lookup=data.get("is_lookup", False),
            is_multivalue=data.get("is_multivalue", False),
            is_attachment=data.get("is_attachment", False),
            is_calculated=data.get("is_calculated", False),
            calculated_expression=data.get("calculated_expression"),
            is_hyperlink=data.get("is_hyperlink", False),
            description=data.get("description"),
        )

    def _determine_table_role(self, data: dict) -> TableRole:
        """Determine the role of a table based on its structure and usage."""
        name = data["name"].lower()

        # Check for auth tables
        if any(kw in name for kw in ["user", "login", "account", "role", "permission"]):
            return TableRole.AUTH

        # Check for lookup tables (small, reference data)
        row_count = data.get("row_count", 0) or 0
        if row_count <= 50 and not data.get("is_linked"):
            # Check column patterns
            cols = data.get("columns", [])
            if len(cols) <= 5:
                has_name_col = any(c["name"].lower().endswith("name") for c in cols)
                has_id_col = any(c["name"].lower().endswith("id") for c in cols)
                if has_name_col and has_id_col:
                    return TableRole.LOOKUP

        # Check for junction tables (many-to-many)
        cols = data.get("columns", [])
        fk_cols = [c for c in cols if c["name"].lower().endswith("id") and not c.get("auto_number")]
        if len(cols) <= 4 and len(fk_cols) >= 2:
            # Could be a junction table
            return TableRole.JUNCTION

        return TableRole.ENTITY

    def _detect_external_kind(self, connect_string: str) -> str:
        """Detect the type of external data source from connect string."""
        conn_lower = connect_string.lower()

        if "excel" in conn_lower or ".xls" in conn_lower:
            return "EXCEL"
        if "sql server" in conn_lower or "sqloledb" in conn_lower:
            return "SQL_SERVER"
        if "mysql" in conn_lower:
            return "MYSQL"
        if "postgres" in conn_lower:
            return "POSTGRESQL"
        if "odbc" in conn_lower:
            return "ODBC"
        if "text" in conn_lower or ".txt" in conn_lower or ".csv" in conn_lower:
            return "TEXT"
        if ".accdb" in conn_lower or ".mdb" in conn_lower:
            return "ACCESS_BE"

        return "UNKNOWN"

    # ---------------------------------------------------------------- relationship

    def _build_relationship(self, data: dict) -> RelationshipIR:
        """Build RelationshipIR from raw relationship data."""
        return RelationshipIR(
            name=data["name"],
            parent_table=data["parent_table"],
            child_table=data["child_table"],
            parent_columns=data["parent_columns"],
            child_columns=data["child_columns"],
            enforce_integrity=data.get("enforce_integrity", False),
            cascade_update=data.get("cascade_update", False),
            cascade_delete=data.get("cascade_delete", False),
            one_to_one=data.get("one_to_one", False),
        )

    # ---------------------------------------------------------------- query

    def _build_query(self, data: dict) -> QueryIR:
        """Build QueryIR from raw query data."""
        sql = data.get("sql", "")
        params = data.get("parameters", [])

        query = QueryIR(
            name=data["name"],
            kind=self._classify_query(data.get("dao_type", 0), sql),
            sql=sql,
            parameters=params,
            references_tables=self._extract_table_refs(sql),
            references_queries=self._extract_query_refs(sql),
            access_functions=self._extract_access_functions(sql),
        )

        return query

    def _classify_query(self, dao_type: int, sql: str) -> QueryKind:
        """Classify query type based on DAO type and SQL analysis."""
        # DAO QueryDefTypeEnum values
        # 0 = SELECT, 48 = UPDATE, 64 = APPEND, 80 = DELETE, 96 = DDL
        # 16 = CROSSTAB, 32 = UNION, 112 = PASSTHROUGH, 144 = MAKETABLE

        sql_upper = sql.upper().strip()

        if dao_type == 16 or "TRANSFORM" in sql_upper:
            return QueryKind.CROSSTAB
        if dao_type == 32 or "UNION" in sql_upper:
            return QueryKind.UNION
        if dao_type == 112 or sql_upper.startswith("EXEC "):
            return QueryKind.PASS_THROUGH
        if dao_type == 144:
            return QueryKind.MAKE_TABLE
        if dao_type == 64 or sql_upper.startswith("INSERT "):
            return QueryKind.INSERT if "SELECT" not in sql_upper else QueryKind.APPEND
        if dao_type == 48 or sql_upper.startswith("UPDATE "):
            return QueryKind.UPDATE
        if dao_type == 80 or sql_upper.startswith("DELETE "):
            return QueryKind.DELETE
        if any(kw in sql_upper for kw in ["CREATE ", "ALTER ", "DROP "]):
            return QueryKind.DDL
        if "PARAMETERS" in sql_upper:
            return QueryKind.PARAMETER

        return QueryKind.SELECT

    def _extract_table_refs(self, sql: str) -> list[str]:
        """Extract table names referenced in SQL."""
        import re
        # Simple extraction - look for FROM and JOIN clauses
        refs = []
        sql_upper = sql.upper()

        # FROM clause
        from_matches = re.findall(r'\bFROM\s+\[?(\w+)\]?', sql, re.IGNORECASE)
        refs.extend(from_matches)

        # JOIN clauses
        join_matches = re.findall(r'\bJOIN\s+\[?(\w+)\]?', sql, re.IGNORECASE)
        refs.extend(join_matches)

        # INTO clause for make-table
        into_matches = re.findall(r'\bINTO\s+\[?(\w+)\]?', sql, re.IGNORECASE)
        refs.extend(into_matches)

        return list(set(refs))

    def _extract_query_refs(self, sql: str) -> list[str]:
        """Extract query names referenced in SQL (nested queries)."""
        import re
        # Look for subqueries in FROM clauses
        # This is a simplified extraction
        refs = []

        # Find [queryname] patterns that aren't tables
        bracket_refs = re.findall(r'\[([^\]]+)\]', sql)

        # Check if these are queries vs tables
        table_names = {t["name"] for t in self.raw.get("tables", [])}
        for ref in bracket_refs:
            if ref not in table_names:
                refs.append(ref)

        return list(set(refs))

    def _extract_access_functions(self, sql: str) -> list[str]:
        """Extract Access-specific function calls from SQL."""
        import re
        functions = []

        # Common Access functions
        access_funcs = [
            "Nz", "IIf", "DLookup", "DCount", "DSum", "DMax", "DMin", "DAvg",
            "DateDiff", "DatePart", "DateAdd", "DateSerial", "Format",
            "Switch", "Choose", "Partition", "StrConv", "Val", "CStr", "CInt",
        ]

        for func in access_funcs:
            if re.search(rf'\b{func}\s*\(', sql, re.IGNORECASE):
                functions.append(func)

        return list(set(functions))

    # ---------------------------------------------------------------- form

    def _build_form(self, data: dict) -> FormIR:
        """Build FormIR from raw form data."""
        form = FormIR(
            name=data["name"],
            record_source=data.get("record_source"),
            record_source_kind=self._detect_source_kind(data.get("record_source")),
            caption=data.get("caption"),
            is_subform=data.get("is_subform", False),
            parent_links=data.get("parent_links", {}),
            events=data.get("events", {}),
            module_name=data.get("module"),
            tabbed=False,  # Would need to parse source dump
        )

        # Build controls
        for ctrl_data in data.get("controls", []):
            form.controls.append(self._build_control(ctrl_data))

        return form

    def _build_control(self, data: dict) -> ControlIR:
        """Build ControlIR from raw control data."""
        return ControlIR(
            name=data["name"],
            control_type=data.get("control_type", "Unknown"),
            control_source=data.get("control_source"),
            row_source=data.get("row_source"),
            row_source_kind=self._detect_source_kind(data.get("row_source")),
            caption=data.get("caption"),
            format=data.get("format"),
            default_value=data.get("default_value"),
            validation_rule=data.get("validation_rule"),
            visible=data.get("visible", True),
            enabled=data.get("enabled", True),
            locked=data.get("locked", False),
            events=data.get("events", {}),
        )

    def _detect_source_kind(self, source: Optional[str]) -> Optional[str]:
        """Detect if a source is TABLE, QUERY, or SQL."""
        if not source:
            return None

        source_stripped = source.strip()

        # Check if it's a SQL statement
        if source_stripped.upper().startswith(("SELECT", "PARAMETERS")):
            return "SQL"

        # Otherwise assume it's a table or query name
        # We'd need to check against table/query lists to be sure
        return "TABLE"  # Default assumption

    # ---------------------------------------------------------------- report

    def _build_report(self, data: dict) -> ReportIR:
        """Build ReportIR from raw report data."""
        report = ReportIR(
            name=data["name"],
            record_source=data.get("record_source"),
            caption=data.get("caption"),
            module_name=data.get("module"),
        )

        # Build groups
        for group_data in data.get("groups", []):
            report.groups.append(ReportGroupIR(
                expression=group_data.get("expression", ""),
                sort_order=group_data.get("sort_order", "ASC"),
            ))

        # Build controls
        for ctrl_data in data.get("controls", []):
            report.controls.append(self._build_control(ctrl_data))

        report.summary_fields = data.get("summary_fields", [])
        report.subreports = data.get("subreports", [])

        return report

    # ---------------------------------------------------------------- macro

    def _build_macro(self, data: dict) -> MacroIR:
        """Build MacroIR from raw macro data."""
        macro = MacroIR(
            name=data["name"],
            is_autoexec=data.get("is_autoexec", False),
        )

        # Macro actions would be parsed from source_dump if available
        # For now, we leave actions empty as the extractor only captures metadata

        return macro

    # ---------------------------------------------------------------- module

    def _build_module(self, data: dict) -> VbaModuleIR:
        """Build VbaModuleIR from raw module data."""
        module = VbaModuleIR(
            name=data["name"],
            module_type=data.get("module_type", "STANDARD"),
            source=data.get("source", ""),
        )

        # Procedures, references, etc. would be extracted by VBA analyzer
        # This is placeholder for Phase 11

        return module

    # ---------------------------------------------------------------- startup

    def _build_startup(self) -> StartupConfigIR:
        """Build StartupConfigIR from raw startup data."""
        startup_data = self._get("database.startup", {})

        return StartupConfigIR(
            startup_form=startup_data.get("startup_form"),
            startup_macro=startup_data.get("startup_macro"),
            autoexec_present=any(
                m.get("is_autoexec", False) for m in self.raw.get("macros", [])
            ),
            application_title=startup_data.get("application_title"),
            allow_full_menus=startup_data.get("allow_full_menus", True),
        )

    # ---------------------------------------------------------------- external deps

    def _discover_external_dependencies(self) -> list[ExternalDependencyIR]:
        """Discover external dependencies (spec §8).

        Two independent sources:

        1. Linked tables — an external *data* source.
        2. VBA modules — external *automation* (Outlook, Excel, the file
           system, Win32 ``Declare`` statements).

        The VBA half used to be missing entirely: the analyzer detected
        Outlook/Excel usage but nothing fed it into the IR, so a module
        driving Outlook reported zero external dependencies and the
        supportability engine never saw the risk.
        """
        deps = []

        for table in self.raw.get("tables", []):
            if table.get("is_linked"):
                connect = table.get("connect", "")
                kind = self._detect_external_kind(connect) if connect else "UNKNOWN"

                deps.append(ExternalDependencyIR(
                    kind=kind,
                    target=f"Linked table: {table['name']}",
                    connected_table=table["name"],
                    migration_strategy="REVIEW" if kind == "ACCESS_BE" else "MIGRATE",
                    support=SupportStatus.SUPPORTED_WITH_REVIEW,
                    risk="MEDIUM" if kind in ("ACCESS_BE", "SQL_SERVER") else "HIGH",
                ))

        deps.extend(self._discover_vba_external_dependencies())
        return deps

    def _discover_vba_external_dependencies(self) -> list[ExternalDependencyIR]:
        """Extract external automation dependencies from VBA module source."""
        from converter.app.analyzers.vba import (
            EXTERNAL_APP_PATTERNS, EXTERNAL_KIND_MAP, strip_noncode,
        )

        deps: list[ExternalDependencyIR] = []
        seen: set[tuple[str, str]] = set()

        for module_data in self.raw.get("modules", []):
            source = module_data.get("source") or ""
            if not source:
                continue
            name = module_data.get("name", "?")
            code = strip_noncode(source)

            for app, pattern in EXTERNAL_APP_PATTERNS.items():
                if not re.search(pattern, code, re.IGNORECASE):
                    continue
                kind = EXTERNAL_KIND_MAP.get(app, "COM")
                key = (kind, app)
                if key in seen:
                    continue
                seen.add(key)
                deps.append(ExternalDependencyIR(
                    kind=kind,
                    target=f"{app} automation via VBA module {name}",
                    migration_strategy="REVIEW",
                    support=SupportStatus.UNSUPPORTED
                    if app in ("Outlook", "PowerPoint", "WScript", "Shell")
                    else SupportStatus.SUPPORTED_WITH_REVIEW,
                    risk="HIGH",
                ))

            # Win32 API declarations have no modern equivalent.
            if re.search(r'\bDeclare\s+(?:PtrSafe\s+)?(?:Function|Sub)\b', code, re.IGNORECASE):
                if ("DLL", "win32") not in seen:
                    seen.add(("DLL", "win32"))
                    deps.append(ExternalDependencyIR(
                        kind="DLL",
                        target=f"Win32 API declarations (first seen in {name})",
                        migration_strategy="REVIEW",
                        support=SupportStatus.UNSUPPORTED,
                        risk="HIGH",
                    ))

        return deps


def build_ir(extraction_path: str | Path) -> ApplicationIR:
    """Entry point to build ApplicationIR from extraction JSON."""
    return IRBuilder(extraction_path).load().build()
