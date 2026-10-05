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
        self._use_theme_engine = True  # Use the new theme engine for all styles
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
                helper_imports = (
                    "import { FormField } from '../components/common';\n"
                    f"import {{ create, getById, update }} from '../services/{api_name}Service';\n"
                    if api_name else ""
                )

                # If this is a data-bound form, we need BOTH a list view and a form view
                # so the user can navigate the data and click Edit/New.
                if pres.record_source:
                    list_content = self._theme.render_list_page(pres, endpoint, api_name, helper_imports)
                    form_content = self._theme.render_form_page(pres, endpoint, api_name, helper_imports)
                    files[str(src / "pages" / f"{page_name}Page.jsx")] = list_content
                    files[str(src / "pages" / f"{page_name}FormPage.jsx")] = form_content
                    files[str(src / "pages" / "__tests__" / f"{page_name}FormPage.test.jsx")] = (
                        self._generate_form_page_interaction_test(page_name, api_name, endpoint)
                    )
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
                if form.record_source:
                    api_name = self._resolve_api_name(form.record_source)
                    endpoint = self._to_kebab(form.record_source)
                    files[str(src / "pages" / "__tests__" / f"{page_name}Page.test.jsx")] = (
                        self._generate_legacy_page_interaction_test(page_name, api_name, endpoint)
                    )

        # Generate the reports page when the source app has usable reports
        self._reports = self._resolve_reports()
        if self._reports:
            files[str(src / "pages" / "ReportsPage.jsx")] = self._generate_reports_page()

        # Pages receive a co-located CSS Module.  Theme CSS supplies only the
        # selected design-system layer; page-specific presentation is isolated.
        for page_path, page_content in list(files.items()):
            path = Path(page_path)
            if path.parent == src / "pages" and path.suffix == ".jsx":
                module_name = f"{path.stem}.module.css"
                files[page_path] = self._attach_page_module(page_content, module_name)
                files[str(path.with_name(module_name))] = self._generate_page_css_module()

        # Generate mock data via LLM (for frontend fallback when backend is unavailable)
        self._mock_data = self._generate_mock_data()
        if self._mock_data:
            files[str(src / "services" / "mockData.js")] = self._build_mock_data_file()
            logger.info("Generated mock data for %d entities", len(self._mock_data))

        # Generate a small, centralized Axios client and one service per entity.
        # This avoids a very large api.js for applications with many tables.
        files[str(src / "services" / "apiClient.js")] = self._generate_api_base_client()
        for table in self.app.tables:
            if table.role not in ("SYSTEM", "INTERNAL"):
                entity = self._to_pascal(table.name)
                files[str(src / "services" / f"{entity}Service.js")] = self._generate_entity_service(table)
        if self._reports:
            files[str(src / "services" / "reportService.js")] = self._generate_report_service()

        # Generate index.css — theme-aware
        # Theme CSS remains available as an optional visual layer, while the
        # foundation is split into stable global tokens/reset files.
        files[str(src / "styles" / "tokens.css")] = self._generate_tokens_css()
        files[str(src / "styles" / "reset.css")] = self._generate_reset_css()
        theme_imports: list[str] = []
        if self._use_theme_engine and self._presentations and self._theme:
            theme_files = self._theme.get_css(self.app_name, self._presentations)
            for relative_path, content in theme_files.items():
                files[str(src / "styles" / "theme" / relative_path)] = content
                theme_imports.append(f"./styles/theme/{relative_path}")
        else:
            files[str(src / "styles" / "theme" / "rules.css")] = ""
            theme_imports.append("./styles/theme/rules.css")
        files[str(src / "index.css")] = self._generate_index_css(theme_imports)

        # Generate App.jsx — theme-aware
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

        # Tooling, documentation, and generated test coverage.
        files[str(output_dir / ".eslintrc.cjs")] = self._generate_eslintrc()
        files[str(output_dir / "eslint.config.js")] = self._generate_eslint_flat_config()
        files[str(output_dir / ".prettierrc")] = self._generate_prettierrc()
        files[str(output_dir / "vitest.config.js")] = self._generate_vitest_config_file()
        files[str(output_dir / "README.md")] = self._generate_readme()
        files[str(src / "test" / "setup.js")] = self._generate_test_setup()
        files[str(src / "services" / "__tests__" / "apiClient.test.js")] = self._generate_api_client_test()
        for table in self.app.tables:
            if table.role not in ("SYSTEM", "INTERNAL"):
                entity = self._to_pascal(table.name)
                files[str(src / "services" / "__tests__" / f"{entity}Service.test.js")] = self._generate_page_crud_test(table)

        # Shared component library is emitted once and used by legacy pages;
        # theme pages can adopt it incrementally through helper_imports.
        from .components_generator import ComponentsGenerator
        files.update(ComponentsGenerator().generate(src / "components" / "common"))

        # Write debug artifacts
        if self._engine and self.ui_debug:
            self._engine.write_debug_artifacts(output_dir)

        return files

    def _generate_themed_app_jsx(self) -> str:
        """Generate App.jsx using the theme engine."""
        pages = []
        for pres in self._presentations:
            page_name = self._to_pascal(pres.screen_id.replace("frm", ""))
            endpoint = self._to_kebab(page_name) if pres.record_source else ""

            from .ui.models import PageType
            
            page_info = {
                "nav_link_text": pres.screen_name,
                "nav_path": f"/{endpoint}" if endpoint else f"/{page_name.lower()}",
            }

            if pres.record_source:
                page_info["import"] = f"import {page_name}Page from './pages/{page_name}Page';\nimport {page_name}FormPage from './pages/{page_name}FormPage';\n"
                page_info["routes"] = (
                    f"                        <Route path=\"/{endpoint}\" element={{<{page_name}Page />}} />\n"
                    f"                        <Route path=\"/{endpoint}/:id\" element={{<{page_name}FormPage />}} />\n"
                    f"                        <Route path=\"/{endpoint}/new\" element={{<{page_name}FormPage />}} />"
                )
                page_info["nav_link"] = f'<Link to="/{endpoint}">{pres.screen_name}</Link>\n'
            else:
                page_info["import"] = f"import {page_name}Page from './pages/{page_name}Page';\n"
                page_info["routes"] = (
                    f"                        <Route path=\"/{page_name.lower()}\" element={{<{page_name}Page />}} />"
                )
                page_info["nav_link"] = f'<Link to="/{page_name.lower()}">{pres.screen_name}</Link>\n'

            pages.append(page_info)

        # Reports handling
        report_import = ""
        report_route = ""
        report_link = ""
        if self._reports:
            report_import = "import ReportsPage from './pages/ReportsPage';\n"
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
                # Find the first referenced table from the query SQL
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
        """Generate an info/dashboard page for unbound forms (no record source).

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
        # Standalone labels (not associated with an input, e.g. section headings)
        heading_labels = []
        for c in form.controls:
            if c.control_type == "Label" and c.caption:
                # Only include labels that are NOT associated with an input
                if c.name not in label_map.get("_label_names_used", set()):
                    # Check if this label has a control source (bound label)
                    if c.control_source:
                        heading_labels.append(c)

        # Generate form input fields with proper labels
        field_elements = []
        for ctrl in input_fields:
            source = ctrl.control_source or ctrl.name
            # Resolve label: label_map (from associated Label), then ctrl.caption, then humanized name
            label = label_map.get(ctrl.name) or ctrl.caption or self._humanize_name(ctrl.name)
            field_name = self._to_camel(self._sanitize_control_source(source))

            if self._is_access_expression(source):
                safe_expr = source.replace('"', "'")
                field_elements.append(f"""
            <div className="form-group">
                <label htmlFor="{field_name}">{label}</label>
                <input type="text" id="{field_name}" name="{field_name}" disabled placeholder="Computed field" />
                {{/* TODO: Access expression: {safe_expr} */}}
            </div>""")
            elif "Date" in source or "date" in ctrl.name.lower():
                field_elements.append(f"""
            <div className="form-group">
                <label htmlFor="{field_name}">{label}</label>
                <input type="date" id="{field_name}" name="{field_name}" />
            </div>""")
            elif ctrl.control_type == "ComboBox":
                field_elements.append(f"""
            <div className="form-group">
                <label htmlFor="{field_name}">{label}</label>
                <select id="{field_name}" name="{field_name}">
                    <option value="">Select...</option>
                </select>
            </div>""")
            else:
                field_elements.append(f"""
            <div className="form-group">
                <label htmlFor="{field_name}">{label}</label>
                <input type="text" id="{field_name}" name="{field_name}" />
            </div>""")

        # Generate checkbox fields
        for ctrl in checkboxes:
            source = ctrl.control_source or ctrl.name
            label = label_map.get(ctrl.name) or ctrl.caption or self._humanize_name(ctrl.name)
            field_name = self._to_camel(self._sanitize_control_source(source))
            field_elements.append(f"""
            <div className="form-group">
                <label>
                    <input type="checkbox" name="{field_name}" />
                    {label}
                </label>
            </div>""")

        # Generate button elements with TODO handlers
        button_elements = []
        for ctrl in buttons:
            caption = ctrl.caption or ctrl.name
            handler_name = self._to_camel(ctrl.name)
            button_elements.append(f"""
            <Button
                onClick={{() => console.warn('TODO: Implement {handler_name} — original Access event handler not yet converted')}}
            >
                {caption}
            </Button>""")

        fields_js = "\n".join(field_elements) if field_elements else ""
        buttons_js = "\n".join(button_elements) if button_elements else ""

        return f"""import React from 'react';
import {{ Button, PageHeader }} from '../components/common';

/**
 * {page_name} — Unbound Access form (no database record source).
 *
 * Original Access form: {form.name}
 * This form has {len(form.controls)} controls including {len(buttons)} buttons.
 * Business logic from Access VBA event handlers has NOT been converted.
 * TODO: Implement button click handlers to match original Access behavior.
 */
export default function {page_name}Page() {{
    return (
        <div className="{page_name.lower()}-page">
            <PageHeader title="{form.caption or page_name}" description="This page corresponds to Access form: {form.name}" />
{fields_js}
            <div className="button-group">
{buttons_js}
            </div>
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

        # Strategy 2: Positional adjacency
        for i, ctrl in enumerate(controls):
            if (ctrl.control_type == "Label" and ctrl.caption
                    and i + 1 < len(controls)):
                next_ctrl = controls[i + 1]
                if (next_ctrl.control_type in ("TextBox", "ComboBox", "CheckBox",
                                               "OptionButton", "ListBox", "ToggleButton")
                        and next_ctrl.name not in label_map):
                    label_map[next_ctrl.name] = ctrl.caption.rstrip(":")

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
        """Generate a list/table page."""
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

        # Fix 6: Render as proper <th> elements, not raw JS object literals
        header_ths = "\n                        ".join(
            f'<th>{col}</th>'
            for col in display_cols[:6]
        )

        columns_js = ", ".join(
            f"{{ key: '{self._to_camel(col)}', label: '{col}' }}" for col in display_cols[:6]
        )
        return f"""import React, {{ useState, useEffect }} from 'react';
import {{ Link }} from 'react-router-dom';
import {{ DataTable, ErrorMessage, LoadingSpinner, PageHeader }} from '../components/common';
import {{ getAll }} from '../services/{api_name}Service';

export default function {page_name}Page() {{
    const [{var_name}, set{page_name}] = useState([]);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState(null);

    useEffect(() => {{
        async function fetchData() {{
            try {{
                const data = await getAll();
                set{page_name}(data);
            }} catch (err) {{
                setError(err.message);
            }} finally {{
                setLoading(false);
            }}
        }}
        fetchData();
    }}, []);

    if (loading) return <LoadingSpinner />;
    if (error) return <ErrorMessage error={{error}} />;

    return (
        <div className="{page_name.lower()}-page">
            <PageHeader title="{form.caption or page_name}" />
            <DataTable rows={{{var_name}}} columns={{[{columns_js}]}} renderActions={{(item) => <Link to={{`/{endpoint}/${{item.id}}`}}>View</Link>}} />
            <Link to="/{endpoint}/new" className="btn">Add New</Link>
        </div>
    );
}}
"""

    def _generate_form_page(self, form, page_name: str, endpoint: str, api_name: str = "") -> str:
        """Generate a form page for create/edit."""
        api_name = api_name or page_name
        var_name = self._to_camel(page_name)

        # Build label map for proper human-readable labels
        label_map = self._build_unbound_label_map(form.controls)

        # Generate form fields with Access expression sanitization (Fix 3)
        form_fields = []
        for ctrl in form.controls:
            if ctrl.control_type in ("TextBox", "ComboBox", "CheckBox"):
                # Use control_source if available, fall back to control name
                raw_source = ctrl.control_source or ctrl.name

                # Fix 3: Sanitize Access expressions into valid JS identifiers
                field_name = self._to_camel(self._sanitize_control_source(raw_source))
                label = label_map.get(ctrl.name) or ctrl.caption or self._humanize_name(ctrl.name)
                input_type = "text"
                if ctrl.control_type == "CheckBox":
                    input_type = "checkbox"
                elif "Date" in raw_source:
                    input_type = "date"
                elif "Email" in raw_source:
                    input_type = "email"

                # Evaluate disabled attribute at generation time
                disabled_attr = ' disabled' if ctrl.locked else ''

                # Add a TODO comment for Access-expression fields
                expr_comment = ""
                if self._is_access_expression(raw_source):
                    safe_expr = raw_source.replace('"', "'")
                    expr_comment = f"\n                    {{/* TODO: Original Access expression: {safe_expr} */}}"

                disabled_prop = " disabled" if ctrl.locked else ""
                form_fields.append(f"""{expr_comment}
            <FormField label="{label}" name="{field_name}" type="{input_type}" value={{formData.{field_name}}} onChange={{handleChange}}{disabled_prop} />""")

        form_fields_js = "\n".join(form_fields)

        return f"""import React, {{ useState, useEffect }} from 'react';
import {{ useParams, useNavigate }} from 'react-router-dom';
import {{ Button, ErrorMessage, FormField, LoadingSpinner, PageHeader }} from '../components/common';
import {{ create, getById, update }} from '../services/{api_name}Service';

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
                    const data = await getById(id);
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
                await update(id, formData);
            }} else {{
                await create(formData);
            }}
            navigate('/{endpoint}');
        }} catch (err) {{
            setError(err.message);
        }} finally {{
            setLoading(false);
        }}
    }};

    if (loading) return <LoadingSpinner label="Saving..." />;

    return (
        <div className="{page_name.lower()}-form">
            <PageHeader title={{`${{isEdit ? 'Edit' : 'Create'}} {form.caption or page_name}`}} />
            <ErrorMessage error={{error}} />
            <form onSubmit={{handleSubmit}}>
                {form_fields_js}
                <div className="form-actions">
                    <Button type="submit" disabled={{loading}}>
                        {{isEdit ? 'Update' : 'Create'}}
                    </Button>
                    <Button type="button" onClick={{() => navigate('/{endpoint}')}} variant="secondary">
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
import {{ listReports, runReport, reportDownloadUrl }} from '../services/reportService';

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
        listReports()
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

    def _generate_api_base_client(self) -> str:
        """Generate the shared Axios client used by every entity service."""
        return """import axios from 'axios';

export class ApiError extends Error {
  constructor(message, status = 0, details = null) {
    super(message);
    this.name = 'ApiError';
    this.status = status;
    this.details = details;
  }
}

const api = axios.create({
  baseURL: import.meta.env.VITE_API_BASE || '/api',
  timeout: Number(import.meta.env.VITE_API_TIMEOUT || 15000),
  headers: { 'Content-Type': 'application/json' },
});

api.interceptors.request.use((config) => {
  const token = localStorage.getItem('authToken');
  if (token) config.headers.Authorization = `Bearer ${token}`;
  return config;
});

api.interceptors.response.use(
  (response) => response,
  (error) => {
    const response = error.response;
    const message = response?.data?.message || response?.data?.error || error.message || 'Network request failed';
    return Promise.reject(new ApiError(message, response?.status || 0, response?.data || null));
  },
);

export default api;
"""

    def _generate_entity_service(self, table) -> str:
        """Generate a narrowly scoped Axios CRUD service for a table."""
        entity = self._to_pascal(table.name)
        endpoint = self._to_kebab(table.name)
        has_mock = entity in getattr(self, "_mock_data", {})
        mock_import = f"import {{ mock{entity} }} from './mockData';\n" if has_mock else ""
        mock_rows = f"mock{entity}" if has_mock else "[]"
        return f"""{mock_import}import api from './apiClient';

const ENDPOINT = '/{endpoint}';
const hasMockData = {str(has_mock).lower()};

export async function getAll() {{
  try {{ return (await api.get(ENDPOINT)).data; }}
  catch (error) {{
    if (hasMockData) return [...{mock_rows}];
    throw error;
  }}
}}

export async function getById(id) {{
  try {{ return (await api.get(`${{ENDPOINT}}/${{id}}`)).data; }}
  catch (error) {{
    if (hasMockData) return {mock_rows}.find((item) => String(item.id) === String(id));
    throw error;
  }}
}}

export async function create(data) {{ return (await api.post(ENDPOINT, data)).data; }}
export async function update(id, data) {{ return (await api.put(`${{ENDPOINT}}/${{id}}`, data)).data; }}
export async function remove(id) {{ return (await api.delete(`${{ENDPOINT}}/${{id}}`)).data; }}
"""

    def _generate_report_service(self) -> str:
        """Generate a report-only service, separate from entity CRUD services."""
        fallback = ", ".join(
            f'{{ name: "{getattr(report, "name", "Report")}", endpoint: "{getattr(report, "endpoint", "report")}", columns: [], parameters: [] }}'
            for report in self._reports
        )
        return f"""import api from './apiClient';

function query(params = {{}}) {{
  const values = new URLSearchParams();
  Object.entries(params).forEach(([key, value]) => {{ if (value !== '' && value != null) values.set(key, String(value)); }});
  const serialized = values.toString();
  return serialized ? `?${{serialized}}` : '';
}}

export async function listReports() {{
  try {{ return (await api.get('/reports')).data; }}
  catch {{ return [{fallback}]; }}
}}
export async function runReport(endpoint, params) {{ return (await api.get(`/reports/${{endpoint}}${{query(params)}}`)).data; }}
export function reportDownloadUrl(endpoint, format, params) {{ return `${{api.defaults.baseURL}}/reports/${{endpoint}}/${{format}}${{query(params)}}`; }}
"""

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

    def _page_definitions(self) -> list[dict[str, str | bool]]:
        """Build one routing/navigation record per emitted Access form page."""
        themed = bool(self._use_theme_engine and self._presentations and self._theme)
        source_forms = self._presentations if themed else self.app.forms
        definitions = []
        for source in source_forms:
            raw_name = source.screen_id if themed else source.name
            record_source = source.record_source
            page_name = self._to_pascal(raw_name.replace("frm", ""))
            route_name = self._to_kebab(page_name) if themed and record_source else self._to_kebab(record_source or raw_name)
            title = source.screen_name if themed else (source.caption or page_name)
            definitions.append({"name": page_name, "route": route_name, "title": title, "bound": bool(record_source), "legacy": not themed})
        return definitions

    def _generate_app_jsx(self) -> str:
        """Generate the deliberately small application composition root."""
        return """import { BrowserRouter } from 'react-router-dom';
import ErrorBoundary from './components/common/ErrorBoundary';
import AppLayout from './components/layout/AppLayout';
import AppRouter from './routes/AppRouter';

export default function App() {
  return (
    <ErrorBoundary>
      <BrowserRouter>
        <AppLayout><AppRouter /></AppLayout>
      </BrowserRouter>
    </ErrorBoundary>
  );
}
"""

    def _generate_app_router(self) -> str:
        """Generate route declarations separately from the layout shell."""
        definitions = self._page_definitions()
        imports, routes = [], []
        for page in definitions:
            name, route = page["name"], page["route"]
            imports.append(f"import {name}Page from '../pages/{name}Page';")
            if page["bound"] and not page["legacy"]:
                imports.append(f"import {name}FormPage from '../pages/{name}FormPage';")
                routes.extend([
                    f'<Route path="/{route}" element={{<{name}Page />}} />',
                    f'<Route path="/{route}/new" element={{<{name}FormPage />}} />',
                    f'<Route path="/{route}/:id" element={{<{name}FormPage />}} />',
                ])
            else:
                routes.append(f'<Route path="/{route}" element={{<{name}Page />}} />')
                if page["bound"]:
                    routes.extend([
                        f'<Route path="/{route}/new" element={{<{name}Page />}} />',
                        f'<Route path="/{route}/:id" element={{<{name}Page />}} />',
                    ])
        report_import = "import ReportsPage from '../pages/ReportsPage';" if self._reports else ""
        report_route = '<Route path="/reports" element={<ReportsPage />} />' if self._reports else ""
        imports_js = "\n".join(imports)
        routes_js = " ".join(routes)
        return f"""import {{ Navigate, Route, Routes }} from 'react-router-dom';
{report_import}
{imports_js}

function Home() {{ return <section><h1>{self.app_name}</h1><p>Welcome to the application.</p></section>; }}

export default function AppRouter() {{
  return <Routes>
    <Route path="/" element={{<Home />}} />
    {report_route}
    {routes_js}
    <Route path="*" element={{<Navigate to="/" replace />}} />
  </Routes>;
}}
"""

    def _generate_app_layout(self) -> str:
        links = [f'<NavLink key="{page["route"]}" to="/{page["route"]}">{page["title"]}</NavLink>' for page in self._page_definitions()]
        if self._reports:
            links.append('<NavLink key="reports" to="/reports">Reports</NavLink>')
        links_js = " ".join(links)
        theme_key = self._theme.key if self._theme else "classic"
        if theme_key in ("modern_dashboard", "operations_workspace"):
            shell = f'<div className={{styles.dashboard}}><aside className={{styles.sidebar}}><NavLink className={{styles.brand}} to="/">{self.app_name}</NavLink><nav className={{styles.nav}} aria-label="Primary navigation">{links_js}</nav></aside><main className={{styles.content}}>{{children}}</main></div>'
        elif theme_key == "material":
            shell = f'<div className={{styles.app}}><header className={{styles.appbar}}><NavLink className={{styles.brand}} to="/">{self.app_name}</NavLink><nav className={{styles.nav}} aria-label="Primary navigation">{links_js}</nav></header><main className={{styles.content}}>{{children}}</main></div>'
        else:
            shell = f'<div className={{styles.app}}><header className={{styles.header}}><NavLink className={{styles.brand}} to="/">{self.app_name}</NavLink><nav className={{styles.nav}} aria-label="Primary navigation">{links_js}</nav></header><main className={{styles.content}}>{{children}}</main></div>'
        return f"""import {{ NavLink }} from 'react-router-dom';
import styles from './AppLayout.module.css';

export default function AppLayout({{ children }}) {{
  return {shell};
}}
"""

    @staticmethod
    def _generate_app_layout_css() -> str:
        return """.app { min-height: 100vh; }.header, .appbar { align-items: center; background: var(--color-surface); border-bottom: 1px solid var(--color-border); display: flex; gap: 1.5rem; min-height: 4rem; padding: 0 1.5rem; }.appbar { box-shadow: var(--shadow-sm); }.brand { color: var(--color-text); font-weight: 700; text-decoration: none; white-space: nowrap; }.nav { display: flex; gap: .5rem; overflow-x: auto; }.nav a { color: var(--color-text-muted); padding: .5rem; text-decoration: none; white-space: nowrap; }.nav a[aria-current='page'] { color: var(--color-primary); font-weight: 700; }.content { margin: 0 auto; max-width: 75rem; padding: 2rem; width: 100%; }.dashboard { display: grid; grid-template-columns: 16rem minmax(0, 1fr); min-height: 100vh; }.sidebar { background: #111827; display: flex; flex-direction: column; gap: 1.25rem; padding: 1.25rem; }.sidebar .brand { color: #fff; }.sidebar .nav { flex-direction: column; overflow: visible; }.sidebar .nav a { color: #cbd5e1; }.sidebar .nav a[aria-current='page'] { background: #1d4ed8; border-radius: var(--radius-sm); color: #fff; }@media (max-width: 720px) { .dashboard { grid-template-columns: 1fr; }.sidebar { gap: .5rem; }.sidebar .nav { flex-direction: row; overflow-x: auto; } }\n"""

    @staticmethod
    def _generate_use_api_hook() -> str:
        return """import { useCallback, useEffect, useState } from 'react';

export function useApi(fetchFn, deps = []) {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const refetch = useCallback(async () => {
    setLoading(true); setError(null);
    try { setData(await fetchFn()); } catch (err) { setError(err); } finally { setLoading(false); }
  // Callers pass stable service functions; deps controls refresh explicitly.
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, deps);
  useEffect(() => { refetch(); }, [refetch]);
  return { data, loading, error, refetch };
}
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
        """Generate package.json with the development quality toolchain."""
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
    "format": "prettier --write \\\"src/**/*.{'{'}js,jsx,css,json{'}'}\\\"",
    "format:check": "prettier --check \\\"src/**/*.{'{'}js,jsx,css,json{'}'}\\\"",
    "test": "vitest",
    "test:run": "vitest run",
    "test:coverage": "vitest run --coverage"
  }},
  "dependencies": {{
    "react": "19.2.8",
    "react-dom": "19.2.8",
    "react-router-dom": "7.18.2",
    "axios": "1.20.0"
  }},
  "devDependencies": {{
    "@vitejs/plugin-react": "6.0.5",
    "@eslint/js": "9.27.0",
    "vite": "8.2.1",
    "eslint": "9.27.0",
    "eslint-config-prettier": "10.1.5",
    "eslint-plugin-jsx-a11y": "6.10.2",
    "eslint-plugin-react": "7.37.5",
    "eslint-plugin-react-hooks": "5.2.0",
    "prettier": "3.5.3",
    "vitest": "3.2.1",
    "jsdom": "26.1.0",
    "@testing-library/jest-dom": "6.6.3",
    "@testing-library/react": "16.3.0",
    "@testing-library/user-event": "14.6.1"
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
        """Generate index.html with baseline discoverability metadata."""
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

    @staticmethod
    def _generate_eslintrc() -> str:
        return """module.exports = {
  env: { browser: true, es2024: true },
  extends: ['eslint:recommended', 'plugin:react/recommended', 'plugin:react-hooks/recommended', 'plugin:jsx-a11y/recommended', 'prettier'],
  settings: { react: { version: 'detect' } },
  rules: { 'react/prop-types': 'off', 'no-unused-vars': ['warn', { argsIgnorePattern: '^_' }] },
};
"""

    @staticmethod
    def _generate_eslint_flat_config() -> str:
        return """import js from '@eslint/js';
import react from 'eslint-plugin-react';
import hooks from 'eslint-plugin-react-hooks';
import a11y from 'eslint-plugin-jsx-a11y';
import prettier from 'eslint-config-prettier';

export default [
  js.configs.recommended,
  { files: ['src/**/*.{js,jsx}'], languageOptions: { ecmaVersion: 'latest', sourceType: 'module', parserOptions: { ecmaFeatures: { jsx: true } }, globals: { window: 'readonly', document: 'readonly', console: 'readonly', localStorage: 'readonly', URLSearchParams: 'readonly' } }, plugins: { react, 'react-hooks': hooks, 'jsx-a11y': a11y }, settings: { react: { version: 'detect' } }, rules: { ...react.configs.recommended.rules, ...hooks.configs.recommended.rules, ...a11y.configs.recommended.rules, 'react/react-in-jsx-scope': 'off', 'react/prop-types': 'off', 'no-unused-vars': ['warn', { argsIgnorePattern: '^_' }] } },
  prettier,
];
"""

    @staticmethod
    def _generate_prettierrc() -> str:
        return """{\n  \"singleQuote\": true,\n  \"trailingComma\": \"all\",\n  \"printWidth\": 100,\n  \"tabWidth\": 2,\n  \"semi\": true\n}\n"""

    @staticmethod
    def _generate_vitest_config_file() -> str:
        return """import { defineConfig } from 'vitest/config';
import react from '@vitejs/plugin-react';

export default defineConfig({
  plugins: [react()],
  test: { environment: 'jsdom', globals: true, setupFiles: './src/test/setup.js', include: ['src/**/*.{test,spec}.{js,jsx}'] },
});
"""

    @staticmethod
    def _generate_test_setup() -> str:
        return """import '@testing-library/jest-dom';
"""

    def _generate_readme(self) -> str:
        return f"""# {self.app_name}

Modernized React frontend generated from an MS Access application.

## Quick start

```bash
npm install
npm run dev
```

## Quality checks

```bash
npm run lint
npm run format:check
npm run test:run
npm run build
```

## Architecture

- `src/components/common`: reusable accessible UI primitives with CSS Modules.
- `src/routes/AppRouter.jsx`: application route definitions.
- `src/components/layout/AppLayout.jsx`: navigation shell.
- `src/services/apiClient.js`: centralized Axios client and error normalization.
- `src/services/*Service.js`: one CRUD service per Access table.
- `src/styles`: application tokens, reset, and selected theme layer.

The API base URL defaults to `/api`; set `VITE_API_BASE` to override it.
"""

    @staticmethod
    def _generate_api_client_test() -> str:
        return """import { describe, expect, it } from 'vitest';
import api, { ApiError } from '../apiClient';

describe('apiClient', () => {
  it('uses the configured base URL and timeout', () => {
    expect(api.defaults.baseURL).toBe('/api');
    expect(api.defaults.timeout).toBe(15000);
  });

  it('normalizes failed responses as ApiError', async () => {
    const handler = api.interceptors.response.handlers.find((entry) => entry?.rejected);
    await expect(handler.rejected({ response: { status: 422, data: { message: 'Invalid data' } } })).rejects.toEqual(expect.any(ApiError));
  });
});
"""

    def _generate_page_crud_test(self, table) -> str:
        entity = self._to_pascal(table.name)
        return f"""import {{ beforeEach, describe, expect, it, vi }} from 'vitest';
import api from '../apiClient';
import {{ create, getAll, getById, remove, update }} from '../{entity}Service';

vi.mock('../apiClient', () => ({{ default: {{ get: vi.fn(), post: vi.fn(), put: vi.fn(), delete: vi.fn() }} }}));

describe('{entity} service CRUD operations', () => {{
  beforeEach(() => vi.clearAllMocks());
  it('gets all records', async () => {{ api.get.mockResolvedValue({{ data: [{{ id: 1 }}] }}); await expect(getAll()).resolves.toEqual([{{ id: 1 }}]); expect(api.get).toHaveBeenCalledOnce(); }});
  it('gets one record', async () => {{ api.get.mockResolvedValue({{ data: {{ id: 7 }} }}); await expect(getById(7)).resolves.toEqual({{ id: 7 }}); expect(api.get).toHaveBeenCalledWith(expect.stringContaining('/7')); }});
  it('creates and updates a record', async () => {{ api.post.mockResolvedValue({{ data: {{ id: 1 }} }}); api.put.mockResolvedValue({{ data: {{ id: 1, name: 'Updated' }} }}); await expect(create({{ name: 'New' }})).resolves.toEqual({{ id: 1 }}); await expect(update(1, {{ name: 'Updated' }})).resolves.toEqual({{ id: 1, name: 'Updated' }}); }});
  it('deletes a record', async () => {{ api.delete.mockResolvedValue({{ data: null }}); await expect(remove(1)).resolves.toBeNull(); expect(api.delete).toHaveBeenCalledWith(expect.stringContaining('/1')); }});
}});
"""

    @staticmethod
    def _generate_form_page_interaction_test(page_name: str, api_name: str, endpoint: str) -> str:
        """Generate a render, submit, and navigation test for a CRUD form page."""
        return f"""import React from 'react';
import {{ render, screen }} from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import {{ MemoryRouter, Route, Routes }} from 'react-router-dom';
import {{ beforeEach, describe, expect, it, vi }} from 'vitest';
import {page_name}FormPage from '../{page_name}FormPage';

const service = vi.hoisted(() => ({{ create: vi.fn(), getById: vi.fn(), update: vi.fn() }}));
vi.mock('../../services/{api_name}Service', () => service);

describe('{page_name} CRUD form', () => {{
  beforeEach(() => {{ service.create.mockResolvedValue({{ id: 1 }}); service.getById.mockResolvedValue({{ id: 1 }}); service.update.mockResolvedValue({{ id: 1 }}); }});
  it('renders a create form and submits it', async () => {{
    const user = userEvent.setup();
    render(<MemoryRouter initialEntries={{['/{endpoint}/new']}}><Routes><Route path="/{endpoint}/new" element={{<{page_name}FormPage />}} /><Route path="/{endpoint}" element={{<p>List page</p>}} /></Routes></MemoryRouter>);
    const submit = await screen.findByRole('button', {{ name: /create|save/i }});
    await user.click(submit);
    expect(service.create).toHaveBeenCalled();
  }});
  it('loads and updates an existing record', async () => {{
    const user = userEvent.setup();
    render(<MemoryRouter initialEntries={{['/{endpoint}/7']}}><Routes><Route path="/{endpoint}/:id" element={{<{page_name}FormPage />}} /></Routes></MemoryRouter>);
    await screen.findByRole('button', {{ name: /update|save/i }});
    await user.click(screen.getByRole('button', {{ name: /update|save/i }}));
    expect(service.getById).toHaveBeenCalledWith('7');
    expect(service.update).toHaveBeenCalledWith('7', expect.any(Object));
  }});
}});
"""

    @staticmethod
    def _generate_legacy_page_interaction_test(page_name: str, api_name: str, endpoint: str) -> str:
        """Test legacy combined pages when UI transformation falls back."""
        return f"""import React from 'react';
import {{ render, screen }} from '@testing-library/react';
import {{ MemoryRouter }} from 'react-router-dom';
import {{ describe, expect, it, vi }} from 'vitest';
import {page_name}Page from '../{page_name}Page';

vi.mock('../../services/{api_name}Service', () => ({{ getAll: vi.fn().mockResolvedValue([]), getById: vi.fn(), create: vi.fn(), update: vi.fn() }}));

describe('{page_name} page', () => {{
  it('renders its data state without crashing', async () => {{
    render(<MemoryRouter><{page_name}Page /></MemoryRouter>);
    expect(await screen.findByRole('link', {{ name: /add new/i }})).toHaveAttribute('href', '/{endpoint}/new');
  }});
}});
"""

    @staticmethod
    def _generate_tokens_css() -> str:
        return """:root { --color-primary: #2563eb; --color-text: #1f2937; --color-text-muted: #6b7280; --color-border: #e5e7eb; --color-surface: #fff; --color-surface-muted: #f8fafc; --color-bg: #f3f4f6; --color-danger: #dc2626; --radius-sm: .375rem; --radius-md: .5rem; --shadow-sm: 0 1px 2px rgba(0,0,0,.05); --shadow-md: 0 4px 6px rgba(0,0,0,.1); font-family: Inter, system-ui, sans-serif; color: var(--color-text); background: var(--color-bg); }\n"""

    @staticmethod
    def _generate_reset_css() -> str:
        return """* { box-sizing: border-box; } body { background: var(--color-bg); color: var(--color-text); margin: 0; min-width: 320px; } button, input, select, textarea { font: inherit; } button { cursor: pointer; }\n"""

    @staticmethod
    def _attach_page_module(content: str, module_name: str) -> str:
        """Attach a CSS Module without changing each individual renderer."""
        if "import styles from './" not in content:
            content = f"import styles from './{module_name}';\n" + content
        # Existing themes still have a few action buttons in dashboard/detail
        # templates. Normalize those at the emission boundary so every page
        # uses the same accessible Button primitive (Exact retains positioning).
        if "<button" in content:
            if "Button" not in content.split("\n", 8)[0:8].__str__():
                content = "import { Button } from '../components/common';\n" + content
            content = content.replace("<button", "<Button").replace("</button>", "</Button>")
        import re
        return re.sub(r'className="[^"]+-(?:page|form)"', 'className={styles.page}', content, count=1)

    @staticmethod
    def _generate_page_css_module() -> str:
        return """.page { animation: enter .2s ease-out; background: var(--color-surface); border-radius: var(--radius-md); min-width: 0; }\n@keyframes enter { from { opacity: 0; transform: translateY(4px); } to { opacity: 1; transform: translateY(0); } }\n"""

    def _generate_index_css(self, theme_imports: Optional[list[str]] = None) -> str:
        """Generate global CSS with dynamic form-based styles (Spec section 46)."""
        imports = ["./styles/tokens.css", "./styles/reset.css", *(theme_imports or [])]
        return "".join(f"@import '{path}';\n" for path in imports)
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
