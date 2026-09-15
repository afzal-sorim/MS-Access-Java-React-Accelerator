from .classic import ClassicTheme
from ..ui.models import UIPresentation, UIField, UIAction

class ExactLayoutTheme(ClassicTheme):
    """Theme that generates exact MS Access 1:1 layouts using absolute positioning."""

    @property
    def name(self) -> str:
        return "Exact Layout (Access replica)"

    def _build_form_fields_jsx(self, fields: list[UIField]) -> str:
        """Override to generate absolutely positioned inputs and labels."""
        parts = []
        for field in fields:
            if not field.visible:
                continue

            field_name = self._to_camel(self._sanitize_field(field.data_source or field.id))
            label = field.label or field.id
            disabled = " disabled" if (field.readonly or field.is_expression) else ""

            # MS Access coordinates are in Twips. 1440 twips = 1 inch. Screen is typically 96 DPI, so 1 px = 15 twips.
            def to_px(twips: int) -> str:
                if twips is None:
                    return "auto"
                return f"{twips // 15}px"

            if field.field_type.value == "label":
                label_style = f"{{{{ position: 'absolute', left: '{to_px(field.left)}', top: '{to_px(field.top)}', width: '{to_px(field.width)}', height: '{to_px(field.height)}', fontWeight: 'normal', color: '#333' }}}}"
                parts.append(f"""
            <div style={label_style}>
                {label}
            </div>""")
                continue

            input_style = f"{{{{ position: 'absolute', left: '{to_px(field.left)}', top: '{to_px(field.top)}', width: '{to_px(field.width)}', height: '{to_px(field.height)}', backgroundColor: '{'#f8f9fa' if field.is_expression else '#fff'}', border: '1px solid #ccc', padding: '2px 4px', fontSize: '12px' }}}}"

            # If the label has layout, render it independently
            label_jsx = ""
            if field.label_left is not None and field.label_top is not None:
                label_style = f"{{{{ position: 'absolute', left: '{to_px(field.label_left)}', top: '{to_px(field.label_top)}', width: '{to_px(field.label_width)}', height: '{to_px(field.label_height)}', fontWeight: 'bold', fontSize: '12px' }}}}"
                label_jsx = f"""
            <label htmlFor="{field_name}" style={label_style}>
                {label}
            </label>"""

            if field.is_expression:
                expression_val = str(field.default_value or field.data_source or "#Name?").replace('"', '&quot;')
                value_binding = f'"{expression_val}"'
            else:
                value_binding = f"formData.{field_name} || ''"

            if field.field_type.value == "checkbox":
                input_jsx = f"""
            <input
                type="checkbox"
                id="{field_name}"
                name="{field_name}"
                checked={{formData.{field_name} || false}}
                onChange={{handleChange}}{disabled}
                style={input_style}
            />"""
            elif field.field_type.value == "select":
                input_jsx = f"""
            <select
                id="{field_name}"
                name="{field_name}"
                value={{{value_binding}}}
                onChange={{handleChange}}{disabled}
                style={input_style}
            >
                <option value="">Select...</option>
            </select>"""
            elif field.field_type.value == "textarea":
                input_jsx = f"""
            <textarea
                id="{field_name}"
                name="{field_name}"
                value={{{value_binding}}}
                onChange={{handleChange}}{disabled}
                style={input_style}
            />"""
            else:
                input_type = self._field_type_to_input(field)
                input_jsx = f"""
            <input
                type="{input_type}"
                id="{field_name}"
                name="{field_name}"
                value={{{value_binding}}}
                onChange={{handleChange}}{disabled}
                style={input_style}
            />"""

            parts.append(label_jsx)
            parts.append(input_jsx)

        return "".join(parts)

    def render_dashboard_page(self, presentation: UIPresentation) -> str:
        """Override dashboard render to absolutely position buttons as well."""
        page_name = self._to_pascal(presentation.screen_id.replace("frm", ""))
        
        def to_px(twips: int) -> str:
            return f"{twips // 15}px" if twips is not None else "auto"
            
        button_elements = []
        for action in presentation.actions:
            handler = self._to_camel(action.id)
            nav_route = self._resolve_action_route(action)
            click_handler = f"navigate('{nav_route}')" if nav_route else f"console.warn('No route mapped for: {handler}')"
            
            btn_style = f"{{{{ position: 'absolute', left: '{to_px(action.left)}', top: '{to_px(action.top)}', width: '{to_px(action.width)}', height: '{to_px(action.height)}' }}}}"
            
            button_elements.append(f"""
            <button
                type="button"
                className="btn"
                onClick={{() => {click_handler}}}
                style={btn_style}
            >
                {action.label}
            </button>""")

        form_fields_jsx = self._build_form_fields_jsx(presentation.fields)
        buttons_jsx = "".join(button_elements) if button_elements else ""

        needs_navigate = any(self._resolve_action_route(a) for a in presentation.actions)
        navigate_import = "import { useNavigate } from 'react-router-dom';\n" if needs_navigate else ""
        navigate_hook = "    const navigate = useNavigate();\n" if needs_navigate else ""

        max_height = 800
        for f in presentation.fields:
            if f.top is not None:
                max_height = max(max_height, (f.top + (f.height or 0)) // 15 + 50)
        for a in presentation.actions:
            if a.top is not None:
                max_height = max(max_height, (a.top + (a.height or 0)) // 15 + 50)

        container_style = f"{{ position: 'relative', width: '100%', height: '{max_height}px', border: '1px solid #ccc', backgroundColor: '#f0f0f0' }}"
        
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

    const handleSubmit = (e) => {{
        e.preventDefault();
        console.log('Submit', formData);
    }};

    return (
        <div className="{page_name.lower()}-dashboard" style={{{{ width: '100%', height: '100%', padding: '20px' }}}}>
            <h1>{presentation.screen_name}</h1>
            <form onSubmit={{handleSubmit}}>
                <div className="exact-layout-container" style={{{container_style}}}>
                    {form_fields_jsx}
                    {buttons_jsx}
                </div>
            </form>
        </div>
    );
}}
"""

    def render_form_page(self, presentation: UIPresentation, endpoint: str, api_name: str, helper_imports: str) -> str:
        """Override form render to absolutely position default form buttons (Save/Cancel)."""
        page_name = self._to_pascal(presentation.screen_id.replace("frm", ""))
        form_fields_jsx = self._build_form_fields_jsx(presentation.fields)
        
        max_height = 800
        for f in presentation.fields:
            if f.top is not None:
                max_height = max(max_height, (f.top + (f.height or 0)) // 15 + 100)

        container_style = f"{{ position: 'relative', width: '100%', height: '{max_height}px', border: '1px solid #ccc', backgroundColor: '#f0f0f0' }}"
        btn_submit_style = "{ position: 'absolute', bottom: '20px', right: '120px', width: '80px', height: '35px' }"
        btn_cancel_style = "{ position: 'absolute', bottom: '20px', right: '20px', width: '80px', height: '35px' }"

        return f"""import React, {{ useState, useEffect }} from 'react';
import {{ useNavigate, useParams }} from 'react-router-dom';
{helper_imports}

export default function {page_name}Form() {{
    const navigate = useNavigate();
    const {{ id }} = useParams();
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
        <div className="{page_name.lower()}-form" style={{{{ padding: '20px' }}}}>
            <h1>{{isEdit ? 'Edit' : 'Create'}} {presentation.screen_name}</h1>
            {{error && <div className="error">{{error}}</div>}}
            <form onSubmit={{handleSubmit}}>
                <div className="exact-layout-container" style={{{container_style}}}>
                    {form_fields_jsx}
                    
                    {{/* Fixed absolute position for default buttons since they aren't UIActions with Access layout */}}
                    <button type="submit" disabled={{loading}} className="btn" style={{{btn_submit_style}}}>
                        {{isEdit ? 'Update' : 'Create'}}
                    </button>
                    <button type="button" onClick={{() => navigate('/{endpoint}')}} className="btn btn-secondary" style={{{btn_cancel_style}}}>
                        Cancel
                    </button>
                </div>
            </form>
        </div>
    );
}}
"""
