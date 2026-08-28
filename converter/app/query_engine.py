"""Query conversion engine (plan §12-13).

Converts saved Access queries into executable targets instead of stubs:

* Plain queries          -> translated native PostgreSQL SQL (existing path).
* Queries that call VBA  -> SERVICE_DECOMPOSITION: the base SELECT (without
  row-level functions) runs as native SQL via JdbcTemplate; the converted
  VBA service then evaluates each row IN ORDER with one shared state
  instance, reproducing Access's Static-across-rows semantics exactly.

Strategy selection is dynamic: anything naming a parsed VBA function becomes
a decomposition; crosstabs and untranslatable SQL stay MANUAL_REVIEW.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

from .naming import to_kebab, to_pascal
from .generators.vba_service import service_class_name, _camel, _pascal


@dataclass
class ComputedColumn:
    alias: str
    func_name: str                       # VBA function name as written
    args: list[str]                      # raw argument expressions
    service_class: str = ""              # resolved Java service class
    java_method: str = ""                # resolved Java method
    state_class: str = ""                # '' when method has no Static state
    extra_defaults: list[str] = field(default_factory=list)  # Java literals
                                                             # for trailing
                                                             # optional params


@dataclass
class QueryPlan:
    name: str
    kind: str = "SELECT"
    select_items: list[str] = field(default_factory=list)   # passthrough
    computed: list[ComputedColumn] = field(default_factory=list)
    from_clause: str = ""
    group_by: str = ""
    order_by: str = ""
    base_sql: str = ""
    endpoint: str = ""
    service_class: str = ""
    strategy: str = "MANUAL_REVIEW"
    reasons: list[str] = field(default_factory=list)


def _split_top(s: str, sep: str = ",") -> list[str]:
    parts, depth, cur = [], 0, ""
    for ch in s:
        if ch == "(":
            depth += 1
        elif ch == ")":
            depth -= 1
        if ch == sep and depth == 0:
            parts.append(cur)
            cur = ""
        else:
            cur += ch
    if cur.strip():
        parts.append(cur)
    return parts


def _strip_brackets(s: str) -> str:
    return re.sub(r"\[([^\]]+)\]", r"\1", s)


def _access_strings_to_pg(sql: str) -> str:
    """Access SQL allows "double quoted" literals; PostgreSQL wants '...'."""
    out = []
    i = 0
    n = len(sql)
    while i < n:
        if sql[i] == '"':
            m = re.match(r'"((?:[^"]|"")*)"', sql[i:])
            if m:
                out.append("'" + m.group(1).replace("''", "'").replace("'", "''") + "'")
                i += m.end()
                continue
        out.append(sql[i])
        i += 1
    return "".join(out)


def _java_class_ident(name: str) -> str:
    """Pascal-case with digit-prefix rule (Leszynski '001_x' names)."""
    s = _pascal(name)
    return ("N" + s) if s and s[0].isdigit() else s


def _java_method_ident(name: str) -> str:
    """camel-case with digit-prefix rule for Java methods."""
    s = _camel(name)
    return ("n" + s) if s and s[0].isdigit() else s


def plan_query(query_ir, app_ir,
               vba_registry: dict[str, dict]) -> QueryPlan:
    """Produce a QueryPlan for one QueryIR.

    vba_registry maps function-name(lower) -> {module, params, state} where
    params is the procedure's parsed parameter list and state the Java
    state-class name ('' when none).
    """
    plan = QueryPlan(name=query_ir.name)
    plan.endpoint = to_kebab(query_ir.name)
    sql = query_ir.sql or ""
    upper = sql.upper()

    if upper.startswith("TRANSFORM") or " PIVOT " in upper:
        plan.reasons.append("crosstab TRANSFORM/PIVOT needs manual pivot design")
        return plan

    m = re.search(r"\bSELECT\b(.*?)\bFROM\b(.*)$", sql, re.I | re.S)
    if not m:
        plan.reasons.append("not a parseable SELECT")
        return plan
    select_body = m.group(1).strip()
    rest = m.group(2)

    fm = re.match(r"\s*([^\s]+)\s*(.*)$", rest, re.S)
    from_table = fm.group(1).rstrip(";") if fm else ""
    tail = fm.group(2) if fm else ""

    gb = re.search(r"\bGROUP\s+BY\b(.*?)(?=\bORDER\s+BY\b|\bHAVING\b|$)",
                   tail, re.I | re.S)
    ob = re.search(r"\bORDER\s+BY\b(.*?)$", tail, re.I | re.S)
    plan.group_by = gb.group(1).strip() if gb else ""
    plan.order_by = ob.group(1).strip().rstrip(";") if ob else ""

    def _java_default(vba_default: str, vba_type: str) -> str:
        d = (vba_default or "").strip()
        t = (vba_type or "").strip().upper()
        if d.lower() == "true":
            return "true"
        if d.lower() == "false":
            return "false"
        if re.fullmatch(r"[+-]?\d+(\.\d+)?", d):
            return d
        if d.startswith('"') and d.endswith('"'):
            return d
        return "null"

    # classify select items
    for item in _split_top(select_body):
        item = item.strip()
        if not item:
            continue
        fm2 = re.match(
            r"^([A-Za-z_]\w*)\s*\((.*)\)\s+AS\s+(\[?[^\s\]]+\]?)\s*$",
            item, re.I | re.S)
        if fm2 and fm2.group(1).lower() in vba_registry:
            info = vba_registry[fm2.group(1).lower()]
            alias = fm2.group(3).strip("[]")
            provided = [a.strip() for a in _split_top(fm2.group(2))]
            params = info.get("params") or []
            extra: list[str] = []
            for p in params[len(provided):]:
                if p.get("default") is not None:
                    extra.append(_java_default(p.get("default", ""),
                                               p.get("type", "")))
            plan.computed.append(ComputedColumn(
                alias=alias,
                func_name=fm2.group(1),
                args=provided,
                service_class=service_class_name(info["module"]),
                java_method=_camel(fm2.group(1)),
                state_class=info.get("state", ""),
                extra_defaults=extra,
            ))
            continue
        plan.select_items.append(item)

    if plan.computed:
        plan.strategy = "SERVICE_DECOMPOSITION"
        plan.service_class = _java_class_ident(plan.name) + "QueryService"
        plan.reasons.append(
            f"row-level VBA functions {[c.func_name for c in plan.computed]} "
            f"evaluated by converted services in row order")
    else:
        plan.strategy = "NATIVE_QUERY"

    # base SQL: passthrough columns only, in original order, grouped/ordered
    cols = ", ".join(_strip_brackets(i) for i in plan.select_items) or "*"
    base = f"SELECT {cols} FROM {_strip_brackets(from_table)}"
    if plan.group_by:
        base += " GROUP BY " + _strip_brackets(plan.group_by)
    if plan.order_by:
        base += " ORDER BY " + _strip_brackets(plan.order_by)
    plan.base_sql = _access_strings_to_pg(base.rstrip(";"))
    plan.from_clause = _strip_brackets(from_table)
    return plan


# ------------------------------------------------------------------ Java gen

def _java_arg(arg: str) -> str:
    """Translate a VBA function argument into a Java row-expression."""
    a = arg.strip()
    # [Column] reference
    cm = re.fullmatch(r"\[([^\]]+)\]", a)
    if cm:
        return f'row.get("{cm.group(1)}")'
    # "literal"
    if a.startswith('"') and a.endswith('"') and len(a) >= 2:
        inner = a[1:-1].replace("\\", "\\\\").replace('"', '\\"')
        return f'"{inner}"'
    # bare number or boolean
    if re.fullmatch(r"[+-]?\d+(\.\d+)?", a):
        return a
    if a.lower() in ("true", "false"):
        return a.lower()
    # column without brackets
    if re.fullmatch(r"[A-Za-z_]\w*", a):
        return f'row.get("{a}")'
    return f'/* ACCESS-MIGRATION: unresolved arg {a} */ null'


def _default_arg_fill(computed: ComputedColumn, plan: QueryPlan) -> list[str]:
    """Optional args the converted Java method expects beyond provided args."""
    return []


def generate_query_service_java(plan: QueryPlan, base_package: str) -> str:
    """Emit a @Service executing a decomposed query.

    Computed columns carry their resolved service class, state class and
    trailing optional-argument defaults, so call sites always compile.
    """
    cls = plan.service_class or (_java_class_ident(plan.name) + "QueryService")
    lines = []
    lines.append("// ACCESS-SOURCE:")
    lines.append(f"// Query: {plan.name}")
    lines.append(f"// Strategy: {plan.strategy}")
    lines.append("")
    lines.append(f"package {base_package}.service;")
    lines.append("")
    lines.append("import org.springframework.jdbc.core.JdbcTemplate;")
    lines.append("import org.springframework.stereotype.Service;")
    lines.append("")
    lines.append("import java.util.ArrayList;")
    lines.append("import java.util.LinkedHashMap;")
    lines.append("import java.util.List;")
    lines.append("import java.util.Map;")
    lines.append("")
    lines.append("/**")
    lines.append(f" * Executable conversion of Access query '{plan.name}'.")
    lines.append(" * Base rows stream through the converted VBA services in")
    lines.append(" * query order; Static-state semantics are preserved by sharing")
    lines.append(" * one state instance across the whole result set.")
    lines.append(" */")
    lines.append("@Service")
    lines.append(f"public class {cls} {{")

    lines.append("    private final JdbcTemplate jdbcTemplate;")
    deps = ["JdbcTemplate jdbcTemplate"]
    fields = ["    private final JdbcTemplate jdbcTemplate;"]
    seen_services: dict[str, str] = {}
    for c in plan.computed:
        var = _camel(c.service_class)
        if c.service_class not in seen_services:
            seen_services[c.service_class] = var
            fields.append(f"    private final {c.service_class} {var};")
            deps.append(f"{c.service_class} {var}")
    lines.extend(fields)
    lines.append("")
    lines.append(f"    public {cls}({', '.join(deps)}) {{")
    lines.append("        this.jdbcTemplate = jdbcTemplate;")
    for svc, var in seen_services.items():
        lines.append(f"        this.{var} = {var};")
    lines.append("    }")
    lines.append("")
    lines.append("    public List<Map<String, Object>> execute() {")
    lines.append(f'        String sql = "{plan.base_sql.replace(chr(34), chr(92)+chr(34))}";')
    lines.append("        List<Map<String, Object>> rows = jdbcTemplate.queryForList(sql);")
    # shared state instances (one per stateful function, per plan §11)
    for c in plan.computed:
        if c.state_class:
            lines.append(f"        {c.service_class}.{c.state_class} $state = "
                         f"new {c.service_class}.{c.state_class}();")
        else:
            lines.append(f"        // {_camel(c.service_class)}: no Static state required")
    lines.append("        List<Map<String, Object>> out = new ArrayList<>();")
    lines.append("        for (Map<String, Object> row : rows) {")
    lines.append("            Map<String, Object> o = new LinkedHashMap<>(row);")
    for c in plan.computed:
        var = _camel(c.service_class)
        args = ", ".join([_java_arg(a) for a in c.args] + list(c.extra_defaults))
        state_prefix = "$state, " if c.state_class else ""
        target = f"{var}.{c.java_method}({state_prefix}{args})"
        lines.append(f'            o.put("{c.alias}", {target});')
    lines.append("            out.add(o);")
    lines.append("        }")
    lines.append("        return out;")
    lines.append("    }")
    lines.append("}")
    return "\n".join(lines)


def generate_query_controller_java(plans: list[QueryPlan],
                                   base_package: str) -> str:
    """One controller exposing every decomposed query as GET /api/queries/x."""
    lines = []
    lines.append("// ACCESS-SOURCE:")
    lines.append("// Generated from saved Access queries (dynamic set).")
    lines.append("")
    lines.append(f"package {base_package}.controller;")
    lines.append("")
    lines.append("import org.springframework.beans.factory.annotation.Autowired;")
    lines.append("import org.springframework.web.bind.annotation.*;")
    lines.append("")
    lines.append("import java.util.List;")
    lines.append("import java.util.Map;")
    lines.append("")
    lines.append("/**")
    lines.append(" * REST endpoints for converted Access queries. Only queries that")
    lines.append(" * decomposed successfully appear here; the rest are listed in")
    lines.append(" * QueryStubs.java with their blocking reasons.")
    lines.append(" */")
    lines.append("@RestController")
    lines.append('@RequestMapping("/api/queries")')
    lines.append("@CrossOrigin(origins = \"*\")")
    lines.append("public class QueryServicesController {")
    for plan in plans:
        svc = plan.service_class or (_java_class_ident(plan.name) + "QueryService")
        var = _camel(svc)
        lines.append("")
        lines.append("    @Autowired")
        lines.append(f"    private {svc} {var};")
    lines.append("")
    for plan in plans:
        svc = plan.service_class or (_java_class_ident(plan.name) + "QueryService")
        var = _camel(svc)
        ep = plan.endpoint
        lines.append(f"    /** Converted from Access query: {plan.name} */")
        lines.append(f'    @GetMapping("/{ep}")')
        lines.append("    public List<Map<String, Object>> "
                     f"{_java_method_ident(plan.name)}() {{")
        lines.append(f"        return {var}.execute();")
        lines.append("    }")
    lines.append("}")
    return "\n".join(lines)


def build_vba_registry(app_ir, state_map: dict[str, dict] | None = None
                       ) -> dict[str, dict]:
    """function-name -> conversion info for every parsed FUNCTION.

    state_map optionally carries {module_name -> {proc -> state-class}},
    produced by running the VBA converter; when absent the state class is
    derived from the naming rules.
    """
    registry: dict[str, dict] = {}
    for module in app_ir.vba_modules:
        proc_states = (state_map or {}).get(module.name, {})
        for proc in module.procedures:
            if proc.kind.upper() == "FUNCTION":
                registry.setdefault(proc.name.lower(), {
                    "module": module.name,
                    "params": proc.parameters or [],
                    "state": proc_states.get(proc.name, ""),
                })
    return registry


def build_query_plans(app_ir, state_map: dict[str, dict] | None = None,
                      blocked_functions: set[str] | None = None
                      ) -> tuple[list[QueryPlan], list[dict]]:
    """Plan every query; return (decomposed_plans, deferred_queries).

    blocked_functions names VBA functions whose conversion carries
    MANUAL_REVIEW constructs; queries depending on them are deferred with
    an explicit reason instead of generating partially-behaving services.
    """
    blocked_functions = blocked_functions or set()
    registry = build_vba_registry(app_ir, state_map)
    decomposed: list[QueryPlan] = []
    deferred: list[dict] = []
    for q in app_ir.queries:
        plan = plan_query(q, app_ir, registry)
        if plan.strategy == "SERVICE_DECOMPOSITION" and plan.computed:
            blockers = [c.func_name for c in plan.computed
                        if c.func_name.lower() in blocked_functions]
            if blockers:
                deferred.append({
                    "name": q.name,
                    "strategy": "MANUAL_REVIEW",
                    "reasons": [f"depends on VBA function(s) {blockers} "
                                f"with unconverted constructs"],
                })
                continue
            decomposed.append(plan)
        else:
            deferred.append({
                "name": q.name,
                "strategy": plan.strategy,
                "reasons": plan.reasons,
            })
    return decomposed, deferred
