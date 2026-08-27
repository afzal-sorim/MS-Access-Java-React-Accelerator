"""React frontend generator - pages, components, forms from Access forms.

Spec section 19: Forms → React pages/components with proper control mappings.
Spec section 46: Generate routes, pages, components, forms, tables, API clients.
"""
from __future__ import annotations

from pathlib import Path
from typing import Optional


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
    ):
        self.app = app_ir
        self.app_name = app_name or app_ir.application_name
        self.report_strategy = (report_strategy or "pdf").strip().lower()
        self.warnings: list[str] = []
        self._pk_map: dict[str, str] = {}
        self._analyze_keys()
        self._reports: list = []

    def generate(self, output_dir: str | Path) -> dict[str, str]:
        """Generate all React files and return a map of path -> content."""
        output_dir = Path(output_dir)
        files: dict[str, str] = {}

        src = output_dir / "src"

        # Generate pages from forms
        for form in self.app.forms:
            page_name = self._to_pascal(form.name.replace("frm", ""))
            page_content = self._generate_page(form)
            files[str(src / "pages" / f"{page_name}Page.jsx")] = page_content

        # Generate the reports page when the source app has usable reports
        # (spec section 20: report parameters, view, CSV/PDF download).
        self._reports = self._resolve_reports()
        if self._reports:
            files[str(src / "pages" / "ReportsPage.jsx")] = self._generate_reports_page()

        # Generate API client
        files[str(src / "services" / "api.js")] = self._generate_api_client()

        # Generate App.jsx with routing
        files[str(src / "App.jsx")] = self._generate_app_jsx()

        # Generate main.jsx
        files[str(src / "main.jsx")] = self._generate_main_jsx()

        # Generate package.json
        files[str(output_dir / "package.json")] = self._generate_package_json()

        # Generate vite.config.js
        files[str(output_dir / "vite.config.js")] = self._generate_vite_config()

        # Generate index.html
        files[str(output_dir / "index.html")] = self._generate_index_html()

        return files

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

        # Fix 4: Unbound forms (no record_source) get info/dashboard pages, not CRUD
        if not form.record_source:
            return self._generate_unbound_page(form, page_name)

        endpoint = self._to_kebab(form.record_source)
        # Fix 5: API name must match api.js exports (table-based names)
        api_name = self._resolve_api_name(form.record_source)

        # Determine if this is a list page or form page
        is_list = any(
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
        NOT database CRUD forms. We render them as informational pages with
        labels and buttons that have TODO comments for their event logic.
        """
        # Separate controls by type
        labels = [c for c in form.controls if c.control_type == "Label"]
        buttons = [c for c in form.controls if c.control_type == "CommandButton"]
        text_fields = [c for c in form.controls if c.control_type in ("TextBox", "ComboBox") and c.visible]
        checkboxes = [c for c in form.controls if c.control_type == "CheckBox"]

        # Generate label display
        label_elements = []
        for ctrl in labels:
            caption = ctrl.caption or ctrl.name
            source = ctrl.control_source or ""
            if self._is_access_expression(source):
                # Render Access expression as a comment, not as broken JSX
                sanitized = self._sanitize_control_source(source)
                safe_expr = source.replace('"', "'")
                label_elements.append(f"""
            <div className="info-field">
                <span className="info-label">{caption}</span>
                <span className="info-value" id="{sanitized}">{{/* TODO: Access expression: {safe_expr} */}}</span>
            </div>""")
            elif source:
                sanitized = self._sanitize_control_source(source)
                label_elements.append(f"""
            <div className="info-field">
                <span className="info-label">{caption}</span>
                <span className="info-value">{source}</span>
            </div>""")
            else:
                label_elements.append(f"""
            <div className="info-field">
                <span className="info-label">{caption}</span>
            </div>""")

        # Generate text field display (read-only for unbound forms)
        field_elements = []
        for ctrl in text_fields:
            source = ctrl.control_source or ctrl.name
            label = ctrl.caption or source
            if self._is_access_expression(source):
                sanitized = self._sanitize_control_source(source)
                safe_expr = source.replace('"', "'")
                field_elements.append(f"""
            <div className="info-field">
                <span className="info-label">{label}</span>
                <span className="info-value" id="{sanitized}">{{/* TODO: Access expression: {safe_expr} */}}</span>
            </div>""")
            else:
                sanitized = self._sanitize_control_source(source)
                field_elements.append(f"""
            <div className="info-field">
                <span className="info-label">{label}</span>
                <span className="info-value" id="{sanitized}"></span>
            </div>""")

        # Generate button elements with TODO handlers
        button_elements = []
        for ctrl in buttons:
            caption = ctrl.caption or ctrl.name
            handler_name = self._to_camel(ctrl.name)
            button_elements.append(f"""
            <button
                className="btn"
                onClick={{() => console.warn('TODO: Implement {handler_name} — original Access event handler not yet converted')}}
            >
                {caption}
            </button>""")

        labels_js = "\n".join(label_elements) if label_elements else ""
        fields_js = "\n".join(field_elements) if field_elements else ""
        buttons_js = "\n".join(button_elements) if button_elements else ""

        return f"""import React from 'react';

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
            <h1>{form.caption or page_name}</h1>
            <p className="form-description">This page corresponds to Access form: {form.name}</p>
{labels_js}
{fields_js}
            <div className="button-group">
{buttons_js}
            </div>
        </div>
    );
}}
"""

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

        return f"""import React, {{ useState, useEffect }} from 'react';
import {{ Link }} from 'react-router-dom';
import {{ get{api_name} }} from '../services/api';

export default function {page_name}Page() {{
    const [{var_name}, set{page_name}] = useState([]);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState(null);

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

    if (loading) return <div className="loading">Loading...</div>;
    if (error) return <div className="error">{{error}}</div>;

    return (
        <div className="{page_name.lower()}-page">
            <h1>{form.caption or page_name}</h1>
            <table className="data-table">
                <thead>
                    <tr>
                        <th>Action</th>
                        {header_ths}
                    </tr>
                </thead>
                <tbody>
                    {{{var_name}.map(item => (
                        <tr key={{item.id}}>
                            <td>
                                <Link to={{`/{endpoint}/${{item.id}}`}}>View</Link>
                            </td>
                            {"".join([f'<td>{{item.{self._to_camel(col)}}}</td>' for col in display_cols[:6]])}
                        </tr>
                    ))}}
                </tbody>
            </table>
            <Link to="/{endpoint}/new" className="btn">Add New</Link>
        </div>
    );
}}
"""

    def _generate_form_page(self, form, page_name: str, endpoint: str, api_name: str = "") -> str:
        """Generate a form page for create/edit."""
        api_name = api_name or page_name
        var_name = self._to_camel(page_name)

        # Generate form fields with Access expression sanitization (Fix 3)
        form_fields = []
        for ctrl in form.controls:
            if ctrl.control_type in ("TextBox", "ComboBox", "CheckBox"):
                # Use control_source if available, fall back to control name
                raw_source = ctrl.control_source or ctrl.name

                # Fix 3: Sanitize Access expressions into valid JS identifiers
                field_name = self._to_camel(self._sanitize_control_source(raw_source))
                label = ctrl.caption or raw_source
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

                if ctrl.control_type == "CheckBox":
                    form_fields.append(f"""
            <div className="form-group">{expr_comment}
                <label>
                    <input
                        type="checkbox"
                        name="{field_name}"
                        checked={{formData.{field_name} || false}}
                        onChange={{handleChange}}{disabled_attr}
                    />
                    {label}
                </label>
            </div>""")
                else:
                    form_fields.append(f"""
            <div className="form-group">{expr_comment}
                <label htmlFor="{field_name}">{label}</label>
                <input
                    type="{input_type}"
                    id="{field_name}"
                    name="{field_name}"
                    value={{formData.{field_name} || ''}}
                    onChange={{handleChange}}{disabled_attr}
                />
            </div>""")

        form_fields_js = "\n".join(form_fields)

        return f"""import React, {{ useState, useEffect }} from 'react';
import {{ useParams, useNavigate }} from 'react-router-dom';
import {{ get{api_name}ById, create{api_name}, update{api_name} }} from '../services/api';

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

    if (loading) return <div className="loading">Saving...</div>;

    return (
        <div className="{page_name.lower()}-form">
            <h1>{{isEdit ? 'Edit' : 'Create'}} {form.caption or page_name}</h1>
            {{error && <div className="error">{{error}}</div>}}
            <form onSubmit={{handleSubmit}}>
                {form_fields_js}
                <div className="form-actions">
                    <button type="submit" disabled={{loading}}>
                        {{isEdit ? 'Update' : 'Create'}}
                    </button>
                    <button type="button" onClick={{() => navigate('/{endpoint}')}}>
                        Cancel
                    </button>
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
import {{ listReports, runReport, reportDownloadUrl }} from '../services/api';

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
                        <button type="submit" disabled={{loading || missingRequired.length > 0}}>
                            {{loading ? 'Running...' : 'Run Report'}}
                        </button>
                        <button
                            type="button"
                            onClick={{() => download('csv')}}
                            disabled={{loading || missingRequired.length > 0}}
                        >
                            Download CSV
                        </button>{pdf_button}
                    </div>

                    {{definition.notes.length > 0 && (
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

    def _generate_api_client(self) -> str:
        """Generate API client service."""
        endpoints = []

        for table in self.app.tables:
            if table.role in ("SYSTEM", "INTERNAL"):
                continue

            entity_name = self._to_pascal(table.name)
            endpoint = self._to_kebab(table.name)

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
            report_api = """
// Reports (generated from Access reports)

/** List available reports with their columns and parameters. */
export async function listReports() {
    const response = await fetch(`${API_BASE}/reports`);
    if (!response.ok) throw new Error('Failed to load reports');
    return response.json();
}

/** Run a report and return { columns, rows, rowCount }. */
export async function runReport(endpoint, params = {}) {
    const query = buildReportQuery(params);
    const response = await fetch(`${API_BASE}/reports/${endpoint}${query}`);
    if (!response.ok) {
        const detail = await response.json().catch(() => null);
        throw new Error(detail?.error || `Failed to run report ${endpoint}`);
    }
    return response.json();
}

/** URL for a CSV or PDF export, for use in a download link. */
export function reportDownloadUrl(endpoint, format, params = {}) {
    return `${API_BASE}/reports/${endpoint}/${format}${buildReportQuery(params)}`;
}

function buildReportQuery(params) {
    const search = new URLSearchParams();
    Object.entries(params).forEach(([key, value]) => {
        if (value !== undefined && value !== null && String(value) !== '') {
            search.append(key, String(value));
        }
    });
    const query = search.toString();
    return query ? `?${query}` : '';
}
"""

        return f"""const API_BASE = 'http://localhost:8080/api';
{''.join(endpoints)}{report_api}
"""

    def _generate_app_jsx(self) -> str:
        """Generate App.jsx with routing."""
        routes = []
        imports = []

        for form in self.app.forms:
            page_name = self._to_pascal(form.name.replace("frm", ""))
            route_path = self._to_kebab(form.record_source) if form.record_source else self._to_kebab(form.name)

            imports.append(f"import {page_name}Page from './pages/{page_name}Page';")
            routes.append(f'            <Route path="/{route_path}" element={{<{page_name}Page />}} />')
            routes.append(f'            <Route path="/{route_path}/:id" element={{<{page_name}Page />}} />')
            routes.append(f'            <Route path="/{route_path}/new" element={{<{page_name}Page />}} />')

        imports_js = "\n".join(imports)
        routes_js = "\n".join(routes)

        report_import = ""
        report_route = ""
        report_link = ""
        if self._reports:
            report_import = "import ReportsPage from './pages/ReportsPage';\n"
            report_route = '            <Route path="/reports" element={<ReportsPage />} />\n'
            report_link = '<Link to="/reports">Reports</Link>'

        return f"""import React from 'react';
import {{ BrowserRouter as Router, Routes, Route, Link }} from 'react-router-dom';
{report_import}{imports_js}

export default function App() {{
    return (
        <Router>
            <div className="app">
                <nav className="navbar">
                    <Link to="/">Home</Link>
                    {"".join([f'<Link to="/{self._to_kebab(f.record_source) if f.record_source else self._to_kebab(f.name)}">{f.caption or self._to_pascal(f.name.replace("frm", ""))}</Link>' for f in self.app.forms if f.name.lower() != "frmlogin"])}
                    {report_link}
                </nav>
                <main className="content">
                    <Routes>
                        <Route path="/" element={{<HomePage />}} />
{report_route}{routes_js}
                    </Routes>
                </main>
            </div>
        </Router>
    );
}}

function HomePage() {{
    return (
        <div className="home">
            <h1>{self.app_name}</h1>
            <p>Welcome to the application.</p>
        </div>
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
        """Generate package.json."""
        return f"""{{
  "name": "{self._to_kebab(self.app_name)}",
  "version": "1.0.0",
  "type": "module",
  "scripts": {{
    "dev": "vite",
    "build": "vite build",
    "preview": "vite preview"
  }},
  "dependencies": {{
    "react": "19.2.8",
    "react-dom": "19.2.8",
    "react-router-dom": "7.18.2"
  }},
  "devDependencies": {{
    "@vitejs/plugin-react": "6.0.5",
    "vite": "8.2.1"
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
        """Generate index.html."""
        return f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{self.app_name}</title>
</head>
<body>
    <div id="root"></div>
    <script type="module" src="/src/main.jsx"></script>
</body>
</html>
"""

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
    """Entry point to generate React frontend."""
    generator = ReactGenerator(app_ir, **kwargs)
    return generator.generate(output_dir)
