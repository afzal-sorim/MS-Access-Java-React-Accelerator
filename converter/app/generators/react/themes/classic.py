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

    def get_css(self, app_name: str, presentations: list[UIPresentation]) -> dict[str, str]:
        css_files = {
            "index.css": """@import './styles/tokens.css';
@import './styles/reset.css';

/* demo_version aesthetic overrides */
.app { background: #f1f5f9; min-height: 100vh; font-family: inherit; color: #20314e; }
.navbar { display: flex; gap: 4px; padding: 10px 24px; background: #fff; border-bottom: 1px solid #e2e8f0; overflow-x: auto; }
.navbar a { color: #4d5c75; text-decoration: none; padding: 8px 12px; border-radius: 6px; font-weight: 600; white-space: nowrap; }
.navbar a:hover { background: #eaf1fb; color: #1762b5; }
.content { padding: 24px; }
"""
        }
        
        # Dynamic per-page styles (CSS Modules)
        for p in presentations:
            name = self._to_pascal(p.screen_id.replace("frm", ""))
            hue = sum(ord(c) for c in name) % 360
            css_files[f"pages/{name}Page.module.css"] = f"""/* {name} CSS Module */
.pageContainer {{
    --form-accent: hsl({hue}, 65%, 40%);
    animation: fadeIn 0.4s ease-out;
    background: #fff;
    border: 1px solid #e2e8f0;
    border-radius: 8px;
    padding: 16px;
    margin-bottom: 2rem;
}}
.pageContainer:hover {{
    border-color: #88a9d6;
    box-shadow: 0 4px 12px rgba(11,59,130,.10);
}}

.pageContainer :global(h1) {{
    color: #44536c;
    font-size: 18px;
    margin-bottom: 0.5rem;
    font-weight: 800;
}}

.pageContainer :global(.btn), .pageContainer :global(button[type="submit"]) {{
    background-color: #1762b5;
    border-radius: 5px;
    padding: 9px 14px;
    font-weight: 700;
    color: #fff;
    border: none;
    cursor: pointer;
}}
.pageContainer :global(.btn):hover {{
    background-color: #124d8f;
}}
"""
        return css_files

    # ──────────────────────────────────── Pages

    def render_list_page(self, presentation, endpoint, api_name, helper_imports):
        page_name = self._to_pascal(presentation.screen_id.replace("frm", ""))
        var_name = self._to_camel(page_name)
        
        return f"""import React, {{ useState }} from 'react';
import {{ useNavigate }} from 'react-router-dom';
import {{ getAll }} from '../services/{api_name}Service';
import {{ useApi }} from '../hooks/useApi';
import PageHeader from '../components/common/PageHeader';
import DataTable from '../components/common/DataTable';
import LoadingSpinner from '../components/common/LoadingSpinner';
import ErrorMessage from '../components/common/ErrorMessage';
import EmptyState from '../components/common/EmptyState';
import Button from '../components/common/Button';

import styles from './{page_name}Page.module.css';

export default function {page_name}Page() {{
    const navigate = useNavigate();
    const {{ data: {var_name}, loading, error }} = useApi(getAll);

    if (loading) return <LoadingSpinner />;
    if (error) return <ErrorMessage message={{error}} />;

    const columns = [
        {{ key: 'id', label: 'ID' }},
        // TODO: Map other columns
    ];

    return (
        <div className="{page_name.lower()}-page">
            <PageHeader title="{presentation.screen_name}" />
            
            {{!{var_name} || {var_name}.length === 0 ? (
                <EmptyState message="No {page_name.lower()}s found." />
            ) : (
                <DataTable 
                    data={{{var_name}}} 
                    columns={{columns}} 
                    onRowClick={{(row) => navigate(`/{endpoint}/${{row.id}}`)}}
                />
            )}}
            
            <Button onClick={{() => navigate(`/{endpoint}/new`)}}>Add New</Button>
        </div>
    );
}}
"""

    def render_form_page(self, presentation, endpoint, api_name, helper_imports):
        page_name = self._to_pascal(presentation.screen_id.replace("frm", ""))
        form_fields_jsx = self._build_form_fields_jsx(presentation.fields)

        return f"""import React, {{ useState, useEffect }} from 'react';
import {{ useNavigate, useParams }} from 'react-router-dom';
import {{ getById, create, update }} from '../services/{api_name}Service';
import PageHeader from '../components/common/PageHeader';
import FormField from '../components/common/FormField';
import Button from '../components/common/Button';
import LoadingSpinner from '../components/common/LoadingSpinner';
import ErrorMessage from '../components/common/ErrorMessage';

import styles from './{page_name}Page.module.css';

export default function {page_name}FormPage() {{
    const {{ id }} = useParams();
    const navigate = useNavigate();
    const isEdit = Boolean(id);
    const [formData, setFormData] = useState({{}});
    const [loading, setLoading] = useState(isEdit);
    const [error, setError] = useState(null);

    useEffect(() => {{
        if (isEdit) {{
            getById(id)
                .then(data => setFormData(data))
                .catch(err => setError(err.message))
                .finally(() => setLoading(false));
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
            if (isEdit) await update(id, formData);
            else await create(formData);
            navigate('/{endpoint}');
        }} catch (err) {{
            setError(err.message);
        }}
    }};

    if (loading) return <LoadingSpinner />;
    if (error) return <ErrorMessage message={{error}} />;

    return (
        <div className="{page_name.lower()}-form">
            <PageHeader title={{isEdit ? \'Edit {presentation.screen_name}\' : \'Add {presentation.screen_name}\'}} />
            <form onSubmit={{handleSubmit}}>
{form_fields_jsx}
                <div className="form-actions">
                    <Button type="submit">Save</Button>
                    <Button variant="secondary" onClick={{() => navigate(`/{endpoint}`)}}>Cancel</Button>
                </div>
            </form>
        </div>
    );
}}
"""

    def render_dashboard_page(self, presentation, endpoint, api_name, helper_imports):
        page_name = self._to_pascal(presentation.screen_id.replace("frm", ""))
        button_elements = []
        for action in presentation.actions:
            route = self._resolve_action_route(action)
            on_click = f"onClick={{() => navigate('{route}')}}" if route else ""
            button_elements.append(f"""
                <Button {on_click}>
                    {action.label or action.id}
                </Button>""")
        buttons_jsx = "\n".join(button_elements)
        form_fields_jsx = self._build_form_fields_jsx(presentation.fields)

        return f"""import React from 'react';
import {{ useNavigate }} from 'react-router-dom';
import PageHeader from '../components/common/PageHeader';
import Button from '../components/common/Button';
import FormField from '../components/common/FormField';

import styles from './{page_name}Page.module.css';

export default function {page_name}Page() {{
    const navigate = useNavigate();
    return (
        <div className="{page_name.lower()}-page">
            <PageHeader title="{presentation.screen_name}" />
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
        return self.render_list_page(presentation, endpoint, api_name, helper_imports)

    def render_master_detail_page(self, presentation, endpoint, api_name, helper_imports):
        return self.render_list_page(presentation, endpoint, api_name, helper_imports)

    def render_app_shell(self, app_name, pages, report_import, report_route, report_link) -> dict[str, str]:
        imports = "\n".join(p["import"] for p in pages)
        routes = "\n".join(p["routes"] for p in pages)
        nav_links = "".join(p.get("nav_link", "") for p in pages)

        app_jsx = f"""import React, {{ useState }} from 'react';
import {{ BrowserRouter as Router }} from 'react-router-dom';
import AppLayout from './components/layout/AppLayout';
import AppRouter from './routes/AppRouter';
import ErrorBoundary from './components/common/ErrorBoundary';

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

        app_router_jsx = f"""import React, {{ useState }} from 'react';
import {{ Routes, Route }} from 'react-router-dom';
{report_import}{imports}

export default function AppRouter() {{
    return (
        <Routes>
            <Route path="/" element={{<HomePage />}} />
{report_route}{routes}
        </Routes>
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

        app_layout_jsx = f"""import React, {{ useState }} from 'react';
import {{ Link }} from 'react-router-dom';

export default function AppLayout({{ children }}) {{
    return (
        <div className="app">
            <nav className="navbar">
                <Link to="/">Home</Link>
                {nav_links}
                {report_link}
            </nav>
            <main className="content">
                {{children}}
            </main>
        </div>
    );
}}
"""

        return {
            "App.jsx": app_jsx,
            "routes/AppRouter.jsx": app_router_jsx,
            "components/layout/AppLayout.jsx": app_layout_jsx,
        }