"""Classic Enterprise Theme — clean, professional design with top navigation.

This theme reproduces the existing ReactGenerator output (the "apple" design).
It serves as the zero-regression baseline and deterministic fallback.
"""
from __future__ import annotations

from .base import Theme
from ..ui.models import UIPresentation, UIField, InfoLevel


class ClassicTheme(Theme):
    """Classic enterprise design — top navbar, traditional tables, blue/gray palette."""

    @property
    def name(self) -> str:
        return "Classic Enterprise"

    @property
    def key(self) -> str:
        return "classic"

    # ──────────────────────────────────── CSS

    def get_css(self, app_name: str, presentations: list[UIPresentation]) -> str:
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

.navbar a:hover { color: var(--color-primary); }

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

.info-value { flex: 1; color: var(--color-text); }

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

.form-group input, .form-group select, .form-group textarea {
    width: 100%;
    padding: 0.75rem;
    border: 1px solid var(--color-border);
    border-radius: var(--radius-md);
    background: white;
    transition: border-color 0.2s;
}

.form-group input:focus, .form-group select:focus, .form-group textarea:focus {
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

.btn-danger {
    background-color: #ef4444;
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

.section-card {
    background: var(--color-white);
    border-radius: var(--radius-md);
    padding: 1.5rem;
    margin-bottom: 1.5rem;
    box-shadow: var(--shadow-sm);
}

.section-card h2 {
    font-size: 1.1rem;
    margin-bottom: 1rem;
    color: var(--color-text);
}

.two-column {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 1rem;
}

@media (max-width: 768px) {
    .two-column { grid-template-columns: 1fr; }
}

.loading { text-align: center; padding: 3rem; color: var(--color-text-muted); }
.error { color: #ef4444; padding: 1rem; background: #fef2f2; border-radius: var(--radius-md); margin: 1rem 0; }
.empty { text-align: center; color: var(--color-text-muted); padding: 2rem; }

@keyframes fadeIn {
    from { opacity: 0; transform: translateY(10px); }
    to { opacity: 1; transform: translateY(0); }
}
"""
        # Dynamic per-page styles
        for p in presentations:
            name = self._to_pascal(p.screen_id.replace("frm", ""))
            cls = name.lower()
            hue = sum(ord(c) for c in name) % 360
            css += f"""
/* {name} */
.{cls}-page, .{cls}-form {{
    --form-accent: hsl({hue}, 65%, 40%);
    animation: fadeIn 0.4s ease-out;
    background: var(--color-white);
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

.{cls}-page .btn, .{cls}-form button[type="submit"] {{ background-color: var(--form-accent); }}
.{cls}-page .data-table th {{ border-bottom: 2px solid var(--form-accent); }}
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
            <h1>{presentation.screen_name}</h1>
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
                            {body_tds}
                        </tr>
                    ))}}
                </tbody>
            </table>
            <Link to="/{endpoint}/new" className="btn">Add New</Link>
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
            <h1>{{isEdit ? 'Edit' : 'Create'}} {presentation.screen_name}</h1>
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
    );
}}
"""

    def render_dashboard_page(self, presentation):
        page_name = self._to_pascal(presentation.screen_id.replace("frm", ""))
        button_elements = []
        for action in presentation.actions:
            handler = self._to_camel(action.id)
            nav_route = self._resolve_action_route(action)
            if nav_route:
                click_handler = f"navigate('{nav_route}')"
            else:
                click_handler = f"console.warn('No route mapped for: {handler}')"
            button_elements.append(f"""
            <button
                className="btn"
                onClick={{() => {click_handler}}}
            >
                {action.label}
            </button>""")

        # Render actual form input elements instead of read-only spans
        form_fields_jsx = self._build_form_fields_jsx(presentation.fields)

        buttons_jsx = "\n".join(button_elements) if button_elements else ""

        needs_navigate = any(self._resolve_action_route(a) for a in presentation.actions)
        navigate_import = "import { useNavigate } from 'react-router-dom';\n" if needs_navigate else ""
        navigate_hook = "    const navigate = useNavigate();\n" if needs_navigate else ""

        return f"""import React, {{ useState }} from 'react';
{navigate_import}
export default function {page_name}Page() {{
{navigate_hook}    const [formData, setFormData] = useState({{}});

    const handleChange = (e) => {{
        const {{ name, value, type, checked }} = e.target;
        setFormData(prev => ({{
            ...prev,
            [name]: type === 'checkbox' ? checked : value
        }}));
    }};

    return (
        <div className="{page_name.lower()}-page">
            <h1>{presentation.screen_name}</h1>
            <p className="form-description">This page corresponds to Access form: {presentation.screen_id}</p>
{form_fields_jsx}
            <div className="button-group">
{buttons_jsx}
            </div>
        </div>
    );
}}
"""

    def render_detail_page(self, presentation, endpoint, api_name, helper_imports):
        # For classic theme, detail page is same as form page but read-heavy
        return self.render_form_page(presentation, endpoint, api_name, helper_imports)

    def render_master_detail_page(self, presentation, endpoint, api_name, helper_imports):
        page_name = self._to_pascal(presentation.screen_id.replace("frm", ""))
        primary_fields = [f for f in presentation.fields if f.info_level == InfoLevel.PRIMARY]
        form_fields = self._build_form_fields_jsx(primary_fields)

        subform_tables = []
        for sf in presentation.subforms:
            sf_name = self._to_pascal(sf.name)
            subform_tables.append(f"""
            <div className="section-card">
                <h2>{sf.name}</h2>
                <p className="form-description">Related data from: {sf.record_source or sf.name}</p>
                {{/* TODO: Load and display related {sf_name} data */}}
            </div>""")

        subforms_jsx = "\n".join(subform_tables)

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
            async function fetchData() {{
                try {{
                    const data = await get{api_name}ById(id);
                    setFormData(data);
                    setLoading(false);
                }} catch (err) {{
                    setError(err.message);
                    setLoading(false);
                }}
            }}
            fetchData();
        }} else {{
            setLoading(false);
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
        try {{
            if (isEdit) {{
                await update{api_name}(id, formData);
            }} else {{
                await create{api_name}(formData);
            }}
            navigate('/{endpoint}');
        }} catch (err) {{
            setError(err.message);
        }}
    }};

    if (loading) return <div className="loading">Loading...</div>;
    if (error) return <div className="error">{{error}}</div>;

    return (
        <div className="{page_name.lower()}-page">
            <h1>{presentation.screen_name}</h1>
            <div className="section-card">
                <form onSubmit={{handleSubmit}}>
                    {form_fields}
                    <div className="form-actions">
                        <button type="submit" className="btn">Save</button>
                        <button type="button" onClick={{() => navigate('/{endpoint}')}} className="btn btn-secondary">Cancel</button>
                    </div>
                </form>
            </div>
{subforms_jsx}
        </div>
    );
}}
"""

    def render_app_shell(self, app_name, pages, report_import, report_route, report_link):
        imports = "\n".join(p["import"] for p in pages)
        routes = "\n".join(p["routes"] for p in pages)
        nav_links = "".join(p.get("nav_link", "") for p in pages)

        return f"""import React from 'react';
import {{ BrowserRouter as Router, Routes, Route, Link }} from 'react-router-dom';
{report_import}{imports}

export default function App() {{
    return (
        <Router>
            <div className="app">
                <nav className="navbar">
                    <Link to="/">Home</Link>
                    {nav_links}
                    {report_link}
                </nav>
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
        <div className="home">
            <h1>{app_name}</h1>
            <p>Welcome to the application.</p>
        </div>
    );
}}
"""
