"""Access Intermediate Representation (AIR) — the canonical model.

Everything downstream (dependency graph, supportability, generators, reports)
consumes this model. Extractors normalize Access/DAO/COM data into it; the
Access APIs are never referenced past this boundary (spec section 10).
"""
from __future__ import annotations

from enum import Enum
from typing import Any, Optional

from pydantic import BaseModel, Field


# ---------------------------------------------------------------- enums

class SupportStatus(str, Enum):
    SUPPORTED = "SUPPORTED"
    SUPPORTED_WITH_TRANSFORMATION = "SUPPORTED_WITH_TRANSFORMATION"
    SUPPORTED_WITH_REVIEW = "SUPPORTED_WITH_REVIEW"
    UNSUPPORTED = "UNSUPPORTED"
    FAILED_EXTRACTION = "FAILED_EXTRACTION"


class KnowledgeOrigin(str, Enum):
    """Spec section 71: every fact knows where it came from."""
    FACT = "FACT"              # deterministic extraction
    TRANSFORMATION = "TRANSFORMATION"  # deterministic rule application
    INFERENCE = "INFERENCE"    # LLM semantic analysis
    GUESS = "GUESS"            # must never silently become behavior


class QueryKind(str, Enum):
    SELECT = "SELECT"
    PARAMETER = "PARAMETER"
    INSERT = "INSERT"
    UPDATE = "UPDATE"
    DELETE = "DELETE"
    APPEND = "APPEND"          # INSERT ... SELECT
    MAKE_TABLE = "MAKE_TABLE"
    CROSSTAB = "CROSSTAB"
    UNION = "UNION"
    PASS_THROUGH = "PASS_THROUGH"
    DDL = "DDL"
    UNKNOWN = "UNKNOWN"


class TableRole(str, Enum):
    ENTITY = "ENTITY"          # business entity -> full REST API
    LOOKUP = "LOOKUP"          # reference data -> read API + admin UI
    JUNCTION = "JUNCTION"      # many-to-many join table
    INTERNAL = "INTERNAL"      # used by app logic, no direct UI
    SYSTEM = "SYSTEM"          # Access/system table, never converted
    AUTH = "AUTH"              # users/roles -> Spring Security model


# ---------------------------------------------------------------- database

class ColumnIR(BaseModel):
    name: str
    access_type: str                     # raw DAO type name, e.g. "Long Integer"
    sql_type: Optional[str] = None       # resolved PostgreSQL type
    java_type: Optional[str] = None
    size: Optional[int] = None
    precision: Optional[int] = None
    scale: Optional[int] = None
    required: bool = False
    allow_null: bool = True
    primary_key: bool = False
    auto_number: bool = False
    unique: bool = False
    default_value: Optional[str] = None
    validation_rule: Optional[str] = None
    validation_text: Optional[str] = None
    is_lookup: bool = False              # Access lookup field (combo wizard)
    is_multivalue: bool = False
    is_attachment: bool = False
    is_calculated: bool = False
    calculated_expression: Optional[str] = None
    is_hyperlink: bool = False
    is_ole: bool = False
    is_replication_id: bool = False
    description: Optional[str] = None


class IndexIR(BaseModel):
    name: str
    columns: list[str]
    primary: bool = False
    unique: bool = False


class TableIR(BaseModel):
    name: str
    columns: list[ColumnIR] = Field(default_factory=list)
    indexes: list[IndexIR] = Field(default_factory=list)
    row_count: Optional[int] = None
    is_linked: bool = False
    connect_string: Optional[str] = None   # sanitized: never contains PWD
    source_table_name: Optional[str] = None
    external_kind: Optional[str] = None    # ACCESS_BE | SQL_SERVER | EXCEL | TEXT | ODBC | ...
    role: TableRole = TableRole.ENTITY
    description: Optional[str] = None


class RelationshipIR(BaseModel):
    name: str
    parent_table: str
    child_table: str
    parent_columns: list[str]
    child_columns: list[str]
    enforce_integrity: bool = False
    cascade_update: bool = False
    cascade_delete: bool = False
    one_to_one: bool = False


# ---------------------------------------------------------------- queries

class QueryIR(BaseModel):
    name: str
    kind: QueryKind = QueryKind.UNKNOWN
    sql: str = ""
    parameters: list[dict[str, str]] = Field(default_factory=list)  # {"name","type"}
    references_tables: list[str] = Field(default_factory=list)
    references_queries: list[str] = Field(default_factory=list)
    access_functions: list[str] = Field(default_factory=list)  # Nz, IIf, DLookup...
    converted_sql: Optional[str] = None     # PostgreSQL translation
    operation: Optional[str] = None         # target operation, e.g. list query for a form


# ---------------------------------------------------------------- forms

class ControlIR(BaseModel):
    name: str
    control_type: str                     # TextBox, ComboBox, ...
    control_source: Optional[str] = None  # bound field or expression
    row_source: Optional[str] = None      # combo/list source
    row_source_kind: Optional[str] = None  # TABLE | QUERY | VALUE_LIST | SQL
    caption: Optional[str] = None
    format: Optional[str] = None
    default_value: Optional[str] = None
    validation_rule: Optional[str] = None
    visible: bool = True
    enabled: bool = True
    locked: bool = False
    events: dict[str, str] = Field(default_factory=dict)  # event -> handler name


class FormIR(BaseModel):
    name: str
    record_source: Optional[str] = None
    record_source_kind: Optional[str] = None  # TABLE | QUERY
    caption: Optional[str] = None
    is_subform: bool = False
    parent_links: dict[str, str] = Field(default_factory=dict)  # child field -> master field
    controls: list[ControlIR] = Field(default_factory=list)
    events: dict[str, str] = Field(default_factory=dict)
    module_name: Optional[str] = None     # Form_frmX if HasModule
    tabbed: bool = False


# ---------------------------------------------------------------- reports

class ReportGroupIR(BaseModel):
    expression: str
    sort_order: str = "ASC"
    header: bool = True
    footer: bool = False


class ReportIR(BaseModel):
    name: str
    record_source: Optional[str] = None
    caption: Optional[str] = None
    groups: list[ReportGroupIR] = Field(default_factory=list)
    controls: list[ControlIR] = Field(default_factory=list)
    summary_fields: list[str] = Field(default_factory=list)  # =Sum(...) etc.
    module_name: Optional[str] = None
    subreports: list[str] = Field(default_factory=list)


# ---------------------------------------------------------------- macros / vba

class MacroActionIR(BaseModel):
    action: str
    arguments: str = ""
    condition: Optional[str] = None


class MacroIR(BaseModel):
    name: str
    actions: list[MacroActionIR] = Field(default_factory=list)
    is_autoexec: bool = False


class VbaProcedureIR(BaseModel):
    name: str
    kind: str = "SUB"                     # SUB | FUNCTION | EVENT
    signature: str = ""
    body: str = ""
    calls: list[str] = Field(default_factory=list)
    business_rules: list[str] = Field(default_factory=list)  # rule ids extracted


class VbaModuleIR(BaseModel):
    name: str
    module_type: str = "STANDARD"         # STANDARD | FORM | REPORT | CLASS
    source: str = ""
    procedures: list[VbaProcedureIR] = Field(default_factory=list)
    references_com: list[str] = Field(default_factory=list)   # CreateObject targets
    declares_api: list[str] = Field(default_factory=list)     # Declare statements
    uses_external: list[str] = Field(default_factory=list)    # Outlook., Excel., ...


class BusinessRuleIR(BaseModel):
    """Spec section 18 — implicit VBA behavior made explicit and testable."""
    id: str
    name: str
    origin: str                           # module.procedure
    origin_kind: str = "VBA"              # VBA | MACRO | TABLE_VALIDATION | QUERY
    rule_type: str = "CONDITIONAL_ASSIGNMENT"
    condition: Optional[str] = None
    actions: list[str] = Field(default_factory=list)
    else_actions: list[str] = Field(default_factory=list)
    inputs: list[str] = Field(default_factory=list)
    confidence: float = 1.0
    origin_class: KnowledgeOrigin = KnowledgeOrigin.TRANSFORMATION
    test_cases: list[dict[str, Any]] = Field(default_factory=list)


# ---------------------------------------------------------------- dependency / supportability

class ExternalDependencyIR(BaseModel):
    kind: str                             # ACCESS_BACKEND | SQL_SERVER | EXCEL | TEXT | ODBC | OUTLOOK | COM | FILE | DLL | API
    target: str                           # sanitized description, credentials removed
    connected_table: Optional[str] = None
    migration_strategy: str = "REVIEW"
    support: SupportStatus = SupportStatus.SUPPORTED_WITH_REVIEW
    risk: str = "MEDIUM"


class ObjectSupport(BaseModel):
    object: str
    category: str                         # TABLE | QUERY | FORM | REPORT | MACRO | VBA | EXTERNAL
    status: SupportStatus
    complexity: str = "LOW"
    risk: str = "LOW"
    conversion: str = ""                  # strategy id, e.g. SPRING_SERVICE_RULE
    confidence: float = 1.0
    reason: str = ""


class CoverageReport(BaseModel):
    database_coverage: float = 0.0
    query_coverage: float = 0.0
    form_coverage: float = 0.0
    vba_coverage: float = 0.0
    report_coverage: float = 0.0
    macro_coverage: float = 0.0
    external_dependency_coverage: float = 0.0
    overall: float = 0.0
    fully_supported_pct: float = 0.0
    supported_with_review_pct: float = 0.0
    unsupported_pct: float = 0.0


# ---------------------------------------------------------------- application

class StartupConfigIR(BaseModel):
    startup_form: Optional[str] = None
    startup_macro: Optional[str] = None
    autoexec_present: bool = False
    application_title: Optional[str] = None
    allow_full_menus: bool = True


class ApplicationIR(BaseModel):
    application_name: str = "AccessApplication"
    source_file: str = ""
    access_version: Optional[str] = None
    file_format: Optional[str] = None
    split_role: str = "STANDALONE"        # STANDALONE | FRONTEND | BACKEND
    tables: list[TableIR] = Field(default_factory=list)
    relationships: list[RelationshipIR] = Field(default_factory=list)
    queries: list[QueryIR] = Field(default_factory=list)
    forms: list[FormIR] = Field(default_factory=list)
    reports: list[ReportIR] = Field(default_factory=list)
    macros: list[MacroIR] = Field(default_factory=list)
    vba_modules: list[VbaModuleIR] = Field(default_factory=list)
    business_rules: list[BusinessRuleIR] = Field(default_factory=list)
    external_dependencies: list[ExternalDependencyIR] = Field(default_factory=list)
    startup: StartupConfigIR = Field(default_factory=StartupConfigIR)
    references: list[str] = Field(default_factory=list)
    supportability: list[ObjectSupport] = Field(default_factory=list)
    coverage: Optional[CoverageReport] = None
    warnings: list[str] = Field(default_factory=list)
    origin_facts: KnowledgeOrigin = KnowledgeOrigin.FACT

    def table(self, name: str) -> Optional[TableIR]:
        return next((t for t in self.tables if t.name.lower() == name.lower()), None)

    def query(self, name: str) -> Optional[QueryIR]:
        return next((q for q in self.queries if q.name.lower() == name.lower()), None)

    def form(self, name: str) -> Optional[FormIR]:
        return next((f for f in self.forms if f.name.lower() == name.lower()), None)
