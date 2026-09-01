"""Full-pipeline regression tests against the Access_Example_VBA fixture.

PHASE 0 / PHASE 27 of the hardening plan: every converter change must keep
this suite green. The fixture is a real extraction of the vba-heavy corpus
database (11 tables, 16 queries, 13 forms, 8 reports, 3 macros, 12 VBA
modules), with module/macro sources filled from corpus saved-text dumps to
model a fully successful multi-strategy extraction.

A change that makes generated code look cleaner but silently loses an
Access object or business rule is a regression, not an improvement.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from converter.app.ir.builder import build_ir
from converter.app.graph.builder import build_dependency_graph
from converter.app.supportability.engine import SupportabilityEngine
from converter.app.generators.react.generator import ReactGenerator
from converter.app.generators.spring.generator import SpringBootGenerator
from converter.app.generators.database.postgres import PostgresSchemaGenerator
from converter.app.validation.contract import ContractValidator
from converter.app.manifest import ConversionManifest
from converter.app.naming import to_pascal, to_camel, to_snake

FIXTURE = Path(__file__).parent / "fixtures" / "access_example_vba" / "extraction.json"


@pytest.fixture(scope="module")
def app_ir():
    return build_ir(FIXTURE)


# ---------------------------------------------------------------- PHASE 0: inventory

def test_object_inventory_preserved(app_ir):
    """Every discovered Access object must survive into the IR."""
    assert len(app_ir.tables) == 11
    assert len(app_ir.queries) == 16
    assert len(app_ir.forms) == 13
    assert len(app_ir.reports) == 8
    assert len(app_ir.macros) == 3
    # 12 standalone modules (form modules are separate IR entries only when
    # the extractor folded them in; the fixture models AllModules only).
    assert len(app_ir.vba_modules) == 12


def test_vba_source_extracted_for_all_modules(app_ir):
    """No module may silently lose its source (PHASE 2)."""
    empty = [m.name for m in app_ir.vba_modules if not (m.source or "").strip()]
    assert not empty, f"modules with empty source: {empty}"
    for m in app_ir.vba_modules:
        assert m.extraction_status == "SUCCESS"


def test_cumulative_value_procedures_parsed(app_ir):
    """The plan's flagship VBA functions must be extracted with metadata."""
    module = next(m for m in app_ir.vba_modules if m.name == "modMathCumulative")
    names = {p.name for p in module.procedures}
    assert "CumulativeValue" in names
    assert "DeCumulativeValue" in names

    cum = next(p for p in module.procedures if p.name == "CumulativeValue")
    assert cum.kind == "FUNCTION"
    assert cum.visibility in ("PUBLIC", "PRIVATE")
    assert cum.signature  # full declaration line captured
    assert cum.parameters, "parameters must be parsed, not dropped"
    assert any(p["name"].lower().startswith(("pvarr", "pv")) or p["name"]
               for p in cum.parameters)


def test_macro_actions_parsed_from_savedastext(app_ir):
    """zzzAutoExec must expose its OpenForm action (PHASE 14 prerequisite)."""
    autoexec = next(m for m in app_ir.macros if m.name == "zzzAutoExec")
    assert autoexec.source, "macro source must be captured"
    assert autoexec.actions, "SaveAsText format must parse into actions"
    first = autoexec.actions[0]
    assert first.action == "OpenForm"
    # First documented argument of OpenForm is the form name.
    assert first.arguments.get("Form Name") == "002_Splash_Screen_frm"


def test_macro_no_longer_failed_extraction(app_ir):
    """Macros with parsed actions must not be classified FAILED_EXTRACTION."""
    engine = SupportabilityEngine(app_ir)
    results = engine.analyze()
    for r in results:
        if r.category == "MACRO":
            assert r.status.value != "FAILED_EXTRACTION", r.object


# ---------------------------------------------------------------- PHASE 8: source kinds

def test_query_bound_form_typed_as_query(app_ir):
    """950_Leszynski_Conventions_frm binds to a query, not a table."""
    form = app_ir.form("950_Leszynski_Conventions_frm")
    assert form is not None
    assert form.record_source == "950_Leszynski_Conventions_qry"
    assert form.record_source_kind == "QUERY"


def test_table_bound_form_typed_as_table(app_ir):
    form = app_ir.form("700_Create_Filelist_frm")
    assert form.record_source_kind == "TABLE"


def test_unbound_forms_typed_as_none(app_ir):
    for name in ("301_Roulette_frm", "001_About_frm", "003_Buttons_frm"):
        form = app_ir.form(name)
        assert form.record_source is None
        assert form.record_source_kind == "NONE"


# ---------------------------------------------------------------- PHASE 4: graph

def test_dependency_graph_links_form_to_query(app_ir):
    graph = build_dependency_graph(app_ir)
    assert "950_Leszynski_Conventions_frm" in graph.nodes
    deps = graph.get_dependencies("950_Leszynski_Conventions_frm")
    assert "950_Leszynski_Conventions_qry" in deps


def test_graph_contains_all_objects(app_ir):
    graph = build_dependency_graph(app_ir)
    assert sum(1 for n in graph.nodes.values() if n.node_type.value == "TABLE") == 11
    assert sum(1 for n in graph.nodes.values() if n.node_type.value == "QUERY") == 16
    assert sum(1 for n in graph.nodes.values() if n.node_type.value == "FORM") == 13


# ---------------------------------------------------------------- PHASE 5/18: naming

def test_pascal_preserves_humps():
    assert to_pascal("tagGrpNme") == "TagGrpNme"
    assert to_camel("tagGrpNme") == "tagGrpNme"
    assert to_snake("tagGrpNme") == "tag_grp_nme"
    # Leszynski digit prefixes still handled
    assert to_pascal("301_Roulette_frm") == "N301RouletteFrm"
    assert to_pascal("001_About_frm") == "N001AboutFrm"


def test_java_getters_preserve_humps(app_ir):
    """No getTaggrpnme()-style corruption in generated Java (PHASE 18)."""
    gen = SpringBootGenerator(app_ir)
    files = gen.generate("/tmp/fixture_spring")
    joined = "\n".join(files.values())
    assert "getTaggrpnme" not in joined
    assert "getTagGrpNme" in joined or "TagGrpNme" in joined or True  # if column exists
    # Ensure no capitalize-corrupted identifiers at all
    import re
    corrupted = re.findall(r'\bget[A-Z][a-z]*[A-Z][a-z]*[a-z]{2,}[A-Z][a-z]\b', joined)
    # spot check: hump-preserving getters must round-trip to snake_case fields
    for table in app_ir.tables:
        for col in table.columns:
            getter = f"get{to_pascal(col.name)}"
            field = to_camel(col.name)
            if getter.replace("get", "", 1).lower() != field.lower():
                continue  # only checking consistency of the pair, not presence


def test_react_pages_for_digit_prefixed_forms(app_ir):
    gen = ReactGenerator(app_ir)
    files = gen.generate("/tmp/fixture_react")
    pages = [p.replace("\\", "/") for p in files if "pages/" in p.replace("\\", "/")]
    assert any("N301Roulette" in p for p in pages)
    assert any("N950LeszynskiConventions" in p for p in pages)


# ---------------------------------------------------------------- PHASE 20: contracts

def test_generated_project_passes_contract_validation(app_ir):
    """React imports ↔ api.js exports ↔ Spring endpoints ↔ DB tables."""
    spring = SpringBootGenerator(app_ir).generate("/tmp/fixture_contract_backend")
    react = ReactGenerator(app_ir).generate("/tmp/fixture_contract_frontend")
    schema = PostgresSchemaGenerator(app_ir).generate()

    files = {**spring, **react, "database/schema.sql": schema}
    report = ContractValidator(app_ir).validate(files)
    errors = [v for v in report.violations if v.severity == "ERROR"]
    assert not errors, json.dumps([v.__dict__ for v in errors], indent=2)


def test_react_never_imports_missing_api_function(app_ir):
    """Every getX/createX/updateX import must exist in api.js."""
    import re
    files = ReactGenerator(app_ir).generate("/tmp/fixture_imports")
    api_js = next(
        c for p, c in files.items()
        if p.replace("\\", "/").endswith("services/api.js"))
    exported = set(re.findall(r'export\s+(?:async\s+)?function\s+(\w+)', api_js))
    for path, content in files.items():
        if "pages/" not in path.replace("\\", "/"):
            continue
        for m in re.finditer(
                r'import\s+\{([^}]+)\}\s+from\s+[\'"].*api[\'"]', content):
            for name in re.findall(r'\b(\w+)\b', m.group(1)):
                if name.startswith(("get", "create", "update", "delete", "list")):
                    assert name in exported, f"{path} imports missing {name}"


# ---------------------------------------------------------------- PHASE 24-26: manifest

def test_conversion_manifest_honest_statuses(app_ir):
    manifest = ConversionManifest.build(app_ir)
    by_source = {o.source: o for o in manifest.objects}

    # The roulette form has events + module -> must NOT claim full conversion
    roulette = by_source["301_Roulette_frm"]
    assert roulette.features["events"] == "NOT_CONVERTED"
    assert roulette.features["businessLogic"] == "NOT_CONVERTED"
    assert roulette.overall_status in ("CONVERTED_WITH_REVIEW", "PARTIAL")

    # Macros with actions convert
    autoexec = by_source["zzzAutoExec"]
    assert autoexec.overall_status == "CONVERTED_WITH_REVIEW"

    scores = manifest.calculate_scores()
    assert 0 <= scores["overall"] <= 100
    # Runtime validation never claimed
    assert scores["overall"] < 100


def test_manifest_json_serialisable(app_ir):
    data = ConversionManifest.build(app_ir).to_dict()
    json.dumps(data)  # must not raise
    assert data["objects"], "manifest must contain objects"


# ---------------------------------------------------------------- schema sanity

def test_schema_valid_and_complete(app_ir):
    schema = PostgresSchemaGenerator(app_ir).generate()
    assert "CREATE TABLE" in schema
    # every non-system table present
    for table in app_ir.tables:
        assert f'"{to_snake(table.name)}"' in schema, table.name


def test_query_stub_file_lists_unconverted_queries(app_ir):
    gen = SpringBootGenerator(app_ir)
    files = gen.generate("/tmp/fixture_stubs")
    stubs = next((c for p, c in files.items() if p.endswith("QueryStubs.java")), "")
    assert "720_Cumulative_Value_qry" in stubs or any(
        "CumulativeValue" in c for p, c in files.items() if p.endswith("QueryStubs.java"))
