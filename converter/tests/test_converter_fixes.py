"""Unit tests verifying the 7 converter issue fixes.

Tests:
1. React identifier sanitation (digit prefix -> 'N' prefix)
2. React API client & page naming alignment with record_source
3. Form control rendering & disabled attribute syntax
4. JPA @Id generation for PK-less tables
5. Postgres schema generation with synthetic PK
6. Supportability engine FAILED_EXTRACTION classification
7. QueryStubs.java generation and honest migration report fields
"""
import pytest
from converter.app.ir.models import (
    ApplicationIR, TableIR, ColumnIR, FormIR, ControlIR,
    QueryIR, QueryKind, VbaModuleIR, MacroIR, SupportStatus,
)
from converter.app.generators.react.generator import ReactGenerator
from converter.app.generators.spring.generator import SpringBootGenerator
from converter.app.generators.database.postgres import PostgresSchemaGenerator
from converter.app.supportability.engine import SupportabilityEngine


def test_react_identifier_sanitation():
    """Verify digit-prefixed form names become valid JS identifiers."""
    assert ReactGenerator._to_pascal("001_About_frm".replace("frm", "")) == "N001About"
    assert ReactGenerator._to_pascal("001_About_frm") == "N001AboutFrm"
    assert ReactGenerator._to_pascal("301_Roulette_frm".replace("frm", "")) == "N301Roulette"
    assert ReactGenerator._to_pascal("frm_customers") == "FrmCustomers"
    assert ReactGenerator._to_camel("001_About_frm") == "n001AboutFrm"


def test_react_api_and_form_generation():
    """Verify page imports table-based API function and valid JSX."""
    app_ir = ApplicationIR(
        application_name="TestApp",
        tables=[
            TableIR(
                name="Roulette_tb",
                columns=[
                    ColumnIR(name="ID", access_type="Long Integer", auto_number=True),
                    ColumnIR(name="BetAmount", access_type="Currency"),
                ],
            )
        ],
        forms=[
            FormIR(
                name="301_Roulette_frm",
                record_source="Roulette_tb",
                caption="Roulette Game",
                controls=[
                    ControlIR(
                        name="txtBet",
                        control_type="TextBox",
                        control_source="BetAmount",
                        caption="Bet Amount",
                        locked=True,
                    ),
                    ControlIR(
                        name="chkActive",
                        control_type="CheckBox",
                        control_source="IsActive",
                        caption="Active Bet",
                    ),
                ],
            )
        ],
    )

    gen = ReactGenerator(app_ir)
    files = gen.generate("/tmp/test_react")

    # Look for the generated page file
    matching_pages = [k for k in files.keys() if "N301RoulettePage.jsx" in k]
    assert matching_pages, f"Page file not found in {list(files.keys())}"
    page_code = files[matching_pages[0]]

    # Check that API calls use table name RouletteTb instead of form name N301Roulette
    assert "getRouletteTbById" in page_code
    assert "updateRouletteTb" in page_code
    assert "createRouletteTb" in page_code
    # Check that locked control has disabled attribute
    assert "disabled" in page_code
    # Check that App.jsx imports valid identifier
    matching_apps = [k for k in files.keys() if "App.jsx" in k]
    app_jsx = files[matching_apps[0]]
    assert "import N301RoulettePage from './pages/N301RoulettePage';" in app_jsx


def test_spring_boot_synthetic_id_and_query_stubs():
    """Verify tables without PKs get synthetic @Id and unconverted queries get stubs."""
    app_ir = ApplicationIR(
        application_name="TestApp",
        tables=[
            TableIR(
                name="Roulette_tb",
                columns=[
                    ColumnIR(name="BetNumber", access_type="Integer"),
                    ColumnIR(name="Payout", access_type="Double"),
                ],
                # No primary key defined in indexes
                indexes=[],
            )
        ],
        queries=[
            QueryIR(
                name="720_Cumulative_Value_qry",
                kind=QueryKind.SELECT,
                sql="SELECT CumulativeValue([Amt]) FROM CumVal_tb",
                access_functions=["CumulativeValue"],
            )
        ],
    )

    gen = SpringBootGenerator(app_ir)
    files = gen.generate("/tmp/test_spring")

    matching_entities = [k for k in files.keys() if "RouletteTb.java" in k]
    assert matching_entities
    entity_code = files[matching_entities[0]]
    assert "@Id" in entity_code
    assert "@GeneratedValue(strategy = GenerationType.IDENTITY)" in entity_code
    assert "private Long generatedId;" in entity_code
    assert "public Long getGeneratedId()" in entity_code

    # Check query stubs file exists and contains TODO
    matching_stubs = [k for k in files.keys() if "QueryStubs.java" in k]
    assert matching_stubs
    stubs_code = files[matching_stubs[0]]
    assert "720_Cumulative_Value_qry" in stubs_code
    assert "CumulativeValue" in stubs_code
    assert any("CumulativeValue" in w for w in gen.warnings)


def test_postgres_synthetic_pk():
    """Verify Postgres generator outputs BIGSERIAL PRIMARY KEY for PK-less tables."""
    app_ir = ApplicationIR(
        application_name="TestApp",
        tables=[
            TableIR(
                name="Roulette_tb",
                columns=[
                    ColumnIR(name="BetNumber", access_type="Integer"),
                ],
                indexes=[],
            )
        ],
    )

    gen = PostgresSchemaGenerator(app_ir)
    sql = gen.generate()
    assert '"generated_id" BIGSERIAL PRIMARY KEY' in sql


def test_supportability_failed_extraction():
    """Verify empty VBA modules/macros/forms are classified as FAILED_EXTRACTION."""
    app_ir = ApplicationIR(
        application_name="TestApp",
        vba_modules=[
            VbaModuleIR(name="modMath", module_type="STANDARD", source="")
        ],
        macros=[
            MacroIR(name="mcrAuto", actions=[])
        ],
        forms=[
            FormIR(
                name="frmMain",
                module_name="Form_frmMain",
            )
        ],
    )
    # Add empty form VBA module
    app_ir.vba_modules.append(
        VbaModuleIR(name="Form_frmMain", module_type="FORM", source="")
    )

    engine = SupportabilityEngine(app_ir)
    results = engine.analyze()

    status_by_obj = {r.object: r.status for r in results}
    assert status_by_obj["modMath"] == SupportStatus.FAILED_EXTRACTION
    assert status_by_obj["mcrAuto"] == SupportStatus.FAILED_EXTRACTION
    assert status_by_obj["frmMain"] == SupportStatus.FAILED_EXTRACTION

    coverage = engine.calculate_coverage()
    assert coverage["vba_coverage"] == 0.0
    assert coverage["macro_coverage"] == 0.0


def test_react_expression_sanitization():
    """Verify Access calculated expressions are sanitized into valid JS identifiers."""
    assert ReactGenerator._sanitize_control_source('=GetProperties("Title")') == "propertyTitle"
    assert ReactGenerator._sanitize_control_source('=CurrentUser()') == "currentUser"
    assert ReactGenerator._sanitize_control_source('=Environ("USERNAME")') == "environUsername"
    assert ReactGenerator._sanitize_control_source('=2') == "calculatedField2"
    assert ReactGenerator._sanitize_control_source('="atar.eapRptSetup"') == "literalAtareaprptsetup"
    assert ReactGenerator._sanitize_control_source('NormalField') == "NormalField"


def test_react_unbound_form_generation():
    """Verify unbound forms generate informational pages without CRUD API calls."""
    app_ir = ApplicationIR(
        application_name="TestApp",
        forms=[
            FormIR(
                name="001_About_frm",
                record_source="",  # Unbound
                caption="About Application",
                controls=[
                    ControlIR(
                        name="lblTitle",
                        control_type="Label",
                        caption="Application Title",
                    ),
                    ControlIR(
                        name="txtProp",
                        control_type="TextBox",
                        control_source='=GetProperties("Title")',
                        caption="Title Property",
                        visible=True,
                    ),
                    ControlIR(
                        name="cmdClose",
                        control_type="CommandButton",
                        caption="Close",
                    ),
                ],
            )
        ],
    )

    gen = ReactGenerator(app_ir)
    files = gen.generate("/tmp/test_unbound")

    matching = [k for k in files.keys() if "N001AboutPage.jsx" in k]
    assert matching
    code = files[matching[0]]

    # Should NOT import CRUD API functions
    assert "getN001About" not in code
    assert "createN001About" not in code
    assert "useParams" not in code
    # Should render button with TODO handler (hump preserved in camelCase)
    assert "cmdClose" in code
    assert "TODO: Implement cmdClose" in code
    assert "Close" in code
    # Access expression should be a comment, not broken JSX value
    assert "formData.=getproperties" not in code


def test_react_list_page_th_rendering():
    """Verify list page columns render valid <th> tags."""
    app_ir = ApplicationIR(
        application_name="TestApp",
        tables=[
            TableIR(
                name="FileList",
                columns=[
                    ColumnIR(name="ID", access_type="Long Integer", auto_number=True),
                    ColumnIR(name="PathName", access_type="Short Text"),
                    ColumnIR(name="FileType", access_type="Short Text"),
                ],
            )
        ],
        forms=[
            FormIR(
                name="700_Create_Filelist_frm",
                record_source="FileList",
                caption="Create File List",
                controls=[
                    ControlIR(
                        name="lstFiles",
                        control_type="ListBox",
                        control_source="FileList",
                    ),
                    ControlIR(
                        name="txtPath",
                        control_type="TextBox",
                        control_source="PathName",
                        visible=True,
                    ),
                    ControlIR(
                        name="txtType",
                        control_type="TextBox",
                        control_source="FileType",
                        visible=True,
                    ),
                ],
            )
        ],
    )

    gen = ReactGenerator(app_ir)
    files = gen.generate("/tmp/test_list")

    matching = [k for k in files.keys() if "N700CreateFilelistPage.jsx" in k]
    assert matching
    code = files[matching[0]]
    # Must contain <th> elements, NOT raw { key: "...", header: "..." } in JSX
    assert "<th>PathName</th>" in code
    assert "<th>FileType</th>" in code
    assert '{ key: "pathName"' not in code


def test_spring_boot_application_and_web_config():
    """Verify Spring Boot generator creates Application.java and WebConfig.java."""
    app_ir = ApplicationIR(
        application_name="SampleApp",
        tables=[
            TableIR(
                name="Item",
                columns=[
                    ColumnIR(name="ID", access_type="Long Integer", auto_number=True),
                ],
                indexes=[],
            )
        ],
    )

    gen = SpringBootGenerator(app_ir, base_package="com.example.app")
    files = gen.generate("/tmp/test_spring_app")

    # Check Application.java
    matching_app = [k for k in files.keys() if "Application.java" in k]
    assert matching_app
    app_code = files[matching_app[0]]
    assert "@SpringBootApplication" in app_code
    assert "public class Application" in app_code
    assert "SpringApplication.run(Application.class, args);" in app_code
    assert "package com.example.app;" in app_code

    # Check WebConfig.java
    matching_web = [k for k in files.keys() if "WebConfig.java" in k]
    assert matching_web
    web_code = files[matching_web[0]]
    assert "@Configuration" in web_code
    assert "WebMvcConfigurer" in web_code
    assert "addCorsMappings" in web_code


def test_postgres_fk_deduplication_and_defaults():
    """Verify duplicate FKs are omitted and Access expressions converted."""
    from converter.app.ir.models import RelationshipIR

    app_ir = ApplicationIR(
        application_name="TestApp",
        tables=[
            TableIR(
                name="tag_grp_tb",
                columns=[
                    ColumnIR(name="tag_grp_id", access_type="Long Integer", auto_number=True),
                ],
            ),
            TableIR(
                name="tag_nme_tb",
                columns=[
                    ColumnIR(name="tag_nme_id", access_type="Long Integer", auto_number=True),
                    ColumnIR(name="tag_grp_id", access_type="Long Integer"),
                    ColumnIR(
                        name="created_by",
                        access_type="Short Text",
                        default_value='=Environ("USERNAME")',
                    ),
                ],
            ),
        ],
        relationships=[
            RelationshipIR(
                name="tag_grp_tbtag_nme_tb",
                parent_table="tag_grp_tb",
                child_table="tag_nme_tb",
                parent_columns=["tag_grp_id"],
                child_columns=["tag_grp_id"],
            ),
            # Duplicate relationship with same name/table
            RelationshipIR(
                name="tag_grp_tbtag_nme_tb",
                parent_table="tag_grp_tb",
                child_table="tag_nme_tb",
                parent_columns=["tag_grp_id"],
                child_columns=["tag_grp_id"],
            ),
        ],
    )

    gen = PostgresSchemaGenerator(app_ir)
    sql = gen.generate()

    # Must contain the FK constraint exactly once
    count = sql.count('ADD CONSTRAINT "tag_grp_tbtag_nme_tb"')
    assert count == 1, f"Expected 1 FK constraint, found {count}"

    # Default value must be CURRENT_USER, NOT '=Environ("USERNAME")'
    assert 'DEFAULT CURRENT_USER' in sql
    assert 'DEFAULT \'="Environ("USERNAME")"\'' not in sql
    assert 'DEFAULT \'=Environ("USERNAME")\'' not in sql

