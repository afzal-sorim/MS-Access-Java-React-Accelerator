import os
import re

THEMES_DIR = r"c:\Users\Afzal\ZCodeProject\converter\app\generators\react\themes"

def update_theme_file(filepath):
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()

    # 1. Update get_css to return dict
    css_pattern = re.compile(r'    def get_css\(self, app_name[^:]*:\s*.*?return css_?files?|    def get_css\(self, app_name[^:]*:\s*.*?(?=\n    # ─+ Pages|\n    def render_list_page)', re.DOTALL)
    
    new_get_css = '''    def get_css(self, app_name: str, presentations: list) -> dict[str, str]:
        css_files = {
            "index.css": "@import './styles/tokens.css';\\n@import './styles/reset.css';\\n"
        }
        for p in presentations:
            name = self._to_pascal(p.screen_id.replace("frm", ""))
            hue = sum(ord(c) for c in name) % 360
            css_files[f"pages/{name}Page.module.css"] = f"""/* {name} CSS Module */
.pageContainer {{
    animation: fadeIn 0.3s ease-out;
}}
"""
        return css_files
'''
    if 'def get_css' in content:
        content = css_pattern.sub(new_get_css, content)

    # 2. Update render_app_shell to return dict
    app_shell_pattern = re.compile(r'    def render_app_shell\(self.*?(?=\n    def |\Z)', re.DOTALL)
    
    new_app_shell = '''    def render_app_shell(self, app_name, pages, report_import, report_route, report_link) -> dict[str, str]:
        imports = "\\n".join(p["import"] for p in pages)
        routes = "\\n".join(p["routes"] for p in pages)
        nav_links = "".join(p.get("nav_link", "") for p in pages)
        if not nav_links and "nav_link_text" in pages[0]:
            nav_links = "\\n".join(f\'                        <Link to="{p["nav_path"]}">{p["nav_link_text"]}</Link>\' for p in pages if "nav_link_text" in p)

        app_jsx = f"""import React from 'react';
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

        app_router_jsx = f"""import React from 'react';
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

        app_layout_jsx = f"""import React from 'react';
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
'''
    if 'def render_app_shell' in content:
        content = app_shell_pattern.sub(new_app_shell, content)
        
    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(content)

for filename in ['material.py', 'modern_dashboard.py', 'operations_workspace.py', 'exact.py']:
    update_theme_file(os.path.join(THEMES_DIR, filename))

print("Updated themes successfully.")
