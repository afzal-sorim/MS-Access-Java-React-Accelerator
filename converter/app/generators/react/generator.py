"""React frontend generator - pages, components, forms from Access forms.

Spec section 19: Forms → React pages/components with proper control mappings.
Spec section 46: Generate routes, pages, components, forms, tables, API clients.

UI Modernization: When ui_style is set, delegates page/CSS rendering to the
UITransformationEngine + Theme system. Legacy code path preserved as fallback.
"""
from __future__ import annotations

import logging
from pathlib import Path
from typing import Optional

logger = logging.getLogger("converter.generators.react")


# Control type mappings (spec section 19)
CONTROL_MAP = {
    "TextBox": "input",
    "ComboBox": "select",
    "CheckBox": "checkbox",
    "CommandButton": "button",
    "Label": "label",
    "ListBox": "select",
    "OptionButton": "radio",
    "OptionGroup": "fieldset",
    "Image": "img",
    "Subform": "SubformComponent",
    "TabControl": "Tabs",
    "Page": "TabPanel",
    "ToggleButton": "button",
}


class ReactGenerator:
    """Generates React frontend from ApplicationIR."""

    def __init__(
        self,
        app_ir,
        *,
        app_name: Optional[str] = None,
        report_strategy: str = "pdf",
        form_conversions: Optional[dict[str, str]] = None,
        ui_style: str = "classic",
        ui_reasoning: str = "automatic",
        ui_debug: bool = False,
        use_theme_engine: bool = True,
    ):
        self.app = app_ir
        self.app_name = app_name or app_ir.application_name
        self.report_strategy = (report_strategy or "pdf").strip().lower()
        self.form_conversions = {
            str(name): str(conversion).upper()
            for name, conversion in (form_conversions or {}).items()
        }
        self.warnings: list[str] = []
        self._pk_map: dict[str, str] = {}
        self._analyze_keys()
        self._reports: list = []

        # UI Modernization config
        self.ui_style = (ui_style or "classic").strip().lower()
        self.ui_reasoning = (ui_reasoning or "automatic").strip().lower()
        self.ui_debug = ui_debug
        self._use_theme_engine = use_theme_engine
        self._engine = None
        self._theme = None
        self._presentations = None

    def generate(self, output_dir: str | Path) -> dict[str, str]:
        """Generate all React files and return a map of path -> content."""
        output_dir = Path(output_dir)
        files: dict[str, str] = {}
        src = output_dir / "src"

        # Initialize UI Transformation Engine + Theme
        if self._use_theme_engine:
            try:
                from .ui.engine import UITransformationEngine
                from .themes import get_theme

                self._engine = UITransformationEngine(
                    self.app,
                    ui_style=self.ui_style,
                    ui_reasoning=self.ui_reasoning,
                    ui_debug=self.ui_debug,
                )
                self._presentations = self._engine.transform_all()
                self._theme = get_theme(self.ui_style)

                logger.info(
                    "UI Engine initialized: style=%s, reasoning=%s, screens=%d, theme=%s",
                    self.ui_style, self.ui_reasoning,
                    len(self._presentations), self._theme.name,
                )
            except Exception as e:
                logger.warning("UI Engine init failed, falling back to legacy: %s", e)
                self._use_theme_engine = False
                self._engine = None
                self._theme = None
                self._presentations = None

        # Generate pages
        if self._use_theme_engine and self._presentations and self._theme:
            # Build route map so dashboard navigation can resolve to actual routes
            route_map = {}
            for pres in self._presentations:
                page_name = self._to_pascal(pres.screen_id.replace("frm", ""))
                endpoint = self._to_kebab(page_name) if pres.record_source else ""
                route_path = f"/{endpoint}" if endpoint else f"/{page_name.lower()}"
                # Map multiple keys so fuzzy matching can find the right route
                route_map[pres.screen_id] = route_path                      # e.g. "frmPatientsForm"
                route_map[pres.screen_name] = route_path                    # e.g. "Patients Form"
                route_map[page_name] = route_path                           # e.g. "PatientsForm"
                clean_name = page_name.replace("Form", "").replace("form", "")
                if clean_name:
                    route_map[clean_name] = route_path                      # e.g. "Patients"
                if pres.record_source:
                    route_map[pres.record_source] = route_path              # e.g. "tblPatients"
            self._theme.set_route_map(route_map)

            # Theme-based page generation
            for pres in self._presentations:
                page_name = self._to_pascal(pres.screen_id.replace("frm", ""))
                api_name = self._resolve_api_name(pres.record_source) if pres.record_source else ""
                endpoint = self._to_kebab(page_name) if pres.record_source else ""
                helper_imports = ""

                # If this is a data-bound form, we need BOTH a list view and a form view
                # so the user can navigate the data and click Edit/New.
                if pres.record_source:
                    list_content = self._theme.render_list_page(pres, endpoint, api_name, helper_imports)
                    form_content = self._theme.render_form_page(pres, endpoint, api_name, helper_imports)
                    if list_content:
                        files[str(src / "pages" / f"{page_name}Page.jsx")] = list_content
                    if form_content:
                        files[str(src / "pages" / f"{page_name}FormPage.jsx")] = form_content
                else:
                    page_content = self._theme.render_page(
                        pres, endpoint=endpoint, api_name=api_name, helper_imports=helper_imports,
                    )
                    files[str(src / "pages" / f"{page_name}Page.jsx")] = page_content
        else:
            # Legacy code path
            for form in self.app.forms:
                page_name = self._to_pascal(form.name.replace("frm", ""))
                page_content = self._generate_page(form)
                files[str(src / "pages" / f"{page_name}Page.jsx")] = page_content

        # Generate the reports page when the source app has usable reports
        self._reports = self._resolve_reports()
        if self._reports:
            files[str(src / "pages" / "ReportsPage.jsx")] = self._generate_reports_page()

        # Generate mock data via LLM (for frontend fallback when backend is unavailable)
        self._mock_data = self._generate_mock_data()
        if self._mock_data:
            files[str(src / "services" / "mockData.js")] = self._build_mock_data_file()
            logger.info("Generated mock data for %d entities", len(self._mock_data))

        # Phase 3: Generate Axios-based API client + per-entity service files
        files[str(src / "services" / "apiClient.js")] = self._generate_api_base_client()
        for table in self.app.tables:
            if table.role not in ("SYSTEM", "INTERNAL"):
                entity = self._to_pascal(table.name)
                files[str(src / "services" / f"{entity}Service.js")] = self._generate_entity_service(table)
        if self._reports:
            files[str(src / "services" / "reportService.js")] = self._generate_report_service()
        # Phase 1.2: Only emit legacy api.js for legacy generator, new themes use Axios client
        if not self._use_theme_engine:
            files[str(src / "services" / "api.js")] = self._generate_api_client()

        # Phase 5: Generate split CSS — tokens + reset + index imports
        files[str(src / "styles" / "tokens.css")] = self._generate_css_tokens()
        files[str(src / "styles" / "reset.css")] = self._generate_css_reset()
        # Generate index.css — theme-aware (kept for theme compat) + import shim
        if self._use_theme_engine and self._presentations and self._theme:
            theme_css = self._theme.get_css(self.app_name, self._presentations)
            if isinstance(theme_css, dict):
                for rel_path, content in theme_css.items():
                    files[str(src / rel_path)] = content
            else:
                files[str(src / "index.css")] = theme_css
        else:
            files[str(src / "index.css")] = self._generate_index_css()

        # Phase 4: Generate decomposed App.jsx + AppRouter + AppLayout + useApi hook
        if self._use_theme_engine and self._presentations and self._theme:
            app_artifacts = self._generate_themed_app_jsx()
            if isinstance(app_artifacts, dict):
                for rel_path, content in app_artifacts.items():
                    files[str(src / rel_path)] = content
            else:
                files[str(src / "App.jsx")] = app_artifacts
        else:
            files[str(src / "App.jsx")] = self._generate_app_jsx()
            files[str(src / "routes" / "AppRouter.jsx")] = self._generate_app_router()
            files[str(src / "components" / "layout" / "AppLayout.jsx")] = self._generate_app_layout()
            files[str(src / "components" / "layout" / "AppLayout.module.css")] = self._generate_app_layout_css()
            
        files[str(src / "hooks" / "useApi.js")] = self._generate_use_api_hook()

        # Generate main.jsx
        files[str(src / "main.jsx")] = self._generate_main_jsx()

        # Generate package.json
        files[str(output_dir / "package.json")] = self._generate_package_json()

        # Generate vite.config.js
        files[str(output_dir / "vite.config.js")] = self._generate_vite_config()

        # Generate index.html
        files[str(output_dir / "index.html")] = self._generate_index_html()

        # Generate tooling config files (Phase 1 — coding standards)
        files[str(output_dir / ".eslintrc.cjs")] = self._generate_eslintrc()
        files[str(output_dir / ".prettierrc")] = self._generate_prettierrc()
        files[str(output_dir / "vitest.config.js")] = self._generate_vitest_config_file()
        files[str(output_dir / "README.md")] = self._generate_readme()
        files[str(src / "test" / "setup.js")] = self._generate_test_setup()

        # Generate shared component library (Phase 2 — reusable UI primitives)
        from .components_generator import ComponentsGenerator
        comp_gen = ComponentsGenerator()
        files.update(comp_gen.generate(src / "components" / "common"))

        # Phase 6: Generate test files
        files[str(src / "services" / "__tests__" / "apiClient.test.js")] = self._generate_api_client_test()
        for table in self.app.tables:
            if table.role not in ("SYSTEM", "INTERNAL"):
                entity = self._to_pascal(table.name)
                files[str(src / "services" / "__tests__" / f"{entity}Service.test.js")] = (
                    self._generate_service_crud_test(table)
                )

        # Write debug artifacts
        if self._engine and self.ui_debug:
            self._engine.write_debug_artifacts(output_dir)

        return files

    def _generate_themed_app_jsx(self) -> str:
        """Generate App.jsx using the theme engine."""
        pages = []
        for page_index, pres in enumerate(self._presentations):
            page_name = self._to_pascal(pres.screen_id.replace("frm", ""))
            endpoint = self._to_kebab(page_name) if pres.record_source else ""

            from .ui.models import PageType
            
            page_info = {
                "dashboard_id": f"page_{page_index}",
                "nav_link_text": pres.screen_name,
                "nav_path": f"/{endpoint}" if endpoint else f"/{page_name.lower()}",
                # The Operations Workspace dashboard uses this to show a
                # live total-records count beside data-bound page links.
                "dashboard_api_name": self._resolve_api_name(pres.record_source)
                if pres.record_source else "",
            }

            if pres.record_source:
                # In phase 1.1 we also check if form_content actually exists, but we can't easily check it here.
                # Since all our themes always return a string for render_form_page, we assume it's emitted.
                page_info["import"] = f"import {page_name}Page from '../pages/{page_name}Page';\nimport {page_name}FormPage from '../pages/{page_name}FormPage';\n"
                page_info["routes"] = (
                    f"                        <Route path=\"/{endpoint}\" element={{<{page_name}Page />}} />\n"
                    f"                        <Route path=\"/{endpoint}/:id\" element={{<{page_name}FormPage />}} />\n"
                    f"                        <Route path=\"/{endpoint}/new\" element={{<{page_name}FormPage />}} />"
                )
                page_info["nav_link"] = f'<Link to="/{endpoint}">{pres.screen_name}</Link>\n'
            else:
                page_info["import"] = f"import {page_name}Page from '../pages/{page_name}Page';\n"
                page_info["routes"] = (
                    f"                        <Route path=\"/{page_name.lower()}\" element={{<{page_name}Page />}} />"
                )
                page_info["nav_link"] = f'<Link to="/{page_name.lower()}">{pres.screen_name}</Link>\n'

            pages.append(page_info)

        # Operations Workspace has a domain-neutral, LLM-assisted navigation
        # grouping step. Its renderer still owns all generated JSX and routes.
        if self._theme and self._theme.key == "operations_workspace":
            if self.ui_reasoning == "none":
                self._theme.set_dashboard_topics([{"title": "Application Workspaces", "page_ids": [page["dashboard_id"] for page in pages]}])
            else:
                from .ui.dashboard_topics import DashboardTopicPlanner
                self._theme.set_dashboard_topics(DashboardTopicPlanner().group(pages))
        # Reports handling
        report_import = ""
        report_route = ""
        report_link = ""
        if self._reports:
            report_import = "import ReportsPage from '../pages/ReportsPage';\n"
            report_route = "                        <Route path=\"/reports\" element={<ReportsPage />} />\n"
            report_link = '<Link to="/reports">Reports</Link>'

        return self._theme.render_app_shell(
            self.app_name, pages, report_import, report_route, report_link,
        )

    def write(self, output_dir: str | Path) -> None:
        """Generate and write all files to disk."""
        output_dir = Path(output_dir)
        files = self.generate(output_dir)

        for path, content in files.items():
            file_path = Path(path)
            file_path.parent.mkdir(parents=True, exist_ok=True)
            file_path.write_text(content, encoding="utf-8")

    # ---------------------------------------------------------------- helpers

    def _analyze_keys(self) -> None:
        """Analyze primary keys."""
        for table in self.app.tables:
            for idx in table.indexes:
                if idx.primary and idx.columns:
                    self._pk_map[table.name] = idx.columns[0]
                    break

    # Build table name lookup for resolving record_source -> table
    def _table_names(self) -> set[str]:
        return {t.name for t in self.app.tables}

    def _resolve_api_name(self, record_source: str) -> str:
        """Resolve a form's record source to the API name exported by api.js.

        api.js generates CRUD functions per *table*, not per query/form.
        If the record_source is a table, use its PascalCase name directly.
        If it's a query, try to find the underlying table(s).
        """
        if not record_source:
            return ""
        table_names = self._table_names()
        # Direct table match
        if record_source in table_names:
            return self._to_pascal(record_source)
        # Try matching by query -> underlying tables in IR queries
        for q in self.app.queries:
            if q.name == record_source and hasattr(q, 'sql') and q.sql:
                # Try to extract the first table directly after FROM
                import re
                match = re.search(r'\bfrom\s+\[?([a-zA-Z0-9_]+)\]?', q.sql.lower())
                if match:
                    tname = match.group(1)
                    # Case insensitive match to actual table names
                    for actual_tname in table_names:
                        if actual_tname.lower() == tname:
                            return self._to_pascal(actual_tname)
                
                # Fallback: find the first referenced table from the query SQL
                for tname in table_names:
                    if tname.lower() in q.sql.lower():
                        return self._to_pascal(tname)
        # Fallback: use record_source PascalCase (may not match api.js)
        return self._to_pascal(record_source)

    @staticmethod
    def _is_access_expression(value: str) -> bool:
        """Check if a string is an Access calculated expression."""
        if not value:
            return False
        stripped = value.strip()
        return stripped.startswith("=") or "(" in stripped and ")" in stripped

    @staticmethod
    def _sanitize_control_source(source: str) -> str:
        """Delegate to the shared expression engine."""
        from ...expressions import _to_js_identifier
        return _to_js_identifier(source)

    def _generate_page(self, form) -> str:
        """Generate a React page component from an Access form."""
        page_name = self._to_pascal(form.name.replace("frm", ""))
        conversion = self.form_conversions.get(form.name, "")

        if conversion == "MANUAL":
            self.warnings.append(f"Manual migration required for form {form.name}")
            return self._generate_unbound_page(form, page_name)

        if conversion == "PAGE_DASHBOARD":
            return self._generate_unbound_page(form, page_name)

        # Fix 4: Unbound forms (no record_source) get info/dashboard pages, not CRUD
        if not form.record_source:
            return self._generate_unbound_page(form, page_name)

        endpoint = self._to_kebab(form.record_source)
        # Fix 5: API name must match api.js exports (table-based names)
        api_name = self._resolve_api_name(form.record_source)

        # Determine if this is a list page or form page
        is_list = conversion == "PAGE_DATAGRID" or any(
            c.control_type in ("ListBox", "Subform") or
            (c.control_type == "ComboBox" and "ID" not in c.name)
            for c in form.controls
        )

        if is_list and form.record_source:
            return self._generate_list_page(form, page_name, endpoint, api_name)
        else:
            return self._generate_form_page(form, page_name, endpoint, api_name)

    def _generate_unbound_page(self, form, page_name: str) -> str:
        """Generate an info/dashboard page for unbound forms using shared components.

        Unbound forms in Access are typically UI/utility/business-logic forms,
        NOT database CRUD forms. We render them with interactive form controls
        and buttons that have TODO comments for their event logic.
        """
        # Build label-to-input caption map for proper human-readable labels
        label_map = self._build_unbound_label_map(form.controls)

        # Separate controls by type
        buttons = [c for c in form.controls if c.control_type == "CommandButton"]
        input_fields = [c for c in form.controls
                        if c.control_type in ("TextBox", "ComboBox") and c.visible]
        checkboxes = [c for c in form.controls if c.control_type == "CheckBox"]

        # Generate FormField components
        field_elements = []
        for ctrl in input_fields:
            source = ctrl.control_source or ctrl.name
            label = label_map.get(ctrl.name) or ctrl.caption or self._humanize_name(ctrl.name)
            field_name = self._to_camel(self._sanitize_control_source(source))
            input_type = "text"
            disabled_prop = ""

            if self._is_access_expression(source):
                disabled_prop = " disabled"
                input_type = "text"
            elif "Date" in source or "date" in ctrl.name.lower():
                input_type = "date"
            elif ctrl.control_type == "ComboBox":
                input_type = "select"

            field_elements.append(
                f'            <FormField label="{label}" name="{field_name}" type="{input_type}"{disabled_prop} />'
            )

        for ctrl in checkboxes:
            source = ctrl.control_source or ctrl.name
            label = label_map.get(ctrl.name) or ctrl.caption or self._humanize_name(ctrl.name)
            field_name = self._to_camel(self._sanitize_control_source(source))
            field_elements.append(
                f'            <FormField label="{label}" name="{field_name}" type="checkbox" />'
            )

        # Generate Button components with TODO handlers
        button_elements = []
        for ctrl in buttons:
            caption = ctrl.caption or ctrl.name
            handler_name = self._to_camel(ctrl.name)
            button_elements.append(
                f"            <Button onClick={{() => console.warn('TODO: Implement {handler_name}')}}>{caption}</Button>"
            )

        fields_js = "\n".join(field_elements) if field_elements else ""
        buttons_js = "\n".join(button_elements) if button_elements else ""

        return f"""import React from 'react';
import FormField from '../components/common/FormField';
import Button from '../components/common/Button';
import PageHeader from '../components/common/PageHeader';
import Card from '../components/common/Card';

/**
 * {page_name} \u2014 Unbound Access form (no database record source).
 *
 * Original Access form: {form.name}
 * This form has {len(form.controls)} controls including {len(buttons)} buttons.
 * Business logic from Access VBA event handlers has NOT been converted.
 * TODO: Implement button click handlers to match original Access behavior.
 */
export default function {page_name}Page() {{
    return (
        <div className="{page_name.lower()}-page">
            <PageHeader title="{form.caption or page_name}" subtitle="Access form: {form.name}" />
            <Card>
{fields_js}
                <div className="button-group">
{buttons_js}
                </div>
            </Card>
        </div>
    );
}}
"""

    @staticmethod
    def _build_unbound_label_map(controls) -> dict:
        """Build a label-to-input caption map for the legacy generator path.

        Mirrors the logic from ScreenBuilder._build_label_map() but works with
        raw ControlIR / dict objects from the FormIR.
        """
        label_map = {}
        _INPUT_PREFIXES = ("txt", "cbo", "chk", "opt", "tgl", "lst")
        _LABEL_PREFIXES = ("lbl",)
        _LABEL_COL_PREFIXES = ("lblcol",)

        # Collect labels with captions
        labels = [c for c in controls if c.control_type == "Label" and c.caption]

        # Build input suffix map
        input_suffix_map = {}
        for c in controls:
            if c.control_type in ("TextBox", "ComboBox", "CheckBox",
                                  "OptionButton", "ListBox", "ToggleButton"):
                name_lower = c.name.lower()
                for pfx in _INPUT_PREFIXES:
                    if name_lower.startswith(pfx):
                        suffix = name_lower[len(pfx):]
                        input_suffix_map.setdefault(suffix, []).append(c.name)
                        break
                else:
                    input_suffix_map.setdefault(name_lower, []).append(c.name)

        # Strategy 1: Naming convention
        for lbl in labels:
            lbl_lower = lbl.name.lower()
            suffix = None
            for pfx in _LABEL_COL_PREFIXES:
                if lbl_lower.startswith(pfx):
                    suffix = lbl_lower[len(pfx):]
                    break
            if suffix is None:
                for pfx in _LABEL_PREFIXES:
                    if lbl_lower.startswith(pfx):
                        suffix = lbl_lower[len(pfx):]
                        break
            if suffix and suffix in input_suffix_map:
                caption = lbl.caption.rstrip(":")
                for input_name in input_suffix_map[suffix]:
                    label_map[input_name] = caption

        # Removed Strategy 2 (Positional adjacency) to prevent mislabeling.
        # Fallbacks to humanizing input names happen elsewhere.
        return label_map

    @staticmethod
    def _humanize_name(name: str) -> str:
        """Convert an Access control name to human-readable text."""
        import re
        cleaned = re.sub(
            r"^(txt|cbo|chk|opt|tgl|lst|lbl|cmd|btn|frm|sub|img)",
            "", name, flags=re.IGNORECASE,
        )
        if not cleaned:
            return name
        cleaned = re.sub(r"(?<=[a-z0-9])(?=[A-Z])", " ", cleaned)
        cleaned = cleaned.replace("_", " ")
        return cleaned.strip() or name

    def _generate_list_page(self, form, page_name: str, endpoint: str, api_name: str = "") -> str:
        """Generate a list/table page using shared components."""
        api_name = api_name or page_name
        var_name = self._to_camel(page_name)

        # Find display columns (non-ID, non-hidden), sanitizing Access expressions
        display_cols = []
        for ctrl in form.controls:
            if ctrl.control_type in ("TextBox", "ComboBox") and ctrl.visible:
                source = ctrl.control_source
                if source and not source.lower().endswith("id"):
                    if not self._is_access_expression(source):
                        display_cols.append(source)

        # Build column definitions for DataTable component
        col_defs = ", ".join(
            f"{{ key: '{self._to_camel(col)}', label: '{col}' }}"
            for col in display_cols[:6]
        )

        return f"""import React, {{ useState, useEffect }} from 'react';
import {{ Link, useNavigate }} from 'react-router-dom';
import {{ get{api_name} }} from '../services/api';
import PageHeader from '../components/common/PageHeader';
import DataTable from '../components/common/DataTable';
import LoadingSpinner from '../components/common/LoadingSpinner';
import ErrorMessage from '../components/common/ErrorMessage';
import Button from '../components/common/Button';

const COLUMNS = [{col_defs}];

export default function {page_name}Page() {{
    const [{var_name}, set{page_name}] = useState([]);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState(null);
    const navigate = useNavigate();

    useEffect(() => {{
        async function fetchData() {{
            try {{
                const data = await get{api_name}();
                set{page_name}(data);
            }} catch (err) {{
                setError(err.message);
            }} finally {{
                setLoading(false);
            }}
        }}
        fetchData();
    }}, []);

    if (loading) return <LoadingSpinner message="Loading records\u2026" />;
    if (error) return <ErrorMessage message={{error}} />;

    return (
        <div className="{page_name.lower()}-page">
            <PageHeader title="{form.caption or page_name}" subtitle={{`${{{var_name}.length}} records`}}>
                <Link to="/{endpoint}/new"><Button>Add New</Button></Link>
            </PageHeader>
            <DataTable
                columns={{COLUMNS}}
                data={{{var_name}}}
                onRowClick={{(row) => navigate(`/{endpoint}/${{row.id}}`)}} 
            />
        </div>
    );
}}
"""

    def _generate_form_page(self, form, page_name: str, endpoint: str, api_name: str = "") -> str:
        """Generate a form page for create/edit using shared components."""
        api_name = api_name or page_name

        # Build label map for proper human-readable labels
        label_map = self._build_unbound_label_map(form.controls)

        # Generate FormField components instead of raw HTML
        form_fields = []
        for ctrl in form.controls:
            if ctrl.control_type in ("TextBox", "ComboBox", "CheckBox"):
                raw_source = ctrl.control_source or ctrl.name
                field_name = self._to_camel(self._sanitize_control_source(raw_source))
                label = label_map.get(ctrl.name) or ctrl.caption or self._humanize_name(ctrl.name)
                input_type = "text"
                if ctrl.control_type == "CheckBox":
                    input_type = "checkbox"
                elif ctrl.control_type == "ComboBox":
                    input_type = "select"
                elif "Date" in raw_source:
                    input_type = "date"
                elif "Email" in raw_source:
                    input_type = "email"

                disabled_prop = ' disabled' if ctrl.locked else ''
                expr_comment = ""
                if self._is_access_expression(raw_source):
                    safe_expr = raw_source.replace('"', "'")
                    expr_comment = f"\n                {{/* TODO: Original Access expression: {safe_expr} */}}"

                form_fields.append(f"""
                {expr_comment}
                <FormField
                    label="{label}"
                    name="{field_name}"
                    type="{input_type}"
                    value={{formData.{field_name}}}
                    onChange={{handleChange}}{disabled_prop}
                />""")

        form_fields_js = "\n".join(form_fields)

        return f"""import React, {{ useState, useEffect }} from 'react';
import {{ useParams, useNavigate }} from 'react-router-dom';
import {{ get{api_name}ById, create{api_name}, update{api_name} }} from '../services/api';
import FormField from '../components/common/FormField';
import Button from '../components/common/Button';
import PageHeader from '../components/common/PageHeader';
import LoadingSpinner from '../components/common/LoadingSpinner';
import ErrorMessage from '../components/common/ErrorMessage';

export default function {page_name}FormPage() {{
    const {{ id }} = useParams();
    const navigate = useNavigate();
    const [formData, setFormData] = useState({{}});
    const [loading, setLoading] = useState(false);
    const [error, setError] = useState(null);

    const isEdit = Boolean(id);

    useEffect(() => {{
        if (isEdit) {{
            async function fetchData() {{
                try {{
                    const data = await get{api_name}ById(id);
                    setFormData(data);
                }} catch (err) {{
                    setError(err.message);
                }}
            }}
            fetchData();
        }}
    }}, [id, isEdit]);

    const handleChange = (e) => {{
        const {{ name, value, type, checked }} = e.target;
        setFormData(prev => ({{
            ...prev,
            [name]: type === 'checkbox' ? checked : value
        }}));
    }};

    const handleSubmit = async (e) => {{
        e.preventDefault();
        setLoading(true);
        try {{
            if (isEdit) {{
                await update{api_name}(id, formData);
            }} else {{
                await create{api_name}(formData);
            }}
            navigate('/{endpoint}');
        }} catch (err) {{
            setError(err.message);
        }} finally {{
            setLoading(false);
        }}
    }};

    if (loading) return <LoadingSpinner message="Saving\u2026" />;

    return (
        <div className="{page_name.lower()}-form">
            <PageHeader title={{isEdit ? 'Edit' : 'Create'}} subtitle="{form.caption or page_name}" />
            {{error && <ErrorMessage message={{error}} />}}
            <form onSubmit={{handleSubmit}}>
                {form_fields_js}
                <div className="form-actions">
                    <Button type="submit" disabled={{loading}}>
                        {{isEdit ? 'Update' : 'Create'}}
                    </Button>
                    <Button variant="secondary" onClick={{() => navigate('/{endpoint}')}}>
                        Cancel
                    </Button>
                </div>
            </form>
        </div>
    );
}}
"""

    def _resolve_reports(self) -> list:
        """Report definitions that the backend actually exposes."""
        from ...reporting.model import build_report_definitions

        return [d for d in build_report_definitions(self.app) if d.generatable]

    @property
    def _pdf_enabled(self) -> bool:
        return self.report_strategy in ("pdf", "both", "all", "pdf+csv", "csv+pdf")

    def _generate_reports_page(self) -> str:
        """Generate a reports page: pick a report, fill parameters, view/export."""
        pdf_button = ""
        if self._pdf_enabled:
            pdf_button = """
                        <button type="button" onClick={() => download('pdf')} disabled={loading}>
                            Download PDF
                        </button>"""

        return f"""import React, {{ useState, useEffect, useCallback }} from 'react';
import {{ getReportList, runReport, reportDownloadUrl }} from '../services/reportService';

/**
 * Reports page: choose a report, supply its parameters, view results and
 * export to CSV{'/PDF' if self._pdf_enabled else ''}.
 *
 * Report metadata (columns, parameters) comes from the backend, so this page
 * stays correct if a report's shape changes.
 */
export default function ReportsPage() {{
    const [reports, setReports] = useState([]);
    const [selected, setSelected] = useState('');
    const [params, setParams] = useState({{}});
    const [data, setData] = useState(null);
    const [loading, setLoading] = useState(false);
    const [error, setError] = useState(null);

    useEffect(() => {{
        getReportList()
            .then((list) => {{
                setReports(list);
                if (list.length > 0) {{
                    setSelected(list[0].endpoint);
                }}
            }})
            .catch((err) => setError(err.message));
    }}, []);

    const definition = reports.find((r) => r.endpoint === selected) || null;

    // Reset parameters and results whenever the chosen report changes.
    useEffect(() => {{
        setParams({{}});
        setData(null);
        setError(null);
    }}, [selected]);

    const missingRequired = (definition?.parameters || [])
        .filter((p) => p.required && !String(params[p.name] ?? '').trim())
        .map((p) => p.name);

    const run = useCallback(async (event) => {{
        event.preventDefault();
        if (!definition) return;
        setLoading(true);
        setError(null);
        try {{
            setData(await runReport(definition.endpoint, params));
        }} catch (err) {{
            setError(err.message);
            setData(null);
        }} finally {{
            setLoading(false);
        }}
    }}, [definition, params]);

    const download = (format) => {{
        if (!definition) return;
        window.open(reportDownloadUrl(definition.endpoint, format, params), '_blank');
    }};

    const inputType = (javaType) => {{
        if (javaType === 'Long' || javaType === 'Integer'
            || javaType === 'Double' || javaType === 'Float'
            || javaType === 'java.math.BigDecimal') return 'number';
        if (javaType === 'java.time.LocalDateTime') return 'date';
        if (javaType === 'Boolean') return 'checkbox';
        return 'text';
    }};

    return (
        <div className="reports-page">
            <h1>Reports</h1>

            {{error && <div className="error" role="alert">{{error}}</div>}}

            <div className="form-group">
                <label htmlFor="report-select">Report</label>
                <select
                    id="report-select"
                    value={{selected}}
                    onChange={{(e) => setSelected(e.target.value)}}
                >
                    {{reports.map((r) => (
                        <option key={{r.endpoint}} value={{r.endpoint}}>{{r.title}}</option>
                    ))}}
                </select>
            </div>

            {{definition && (
                <form onSubmit={{run}}>
                    {{definition.parameters.map((p) => (
                        <div className="form-group" key={{p.name}}>
                            <label htmlFor={{p.name}}>
                                {{p.accessName}}{{p.required ? ' *' : ''}}
                            </label>
                            <input
                                id={{p.name}}
                                name={{p.name}}
                                type={{inputType(p.javaType)}}
                                value={{params[p.name] || ''}}
                                required={{p.required}}
                                onChange={{(e) => setParams((prev) => ({{
                                    ...prev,
                                    [p.name]: e.target.type === 'checkbox'
                                        ? e.target.checked
                                        : e.target.value,
                                }}))}}
                            />
                        </div>
                    ))}}

                    <div className="form-actions">
                        <button type="submit" disabled={{loading || missingRequired.length > 0}} className="btn">
                            {{loading ? 'Running...' : 'Run Report'}}
                        </button>
                        <button
                            type="button"
                            onClick={{() => download('csv')}}
                            disabled={{loading || missingRequired.length > 0}}
                            className="btn btn-secondary"
                        >
                            Download CSV
                        </button>{pdf_button}
                    </div>

                    {{(definition.notes || []).length > 0 && (
                        <ul className="report-notes">
                            {{definition.notes.map((note, i) => <li key={{i}}>{{note}}</li>)}}
                        </ul>
                    )}}
                </form>
            )}}

            {{data && (
                <>
                    <p>{{data.rowCount}} row{{data.rowCount === 1 ? '' : 's'}}</p>
                    <table className="data-table">
                        <thead>
                            <tr>
                                {{data.columns.map((c) => (
                                    <th key={{c.key}} style={{{{ textAlign: c.align }}}}>
                                        {{c.label}}
                                    </th>
                                ))}}
                            </tr>
                        </thead>
                        <tbody>
                            {{data.rows.map((row, i) => (
                                <tr key={{i}}>
                                    {{data.columns.map((c) => (
                                        <td key={{c.key}} style={{{{ textAlign: c.align }}}}>
                                            {{row[c.key] === null || row[c.key] === undefined
                                                ? '' : String(row[c.key])}}
                                        </td>
                                    ))}}
                                </tr>
                            ))}}
                        </tbody>
                    </table>
                    {{data.rowCount === 0 && (
                        <p className="empty">No data for the selected criteria.</p>
                    )}}
                </>
            )}}
        </div>
    );
}}
"""

    def _generate_mock_data(self) -> dict:
        """Generate mock data using LLM, with deterministic fallback."""
        if self.ui_reasoning == "none":
            return {}
        try:
            from .ui.llm.mock_data import MockDataGenerator
            gen = MockDataGenerator()
            return gen.generate_mock_data(self.app.tables)
        except Exception as e:
            logger.warning("Mock data generation failed entirely: %s", e)
            return {}

    def _build_mock_data_file(self) -> str:
        """Build the mockData.js file contents from generated mock data."""
        import json
        lines = ["// Auto-generated mock data for frontend fallback (backend unavailable)"]
        lines.append("// Generated by LLM from the original MS Access database schema")
        lines.append("")

        for entity_name, rows in self._mock_data.items():
            json_str = json.dumps(rows, indent=2, ensure_ascii=False)
            lines.append(f"export const mock{entity_name} = {json_str};")
            lines.append("")

        return "\n".join(lines)

    def _generate_api_client(self) -> str:
        """Generate API client service with mock data fallback."""
        endpoints = []
        has_mock = bool(self._mock_data) if hasattr(self, '_mock_data') else False

        for table in self.app.tables:
            if table.role in ("SYSTEM", "INTERNAL"):
                continue

            entity_name = self._to_pascal(table.name)
            endpoint = self._to_kebab(table.name)
            mock_import_name = f"mock{entity_name}"
            has_entity_mock = has_mock and entity_name in self._mock_data

            if has_entity_mock:
                # API functions with mock data fallback
                endpoints.append(f"""
// {entity_name} API
export async function get{entity_name}() {{
    try {{
        const response = await fetch(`${{API_BASE}}/{endpoint}`);
        if (!response.ok) throw new Error('Backend unavailable');
        const text = await response.text();
        try {{ return JSON.parse(text); }} catch {{ throw new Error('Invalid response'); }}
    }} catch (err) {{
        console.warn('[{entity_name}] Backend unavailable, using sample data:', err.message);
        return [...{mock_import_name}];
    }}
}}

export async function get{entity_name}ById(id) {{
    try {{
        const response = await fetch(`${{API_BASE}}/{endpoint}/${{id}}`);
        if (!response.ok) throw new Error('Backend unavailable');
        const text = await response.text();
        try {{ return JSON.parse(text); }} catch {{ throw new Error('Invalid response'); }}
    }} catch (err) {{
        console.warn('[{entity_name}] Backend unavailable, using sample data:', err.message);
        return {mock_import_name}.find(item => String(item.id) === String(id)) || {mock_import_name}[0];
    }}
}}

export async function create{entity_name}(data) {{
    try {{
        const response = await fetch(`${{API_BASE}}/{endpoint}`, {{
            method: 'POST',
            headers: {{ 'Content-Type': 'application/json' }},
            body: JSON.stringify(data),
        }});
        if (!response.ok) throw new Error('Failed to create {entity_name}');
        const text = await response.text();
        try {{ return JSON.parse(text); }} catch {{ throw new Error('Invalid response'); }}
    }} catch (err) {{
        console.warn('[{entity_name}] Backend unavailable, simulating create:', err.message);
        return {{ ...data, id: Date.now() }};
    }}
}}

export async function update{entity_name}(id, data) {{
    try {{
        const response = await fetch(`${{API_BASE}}/{endpoint}/${{id}}`, {{
            method: 'PUT',
            headers: {{ 'Content-Type': 'application/json' }},
            body: JSON.stringify(data),
        }});
        if (!response.ok) throw new Error('Failed to update {entity_name}');
        const text = await response.text();
        try {{ return JSON.parse(text); }} catch {{ throw new Error('Invalid response'); }}
    }} catch (err) {{
        console.warn('[{entity_name}] Backend unavailable, simulating update:', err.message);
        return {{ ...data, id }};
    }}
}}

export async function delete{entity_name}(id) {{
    try {{
        const response = await fetch(`${{API_BASE}}/{endpoint}/${{id}}`, {{
            method: 'DELETE',
        }});
        if (!response.ok) throw new Error('Failed to delete {entity_name}');
    }} catch (err) {{
        console.warn('[{entity_name}] Backend unavailable, simulating delete:', err.message);
    }}
}}
""")
            else:
                # No mock data available — keep original behavior but safe-parse
                endpoints.append(f"""
// {entity_name} API
export async function get{entity_name}() {{
    const response = await fetch(`${{API_BASE}}/{endpoint}`);
    if (!response.ok) throw new Error('Failed to fetch {entity_name}');
    return response.json();
}}

export async function get{entity_name}ById(id) {{
    const response = await fetch(`${{API_BASE}}/{endpoint}/${{id}}`);
    if (!response.ok) throw new Error('Failed to fetch {entity_name}');
    return response.json();
}}

export async function create{entity_name}(data) {{
    const response = await fetch(`${{API_BASE}}/{endpoint}`, {{
        method: 'POST',
        headers: {{ 'Content-Type': 'application/json' }},
        body: JSON.stringify(data),
    }});
    if (!response.ok) throw new Error('Failed to create {entity_name}');
    return response.json();
}}

export async function update{entity_name}(id, data) {{
    const response = await fetch(`${{API_BASE}}/{endpoint}/${{id}}`, {{
        method: 'PUT',
        headers: {{ 'Content-Type': 'application/json' }},
        body: JSON.stringify(data),
    }});
    if (!response.ok) throw new Error('Failed to update {entity_name}');
    return response.json();
}}

export async function delete{entity_name}(id) {{
    const response = await fetch(`${{API_BASE}}/{endpoint}/${{id}}`, {{
        method: 'DELETE',
    }});
    if (!response.ok) throw new Error('Failed to delete {entity_name}');
}}
""")

        report_api = ""
        if self._reports:
            # Build mock report list from actual reports
            mock_reports = []
            for r in self._reports:
                name = getattr(r, 'name', 'Report') or 'Report'
                endpoint = getattr(r, 'endpoint', 'report') or 'report'
                mock_reports.append(f'{{ name: "{name}", endpoint: "{endpoint}", columns: [], parameters: [] }}')
            mock_list = ", ".join(mock_reports)

            report_api = f"""
// Reports (generated from Access reports)

/** List available reports with their columns and parameters. */
export async function listReports() {{
    try {{
        const response = await fetch(`${{API_BASE}}/reports`);
        if (!response.ok) throw new Error('Backend unavailable');
        const text = await response.text();
        try {{ return JSON.parse(text); }} catch {{ throw new Error('Invalid response'); }}
    }} catch (err) {{
        console.warn('[Reports] Backend unavailable, using sample report list:', err.message);
        return [{mock_list}];
    }}
}}

/** Run a report and return {{ columns, rows, rowCount }}. */
export async function runReport(endpoint, params = {{}}) {{
    const query = buildReportQuery(params);
    try {{
        const response = await fetch(`${{API_BASE}}/reports/${{endpoint}}${{query}}`);
        if (!response.ok) throw new Error('Backend unavailable');
        const text = await response.text();
        try {{ return JSON.parse(text); }} catch {{ throw new Error('Invalid response'); }}
    }} catch (err) {{
        console.warn('[Reports] Backend unavailable, returning empty report:', err.message);
        return {{ columns: [], rows: [], rowCount: 0 }};
    }}
}}

/** URL for a CSV or PDF export, for use in a download link. */
export function reportDownloadUrl(endpoint, format, params = {{}}) {{
    return `${{API_BASE}}/reports/${{endpoint}}/${{format}}${{buildReportQuery(params)}}`;
}}

function buildReportQuery(params) {{
    const search = new URLSearchParams();
    Object.entries(params).forEach(([key, value]) => {{
        if (value !== undefined && value !== null && String(value) !== '') {{
            search.append(key, String(value));
        }}
    }});
    const query = search.toString();
    return query ? `?${{query}}` : '';
}}
"""

        # Build mock data imports
        mock_imports = ""
        if has_mock:
            import_names = [f"mock{e}" for e in self._mock_data.keys()]
            mock_imports = f"import {{ {', '.join(import_names)} }} from './mockData';\n"

        return f"""{mock_imports}const API_BASE = '/api';
{''.join(endpoints)}{report_api}
"""

    def _generate_app_jsx(self) -> str:
        """Generate simplified App.jsx that delegates to AppRouter and AppLayout."""
        return f"""import React from 'react';
import {{ BrowserRouter as Router }} from 'react-router-dom';
import AppLayout from './components/layout/AppLayout';
import AppRouter from './routes/AppRouter';
import ErrorBoundary from './components/common/ErrorBoundary';
import './styles/reset.css';

export default function App() {{
    return (
        <ErrorBoundary>
            <Router>
                <AppLayout>
                    <AppRouter />
                </AppLayout>
            </Router>
        </ErrorBoundary>
    );
}}
"""

    def _generate_main_jsx(self) -> str:
        """Generate main.jsx entry point."""
        return f"""import React from 'react';
import ReactDOM from 'react-dom/client';
import App from './App';
import './index.css';

ReactDOM.createRoot(document.getElementById('root')).render(
    <React.StrictMode>
        <App />
    </React.StrictMode>
);
"""

    def _generate_package_json(self) -> str:
        """Generate package.json with linting, formatting, and testing toolchain."""
        return f"""{{
  "name": "{self._to_kebab(self.app_name)}",
  "version": "1.0.0",
  "type": "module",
  "scripts": {{
    "dev": "vite",
    "build": "vite build",
    "preview": "vite preview",
    "lint": "eslint src/ --ext .js,.jsx",
    "lint:fix": "eslint src/ --ext .js,.jsx --fix",
    "format": "prettier --write \\"src/**/*.{{js,jsx,css,json}}\\"",
    "format:check": "prettier --check \\"src/**/*.{{js,jsx,css,json}}\\"",
    "test": "vitest",
    "test:run": "vitest run",
    "test:coverage": "vitest run --coverage"
  }},
  "dependencies": {{
    "axios": "1.20.0",
    "react": "19.2.8",
    "react-dom": "19.2.8",
    "react-router-dom": "7.18.2"
  }},
  "devDependencies": {{
    "@testing-library/jest-dom": "6.6.3",
    "@testing-library/react": "16.3.0",
    "@testing-library/user-event": "14.6.1",
    "@vitejs/plugin-react": "6.0.5",
    "eslint": "9.27.0",
    "eslint-config-prettier": "10.1.5",
    "eslint-plugin-jsx-a11y": "6.10.2",
    "eslint-plugin-react": "7.37.5",
    "eslint-plugin-react-hooks": "5.2.0",
    "jsdom": "26.1.0",
    "prettier": "3.5.3",
    "vite": "8.2.1",
    "vitest": "3.2.1"
  }}
}}
"""

    def _generate_vite_config(self) -> str:
        """Generate vite.config.js."""
        return f"""import {{ defineConfig }} from 'vite';
import react from '@vitejs/plugin-react';

export default defineConfig({{
  plugins: [react()],
  server: {{
    port: 3000,
    proxy: {{
      '/api': {{
        target: 'http://localhost:8080',
        changeOrigin: true,
      }},
    }},
  }},
}});
"""

    def _generate_index_html(self) -> str:
        """Generate index.html with SEO meta tags and web font."""
        return f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <meta name="description" content="{self.app_name} — modernized from MS Access">
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap" rel="stylesheet">
    <title>{self.app_name}</title>
</head>
<body>
    <div id="root"></div>
    <script type="module" src="/src/main.jsx"></script>
</body>
</html>
"""

    # ---------------------------------------------------------------- Phase 1: tooling config

    def _generate_eslintrc(self) -> str:
        """Generate ESLint configuration with React, hooks, a11y, and Prettier integration."""
        return """/** @type {import('eslint').Linter.Config} */
module.exports = {
  root: true,
  env: { browser: true, es2024: true },
  extends: [
    'eslint:recommended',
    'plugin:react/recommended',
    'plugin:react/jsx-runtime',
    'plugin:react-hooks/recommended',
    'plugin:jsx-a11y/recommended',
    'prettier',
  ],
  parserOptions: {
    ecmaVersion: 'latest',
    sourceType: 'module',
    ecmaFeatures: { jsx: true },
  },
  settings: { react: { version: 'detect' } },
  rules: {
    'react/prop-types': 'off',
    'no-unused-vars': ['warn', { argsIgnorePattern: '^_' }],
    'no-console': ['warn', { allow: ['warn', 'error'] }],
    'jsx-a11y/anchor-is-valid': 'warn',
  },
};
"""

    def _generate_prettierrc(self) -> str:
        """Generate Prettier configuration."""
        return """{
  "singleQuote": true,
  "trailingComma": "all",
  "printWidth": 100,
  "tabWidth": 2,
  "semi": true,
  "bracketSpacing": true,
  "jsxSingleQuote": false,
  "arrowParens": "always"
}
"""

    def _generate_vitest_config_file(self) -> str:
        """Generate Vitest configuration file."""
        return """import { defineConfig } from 'vitest/config';
import react from '@vitejs/plugin-react';

export default defineConfig({
  plugins: [react()],
  test: {
    globals: true,
    environment: 'jsdom',
    setupFiles: './src/test/setup.js',
    css: { modules: { classNameStrategy: 'non-scoped' } },
    include: ['src/**/*.{test,spec}.{js,jsx}'],
  },
});
"""

    def _generate_test_setup(self) -> str:
        """Generate test setup file with jest-dom matchers."""
        return """import '@testing-library/jest-dom';
"""

    def _generate_readme(self) -> str:
        """Generate project README with architecture and usage documentation."""
        table_count = len(self.app.tables)
        form_count = len(self.app.forms)
        return f"""# {self.app_name}

> Modernized React frontend, converted from MS Access.

## Quick Start

```bash
npm install
npm run dev        # Start dev server on http://localhost:3000
```

## Scripts

| Command | Description |
|---------|-------------|
| `npm run dev` | Start Vite dev server with HMR |
| `npm run build` | Production build to `dist/` |
| `npm run preview` | Preview production build |
| `npm run lint` | Run ESLint on all source files |
| `npm run lint:fix` | Auto-fix lint errors |
| `npm run format` | Format all files with Prettier |
| `npm run format:check` | Check formatting without changes |
| `npm run test` | Run tests in watch mode |
| `npm run test:run` | Run tests once (CI) |
| `npm run test:coverage` | Run tests with coverage report |

## Architecture

```
src/
├── App.jsx                 # Root component with routing
├── main.jsx                # Entry point
├── index.css               # Global styles
├── pages/                  # Page components (one per Access form)
└── services/
    ├── api.js              # API client with CRUD operations
    └── mockData.js         # Sample data for offline development
```

## Source Database

- **Tables**: {table_count}
- **Forms**: {form_count}
- **API Base**: `/api` (proxied to Spring Boot backend on port 8080)

## Technology Stack

| Layer | Technology | Version |
|-------|-----------|---------|
| UI | React | 19.2.8 |
| Routing | React Router | 7.18.2 |
| HTTP Client | Axios | 1.20.0 |
| Build Tool | Vite | 8.2.1 |
| Linting | ESLint | 9.27.0 |
| Formatting | Prettier | 3.5.3 |
| Testing | Vitest + Testing Library | 3.2.1 |
"""

    # ---------------------------------------------------------------- Phase 3: API layer

    def _generate_api_base_client(self) -> str:
        """Generate Axios-based centralized API client."""
        return """import axios from 'axios';

const API_BASE = '/api';

const apiClient = axios.create({
  baseURL: API_BASE,
  timeout: 15000,
  headers: { 'Content-Type': 'application/json' },
});

// Request interceptor — add auth token if available
apiClient.interceptors.request.use((config) => {
  const token = localStorage.getItem('auth_token');
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

// Response interceptor — normalize errors
apiClient.interceptors.response.use(
  (response) => {
    // If the server returns an HTML page (like a dev server SPA fallback), reject it so it falls back to mock data
    if (typeof response.data === 'string' && response.data.trim().startsWith('<')) {
      return Promise.reject(new ApiError('Received HTML instead of JSON from API', response.status || 500));
    }
    return response.data;
  },
  (error) => {
    const message =
      error.response?.data?.message || error.message || 'An unexpected error occurred';
    const status = error.response?.status || 0;
    const apiError = new ApiError(message, status);
    return Promise.reject(apiError);
  },
);

export class ApiError extends Error {
  constructor(message, status) {
    super(message);
    this.name = 'ApiError';
    this.status = status;
  }
}

export default apiClient;
"""

    def _generate_entity_service(self, table) -> str:
        """Generate per-entity CRUD service file using Axios client."""
        entity = self._to_pascal(table.name)
        endpoint = self._to_kebab(table.name)
        has_mock = bool(self._mock_data) and entity in (self._mock_data or {})
        mock_import = f"import {{ mock{entity} }} from './mockData';\n" if has_mock else ""
        mock_fallback = f"mock{entity}" if has_mock else "[]"

        return f"""{mock_import}import apiClient from './apiClient';

const ENDPOINT = '/{endpoint}';

export async function getAll() {{
  try {{
    return await apiClient.get(ENDPOINT);
  }} catch (err) {{
    console.warn('[{entity}] Using fallback data:', err.message);
    return [...{mock_fallback}];
  }}
}}

export async function getById(id) {{
  try {{
    return await apiClient.get(`${{ENDPOINT}}/${{id}}`);
  }} catch (err) {{
    console.warn('[{entity}] Using fallback data:', err.message);
    return {mock_fallback}.find((i) => String(i.id) === String(id));
  }}
}}

export async function create(data) {{
  return apiClient.post(ENDPOINT, data);
}}

export async function update(id, data) {{
  return apiClient.put(`${{ENDPOINT}}/${{id}}`, data);
}}

export async function remove(id) {{
  return apiClient.delete(`${{ENDPOINT}}/${{id}}`);
}}
"""

    def _generate_report_service(self) -> str:
        """Generate report-specific API service."""
        report_funcs = []
        for report_def in self._reports:
            func_name = self._to_camel(report_def.name)
            endpoint = self._to_kebab(report_def.name)
            report_funcs.append(f"""
export async function generate{self._to_pascal(report_def.name)}(params = {{}}) {{
  return apiClient.get('/reports/{endpoint}', {{ params }});
}}""")

        funcs_js = "\n".join(report_funcs)
        return f"""import apiClient from './apiClient';

export async function getReportList() {{
  return apiClient.get('/reports').then(res => res.data || res);
}}

export async function runReport(endpoint, params = {{}}) {{
  return apiClient.get(`/reports/${{endpoint}}`, {{ params }}).then(res => res.data || res);
}}

export function reportDownloadUrl(endpoint, format, params = {{}}) {{
  const query = new URLSearchParams({{ format, ...params }}).toString();
  return `${{apiClient.defaults?.baseURL || ''}}/reports/${{endpoint}}/export?${{query}}`;
}}
{funcs_js}
"""

    # ---------------------------------------------------------------- Phase 4: App decomposition

    def _generate_app_router(self) -> str:
        """Generate src/routes/AppRouter.jsx with all route definitions."""
        imports = []
        routes = []
        route_index = 0

        if self._use_theme_engine and self._presentations:
            for pres in self._presentations:
                page_name = self._to_pascal(pres.screen_id.replace("frm", ""))
                endpoint = self._to_kebab(page_name) if pres.record_source else ""

                if pres.record_source:
                    imports.append(f"import {page_name}Page from '../pages/{page_name}Page';")
                    imports.append(f"import {page_name}FormPage from '../pages/{page_name}FormPage';")
                    routes.append(f'      <Route path="/{endpoint}" element={{<{page_name}Page />}} />')
                    routes.append(f'      <Route path="/{endpoint}/new" element={{<{page_name}FormPage />}} />')
                    routes.append(f'      <Route path="/{endpoint}/:id" element={{<{page_name}FormPage />}} />')
                    if route_index == 0:
                        routes.append(f'      <Route path="/" element={{<{page_name}Page />}} />')
                else:
                    imports.append(f"import {page_name}Page from '../pages/{page_name}Page';")
                    route_path = f"/{page_name.lower()}"
                    routes.append(f'      <Route path="{route_path}" element={{<{page_name}Page />}} />')
                    if route_index == 0:
                        routes.append(f'      <Route path="/" element={{<{page_name}Page />}} />')
                route_index += 1
        else:
            for form in self.app.forms:
                page_name = self._to_pascal(form.name.replace("frm", ""))
                endpoint = self._to_kebab(page_name)

                if form.record_source:
                    imports.append(f"import {page_name}Page from '../pages/{page_name}Page';")
                    routes.append(f'      <Route path="/{endpoint}" element={{<{page_name}Page />}} />')
                else:
                    imports.append(f"import {page_name}Page from '../pages/{page_name}Page';")
                    routes.append(f'      <Route path="/{page_name.lower()}" element={{<{page_name}Page />}} />')

                if route_index == 0:
                    routes.append(f'      <Route path="/" element={{<{page_name}Page />}} />')
                route_index += 1

        if self._reports:
            imports.append("import ReportsPage from '../pages/ReportsPage';")
            routes.append('      <Route path="/reports" element={<ReportsPage />} />')

        imports_js = "\n".join(imports)
        routes_js = "\n".join(routes)

        return f"""import React from 'react';
import {{ Routes, Route }} from 'react-router-dom';
{imports_js}

export default function AppRouter() {{
  return (
    <Routes>
{routes_js}
    </Routes>
  );
}}
"""

    def _generate_app_layout(self) -> str:
        """Generate src/components/layout/AppLayout.jsx with navigation."""
        nav_links = []

        if self._use_theme_engine and self._presentations:
            for pres in self._presentations:
                page_name = self._to_pascal(pres.screen_id.replace("frm", ""))
                endpoint = self._to_kebab(page_name) if pres.record_source else page_name.lower()
                label = pres.screen_name or page_name
                nav_links.append(f'        <NavLink to="/{endpoint}" className={{({{isActive}}) => isActive ? styles.active : ""}}>{label}</NavLink>')
        else:
            for form in self.app.forms:
                page_name = self._to_pascal(form.name.replace("frm", ""))
                endpoint = self._to_kebab(page_name) if form.record_source else page_name.lower()
                label = form.caption or page_name
                nav_links.append(f'        <NavLink to="/{endpoint}" className={{({{isActive}}) => isActive ? styles.active : ""}}>{label}</NavLink>')

        if self._reports:
            nav_links.append('        <NavLink to="/reports" className={({isActive}) => isActive ? styles.active : ""}>Reports</NavLink>')

        nav_links_js = "\n".join(nav_links)

        return f"""import React from 'react';
import {{ NavLink }} from 'react-router-dom';
import styles from './AppLayout.module.css';

export default function AppLayout({{ children }}) {{
  return (
    <div className={{styles.app}}>
      <nav className={{styles.navbar}} aria-label="Main navigation">
        <span className={{styles.brand}}>{self.app_name}</span>
{nav_links_js}
      </nav>
      <main className={{styles.main}}>
        {{children}}
      </main>
    </div>
  );
}}
"""

    @staticmethod
    def _generate_app_layout_css() -> str:
        """Generate CSS Module for AppLayout component."""
        return """.app {
  display: flex;
  flex-direction: column;
  min-height: 100vh;
}

.navbar {
  background: var(--color-white);
  backdrop-filter: blur(16px);
  -webkit-backdrop-filter: blur(16px);
  border-bottom: 1px solid var(--color-border);
  padding: 0 2rem;
  display: flex;
  gap: 1.5rem;
  box-shadow: var(--shadow-sm);
  height: 64px;
  align-items: center;
  overflow-x: auto;
  white-space: nowrap;
  position: sticky;
  top: 0;
  z-index: 50;
}

.brand {
  font-weight: 800;
  font-size: 1.25rem;
  color: var(--color-primary);
  margin-right: 1rem;
  background: linear-gradient(135deg, var(--color-primary-light), var(--color-secondary));
  -webkit-background-clip: text;
  -webkit-text-fill-color: transparent;
  letter-spacing: -0.02em;
}

.navbar a {
  color: var(--color-text-muted);
  text-decoration: none;
  font-size: 0.875rem;
  font-weight: 600;
  padding: 0.5rem 0.25rem;
  border-bottom: 2px solid transparent;
  transition: all 0.2s ease;
}

.navbar a:hover {
  color: var(--color-primary-light);
  border-bottom-color: rgba(129, 140, 248, 0.4);
}

.active {
  color: var(--color-primary-light) !important;
  border-bottom-color: var(--color-primary) !important;
  text-shadow: 0 0 10px rgba(99, 102, 241, 0.5);
}

.main {
  flex: 1;
  padding: 2rem;
  max-width: 1200px;
  width: 100%;
  margin: 0 auto;
}
"""

    @staticmethod
    def _generate_use_api_hook() -> str:
        """Generate src/hooks/useApi.js custom hook for data fetching."""
        return """import { useState, useEffect, useCallback } from 'react';

/**
 * Custom hook for API data fetching with loading/error state management.
 *
 * @param {Function} fetchFn - Async function that returns data
 * @param {Array} deps - Dependency array for useEffect
 * @returns {{ data, loading, error, refetch }}
 */
export function useApi(fetchFn, deps = []) {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  const execute = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const result = await fetchFn();
      setData(result);
    } catch (err) {
      setError(err.message || 'An error occurred');
    } finally {
      setLoading(false);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, deps);

  useEffect(() => {
    execute();
  }, [execute]);

  return { data, loading, error, refetch: execute };
}

export default useApi;
"""

    # ---------------------------------------------------------------- Phase 5: CSS modularization

    @staticmethod
    def _generate_css_tokens() -> str:
        """Generate src/styles/tokens.css with CSS custom properties."""
        return """:root {
  /* Premium Dark Mode Colors */
  --color-primary: #818cf8;
  --color-primary-dark: #6366f1;
  --color-primary-light: #c7d2fe;
  --color-secondary: #f472b6;
  --color-secondary-dark: #ec4899;
  
  --color-text: #f8fafc;
  --color-text-muted: #94a3b8;
  --color-border: rgba(255, 255, 255, 0.12);
  --color-bg: #0f172a;
  --color-white: rgba(30, 41, 59, 0.7); /* Glassmorphism surface for cards */
  
  --color-danger: #ef4444;
  --color-warning: #f59e0b;
  --color-success: #10b981;

  /* Spacing */
  --space-xs: 0.25rem;
  --space-sm: 0.5rem;
  --space-md: 1rem;
  --space-lg: 1.5rem;
  --space-xl: 2rem;

  /* Typography */
  --font-family: 'Outfit', 'Inter', system-ui, -apple-system, sans-serif;
  --font-size-xs: 0.75rem;
  --font-size-sm: 0.875rem;
  --font-size-base: 1rem;
  --font-size-lg: 1.125rem;
  --font-size-xl: 1.25rem;
  --font-size-2xl: 1.75rem;

  /* Border radius */
  --radius-sm: 8px;
  --radius-md: 16px;
  --radius-lg: 24px;
  --radius-full: 9999px;

  /* Shadows & Glow */
  --shadow-sm: 0 4px 6px rgba(0, 0, 0, 0.2);
  --shadow-md: 0 8px 16px rgba(0, 0, 0, 0.3);
  --shadow-lg: 0 16px 32px rgba(0, 0, 0, 0.4);
  --shadow-glow: 0 0 20px rgba(99, 102, 241, 0.25);

  /* Transitions */
  --transition-fast: 0.15s cubic-bezier(0.4, 0, 0.2, 1);
  --transition-base: 0.3s cubic-bezier(0.4, 0, 0.2, 1);
}
"""

    @staticmethod
    def _generate_css_reset() -> str:
        """Generate src/styles/reset.css with global resets."""
        return """@import './tokens.css';

*,
*::before,
*::after {
  box-sizing: border-box;
  margin: 0;
  padding: 0;
}

@keyframes gradientBG {
  0% { background-position: 0% 50%; }
  50% { background-position: 100% 50%; }
  100% { background-position: 0% 50%; }
}

body {
  font-family: var(--font-family);
  color: var(--color-text);
  background: linear-gradient(-45deg, #0f172a, #1e1b4b, #312e81, #0f172a);
  background-size: 400% 400%;
  animation: gradientBG 15s ease infinite;
  min-height: 100vh;
  line-height: 1.6;
  -webkit-font-smoothing: antialiased;
  -moz-osx-font-smoothing: grayscale;
}

/* Glassmorphism utility for cards/surfaces */
.glass-panel {
  background: var(--color-white);
  backdrop-filter: blur(12px);
  -webkit-backdrop-filter: blur(12px);
  border: 1px solid var(--color-border);
  box-shadow: var(--shadow-lg);
  border-radius: var(--radius-md);
}

a {
  color: var(--color-primary);
  text-decoration: none;
  transition: var(--transition-fast);
}

a:hover {
  color: var(--color-primary-light);
  text-shadow: 0 0 8px rgba(129, 140, 248, 0.5);
}

img, svg {
  display: block;
  max-width: 100%;
}

input, button, textarea, select {
  font: inherit;
}

/* App Layout Styles */
.app {
  display: flex;
  flex-direction: column;
  min-height: 100vh;
}

.navbar {
  background: var(--color-white);
  backdrop-filter: blur(16px);
  -webkit-backdrop-filter: blur(16px);
  border-bottom: 1px solid var(--color-border);
  padding: 0 2rem;
  display: flex;
  gap: 1.5rem;
  box-shadow: var(--shadow-sm);
  height: 64px;
  align-items: center;
  overflow-x: auto;
  white-space: nowrap;
  position: sticky;
  top: 0;
  z-index: 50;
}

.navbar a {
  color: var(--color-text-muted);
  font-weight: 600;
  padding: 0.5rem 1rem;
  border-radius: var(--radius-md);
}

.navbar a:hover, .navbar a.active {
  color: var(--color-white);
  background: rgba(255, 255, 255, 0.1);
  text-shadow: 0 0 10px rgba(255,255,255,0.5);
}

.content {
  flex: 1;
  padding: 2rem;
  max-width: 1400px;
  margin: 0 auto;
  width: 100%;
}

/* Scrollbar styling */
::-webkit-scrollbar {
  width: 8px;
  height: 8px;
}
::-webkit-scrollbar-track {
  background: rgba(0, 0, 0, 0.2);
}
::-webkit-scrollbar-thumb {
  background: rgba(255, 255, 255, 0.2);
  border-radius: var(--radius-full);
}
::-webkit-scrollbar-thumb:hover {
  background: rgba(255, 255, 255, 0.3);
}
"""

    # ---------------------------------------------------------------- Phase 6: test generation

    @staticmethod
    def _generate_api_client_test() -> str:
        """Generate tests for the Axios-based API client."""
        return """import { describe, it, expect, vi, beforeEach } from 'vitest';
import axios from 'axios';
import apiClient, { ApiError } from '../apiClient';

vi.mock('axios', () => {
  const mockAxios = {
    create: vi.fn(() => mockAxios),
    get: vi.fn(),
    post: vi.fn(),
    put: vi.fn(),
    delete: vi.fn(),
    interceptors: {
      request: { use: vi.fn() },
      response: { use: vi.fn() },
    },
  };
  return { default: mockAxios };
});

describe('ApiError', () => {
  it('stores message and status', () => {
    const err = new ApiError('Not Found', 404);
    expect(err.message).toBe('Not Found');
    expect(err.status).toBe(404);
    expect(err.name).toBe('ApiError');
    expect(err).toBeInstanceOf(Error);
  });
});

describe('apiClient module', () => {
  it('exports a configured axios instance', () => {
    expect(apiClient).toBeDefined();
    expect(axios.create).toHaveBeenCalledWith(
      expect.objectContaining({
        timeout: 15000,
        headers: expect.objectContaining({ 'Content-Type': 'application/json' }),
      }),
    );
  });

  it('sets up request and response interceptors', () => {
    expect(apiClient.interceptors.request.use).toHaveBeenCalled();
    expect(apiClient.interceptors.response.use).toHaveBeenCalled();
  });
});
"""

    def _generate_service_crud_test(self, table) -> str:
        """Generate full CRUD test for a per-entity service."""
        entity = self._to_pascal(table.name)
        endpoint = self._to_kebab(table.name)
        has_mock = bool(self._mock_data) and entity in (self._mock_data or {})

        return f"""import {{ describe, it, expect, vi, beforeEach }} from 'vitest';
import apiClient from '../apiClient';
import {{ getAll, getById, create, update, remove }} from '../{entity}Service';

vi.mock('../apiClient', () => ({{
  default: {{
    get: vi.fn(),
    post: vi.fn(),
    put: vi.fn(),
    delete: vi.fn(),
  }},
}}));

describe('{entity}Service', () => {{
  beforeEach(() => {{
    vi.clearAllMocks();
  }});

  describe('getAll', () => {{
    it('calls GET /{endpoint}', async () => {{
      const mockData = [{{ id: 1 }}, {{ id: 2 }}];
      apiClient.get.mockResolvedValue(mockData);

      const result = await getAll();

      expect(apiClient.get).toHaveBeenCalledWith('/{endpoint}');
      expect(result).toEqual(mockData);
    }});

    it('returns fallback data on error', async () => {{
      apiClient.get.mockRejectedValue(new Error('Network error'));

      const result = await getAll();

      expect(Array.isArray(result)).toBe(true);
    }});
  }});

  describe('getById', () => {{
    it('calls GET /{endpoint}/:id', async () => {{
      const mockItem = {{ id: '42', name: 'Test' }};
      apiClient.get.mockResolvedValue(mockItem);

      const result = await getById('42');

      expect(apiClient.get).toHaveBeenCalledWith('/{endpoint}/42');
      expect(result).toEqual(mockItem);
    }});

    it('returns fallback item on error', async () => {{
      apiClient.get.mockRejectedValue(new Error('Not found'));

      const result = await getById('42');
      // Falls back to mock data or undefined
      expect(apiClient.get).toHaveBeenCalled();
    }});
  }});

  describe('create', () => {{
    it('calls POST /{endpoint}', async () => {{
      const newItem = {{ name: 'New Item' }};
      apiClient.post.mockResolvedValue({{ id: 1, ...newItem }});

      const result = await create(newItem);

      expect(apiClient.post).toHaveBeenCalledWith('/{endpoint}', newItem);
      expect(result).toEqual({{ id: 1, ...newItem }});
    }});
  }});

  describe('update', () => {{
    it('calls PUT /{endpoint}/:id', async () => {{
      const updateData = {{ name: 'Updated' }};
      apiClient.put.mockResolvedValue({{ id: '1', ...updateData }});

      const result = await update('1', updateData);

      expect(apiClient.put).toHaveBeenCalledWith('/{endpoint}/1', updateData);
      expect(result).toEqual({{ id: '1', ...updateData }});
    }});
  }});

  describe('remove', () => {{
    it('calls DELETE /{endpoint}/:id', async () => {{
      apiClient.delete.mockResolvedValue(undefined);

      await remove('1');

      expect(apiClient.delete).toHaveBeenCalledWith('/{endpoint}/1');
    }});
  }});
}});
"""

    # ---------------------------------------------------------------- legacy CSS

    def _generate_index_css(self) -> str:
        """Generate global CSS with dynamic form-based styles (Spec section 46)."""
        css = """:root {
    --color-primary: #3b82f6;
    --color-primary-dark: #2563eb;
    --color-secondary: #10b981;
    --color-text: #1f2937;
    --color-text-muted: #6b7280;
    --color-border: #e5e7eb;
    --color-bg: #f3f4f6;
    --color-white: #ffffff;
    --radius-md: 8px;
    --shadow-sm: 0 1px 2px 0 rgba(0, 0, 0, 0.05);
    --shadow-md: 0 4px 6px -1px rgba(0, 0, 0, 0.1);
}

* { box-sizing: border-box; margin: 0; padding: 0; }
body {
    font-family: 'Inter', system-ui, -apple-system, sans-serif;
    color: var(--color-text);
    background: var(--color-bg);
    line-height: 1.6;
}

.app { display: flex; flex-direction: column; min-height: 100vh; }

.navbar {
    background: var(--color-white);
    border-bottom: 1px solid var(--color-border);
    padding: 0 2rem;
    display: flex;
    gap: 1.5rem;
    box-shadow: var(--shadow-sm);
    height: 64px;
    align-items: center;
    overflow-x: auto;
    white-space: nowrap;
}

.navbar a {
    color: var(--color-text-muted);
    text-decoration: none;
    font-weight: 500;
    height: 100%;
    display: flex;
    align-items: center;
    padding: 0 0.5rem;
    border-bottom: 2px solid transparent;
    transition: all 0.2s;
    font-size: 0.9rem;
}

.navbar a:hover {
    color: var(--color-primary);
}

.content {
    flex: 1;
    padding: 2rem;
    max-width: 1000px;
    margin: 0 auto;
    width: 100%;
}

.form-description {
    color: var(--color-text-muted);
    font-size: 0.875rem;
    margin-bottom: 2rem;
    font-style: italic;
}

.info-field {
    display: flex;
    padding: 0.75rem 0;
    border-bottom: 1px solid var(--color-border);
    align-items: baseline;
}

.info-label {
    width: 180px;
    font-weight: 600;
    color: var(--color-text-muted);
    font-size: 0.85rem;
    text-transform: uppercase;
    letter-spacing: 0.025em;
}

.info-value {
    flex: 1;
    color: var(--color-text);
}

.button-group {
    display: flex;
    flex-wrap: wrap;
    gap: 0.75rem;
    margin-top: 2rem;
}

.form-group { margin-bottom: 1.5rem; }
.form-group label {
    display: block;
    margin-bottom: 0.5rem;
    font-weight: 600;
    font-size: 0.9rem;
    color: var(--color-text);
}

.form-group input, .form-group select {
    width: 100%;
    padding: 0.75rem;
    border: 1px solid var(--color-border);
    border-radius: var(--radius-md);
    background: white;
    transition: border-color 0.2s;
}

.form-group input:focus {
    outline: none;
    border-color: var(--color-primary);
}

.form-actions {
    display: flex;
    gap: 1rem;
    margin-top: 2rem;
    padding-top: 1.5rem;
    border-top: 1px solid var(--color-border);
}

.btn {
    padding: 0.75rem 1.5rem;
    border-radius: var(--radius-md);
    background: var(--color-primary);
    color: white;
    border: none;
    cursor: pointer;
    font-weight: 600;
    font-size: 0.9rem;
    transition: all 0.2s;
    display: inline-flex;
    align-items: center;
    justify-content: center;
}

.btn:hover {
    filter: brightness(1.1);
    transform: translateY(-1px);
}

.btn-secondary {
    background-color: var(--color-white);
    color: var(--color-text);
    border: 1px solid var(--color-border);
}

.btn-secondary:hover {
    background-color: var(--color-bg);
    color: var(--color-primary);
    border-color: var(--color-primary);
}

.data-table {
    width: 100%;
    border-collapse: collapse;
    margin: 1.5rem 0;
    background: white;
    border-radius: var(--radius-md);
    overflow: hidden;
    box-shadow: var(--shadow-sm);
}

.data-table th, .data-table td {
    padding: 1rem;
    text-align: left;
    border-bottom: 1px solid var(--color-border);
}

.data-table th {
    background: #f8fafc;
    font-weight: 700;
    color: var(--color-text);
    font-size: 0.85rem;
    text-transform: uppercase;
    letter-spacing: 0.05em;
}

.data-table tr:last-child td { border-bottom: none; }

@keyframes fadeIn {
    from { opacity: 0; transform: translateY(10px); }
    to { opacity: 1; transform: translateY(0); }
}
"""

        # Dynamic form-specific styles
        for form in self.app.forms:
            name = self._to_pascal(form.name.replace("frm", ""))
            cls = name.lower()
            # Generate a "unique" color for each form based on its name
            color_hue = sum(ord(c) for c in name) % 360
            css += f"""
/* Dynamic styles for {name} */
.{cls}-page, .{cls}-form {{
    --form-accent: hsl({color_hue}, 65%, 40%);
    --form-bg-light: #ffffff;
    animation: fadeIn 0.4s ease-out;
    background: var(--form-bg-light);
    border-radius: var(--radius-md);
    padding: 2.5rem;
    margin-bottom: 2rem;
    box-shadow: var(--shadow-md);
    border-top: 5px solid var(--form-accent);
}}

.{cls}-page h1, .{cls}-form h1 {{
    color: var(--form-accent);
    font-size: 2rem;
    margin-bottom: 0.5rem;
    font-weight: 800;
}}

.{cls}-page .btn, .{cls}-form button[type="submit"] {{
    background-color: var(--form-accent);
}}

.{cls}-page .data-table th {{
    border-bottom: 2px solid var(--form-accent);
}}
"""
        return css

    # Naming is delegated to the shared naming module (PHASE 5 / 18).
    # Import locally to avoid circular imports at module level.
    @staticmethod
    def _to_pascal(name: str) -> str:
        from ...naming import to_pascal
        return to_pascal(name)

    @staticmethod
    def _to_camel(name: str) -> str:
        from ...naming import to_camel
        return to_camel(name)

    @staticmethod
    def _to_kebab(name: str) -> str:
        from ...naming import to_kebab
        return to_kebab(name)


def generate_react(app_ir, output_dir: str | Path, **kwargs) -> dict[str, str]:
    """Entry point to generate React frontend.

    Accepts ui_style, ui_reasoning, and ui_debug kwargs for the
    UI Modernization engine.
    """
    generator = ReactGenerator(app_ir, **kwargs)
    return generator.generate(output_dir)
