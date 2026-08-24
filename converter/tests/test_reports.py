"""Tests for report generation (spec section 20).

Grounded in the real Access fixture the corpus ships (rptLeaveSummary bound to
the parameterized query qryEmployeeLeaveSummary), plus focused unit tests for
the Access SQL translator and the refusal paths that keep the converter from
silently generating wrong reports.
"""
from __future__ import annotations

import re

import pytest

from converter.app.ir.models import (
    ApplicationIR,
    ColumnIR,
    ControlIR,
    IndexIR,
    QueryIR,
    QueryKind,
    ReportGroupIR,
    ReportIR,
    SupportStatus,
    TableIR,
)
from converter.app.reporting.model import (
    ReportFieldType,
    build_report_definitions,
)
from converter.app.reporting.spring_reports import (
    PDF_DEPENDENCY,
    SpringReportGenerator,
    generate_report_sources,
)
from converter.app.reporting.sql_translate import (
    to_camel,
    to_snake,
    translate_access_sql,
)


# ---------------------------------------------------------------- fixtures

# The exact SQL the corpus fixture's qryEmployeeLeaveSummary contains.
LEAVE_SUMMARY_SQL = (
    "PARAMETERS DeptID Long;\n"
    "SELECT d.DepartmentName, e.FirstName & ' ' & e.LastName AS EmployeeName, "
    "Count(l.LeaveID) AS LeaveCount, Sum(l.LeaveDays) AS TotalDays\n"
    "FROM (Employees AS e INNER JOIN Departments AS d "
    "ON e.DepartmentID = d.DepartmentID) INNER JOIN Leaves AS l "
    "ON e.EmployeeID = l.EmployeeID\n"
    "WHERE d.DepartmentID = [DeptID]\n"
    "GROUP BY d.DepartmentName, e.FirstName & ' ' & e.LastName\n"
    "ORDER BY d.DepartmentName;"
)


def _employees_table() -> TableIR:
    return TableIR(
        name="Employees",
        columns=[
            ColumnIR(name="EmployeeID", access_type="Long Integer",
                     primary_key=True, auto_number=True),
            ColumnIR(name="FirstName", access_type="Short Text"),
            ColumnIR(name="LastName", access_type="Short Text"),
            ColumnIR(name="Salary", access_type="Currency"),
            ColumnIR(name="HireDate", access_type="Date/Time"),
            ColumnIR(name="IsActive", access_type="Yes/No"),
        ],
        indexes=[IndexIR(name="PrimaryKey", columns=["EmployeeID"], primary=True)],
    )


def _departments_table() -> TableIR:
    return TableIR(
        name="Departments",
        columns=[
            ColumnIR(name="DepartmentID", access_type="Long Integer",
                     primary_key=True, auto_number=True),
            ColumnIR(name="DepartmentName", access_type="Short Text"),
        ],
    )


def _leaves_table() -> TableIR:
    return TableIR(
        name="Leaves",
        columns=[
            ColumnIR(name="LeaveID", access_type="Long Integer", primary_key=True),
            ColumnIR(name="EmployeeID", access_type="Long Integer"),
            ColumnIR(name="LeaveDays", access_type="Integer"),
        ],
    )


def _text(name: str, source: str) -> ControlIR:
    return ControlIR(name=name, control_type="TextBox", control_source=source)


def _label(name: str, caption: str) -> ControlIR:
    return ControlIR(name=name, control_type="Label", caption=caption)


@pytest.fixture
def leave_summary_app() -> ApplicationIR:
    """The corpus employee-hr shape: a report bound to a parameterized query."""
    return ApplicationIR(
        application_name="EmployeeHr",
        tables=[_employees_table(), _departments_table(), _leaves_table()],
        queries=[
            QueryIR(
                name="qryEmployeeLeaveSummary",
                kind=QueryKind.PARAMETER,
                sql=LEAVE_SUMMARY_SQL,
                parameters=[{"name": "DeptID", "type": "Long Integer"}],
            )
        ],
        reports=[
            ReportIR(
                name="rptLeaveSummary",
                record_source="qryEmployeeLeaveSummary",
                caption="Employee Leave Summary",
                controls=[
                    _label("Label0", "Department"),
                    _label("Label2", "Employee"),
                    _label("Label4", "Leaves"),
                    _label("Label6", "Total Days"),
                    _text("Text1", "DepartmentName"),
                    _text("Text3", "EmployeeName"),
                    _text("Text5", "LeaveCount"),
                    _text("Text7", "TotalDays"),
                ],
            )
        ],
    )


# ---------------------------------------------------------------- naming

class TestNaming:
    """Report identifiers must match the schema generator's snake_case."""

    @pytest.mark.parametrize("raw,expected", [
        ("DepartmentName", "department_name"),
        ("EmployeeID", "employee_id"),
        ("Employees", "employees"),
        ("TotalDays", "total_days"),
        ("Order Details", "order_details"),
        ("HTTPServer", "http_server"),
    ])
    def test_to_snake(self, raw, expected):
        assert to_snake(raw) == expected

    @pytest.mark.parametrize("raw,expected", [
        ("DeptID", "deptId"),
        ("Start Date", "startDate"),
        ("employee_id", "employeeId"),
    ])
    def test_to_camel(self, raw, expected):
        assert to_camel(raw) == expected

    def test_snake_matches_schema_generator(self):
        """Drift here would make every report query a non-existent column."""
        from converter.app.generators.database.postgres import PostgresSchemaGenerator

        for name in ["DepartmentName", "EmployeeID", "LeaveDays", "IsActive"]:
            assert to_snake(name) == PostgresSchemaGenerator._to_snake(name)


# ---------------------------------------------------------------- translator

class TestAccessSqlTranslator:
    """Spec section 16: structured translation, not string replacement."""

    def test_translates_the_real_corpus_query(self):
        result = translate_access_sql(
            LEAVE_SUMMARY_SQL,
            known_tables={"Employees", "Departments", "Leaves"},
            declared_parameters=[{"name": "DeptID", "type": "Long Integer"}],
        )

        assert result.ok, result.blockers
        sql = result.sql

        # & became || and the literal survived intact.
        assert "||" in sql
        assert "&" not in sql
        assert "' '" in sql

        # Identifiers folded to the generated schema's snake_case.
        assert '"department_name"' in sql
        assert '"employees"' in sql
        assert '"department_id"' in sql

        # Aggregates preserved.
        assert "COUNT(" in sql.upper()
        assert "SUM(" in sql.upper()

        # The parameter became a named bind, not an inlined value.
        assert ":deptId" in sql
        assert "[DeptID]" not in sql

    def test_parameter_is_typed_from_the_parameters_clause(self):
        result = translate_access_sql(
            LEAVE_SUMMARY_SQL, known_tables={"Employees", "Departments", "Leaves"}
        )
        assert len(result.parameters) == 1
        param = result.parameters[0]
        assert param.access_name == "DeptID"
        assert param.bind_name == "deptId"
        assert param.sql_type == "bigint"
        assert param.java_type == "Long"

    def test_parameters_clause_is_not_left_in_the_sql(self):
        result = translate_access_sql(LEAVE_SUMMARY_SQL)
        assert "PARAMETERS" not in result.sql.upper()
        assert result.sql.upper().startswith("SELECT")

    def test_select_aliases_are_preserved_verbatim(self):
        """An alias is the result-set label the report reads by."""
        result = translate_access_sql(LEAVE_SUMMARY_SQL)
        assert "employee_name" in result.select_aliases
        assert "leave_count" in result.select_aliases
        assert "total_days" in result.select_aliases

    def test_iif_becomes_case_when(self):
        result = translate_access_sql(
            "SELECT IIf([Salary]>1000,'High','Low') AS Band FROM Employees",
            known_tables={"Employees"},
        )
        assert result.ok, result.blockers
        assert "CASE WHEN" in result.sql
        assert "THEN 'High'" in result.sql
        assert "ELSE 'Low'" in result.sql

    def test_nz_becomes_coalesce(self):
        result = translate_access_sql(
            "SELECT Nz([Salary],0) AS Pay FROM Employees", known_tables={"Employees"}
        )
        assert result.ok, result.blockers
        assert "COALESCE(" in result.sql

    def test_scalar_function_renames(self):
        result = translate_access_sql(
            "SELECT UCase([LastName]) AS U, Len([FirstName]) AS L FROM Employees",
            known_tables={"Employees"},
        )
        assert result.ok, result.blockers
        assert "UPPER(" in result.sql
        assert "LENGTH(" in result.sql

    def test_date_part_extraction(self):
        result = translate_access_sql(
            "SELECT Year([HireDate]) AS Y FROM Employees", known_tables={"Employees"}
        )
        assert result.ok, result.blockers
        assert "EXTRACT(YEAR FROM" in result.sql

    def test_top_becomes_limit(self):
        result = translate_access_sql(
            "SELECT TOP 5 LastName FROM Employees", known_tables={"Employees"}
        )
        assert result.ok, result.blockers
        assert result.sql.rstrip().endswith("LIMIT 5")
        assert "TOP" not in result.sql.upper()

    def test_not_equal_normalized(self):
        result = translate_access_sql(
            "SELECT LastName FROM Employees WHERE Salary <> 0",
            known_tables={"Employees"},
        )
        assert result.ok, result.blockers
        assert "!=" in result.sql
        assert "<>" not in result.sql

    def test_like_wildcards_translated_only_inside_like_literals(self):
        result = translate_access_sql(
            "SELECT LastName FROM Employees WHERE LastName LIKE 'Sm*'",
            known_tables={"Employees"},
        )
        assert result.ok, result.blockers
        assert "'Sm%'" in result.sql

    def test_star_select_is_not_treated_as_a_wildcard(self):
        result = translate_access_sql(
            "SELECT * FROM Employees", known_tables={"Employees"}
        )
        assert result.ok, result.blockers
        assert result.sql.upper().startswith("SELECT *")

    def test_quotes_inside_literals_are_escaped(self):
        result = translate_access_sql(
            "SELECT LastName FROM Employees WHERE LastName = \"O'Brien\"",
            known_tables={"Employees"},
        )
        assert result.ok, result.blockers
        assert "'O''Brien'" in result.sql

    def test_undeclared_bracket_in_predicate_becomes_a_parameter(self):
        """Access prompts for these; a column reference would fail at runtime."""
        result = translate_access_sql(
            "SELECT LastName FROM Employees WHERE DepartmentID = [Enter Dept]",
            known_tables={"Employees"},
        )
        assert result.ok, result.blockers
        assert ":enterDept" in result.sql
        assert [p.bind_name for p in result.parameters] == ["enterDept"]


class TestTranslatorRefusals:
    """Spec section 61: never silently fake behavior."""

    @pytest.mark.parametrize("sql,fragment", [
        ("SELECT DLookup('X','T','1=1') AS V FROM Employees", "domain aggregate"),
        ("TRANSFORM Sum(Amt) SELECT D FROM T PIVOT M", "crosstab"),
        ("SELECT a FROM T IN 'other.mdb'", "external Access file"),
        ("DELETE FROM Employees", "action query"),
        ("SELECT Format([HireDate],'yyyy') AS Y FROM Employees", "Format()"),
        ("SELECT DateDiff('d',[A],[B]) AS D FROM T", "DateDiff()"),
        ("SELECT First([Salary]) AS F FROM Employees", "First()"),
    ])
    def test_refused_constructs_report_blockers(self, sql, fragment):
        result = translate_access_sql(sql, known_tables={"Employees", "T"})
        assert not result.ok
        assert any(fragment.lower() in b.lower() for b in result.blockers), result.blockers

    def test_unknown_function_is_refused_not_passed_through(self):
        result = translate_access_sql(
            "SELECT MyUdf([Salary]) AS V FROM Employees", known_tables={"Employees"}
        )
        assert not result.ok
        assert any("MyUdf" in b for b in result.blockers)

    def test_forms_reference_is_refused(self):
        result = translate_access_sql(
            "SELECT a FROM T WHERE x = [Forms]![frmMain]![txtId]",
            known_tables={"T"},
        )
        assert not result.ok
        assert any("Access UI" in b for b in result.blockers)

    def test_unterminated_string_is_refused(self):
        result = translate_access_sql("SELECT 'abc FROM Employees")
        assert not result.ok
        assert any("could not parse" in b for b in result.blockers)

    def test_nested_saved_query_is_refused(self):
        result = translate_access_sql(
            "SELECT a FROM [qryOther] WHERE b = 1",
            known_queries={"qryOther"},
        )
        assert not result.ok
        assert any("saved query" in b for b in result.blockers)

    def test_translator_never_raises(self):
        for junk in ["", "((((", "SELECT", "'", "#", "SELECT a FROM (SELECT"]:
            result = translate_access_sql(junk)
            assert isinstance(result.blockers, list)


# ---------------------------------------------------------------- model

class TestReportDefinition:
    def test_builds_from_the_real_report(self, leave_summary_app):
        definitions = build_report_definitions(leave_summary_app)
        assert len(definitions) == 1
        d = definitions[0]

        assert d.name == "rptLeaveSummary"
        assert d.title == "Employee Leave Summary"
        assert d.endpoint == "leave-summary"
        assert d.method_name == "leaveSummary"
        assert d.source_kind == "QUERY"
        assert d.generatable
        assert not d.blockers, d.blockers

    def test_fields_come_from_bound_controls_in_order(self, leave_summary_app):
        d = build_report_definitions(leave_summary_app)[0]
        assert [f.key for f in d.fields] == [
            "department_name", "employee_name", "leave_count", "total_days",
        ]

    def test_labels_come_from_the_access_labels(self, leave_summary_app):
        d = build_report_definitions(leave_summary_app)[0]
        assert [f.label for f in d.fields] == [
            "Department", "Employee", "Leaves", "Total Days",
        ]

    def test_aggregate_columns_typed_numeric(self, leave_summary_app):
        d = build_report_definitions(leave_summary_app)[0]
        by_key = {f.key: f for f in d.fields}
        assert by_key["leave_count"].field_type == ReportFieldType.NUMBER
        assert by_key["total_days"].field_type == ReportFieldType.NUMBER
        assert by_key["department_name"].field_type == ReportFieldType.TEXT
        # Numeric columns right-align in both renderers.
        assert by_key["total_days"].align == "right"
        assert by_key["department_name"].align == "left"

    def test_parameter_surfaces_on_the_definition(self, leave_summary_app):
        d = build_report_definitions(leave_summary_app)[0]
        assert len(d.parameters) == 1
        assert d.parameters[0].bind_name == "deptId"
        assert d.parameters[0].java_type == "Long"

    def test_column_types_resolve_from_the_schema(self):
        """A table-sourced report should type from the extracted columns."""
        app = ApplicationIR(
            tables=[_employees_table()],
            reports=[
                ReportIR(
                    name="rptEmployees",
                    record_source="Employees",
                    controls=[
                        _text("t1", "LastName"),
                        _text("t2", "Salary"),
                        _text("t3", "HireDate"),
                        _text("t4", "IsActive"),
                    ],
                )
            ],
        )
        d = build_report_definitions(app)[0]
        types = {f.key: f.field_type for f in d.fields}
        assert types["last_name"] == ReportFieldType.TEXT
        assert types["salary"] == ReportFieldType.CURRENCY
        assert types["hire_date"] == ReportFieldType.DATE
        assert types["is_active"] == ReportFieldType.BOOLEAN

    def test_table_source_sql_is_authored_not_translated(self):
        app = ApplicationIR(
            tables=[_employees_table()],
            reports=[
                ReportIR(
                    name="rptEmployees",
                    record_source="Employees",
                    controls=[_text("t1", "LastName"), _text("t2", "Salary")],
                )
            ],
        )
        d = build_report_definitions(app)[0]
        assert d.source_kind == "TABLE"
        assert d.sql == 'SELECT "last_name", "salary" FROM "employees"'
        assert d.status == SupportStatus.SUPPORTED
        assert d.confidence > 0.95

    def test_grouping_adds_ordering_and_subtotals(self):
        app = ApplicationIR(
            tables=[_employees_table(), _departments_table()],
            reports=[
                ReportIR(
                    name="rptByDept",
                    record_source="Employees",
                    groups=[ReportGroupIR(expression="LastName", sort_order="ASC")],
                    controls=[_text("t1", "LastName"), _text("t2", "Salary")],
                )
            ],
        )
        d = build_report_definitions(app)[0]
        assert [g.key for g in d.groups] == ["last_name"]
        assert "ORDER BY" in d.sql
        assert '"last_name" ASC' in d.sql
        # Numeric non-group column becomes an inferred subtotal, and says so.
        assert [(t.key, t.function) for t in d.totals] == [("salary", "SUM")]
        assert any("subtotals inferred" in n for n in d.notes)

    def test_explicit_summary_field_becomes_a_total(self):
        app = ApplicationIR(
            tables=[_employees_table()],
            reports=[
                ReportIR(
                    name="rptPayroll",
                    record_source="Employees",
                    summary_fields=["=Sum([Salary])"],
                    controls=[_text("t1", "LastName"), _text("t2", "Salary")],
                )
            ],
        )
        d = build_report_definitions(app)[0]
        assert [(t.key, t.function) for t in d.totals] == [("salary", "SUM")]

    def test_total_on_a_hidden_column_is_dropped_with_a_note(self):
        app = ApplicationIR(
            tables=[_employees_table()],
            reports=[
                ReportIR(
                    name="rptPayroll",
                    record_source="Employees",
                    summary_fields=["=Sum([Bonus])"],
                    controls=[_text("t1", "LastName")],
                )
            ],
        )
        d = build_report_definitions(app)[0]
        assert d.totals == []
        assert any("does not display" in n for n in d.notes)

    def test_group_on_hidden_column_is_added_so_headers_render(self):
        app = ApplicationIR(
            tables=[_employees_table()],
            reports=[
                ReportIR(
                    name="rptByHire",
                    record_source="Employees",
                    groups=[ReportGroupIR(expression="HireDate")],
                    controls=[_text("t1", "LastName")],
                )
            ],
        )
        d = build_report_definitions(app)[0]
        assert "hire_date" in [f.key for f in d.fields]
        assert any("group headers" in n for n in d.notes)

    def test_descending_group_direction_is_honoured(self):
        app = ApplicationIR(
            tables=[_employees_table()],
            reports=[
                ReportIR(
                    name="rptByName",
                    record_source="Employees",
                    groups=[ReportGroupIR(expression="LastName", sort_order="DESC")],
                    controls=[_text("t1", "LastName")],
                )
            ],
        )
        d = build_report_definitions(app)[0]
        assert d.groups[0].direction == "DESC"
        assert '"last_name" DESC' in d.sql

    def test_table_report_without_bound_controls_falls_back_to_all_columns(self):
        app = ApplicationIR(
            tables=[_employees_table()],
            reports=[ReportIR(name="rptAll", record_source="Employees")],
        )
        d = build_report_definitions(app)[0]
        assert d.generatable
        assert len(d.fields) == len(_employees_table().columns)
        assert any("no bound controls" in n for n in d.notes)

    def test_hidden_controls_are_excluded(self):
        app = ApplicationIR(
            tables=[_employees_table()],
            reports=[
                ReportIR(
                    name="rptEmployees",
                    record_source="Employees",
                    controls=[
                        _text("t1", "LastName"),
                        ControlIR(name="t2", control_type="TextBox",
                                  control_source="Salary", visible=False),
                    ],
                )
            ],
        )
        d = build_report_definitions(app)[0]
        assert [f.key for f in d.fields] == ["last_name"]


class TestReportClassification:
    """Spec section 12/49: status, confidence, and honest reasons."""

    def test_missing_record_source_is_unsupported(self):
        app = ApplicationIR(reports=[ReportIR(name="rptOrphan")])
        d = build_report_definitions(app)[0]
        assert d.status == SupportStatus.UNSUPPORTED
        assert not d.generatable
        assert d.confidence == 0.0
        assert any("no record source" in b for b in d.blockers)

    def test_unknown_record_source_is_unsupported(self):
        app = ApplicationIR(reports=[ReportIR(name="rptX", record_source="tblGhost")])
        d = build_report_definitions(app)[0]
        assert d.status == SupportStatus.UNSUPPORTED
        assert any("matches no extracted table or query" in b for b in d.blockers)

    def test_untranslatable_query_makes_the_report_unsupported(self):
        app = ApplicationIR(
            tables=[_employees_table()],
            queries=[
                QueryIR(
                    name="qryCrosstab",
                    sql="TRANSFORM Sum(Amt) SELECT D FROM Employees PIVOT M",
                )
            ],
            reports=[
                ReportIR(
                    name="rptCrosstab",
                    record_source="qryCrosstab",
                    controls=[_text("t1", "D")],
                )
            ],
        )
        d = build_report_definitions(app)[0]
        assert d.status == SupportStatus.UNSUPPORTED
        assert not d.generatable
        assert any("crosstab" in b.lower() for b in d.blockers)

    def test_subreport_downgrades_to_review(self):
        app = ApplicationIR(
            tables=[_employees_table()],
            reports=[
                ReportIR(
                    name="rptWithSub",
                    record_source="Employees",
                    subreports=["rptChild"],
                    controls=[_text("t1", "LastName")],
                )
            ],
        )
        d = build_report_definitions(app)[0]
        assert d.status == SupportStatus.SUPPORTED_WITH_REVIEW
        assert d.generatable, "review still generates, it just flags"
        assert any("rptChild" in n for n in d.notes)

    def test_report_vba_module_downgrades_to_review(self):
        app = ApplicationIR(
            tables=[_employees_table()],
            reports=[
                ReportIR(
                    name="rptScripted",
                    record_source="Employees",
                    module_name="Report_rptScripted",
                    controls=[_text("t1", "LastName")],
                )
            ],
        )
        d = build_report_definitions(app)[0]
        assert d.status == SupportStatus.SUPPORTED_WITH_REVIEW
        assert any("VBA module" in n for n in d.notes)

    def test_to_dict_never_leaks_a_none(self, leave_summary_app):
        payload = build_report_definitions(leave_summary_app)[0].to_dict()
        assert payload["name"] == "rptLeaveSummary"
        assert payload["parameters"][0]["name"] == "deptId"
        assert isinstance(payload["blockers"], list)
        assert "sql" in payload


# ---------------------------------------------------------------- spring

class TestSpringReportGenerator:
    def test_generates_the_expected_files(self, leave_summary_app):
        defs = build_report_definitions(leave_summary_app)
        files, needs_pdf = generate_report_sources(defs, base_package="com.acme.hr")

        assert needs_pdf
        assert set(files) == {
            "ReportDefinition.java",
            "ReportRegistry.java",
            "ReportRow.java",
            "ReportData.java",
            "ReportService.java",
            "CsvReportWriter.java",
            "PdfReportWriter.java",
            "ReportController.java",
        }
        for name, source in files.items():
            assert source.startswith("package com.acme.hr.report;"), name

    def test_no_reports_generates_nothing(self):
        files, needs_pdf = generate_report_sources([])
        assert files == {}
        assert needs_pdf is False

    def test_registry_embeds_translated_sql_and_binds(self, leave_summary_app):
        defs = build_report_definitions(leave_summary_app)
        registry = generate_report_sources(defs)[0]["ReportRegistry.java"]

        assert '"rptLeaveSummary"' in registry
        assert '"leave-summary"' in registry
        assert ":deptId" in registry
        # snake_case identifiers, and no leftover Access syntax.
        assert '"department_name"' in registry
        assert "[DeptID]" not in registry
        assert " & " not in registry

    def test_service_uses_named_parameters_not_concatenation(self, leave_summary_app):
        defs = build_report_definitions(leave_summary_app)
        service = generate_report_sources(defs)[0]["ReportService.java"]

        assert "NamedParameterJdbcTemplate" in service
        assert "definition.sql()" in service
        # The SQL must never be built from request values.
        assert 'sql +' not in service
        assert '+ endpoint' not in service.split("ReportNotFoundException")[0]

    def test_unsupported_reports_are_documented_not_registered(self):
        app = ApplicationIR(
            tables=[_employees_table()],
            reports=[
                ReportIR(name="rptGood", record_source="Employees",
                         controls=[_text("t1", "LastName")]),
                ReportIR(name="rptOrphan"),
            ],
        )
        defs = build_report_definitions(app)
        gen = SpringReportGenerator(defs)
        registry = gen.generate()["ReportRegistry.java"]

        assert len(gen.definitions) == 1
        assert len(gen.skipped) == 1
        assert 'register(new ReportDefinition(\n                "rptGood"' in registry
        # The gap is visible in the generated source.
        assert "rptOrphan" in registry
        assert "no record source" in registry

    def test_csv_strategy_omits_the_pdf_writer(self, leave_summary_app):
        defs = build_report_definitions(leave_summary_app)
        files, needs_pdf = generate_report_sources(defs, report_strategy="csv")

        assert needs_pdf is False
        assert "PdfReportWriter.java" not in files
        controller = files["ReportController.java"]
        assert "/pdf" not in controller
        assert "com.lowagie" not in controller

    def test_pdf_dependency_is_pinned_exactly(self):
        assert PDF_DEPENDENCY["version"] == "3.0.5"
        assert not re.match(r"^[\^~]", PDF_DEPENDENCY["version"])

    def test_pdf_writer_uses_the_pinned_openpdf_namespace(self, leave_summary_app):
        """OpenPDF 3.x moved its public API from com.lowagie to org.openpdf."""
        defs = build_report_definitions(leave_summary_app)
        files, _ = generate_report_sources(defs)

        assert "import org.openpdf.text.Document;" in files["PdfReportWriter.java"]
        assert "import org.openpdf.text.DocumentException;" in files["ReportController.java"]
        assert "com.lowagie" not in files["PdfReportWriter.java"]

    def test_generated_sql_text_block_is_escaped(self):
        """A backslash in report SQL must not break the Java text block."""
        app = ApplicationIR(
            tables=[_employees_table()],
            queries=[
                QueryIR(
                    name="qryEscape",
                    sql=r"SELECT LastName FROM Employees WHERE LastName LIKE 'a*'",
                )
            ],
            reports=[
                ReportIR(name="rptEscape", record_source="qryEscape",
                         controls=[_text("t1", "LastName")]),
            ],
        )
        defs = build_report_definitions(app)
        registry = generate_report_sources(defs)[0]["ReportRegistry.java"]
        # Text block delimiters stay balanced.
        assert registry.count('"""') % 2 == 0

    def test_csv_writer_quotes_and_guards_formulas(self, leave_summary_app):
        defs = build_report_definitions(leave_summary_app)
        csv = generate_report_sources(defs)[0]["CsvReportWriter.java"]
        # RFC 4180 quoting plus spreadsheet formula neutralization.
        assert "mustQuote" in csv
        assert "'='" in csv or "== '='" in csv
        assert r'\r\n' in csv
