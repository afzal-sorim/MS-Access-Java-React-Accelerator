"""Conversion strategy resolver + capability registry (plan §26-27).

Strategy decisions are derived from the IR and dependency graph, never from
object names.  The capability registry records what the converter can actually
convert today; flipping a capability changes behaviour without rewriting the
generator.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Optional


# ---------------------------------------------------------------- capabilities

CAPABILITIES: dict[str, bool] = {
    # VBA constructs
    "VBA_IF": True,
    "VBA_FOR": True,
    "VBA_FOR_EACH": True,
    "VBA_DO_LOOP": True,
    "VBA_SELECT_CASE": True,
    "VBA_WITH": True,
    "VBA_STATIC_STATE": True,
    "VBA_GOTO": True,             # via control-flow bridge; complex flows -> review
    "VBA_ERROR_HANDLING": True,
    # Runtime functions
    "Nz": True,
    "IsNull": True,
    "IIf": True,
    "DATE_FUNCTIONS": True,
    "STRING_FUNCTIONS": True,
    "CONVERSION_FUNCTIONS": True,   # CDbl / CStr / CInt ...
    # Data access
    "DAO_RECORDSET": False,        # no adapter yet
    "DLOOKUP": True,
    "DCOUNT": True,
    "ADODB": False,
    # Query targets
    "JPA_QUERY": True,
    "NATIVE_QUERY": True,
    "VBA_ROW_FUNCTION_IN_QUERY": True,   # service decomposition
    # Application
    "MSYSOBJECTS": True,
    "DOCMnavigation": True,
    # External systems
    "OUTLOOK": False,
    "WIN32_API": False,
    "EXCEL_COM": False,
}


def set_capability(name: str, enabled: bool) -> None:
    CAPABILITIES[name] = enabled


def capability_enabled(name: str) -> bool:
    return CAPABILITIES.get(name, False)


# ---------------------------------------------------------------- strategies

class TargetStrategy(str, Enum):
    JPA_ENTITY = "JPA_ENTITY"
    JPA_QUERY = "JPA_QUERY"
    NATIVE_QUERY = "NATIVE_QUERY"
    SPRING_SERVICE = "SPRING_SERVICE"
    SERVICE_DECOMPOSITION = "SERVICE_DECOMPOSITION"   # query + VBA row function
    REACT_CRUD_PAGE = "REACT_CRUD_PAGE"
    REACT_EVENT_PLUS_SERVICE = "REACT_EVENT_PLUS_SERVICE"
    WORKFLOW = "WORKFLOW"                              # macro action sequence
    REPORT_SERVICE = "REPORT_SERVICE"
    ADAPTER_REQUIRED = "ADAPTER_REQUIRED"
    MANUAL_REVIEW = "MANUAL_REVIEW"
    DROPPED = "DROPPED"


@dataclass
class StrategyDecision:
    object_name: str
    category: str                       # TABLE | QUERY | VBA | FORM | MACRO | REPORT
    strategy: TargetStrategy
    reasons: list[str] = field(default_factory=list)
    required_capabilities: list[str] = field(default_factory=list)

    @property
    def blocked(self) -> bool:
        return self.strategy in (TargetStrategy.ADAPTER_REQUIRED,
                                 TargetStrategy.MANUAL_REVIEW,
                                 TargetStrategy.DROPPED)


class ConversionStrategyResolver:
    """Chooses a target strategy per object from IR facts alone."""

    def __init__(self, app_ir):
        self.app = app_ir
        self._vba_function_names: dict[str, str] = {}
        for module in app_ir.vba_modules:
            for proc in module.procedures:
                if proc.kind == "FUNCTION":
                    self._vba_function_names.setdefault(proc.name.lower(),
                                                        module.name)
        self._table_names = {t.name.lower() for t in app_ir.tables}

    # ------------------------------------------------------------ queries

    def resolve_query(self, query) -> StrategyDecision:
        reasons: list[str] = []
        vba_funcs = [
            f for f in query.access_functions
            if f.lower() in self._vba_function_names
        ]
        if vba_funcs:
            caps_ok = all(capability_enabled("VBA_ROW_FUNCTION_IN_QUERY"),
                          ) if vba_funcs else True
            caps = ["VBA_ROW_FUNCTION_IN_QUERY", capability_key_for(vba_funcs[0])]
            missing = [c for c in caps if not capability_enabled(c)]
            if not capability_enabled("VBA_ROW_FUNCTION_IN_QUERY"):
                return StrategyDecision(
                    query.name, "QUERY", TargetStrategy.MANUAL_REVIEW,
                    reasons + ["row-level VBA function capability disabled"],
                    caps)
            modules = sorted({self._vba_function_names[f.lower()]
                              for f in vba_funcs})
            return StrategyDecision(
                query.name, "QUERY",
                TargetStrategy.SERVICE_DECOMPOSITION,
                reasons + [f"references VBA functions {vba_funcs} "
                           f"(modules {modules}) - decompose into ordered "
                           f"service evaluation"],
                caps)
        kind = str(query.kind.value if hasattr(query.kind, "value") else query.kind)
        if kind in ("DDL", "MAKE_TABLE"):
            return StrategyDecision(
                query.name, "QUERY", TargetStrategy.NATIVE_QUERY,
                reasons + [f"{kind} query executes as native SQL migration step"])
        unsupported_markers = ("TRANSFORM ", "PIVOT ")
        sql_upper = (query.sql or "").upper()
        if any(m in sql_upper for m in unsupported_markers):
            return StrategyDecision(
                query.name, "QUERY", TargetStrategy.MANUAL_REVIEW,
                reasons + ["crosstab TRANSFORM/PIVOT has no automatic target"])
        if capability_enabled("JPA_QUERY"):
            return StrategyDecision(
                query.name, "QUERY", TargetStrategy.JPA_QUERY,
                reasons + ["plain Access SQL converts to JPQL/native"])
        return StrategyDecision(
            query.name, "QUERY", TargetStrategy.MANUAL_REVIEW,
            reasons + ["query capabilities unavailable"])

    # ------------------------------------------------------------ tables

    def resolve_table(self, table) -> StrategyDecision:
        role = table.role.value if hasattr(table.role, "value") else str(table.role)
        if role == "SYSTEM":
            if capability_enabled("MSYSOBJECTS"):
                return StrategyDecision(
                    table.name, "TABLE", TargetStrategy.JPA_ENTITY,
                    reasons + ["system metadata mapped to generated metadata model"])
            return StrategyDecision(table.name, "TABLE", TargetStrategy.DROPPED,
                                    ["system table and MSYSOBJECTS disabled"])
        special_columns = [c for c in table.columns
                           if c.is_attachment or c.is_multivalue or c.is_ole]
        if special_columns:
            return StrategyDecision(
                table.name, "TABLE", TargetStrategy.JPA_ENTITY,
                reasons + [f"{len(special_columns)} column(s) need adapter "
                           f"(attachment/multivalue/OLE)"],
                required_capabilities=["ACCESS_COMPLEX_TYPES"])
        return StrategyDecision(table.name, "TABLE", TargetStrategy.JPA_ENTITY,
                                [f"role {role}"])

    # ------------------------------------------------------------ VBA

    def resolve_module(self, module) -> StrategyDecision:
        external_kinds = set(module.uses_external or [])
        needs_adapter = []
        if any("outlook" in k.lower() for k in external_kinds):
            needs_adapter.append("OUTLOOK")
        if module.declares_api:
            needs_adapter.append("WIN32_API")
        if any(k.lower() in ("excel.", "excel.application") for k in external_kinds):
            needs_adapter.append("EXCEL_COM")
        blocked_caps = [c for c in needs_adapter if not capability_enabled(c)]
        if not module.procedures:
            return StrategyDecision(module.name, "VBA", TargetStrategy.MANUAL_REVIEW,
                                    ["no parseable procedures"])
        if blocked_caps:
            return StrategyDecision(
                module.name, "VBA", TargetStrategy.ADAPTER_REQUIRED,
                reasons=[f"requires adapter for {blocked_caps}"],
                required_capabilities=blocked_caps)
        return StrategyDecision(
            module.name, "VBA", TargetStrategy.SPRING_SERVICE,
            [f"{len(module.procedures)} procedures map to service methods"])

    def resolve(self, obj, category: str) -> StrategyDecision:
        if category == "QUERY":
            return self.resolve_query(obj)
        if category == "TABLE":
            return self.resolve_table(obj)
        if category == "VBA":
            return self.resolve_module(obj)
        return StrategyDecision(getattr(obj, "name", "?"), category,
                                TargetStrategy.MANUAL_REVIEW,
                                ["no resolver for category"])


def capability_key_for(vba_function: str) -> str:
    """Capability flag that gates a given runtime builtin."""
    lowered = vba_function.lower()
    if lowered in ("nz",):
        return "Nz"
    if lowered in ("isnull",):
        return "IsNull"
    if lowered in ("iif",):
        return "IIf"
    if lowered in ("date", "dateadd", "datediff", "datepart", "dateserial",
                   "now", "time", "year", "month", "day"):
        return "DATE_FUNCTIONS"
    if lowered in ("format", "left", "right", "mid", "trim", "lcase", "ucase",
                   "instr", "replace", "len", "string_", "space"):
        return "STRING_FUNCTIONS"
    return "CONVERSION_FUNCTIONS"
