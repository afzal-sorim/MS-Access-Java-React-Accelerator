"""Material Design Theme — Google Material-inspired with elevation, outlined inputs, responsive grid.

Features:
- Top AppBar with hamburger menu
- Elevation shadows (depth levels)
- Outlined text fields with floating labels
- FAB (Floating Action Button) for primary actions
- Responsive CSS Grid layout
- Roboto font family
"""
from __future__ import annotations

from .base import Theme
from ..ui.models import UIPresentation, InfoLevel


class MaterialTheme(Theme):

    @property
    def name(self) -> str:
        return "Material Design"

    @property
    def key(self) -> str:
        return "material"

    def get_css(self, app_name: str, presentations: list[UIPresentation]) -> str:
        css = """:root {
    --mat-primary: #1976d2;
    --mat-primary-light: #42a5f5;
    --mat-primary-dark: #1565c0;
    --mat-secondary: #9c27b0;
    --mat-surface: #ffffff;
    --mat-background: #fafafa;
    --mat-error: #d32f2f;
    --mat-success: #2e7d32;
    --mat-on-primary: #ffffff;
    --mat-on-surface: #212121;
    --mat-text-primary: rgba(0, 0, 0, 0.87);
    --mat-text-secondary: rgba(0, 0, 0, 0.60);
    --mat-text-disabled: rgba(0, 0, 0, 0.38);
    --mat-divider: rgba(0, 0, 0, 0.12);
    --mat-elevation-1: 0 2px 1px -1px rgba(0,0,0,.2), 0 1px 1px 0 rgba(0,0,0,.14), 0 1px 3px 0 rgba(0,0,0,.12);
    --mat-elevation-2: 0 3px 1px -2px rgba(0,0,0,.2), 0 2px 2px 0 rgba(0,0,0,.14), 0 1px 5px 0 rgba(0,0,0,.12);
    --mat-elevation-4: 0 2px 4px -1px rgba(0,0,0,.2), 0 4px 5px 0 rgba(0,0,0,.14), 0 1px 10px 0 rgba(0,0,0,.12);
    --mat-elevation-8: 0 5px 5px -3px rgba(0,0,0,.2), 0 8px 10px 1px rgba(0,0,0,.14), 0 3px 14px 2px rgba(0,0,0,.12);
    --mat-radius: 4px;
}

@import url('https://fonts.googleapis.com/css2?family=Roboto:wght@300;400;500;700&display=swap');
@import url('https://fonts.googleapis.com/icon?family=Material+Icons');

* { box-sizing: border-box; margin: 0; padding: 0; }
body {
    font-family: 'Roboto', 'Helvetica Neue', Arial, sans-serif;
    background: var(--mat-background);
    color: var(--mat-text-primary);
    line-height: 1.5;
    -webkit-font-smoothing: antialiased;
}

.app {
    display: flex;
    flex-direction: column;
    min-height: 100vh;
}

/* ─── AppBar ─── */
.appbar {
    background: var(--mat-primary);
    color: var(--mat-on-primary);
    padding: 0 1.5rem;
    height: 64px;
    display: flex;
    align-items: center;
    box-shadow: var(--mat-elevation-4);
    position: sticky;
    top: 0;
    z-index: 100;
}

.appbar h1 {
    font-size: 1.25rem;
    font-weight: 500;
    letter-spacing: 0.02em;
}

.appbar-nav {
    display: flex;
    align-items: center;
    gap: 0.25rem;
    margin-left: 2rem;
    height: 100%;
}

.appbar-nav a {
    color: rgba(255, 255, 255, 0.85);
    text-decoration: none;
    font-size: 0.875rem;
    font-weight: 500;
    padding: 0 1rem;
    height: 100%;
    display: flex;
    align-items: center;
    transition: background 0.2s;
    text-transform: uppercase;
    letter-spacing: 0.04em;
    border-radius: var(--mat-radius) var(--mat-radius) 0 0;
}

.appbar-nav a:hover {
    background: rgba(255, 255, 255, 0.1);
    color: white;
}

/* ─── Content ─── */
.content {
    flex: 1;
    padding: 1.5rem;
    max-width: 1200px;
    margin: 0 auto;
    width: 100%;
}

.page-header {
    margin-bottom: 1.5rem;
}

.page-header h1 {
    font-size: 1.5rem;
    font-weight: 400;
    color: var(--mat-text-primary);
}

.page-header p {
    font-size: 0.875rem;
    color: var(--mat-text-secondary);
    margin-top: 0.25rem;
}

/* ─── Material Card ─── */
.card, .section-card {
    background: var(--mat-surface);
    border-radius: var(--mat-radius);
    box-shadow: var(--mat-elevation-2);
    padding: 1.5rem;
    margin-bottom: 1.5rem;
    transition: box-shadow 0.3s;
}

.card:hover {
    box-shadow: var(--mat-elevation-4);
}

.card h2, .section-card h2 {
    font-size: 1.25rem;
    font-weight: 500;
    margin-bottom: 1rem;
    color: var(--mat-text-primary);
}

.card-grid {
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(300px, 1fr));
    gap: 1.5rem;
}

/* ─── Material Outlined Input ─── */
.form-group {
    margin-bottom: 1.25rem;
    position: relative;
}

.form-group label {
    display: block;
    margin-bottom: 0.375rem;
    font-size: 0.75rem;
    font-weight: 500;
    color: var(--mat-text-secondary);
    text-transform: uppercase;
    letter-spacing: 0.08em;
}

.form-group input, .form-group select, .form-group textarea {
    width: 100%;
    padding: 0.875rem 0.75rem;
    border: 1px solid var(--mat-divider);
    border-radius: var(--mat-radius);
    background: transparent;
    color: var(--mat-text-primary);
    font-size: 1rem;
    font-family: inherit;
    transition: border-color 0.2s, box-shadow 0.2s;
}

.form-group input:focus, .form-group select:focus, .form-group textarea:focus {
    outline: none;
    border-color: var(--mat-primary);
    border-width: 2px;
    padding: calc(0.875rem - 1px) calc(0.75rem - 1px);
}

.form-group input:hover, .form-group select:hover {
    border-color: var(--mat-text-primary);
}

.form-actions {
    display: flex;
    gap: 0.75rem;
    margin-top: 1.5rem;
    padding-top: 1rem;
    justify-content: flex-end;
}

/* ─── Material Buttons ─── */
.btn {
    padding: 0 1.5rem;
    height: 36px;
    border-radius: var(--mat-radius);
    background: var(--mat-primary);
    color: var(--mat-on-primary);
    border: none;
    cursor: pointer;
    font-weight: 500;
    font-size: 0.875rem;
    text-transform: uppercase;
    letter-spacing: 0.04em;
    transition: box-shadow 0.2s, background 0.2s;
    display: inline-flex;
    align-items: center;
    justify-content: center;
    box-shadow: var(--mat-elevation-2);
    min-width: 64px;
}

.btn:hover {
    box-shadow: var(--mat-elevation-4);
    background: var(--mat-primary-dark);
}

.btn:active {
    box-shadow: var(--mat-elevation-8);
}

.btn-secondary {
    background: transparent;
    color: var(--mat-primary);
    box-shadow: none;
    border: 1px solid var(--mat-divider);
}

.btn-secondary:hover {
    background: rgba(25, 118, 210, 0.04);
    box-shadow: none;
}

.btn-danger {
    background: var(--mat-error);
}

.btn-text {
    background: transparent;
    color: var(--mat-primary);
    box-shadow: none;
}

.btn-text:hover {
    background: rgba(25, 118, 210, 0.08);
    box-shadow: none;
}

/* ─── FAB ─── */
.fab {
    position: fixed;
    bottom: 1.5rem;
    right: 1.5rem;
    width: 56px;
    height: 56px;
    border-radius: 50%;
    background: var(--mat-secondary);
    color: white;
    border: none;
    cursor: pointer;
    box-shadow: var(--mat-elevation-8);
    display: flex;
    align-items: center;
    justify-content: center;
    font-size: 1.5rem;
    transition: box-shadow 0.3s, transform 0.2s;
    z-index: 50;
    text-decoration: none;
}

.fab:hover {
    transform: scale(1.05);
    box-shadow: 0 7px 8px -4px rgba(0,0,0,.2), 0 12px 17px 2px rgba(0,0,0,.14), 0 5px 22px 4px rgba(0,0,0,.12);
}

/* ─── Material Table ─── */
.data-table {
    width: 100%;
    border-collapse: collapse;
    margin: 0.5rem 0;
}

.data-table th, .data-table td {
    padding: 0.875rem 1rem;
    text-align: left;
    border-bottom: 1px solid var(--mat-divider);
}

.data-table th {
    font-weight: 500;
    font-size: 0.75rem;
    color: var(--mat-text-secondary);
    letter-spacing: 0.04em;
}

.data-table tr:hover td {
    background: rgba(0, 0, 0, 0.04);
}

.data-table a {
    color: var(--mat-primary);
    text-decoration: none;
    font-weight: 500;
}

/* ─── Utilities ─── */
.two-column {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 1.5rem;
}

.stat-card {
    background: var(--mat-surface);
    border-radius: var(--mat-radius);
    box-shadow: var(--mat-elevation-1);
    padding: 1.5rem;
    text-align: center;
}

.stat-card .stat-value {
    font-size: 2.5rem;
    font-weight: 300;
    color: var(--mat-primary);
}

.stat-card .stat-label {
    font-size: 0.75rem;
    color: var(--mat-text-secondary);
    text-transform: uppercase;
    letter-spacing: 0.08em;
    margin-top: 0.25rem;
}

.loading { text-align: center; padding: 3rem; color: var(--mat-text-secondary); }
.error { color: var(--mat-error); padding: 1rem; background: #fef2f2; border-radius: var(--mat-radius); margin: 1rem 0; }
.empty { text-align: center; color: var(--mat-text-disabled); padding: 3rem; }

.info-field {
    display: flex;
    padding: 0.875rem 0;
    border-bottom: 1px solid var(--mat-divider);
}

.info-label {
    width: 200px;
    font-weight: 500;
    color: var(--mat-text-secondary);
    font-size: 0.875rem;
}

.info-value { flex: 1; }

.button-group {
    display: flex;
    flex-wrap: wrap;
    gap: 0.5rem;
    margin-top: 1.5rem;
}

.form-description {
    color: var(--mat-text-secondary);
    font-size: 0.875rem;
    margin-bottom: 1.5rem;
}

.chip {
    display: inline-flex;
    align-items: center;
    height: 32px;
    padding: 0 12px;
    border-radius: 16px;
    background: #e0e0e0;
    font-size: 0.8125rem;
    color: var(--mat-text-primary);
}

@media (max-width: 768px) {
    .two-column { grid-template-columns: 1fr; }
    .card-grid { grid-template-columns: 1fr; }
    .appbar-nav { display: none; }
}

@keyframes fadeIn {
    from { opacity: 0; }
    to { opacity: 1; }
}
"""
        for p in presentations:
            name = self._to_pascal(p.screen_id.replace("frm", ""))
            cls = name.lower()
            css += f"""
.{cls}-page, .{cls}-form {{
    animation: fadeIn 0.3s ease-out;
}}
"""
        return css

    # ──────────────────────────────────── Pages

    def render_list_page(self, presentation, endpoint, api_name, helper_imports):
        page_name = self._to_pascal(presentation.screen_id.replace("frm", ""))
        var_name = self._to_camel(page_name)
        cols = self._build_table_columns(presentation.fields)
        header_ths = "\n                        ".join(f"<th>{f.label}</th>" for f in cols)
        body_tds = "".join(f"<td>{{item.{self._to_camel(self._sanitize_field(f.data_source or f.id))}}}</td>" for f in cols)

        return f"""import React, {{ useState, useEffect }} from 'react';
import {{ Link }} from 'react-router-dom';
import {{ get{api_name} }} from '../services/api';

export default function {page_name}Page() {{
    const [{var_name}, set{page_name}] = useState([]);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState(null);

    useEffect(() => {{
        get{api_name}()
            .then(data => set{page_name}(data))
            .catch(err => setError(err.message))
            .finally(() => setLoading(false));
    }}, []);

    if (loading) return <div className="loading">Loading...</div>;
    if (error) return <div className="error">{{error}}</div>;

    return (
        <div className="{page_name.lower()}-page">
            <div className="page-header">
                <h1>{presentation.screen_name}</h1>
            </div>
            <div className="card">
                <table className="data-table">
                    <thead>
                        <tr>
                            {header_ths}
                            <th></th>
                        </tr>
                    </thead>
                    <tbody>
                        {{{var_name}.map(item => (
                            <tr key={{item.id}}>
                                {body_tds}
                                <td>
                                    <Link to={{`/{endpoint}/${{item.id}}`}} className="btn-text">EDIT</Link>
                                </td>
                            </tr>
                        ))}}
                    </tbody>
                </table>
                {{{var_name}.length === 0 && <p className="empty">No records found.</p>}}
            </div>
            <Link to="/{endpoint}/new" className="fab" title="Add New">+</Link>
        </div>
    );
}}
"""

    def render_form_page(self, presentation, endpoint, api_name, helper_imports):
        page_name = self._to_pascal(presentation.screen_id.replace("frm", ""))
        form_fields = self._build_form_fields_jsx(presentation.fields)

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
            get{api_name}ById(id).then(setFormData).catch(err => setError(err.message));
        }}
    }}, [id, isEdit]);

    const handleChange = (e) => {{
        const {{ name, value, type, checked }} = e.target;
        setFormData(prev => ({{ ...prev, [name]: type === 'checkbox' ? checked : value }}));
    }};

    const handleSubmit = async (e) => {{
        e.preventDefault();
        setLoading(true);
        try {{
            isEdit ? await update{api_name}(id, formData) : await create{api_name}(formData);
            navigate('/{endpoint}');
        }} catch (err) {{ setError(err.message); }}
        finally {{ setLoading(false); }}
    }};

    return (
        <div className="{page_name.lower()}-form">
            <div className="page-header">
                <h1>{{isEdit ? 'Edit' : 'New'}} {presentation.screen_name}</h1>
            </div>
            <div className="card">
                {{error && <div className="error">{{error}}</div>}}
                <form onSubmit={{handleSubmit}}>
                    {form_fields}
                    <div className="form-actions">
                        <button type="button" onClick={{() => navigate('/{endpoint}')}} className="btn btn-secondary">
                            CANCEL
                        </button>
                        <button type="submit" disabled={{loading}} className="btn">
                            {{isEdit ? 'SAVE' : 'CREATE'}}
                        </button>
                    </div>
                </form>
            </div>
        </div>
    );
}}
"""

    def render_dashboard_page(self, presentation):
        page_name = self._to_pascal(presentation.screen_id.replace("frm", ""))
        action_cards = []
        for action in presentation.actions:
            handler = self._to_camel(action.id)
            nav_route = self._resolve_action_route(action)
            if nav_route:
                click_handler = f"navigate('{nav_route}')"
            else:
                click_handler = f"console.warn('No route mapped for: {handler}')"
            action_cards.append(f"""
                <div className="stat-card" style={{{{cursor:'pointer'}}}} onClick={{() => {click_handler}}}>
                    <div className="stat-value" style={{{{fontSize:'1.5rem'}}}}>▶</div>
                    <div className="stat-label">{action.label}</div>
                </div>""")

        # Only import useNavigate if any card actually uses it
        needs_navigate = any(self._resolve_action_route(a) for a in presentation.actions)
        navigate_import = "import { useNavigate } from 'react-router-dom';\n" if needs_navigate else ""
        navigate_hook = "    const navigate = useNavigate();\n" if needs_navigate else ""

        return f"""import React from 'react';
{navigate_import}
export default function {page_name}Page() {{
{navigate_hook}    return (
        <div className="{page_name.lower()}-page">
            <div className="page-header">
                <h1>{presentation.screen_name}</h1>
            </div>
            <div className="card-grid">
{"".join(action_cards)}
            </div>
        </div>
    );
}}
"""

    def render_detail_page(self, presentation, endpoint, api_name, helper_imports):
        return self.render_form_page(presentation, endpoint, api_name, helper_imports)

    def render_master_detail_page(self, presentation, endpoint, api_name, helper_imports):
        page_name = self._to_pascal(presentation.screen_id.replace("frm", ""))
        primary_fields = [f for f in presentation.fields if f.info_level == InfoLevel.PRIMARY]
        form_fields = self._build_form_fields_jsx(primary_fields)

        subform_cards = []
        for sf in presentation.subforms:
            subform_cards.append(f"""
            <div className="card">
                <h2>{sf.name}</h2>
                <p className="form-description">Related: {sf.record_source or sf.name}</p>
            </div>""")

        return f"""import React, {{ useState, useEffect }} from 'react';
import {{ useParams, useNavigate }} from 'react-router-dom';
import {{ get{api_name}ById, create{api_name}, update{api_name} }} from '../services/api';

export default function {page_name}Page() {{
    const {{ id }} = useParams();
    const navigate = useNavigate();
    const [formData, setFormData] = useState({{}});
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState(null);
    const isEdit = Boolean(id);

    useEffect(() => {{
        if (isEdit) {{
            get{api_name}ById(id).then(data => {{ setFormData(data); setLoading(false); }}).catch(err => {{ setError(err.message); setLoading(false); }});
        }} else {{ setLoading(false); }}
    }}, [id, isEdit]);

    const handleChange = (e) => {{
        const {{ name, value, type, checked }} = e.target;
        setFormData(prev => ({{ ...prev, [name]: type === 'checkbox' ? checked : value }}));
    }};

    const handleSubmit = async (e) => {{
        e.preventDefault();
        try {{
            isEdit ? await update{api_name}(id, formData) : await create{api_name}(formData);
            navigate('/{endpoint}');
        }} catch (err) {{ setError(err.message); }}
    }};

    if (loading) return <div className="loading">Loading...</div>;

    return (
        <div className="{page_name.lower()}-page">
            <div className="page-header">
                <h1>{presentation.screen_name}</h1>
            </div>
            <div className="card">
                <h2>Details</h2>
                {{error && <div className="error">{{error}}</div>}}
                <form onSubmit={{handleSubmit}}>
                    <div className="two-column">
                        {form_fields}
                    </div>
                    <div className="form-actions">
                        <button type="button" onClick={{() => navigate('/{endpoint}')}} className="btn btn-secondary">CANCEL</button>
                        <button type="submit" className="btn">SAVE</button>
                    </div>
                </form>
            </div>
{"".join(subform_cards)}
        </div>
    );
}}
"""

    def render_app_shell(self, app_name, pages, report_import, report_route, report_link):
        imports = "\n".join(p["import"] for p in pages)
        routes = "\n".join(p["routes"] for p in pages)
        nav_links = []
        for p in pages:
            if "nav_link_text" in p:
                nav_links.append(f'<Link to="{p["nav_path"]}">{p["nav_link_text"]}</Link>')

        nav_jsx = " ".join(nav_links)
        report_nav = ' <Link to="/reports">Reports</Link>' if report_link else ""

        return f"""import React from 'react';
import {{ BrowserRouter as Router, Routes, Route, Link }} from 'react-router-dom';
{report_import}{imports}

export default function App() {{
    return (
        <Router>
            <div className="app">
                <header className="appbar">
                    <h1>{app_name}</h1>
                    <nav className="appbar-nav">
                        <Link to="/">Home</Link>
                        {nav_jsx}{report_nav}
                    </nav>
                </header>
                <main className="content">
                    <Routes>
                        <Route path="/" element={{<HomePage />}} />
{report_route}{routes}
                    </Routes>
                </main>
            </div>
        </Router>
    );
}}

function HomePage() {{
    return (
        <div>
            <div className="page-header">
                <h1>{app_name}</h1>
                <p>Welcome to the application</p>
            </div>
        </div>
    );
}}
"""
