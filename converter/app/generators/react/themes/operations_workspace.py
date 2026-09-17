"""Access-to-web operations workspace theme.

This theme deliberately translates the *information architecture* of dense
Access screens rather than reproducing their pixels: menu buttons become
grouped workspace actions, continuous forms become a record rail plus a
sectioned detail panel, and report selectors remain data-driven.
"""
from __future__ import annotations

from .classic import ClassicTheme


class OperationsWorkspaceTheme(ClassicTheme):
    @property
    def name(self) -> str:
        return "Operations Workspace"

    @property
    def key(self) -> str:
        return "operations_workspace"

    def get_css(self, app_name, presentations) -> str:
        return """@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap');
:root { --ow-blue:#0b3b82; --ow-blue-2:#164f9b; --ow-ink:#172033; --ow-muted:#62708a; --ow-bg:#f3f5f8; --ow-card:#fff; --ow-line:#e3e8f0; --ow-mint:#dff6ec; --ow-amber:#fff0d4; --ow-danger:#fff0ef; }
* { box-sizing:border-box; } body { margin:0; font-family:Inter,Arial,sans-serif; color:var(--ow-ink); background:var(--ow-bg); font-size:14px; }
.app { min-height:100vh; } .ow-header { height:58px; display:flex; align-items:center; justify-content:space-between; padding:0 24px; background:#fff; border-bottom:1px solid var(--ow-line); }
.ow-brand { color:var(--ow-blue); font-weight:800; font-size:18px; letter-spacing:-.5px; } .ow-user { color:var(--ow-muted); font-size:12px; }
.ow-nav { display:flex; gap:4px; padding:10px 24px; background:#fff; border-bottom:1px solid var(--ow-line); overflow-x:auto; } .ow-nav a { color:#4d5c75; text-decoration:none; padding:8px 12px; border-radius:6px; font-weight:600; white-space:nowrap; } .ow-nav a:hover { background:#eaf1fb; color:var(--ow-blue); }
.content { max-width:none; padding:16px 20px; margin:0; } .page-header { display:flex; align-items:baseline; justify-content:space-between; margin:0 0 12px; } .page-header h1 { font-size:18px; margin:0; color:#20314e; } .page-header p { color:var(--ow-muted); margin:0; font-size:12px; }
.card,.section-card { background:var(--ow-card); border:1px solid var(--ow-line); border-radius:8px; padding:16px; box-shadow:0 1px 2px rgba(24,39,75,.04); } .card-grid { display:grid; grid-template-columns:repeat(auto-fit,minmax(250px,1fr)); gap:12px; }
.ow-action-card { border:1px solid var(--ow-line); border-radius:7px; padding:13px; text-align:left; background:#fff; color:var(--ow-ink); cursor:pointer; min-height:90px; } .ow-action-card:hover { border-color:#88a9d6; box-shadow:0 4px 12px rgba(11,59,130,.10); } .ow-action-card strong { display:block; color:var(--ow-blue); margin-bottom:6px; } .ow-action-card span { color:var(--ow-muted); font-size:12px; }
.ow-workspace { display:grid; grid-template-columns:260px minmax(0,1fr); gap:12px; min-height:600px; } .ow-record-rail { background:#fff; border:1px solid var(--ow-line); border-radius:8px; overflow:auto; } .ow-rail-title { padding:13px; color:#42506a; font-size:12px; font-weight:800; border-bottom:1px solid var(--ow-line); text-transform:uppercase; letter-spacing:.04em; } .ow-record { display:block; width:100%; border:0; border-bottom:1px solid #eef1f5; background:#fff; padding:12px; text-align:left; cursor:pointer; color:var(--ow-ink); } .ow-record:hover,.ow-record.active { background:#f0f5fd; border-left:3px solid var(--ow-blue); padding-left:9px; } .ow-record strong { display:block; font-size:12px; } .ow-record span { color:var(--ow-muted); font-size:11px; }
.ow-detail { background:#fff; border:1px solid var(--ow-line); border-radius:8px; padding:18px; overflow:auto; } .ow-detail-header { display:flex; justify-content:space-between; align-items:center; border-bottom:1px solid var(--ow-line); padding-bottom:12px; margin-bottom:14px; } .ow-detail-header h2 { font-size:16px; margin:0; color:#20314e; } .ow-detail-grid { display:grid; grid-template-columns:repeat(2,minmax(0,1fr)); gap:0 24px; } .info-field { display:flex; flex-direction:column; padding:10px 0; border-bottom:1px solid #eef1f5; } .info-label { color:var(--ow-muted); font-size:11px; font-weight:700; text-transform:uppercase; } .info-value { margin-top:4px; font-weight:600; }
.form-group { margin-bottom:14px; } .form-group label { display:block; color:#44536c; font-size:12px; font-weight:700; margin-bottom:6px; } .form-group input,.form-group select,.form-group textarea { width:100%; border:1px solid #ccd5e3; border-radius:5px; padding:9px; font:inherit; } .form-group input:focus,.form-group select:focus,.form-group textarea:focus { outline:2px solid #c9dcf8; border-color:var(--ow-blue); }.two-column { display:grid; grid-template-columns:1fr 1fr; gap:0 18px; }
.form-actions { border-top:1px solid var(--ow-line); padding-top:14px; margin-top:16px; display:flex; gap:8px; } .btn { display:inline-block; border:0; border-radius:5px; background:var(--ow-blue); color:#fff; padding:9px 14px; font:inherit; font-weight:700; cursor:pointer; text-decoration:none; } .btn:hover { background:var(--ow-blue-2); } .btn-secondary { background:#fff; color:#40506b; border:1px solid #ccd5e3; }
.data-table { width:100%; border-collapse:collapse; background:#fff; } .data-table th { background:var(--ow-blue); color:#fff; text-align:left; padding:10px; font-size:11px; text-transform:uppercase; } .data-table td { border-bottom:1px solid var(--ow-line); padding:10px; } .data-table tr:hover td { background:#f7faff; } .data-table a { color:var(--ow-blue); font-weight:700; text-decoration:none; }.loading,.empty { padding:32px; color:var(--ow-muted); text-align:center; }.error { background:var(--ow-danger); color:#b42318; padding:12px; border-radius:6px; }
.reports-page { display:grid; grid-template-columns:240px minmax(0,1fr); gap:12px; }.reports-page > h1 { grid-column:1/-1; font-size:18px; }.reports-page .form-group { background:#fff; border:1px solid var(--ow-line); border-radius:8px; padding:12px; height:max-content; }.reports-page > div:not(.form-group):not(.error) { background:#fff; border:1px solid var(--ow-line); border-radius:8px; padding:16px; } @media(max-width:760px){.ow-workspace,.reports-page{grid-template-columns:1fr}.ow-record-rail{max-height:240px}.ow-detail-grid,.two-column{grid-template-columns:1fr}.ow-header{padding:0 12px}.ow-nav{padding:8px 12px}.content{padding:12px}}
"""

    def render_dashboard_page(self, presentation):
        page_name = self._to_pascal(presentation.screen_id.replace("frm", ""))
        cards = []
        for action in presentation.actions:
            route = self._resolve_action_route(action)
            on_click = f"onClick={{() => navigate('{route}')}}" if route else ""
            cards.append(f'''                <button className="ow-action-card" {on_click}><strong>{action.label or action.id}</strong><span>Open workspace</span></button>''')
        cards_jsx = "\n".join(cards) or '                <div className="card">No actions were identified for this Access menu.</div>'
        return f'''import React from 'react';
import {{ useNavigate }} from 'react-router-dom';
export default function {page_name}Page() {{
    const navigate = useNavigate();
    return <div className="{page_name.lower()}-page"><div className="page-header"><div><h1>{presentation.screen_name}</h1><p>Operations workspace</p></div></div><section className="card"><div className="card-grid">\n{cards_jsx}\n</div></section></div>;
}}'''

    def render_list_page(self, presentation, endpoint, api_name, helper_imports):
        page_name = self._to_pascal(presentation.screen_id.replace("frm", ""))
        var_name = self._to_camel(page_name)
        fields = self._build_table_columns(presentation.fields, max_cols=8)
        primary = fields[:3]
        rail_title = primary[0].label if primary else "Record"
        rail_value = self._to_camel(self._sanitize_field(primary[0].data_source or primary[0].id)) if primary else "id"
        detail = "\n".join(f'''<div className="info-field"><span className="info-label">{field.label}</span><span className="info-value">{{selected?.{self._to_camel(self._sanitize_field(field.data_source or field.id))} ?? '—'}}</span></div>''' for field in fields)
        return f'''import React, {{ useEffect, useState }} from 'react';
import {{ Link }} from 'react-router-dom';
import {{ get{api_name} }} from '../services/api';
export default function {page_name}Page() {{
 const [{var_name}, set{page_name}] = useState([]); const [selected, setSelected] = useState(null); const [loading, setLoading] = useState(true); const [error, setError] = useState(null);
 useEffect(() => {{ get{api_name}().then(rows => {{ set{page_name}(rows); setSelected(rows[0] || null); }}).catch(err => setError(err.message)).finally(() => setLoading(false)); }}, []);
 if (loading) return <div className="loading">Loading records…</div>; if (error) return <div className="error">{{error}}</div>;
 return <div className="{page_name.lower()}-page"><div className="page-header"><div><h1>{presentation.screen_name}</h1><p>{{{var_name}.length}} records</p></div><Link to="/{endpoint}/new" className="btn">Add record</Link></div><div className="ow-workspace"><aside className="ow-record-rail"><div className="ow-rail-title">{presentation.screen_name}</div>{{{var_name}.map((item, index) => <button key={{item.id ?? index}} className={{`ow-record ${{selected === item ? 'active' : ''}}`}} onClick={{() => setSelected(item)}}><strong>{{item.{rail_value} ?? '{rail_title}'}}</strong><span>Record {{index + 1}}</span></button>)}}</aside><section className="ow-detail"><div className="ow-detail-header"><h2>{{selected?.{rail_value} ?? 'Select a record'}}</h2>{{selected && <Link className="btn btn-secondary" to={{`/{endpoint}/${{selected.id}}`}}>Edit</Link>}}</div><div className="ow-detail-grid">{detail}</div></section></div></div>;
}}'''

    def render_app_shell(self, app_name, pages, report_import, report_route, report_link):
        imports = "\n".join(p["import"] for p in pages); routes = "\n".join(p["routes"] for p in pages)
        links = "\n".join(f'                    <Link to="{p["nav_path"]}">{p["nav_link_text"]}</Link>' for p in pages if "nav_link_text" in p)
        report_nav = '                    <Link to="/reports">Reports</Link>' if report_link else ""
        return f'''import React from 'react';
import {{ BrowserRouter as Router, Routes, Route, Link }} from 'react-router-dom';
{report_import}{imports}
export default function App() {{ return <Router><div className="app"><header className="ow-header"><div className="ow-brand">{app_name}</div><div className="ow-user">Operations workspace</div></header><nav className="ow-nav"><Link to="/">Home</Link>\n{links}\n{report_nav}</nav><main className="content"><Routes><Route path="/" element={{<HomePage />}} />\n{report_route}{routes}</Routes></main></div></Router>; }}
function HomePage() {{ return <div><div className="page-header"><div><h1>Welcome back</h1><p>Choose a workspace to continue.</p></div></div><div className="card"><strong>Application ready</strong><p>Forms and reports are organized as modern operations workspaces.</p></div></div>; }}'''
