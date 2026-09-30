"""Modern Dashboard Theme — dark sidebar, card-based layouts, gradient accents.

Features:
- Collapsible dark sidebar navigation
- Card-based data display with stat widgets
- Gradient header accents
- Dark mode color scheme with vibrant accent colors
- Floating card panels for forms
"""
from __future__ import annotations

from .base import Theme
from ..ui.models import UIPresentation, InfoLevel


class ModernDashboardTheme(Theme):

    @property
    def name(self) -> str:
        return "Modern Dashboard"

    @property
    def key(self) -> str:
        return "modern_dashboard"

    def get_css(self, app_name: str, presentations: list[UIPresentation]) -> str:
        css = """:root {
    --md-bg-dark: #0f172a;
    --md-bg-surface: #1e293b;
    --md-bg-card: #1e293b;
    --md-bg-hover: #334155;
    --md-text-primary: #f1f5f9;
    --md-text-secondary: #94a3b8;
    --md-text-muted: #64748b;
    --md-accent: #6366f1;
    --md-accent-light: #818cf8;
    --md-accent-gradient: linear-gradient(135deg, #6366f1, #8b5cf6);
    --md-success: #22c55e;
    --md-warning: #f59e0b;
    --md-danger: #ef4444;
    --md-border: #334155;
    --md-radius: 12px;
    --md-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.3);
    --md-shadow-lg: 0 10px 25px -3px rgba(0, 0, 0, 0.4);
    --md-sidebar-width: 260px;
}

@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap');

* { box-sizing: border-box; margin: 0; padding: 0; }
body {
    font-family: 'Inter', system-ui, sans-serif;
    background: var(--md-bg-dark);
    color: var(--md-text-primary);
    line-height: 1.6;
}

.app {
    display: flex;
    min-height: 100vh;
}

/* ─── Sidebar Navigation ─── */
.sidebar {
    width: var(--md-sidebar-width);
    background: var(--md-bg-surface);
    border-right: 1px solid var(--md-border);
    display: flex;
    flex-direction: column;
    position: fixed;
    height: 100vh;
    overflow-y: auto;
    z-index: 100;
}

.sidebar-header {
    padding: 1.5rem;
    border-bottom: 1px solid var(--md-border);
}

.sidebar-header h1 {
    font-size: 1.25rem;
    font-weight: 800;
    background: var(--md-accent-gradient);
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
    background-clip: text;
}

.sidebar-nav {
    padding: 1rem 0;
    flex: 1;
}

.sidebar-nav a {
    display: flex;
    align-items: center;
    padding: 0.75rem 1.5rem;
    color: var(--md-text-secondary);
    text-decoration: none;
    font-size: 0.9rem;
    font-weight: 500;
    transition: all 0.2s;
    border-left: 3px solid transparent;
}

.sidebar-nav a:hover {
    background: var(--md-bg-hover);
    color: var(--md-text-primary);
    border-left-color: var(--md-accent);
}

.sidebar-nav a.active {
    background: rgba(99, 102, 241, 0.1);
    color: var(--md-accent-light);
    border-left-color: var(--md-accent);
}

/* ─── Main Content ─── */
.content {
    margin-left: var(--md-sidebar-width);
    flex: 1;
    padding: 2rem;
    min-height: 100vh;
}

.page-header {
    margin-bottom: 2rem;
}

.page-header h1 {
    font-size: 1.75rem;
    font-weight: 800;
    color: var(--md-text-primary);
    margin-bottom: 0.25rem;
}

.page-header p {
    color: var(--md-text-secondary);
    font-size: 0.9rem;
}

/* ─── Cards ─── */
.card {
    background: var(--md-bg-card);
    border: 1px solid var(--md-border);
    border-radius: var(--md-radius);
    padding: 1.5rem;
    margin-bottom: 1.5rem;
    box-shadow: var(--md-shadow);
    transition: transform 0.2s, box-shadow 0.2s;
}

.card:hover {
    box-shadow: var(--md-shadow-lg);
}

.card h2 {
    font-size: 1rem;
    font-weight: 700;
    margin-bottom: 1rem;
    color: var(--md-text-primary);
}

.card-grid {
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
    gap: 1.5rem;
}

.stat-card {
    background: var(--md-bg-card);
    border: 1px solid var(--md-border);
    border-radius: var(--md-radius);
    padding: 1.25rem;
    text-align: center;
}

.stat-card .stat-value {
    font-size: 2rem;
    font-weight: 800;
    background: var(--md-accent-gradient);
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
    background-clip: text;
}

.stat-card .stat-label {
    font-size: 0.8rem;
    color: var(--md-text-muted);
    text-transform: uppercase;
    letter-spacing: 0.05em;
}

/* ─── Forms ─── */
.form-group { margin-bottom: 1.25rem; }
.form-group label {
    display: block;
    margin-bottom: 0.4rem;
    font-weight: 600;
    font-size: 0.85rem;
    color: var(--md-text-secondary);
    text-transform: uppercase;
    letter-spacing: 0.03em;
}

.form-group input, .form-group select, .form-group textarea {
    width: 100%;
    padding: 0.75rem 1rem;
    background: var(--md-bg-dark);
    border: 1px solid var(--md-border);
    border-radius: 8px;
    color: var(--md-text-primary);
    font-size: 0.9rem;
    transition: border-color 0.2s, box-shadow 0.2s;
}

.form-group input:focus, .form-group select:focus, .form-group textarea:focus {
    outline: none;
    border-color: var(--md-accent);
    box-shadow: 0 0 0 3px rgba(99, 102, 241, 0.15);
}

.form-actions {
    display: flex;
    gap: 0.75rem;
    margin-top: 1.5rem;
    padding-top: 1.5rem;
    border-top: 1px solid var(--md-border);
}

/* ─── Buttons ─── */
.btn {
    padding: 0.65rem 1.25rem;
    border-radius: 8px;
    background: var(--md-accent-gradient);
    color: white;
    border: none;
    cursor: pointer;
    font-weight: 600;
    font-size: 0.85rem;
    transition: all 0.2s;
    display: inline-flex;
    align-items: center;
    gap: 0.5rem;
}

.btn:hover {
    transform: translateY(-1px);
    box-shadow: 0 4px 12px rgba(99, 102, 241, 0.3);
}

.btn-secondary {
    background: var(--md-bg-hover);
    color: var(--md-text-primary);
}

.btn-secondary:hover {
    background: var(--md-border);
}

.btn-danger {
    background: var(--md-danger);
}

/* ─── Table ─── */
.data-table {
    width: 100%;
    border-collapse: collapse;
    margin: 1rem 0;
}

.data-table th, .data-table td {
    padding: 0.875rem 1rem;
    text-align: left;
    border-bottom: 1px solid var(--md-border);
}

.data-table th {
    font-weight: 600;
    font-size: 0.75rem;
    color: var(--md-text-muted);
    text-transform: uppercase;
    letter-spacing: 0.05em;
}

.data-table tr:hover td {
    background: rgba(99, 102, 241, 0.05);
}

.data-table a {
    color: var(--md-accent-light);
    text-decoration: none;
    font-weight: 500;
}

/* ─── Utilities ─── */
.two-column {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 1rem;
}

.section-card { /* alias for card */ }

.loading { text-align: center; padding: 3rem; color: var(--md-text-muted); }
.error { color: #fca5a5; padding: 1rem; background: rgba(239, 68, 68, 0.1); border: 1px solid rgba(239, 68, 68, 0.3); border-radius: 8px; margin: 1rem 0; }
.empty { text-align: center; color: var(--md-text-muted); padding: 3rem; }

.info-field {
    display: flex;
    padding: 0.75rem 0;
    border-bottom: 1px solid var(--md-border);
}

.info-label {
    width: 180px;
    font-weight: 600;
    color: var(--md-text-muted);
    font-size: 0.8rem;
    text-transform: uppercase;
}

.info-value { flex: 1; color: var(--md-text-primary); }

.button-group {
    display: flex;
    flex-wrap: wrap;
    gap: 0.75rem;
    margin-top: 1.5rem;
}

@media (max-width: 768px) {
    .sidebar { display: none; }
    .content { margin-left: 0; }
    .two-column { grid-template-columns: 1fr; }
    .card-grid { grid-template-columns: 1fr; }
}

@keyframes fadeIn {
    from { opacity: 0; transform: translateY(8px); }
    to { opacity: 1; transform: translateY(0); }
}
"""
        for p in presentations:
            name = self._to_pascal(p.screen_id.replace("frm", ""))
            cls = name.lower()
            hue = sum(ord(c) for c in name) % 360
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
        async function fetchData() {{
            try {{ set{page_name}(await get{api_name}()); }}
            catch (err) {{ setError(err.message); }}
            finally {{ setLoading(false); }}
        }}
        fetchData();
    }}, []);

    if (loading) return <div className="loading">Loading...</div>;
    if (error) return <div className="error">{{error}}</div>;

    return (
        <div className="{page_name.lower()}-page">
            <div className="page-header">
                <h1>{presentation.screen_name}</h1>
                <p>{{({var_name}.length)}} records found</p>
            </div>
            <div className="card">
                <table className="data-table">
                    <thead>
                        <tr>
                            {header_ths}
                            <th>Actions</th>
                        </tr>
                    </thead>
                    <tbody>
                        {{{var_name}.map(item => (
                            <tr key={{item.id}}>
                                {body_tds}
                                <td>
                                    <Link to={{`/{endpoint}/${{item.id}}`}}>View</Link>
                                </td>
                            </tr>
                        ))}}
                    </tbody>
                </table>
            </div>
            <Link to="/{endpoint}/new" className="btn">+ Add New</Link>
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
                        <button type="submit" disabled={{loading}} className="btn">
                            {{isEdit ? 'Update' : 'Create'}}
                        </button>
                        <button type="button" onClick={{() => navigate('/{endpoint}')}} className="btn btn-secondary">
                            Cancel
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
        button_cards = []
        for action in presentation.actions:
            handler = self._to_camel(action.id)
            # Resolve navigation target from the action
            nav_route = self._resolve_action_route(action)
            if nav_route:
                click_handler = f"navigate('{nav_route}')"
            else:
                click_handler = f"console.warn('No route mapped for: {handler}')"
            button_cards.append(f"""
                <div className="stat-card" style={{{{cursor: 'pointer'}}}} onClick={{() => {click_handler}}}>
                    <div className="stat-value">→</div>
                    <div className="stat-label">{action.label}</div>
                </div>""")

        cards_jsx = "\n".join(button_cards)

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
                <p>Dashboard overview</p>
            </div>
            <div className="card-grid">
{cards_jsx}
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
                <p style={{{{color: 'var(--md-text-muted)', fontSize: '0.85rem'}}}}>Related data from: {sf.record_source or sf.name}</p>
                {{/* TODO: Load related data */}}
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
    if (error) return <div className="error">{{error}}</div>;

    return (
        <div className="{page_name.lower()}-page">
            <div className="page-header">
                <h1>{presentation.screen_name}</h1>
            </div>
            <div className="card">
                <h2>Details</h2>
                <form onSubmit={{handleSubmit}}>
                    <div className="two-column">
                        {form_fields}
                    </div>
                    <div className="form-actions">
                        <button type="submit" className="btn">Save</button>
                        <button type="button" onClick={{() => navigate('/{endpoint}')}} className="btn btn-secondary">Cancel</button>
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
                nav_links.append(f'                    <Link to="{p["nav_path"]}">{p["nav_link_text"]}</Link>')

        nav_jsx = "\n".join(nav_links)
        report_nav = f'\n                    <Link to="/reports">Reports</Link>' if report_link else ""

        return f"""import React from 'react';
import {{ BrowserRouter as Router, Routes, Route, Link }} from 'react-router-dom';
{report_import}{imports}

export default function App() {{
    return (
        <Router>
            <div className="app">
                <aside className="sidebar">
                    <div className="sidebar-header">
                        <h1>{app_name}</h1>
                    </div>
                    <nav className="sidebar-nav">
                        <Link to="/">Dashboard</Link>
{nav_jsx}{report_nav}
                    </nav>
                </aside>
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
                <h1>Welcome</h1>
                <p>{app_name} — Dashboard</p>
            </div>
            <div className="card-grid">
                <div className="stat-card">
                    <div className="stat-value">✓</div>
                    <div className="stat-label">System Online</div>
                </div>
            </div>
        </div>
    );
}}
"""
