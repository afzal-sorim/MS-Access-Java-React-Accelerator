from .classic import ClassicTheme
from ..ui.models import UIPresentation, UIField, UIAction

class ExactLayoutTheme(ClassicTheme):
    """Theme that generates exact MS Access 1:1 layouts using absolute positioning."""

    @property
    def name(self) -> str:
        return "Exact Layout (Access replica)"

    def get_css(self, app_name: str, presentations: list[UIPresentation]) -> str:
        css = super().get_css(app_name, presentations)
        # Override the 1000px max-width from the classic theme to allow full-width exact layouts
        css += "\n/* Exact Layout Overrides */\n.content { max-width: 100% !important; margin: 0 !important; }\n"
        return css

    def _compute_section_offsets(self, presentation) -> dict[int, int]:
        section_max_bottom = {}
        for f in presentation.fields:
            if f.top is not None:
                sec = f.section if f.section is not None else 0
                section_max_bottom[sec] = max(section_max_bottom.get(sec, 0), f.top + (f.height or 0))
            if f.label_top is not None:
                sec = f.label_section if f.label_section is not None else (f.section if f.section is not None else 0)
                section_max_bottom[sec] = max(section_max_bottom.get(sec, 0), f.label_top + (f.label_height or 0))
        for a in presentation.actions:
            if a.top is not None:
                sec = a.section if a.section is not None else 0
                section_max_bottom[sec] = max(section_max_bottom.get(sec, 0), a.top + (a.height or 0))

        ordered_sections = [3, 1, 0, 2, 4]
        offsets = {}
        heights = {}
        current_y = 0
        
        for sec in ordered_sections:
            offsets[sec] = current_y
            if sec in section_max_bottom and section_max_bottom[sec] > 0:
                h = section_max_bottom[sec] + 200
                heights[sec] = h
                current_y += h
            else:
                heights[sec] = 0
                
        offsets[None] = offsets.get(0, 0)
        return offsets, heights

    def _build_form_fields_jsx(self, fields: list[UIField], section_offsets: dict[int, int] = None) -> str:
        """Override to generate absolutely positioned inputs and labels."""
        parts = []
        if section_offsets is None:
            section_offsets = {1: 0, 0: 0, 2: 0, None: 0}
            
        for field in fields:
            if not field.visible:
                continue

            field_name = self._to_camel(self._sanitize_field(field.data_source or field.id))
            label = field.label or field.id
            disabled = " disabled" if (field.readonly or field.is_expression) else ""

            # MS Access coordinates are in Twips. 1440 twips = 1 inch. Screen is typically 96 DPI, so 1 px = 15 twips. 
            # We use 14 as the divisor to slightly scale up the layout, injecting clean margin spacing everywhere.
            def to_px(twips: int) -> str:
                if twips is None:
                    return "auto"
                return f"{twips // 14}px"

            def to_px_y(twips: int, sec: int) -> str:
                if twips is None:
                    return "auto"
                y_offset = section_offsets.get(sec, section_offsets.get(0, 0))
                return f"{(twips + y_offset) // 14}px"

            if field.field_type.value == "label":
                label_style = f"{{{{ position: 'absolute', left: '{to_px(field.left)}', top: '{to_px_y(field.top, field.section)}', width: '{to_px(field.width)}', height: 'auto', minHeight: '{to_px(field.height)}', fontWeight: 'normal', color: '#333', fontSize: '11px', letterSpacing: '0.2px', overflow: 'visible' }}}}"
                parts.append(f"""
            <div style={label_style}>
                {label}
            </div>""")
                continue

            input_style = f"{{{{ position: 'absolute', left: '{to_px(field.left)}', top: '{to_px_y(field.top, field.section)}', width: '{to_px(field.width)}', height: '{to_px(field.height)}', boxSizing: 'border-box', border: '1px solid #ccc', padding: '2px 4px', fontSize: '11px', letterSpacing: '0.2px', backgroundColor: '{'#f8f9fa' if field.is_expression else '#fff'}' }}}}"
            if field.back_color:
                input_style = input_style[:-2] + f", backgroundColor: '{field.back_color}' }}}}"
            if field.fore_color:
                input_style = input_style[:-2] + f", color: '{field.fore_color}' }}}}"

            # If the label has layout, render it independently
            label_jsx = ""
            if field.label_left is not None and field.label_top is not None:
                l_sec = field.label_section if field.label_section is not None else field.section
                label_style = f"{{{{ position: 'absolute', left: '{to_px(field.label_left)}', top: '{to_px_y(field.label_top, l_sec)}', width: '{to_px(field.label_width)}', height: 'auto', minHeight: '{to_px(field.label_height)}', fontWeight: 'bold', color: '#555', fontSize: '11px', letterSpacing: '0.2px', overflow: 'visible', zIndex: 10 }}}}"
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
        section_offsets, section_heights = self._compute_section_offsets(presentation)
        
        # Build section backgrounds
        section_bgs = []
        for sec_id, h in section_heights.items():
            if h > 0:
                bg_c = presentation.section_colors.get(sec_id) if hasattr(presentation, 'section_colors') else None
                if bg_c:
                    section_bgs.append(f"<div style={{{{ position: 'absolute', top: '{section_offsets[sec_id] // 14}px', left: 0, width: '100%', height: '{h // 14}px', backgroundColor: '{bg_c}', zIndex: 0 }}}}></div>")

        
        def to_px(twips: int) -> str:
            return f"{twips // 14}px" if twips is not None else "auto"
            
        def to_px_y(twips: int, sec: int) -> str:
            if twips is None: return "auto"
            y_offset = section_offsets.get(sec, section_offsets.get(0, 0))
            return f"{(twips + y_offset) // 14}px"
            
        button_elements = []
        for action in presentation.actions:
            handler = self._to_camel(action.id)
            nav_route = self._resolve_action_route(action)
            click_handler = f"navigate('{nav_route}')" if nav_route else f"console.warn('No route mapped for: {handler}')"
            
            btn_f_size = '8px' if len(action.label or '') > 5 else '10px'
            btn_style = f"{{{{ position: 'absolute', left: '{to_px(action.left)}', top: '{to_px_y(action.top, action.section)}', width: '{to_px(action.width)}', height: '{to_px(action.height)}', padding: '0 2px', fontSize: '{btn_f_size}', lineHeight: '1.1', display: 'flex', alignItems: 'center', justifyContent: 'center', textAlign: 'center', whiteSpace: 'normal', overflow: 'hidden' }}}}"
            
            if action.back_color:
                btn_style = btn_style[:-2] + f", backgroundColor: '{action.back_color}' }}}}"
            if action.fore_color:
                btn_style = btn_style[:-2] + f", color: '{action.fore_color}' }}}}"
            
            button_elements.append(f"""
            <button
                type="button"
                className="btn"
                onClick={{() => {click_handler}}}
                style={btn_style}
            >
                {action.label}
            </button>""")

        form_fields_jsx = self._build_form_fields_jsx(presentation.fields, section_offsets)
        buttons_jsx = "".join(button_elements) if button_elements else ""

        needs_navigate = any(self._resolve_action_route(a) for a in presentation.actions)
        navigate_import = "import { useNavigate } from 'react-router-dom';\n" if needs_navigate else ""
        navigate_hook = "    const navigate = useNavigate();\n" if needs_navigate else ""

        max_height = 800
        max_width = 800
        for f in presentation.fields:
            if f.top is not None:
                max_height = max(max_height, (f.top + section_offsets.get(f.section or 0, section_offsets.get(0,0)) + (f.height or 0)) // 14 + 50)
            if f.label_top is not None:
                l_sec = f.label_section if f.label_section is not None else f.section
                max_height = max(max_height, (f.label_top + section_offsets.get(l_sec or 0, section_offsets.get(0,0)) + (f.label_height or 0)) // 14 + 50)
            if f.left is not None:
                max_width = max(max_width, (f.left + (f.width or 0)) // 14 + 50)
        for a in presentation.actions:
            if a.top is not None:
                max_height = max(max_height, (a.top + section_offsets.get(a.section or 0, section_offsets.get(0,0)) + (a.height or 0)) // 14 + 50)
            if a.left is not None:
                max_width = max(max_width, (a.left + (a.width or 0)) // 14 + 50)

        bg_color = presentation.back_color or '#f0f0f0'
        container_style = f"{{ position: 'relative', width: '100%', minWidth: '{max_width}px', height: '{max_height}px', border: '1px solid #ccc', backgroundColor: '{bg_color}', overflow: 'auto' }}"
        
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
            <form onSubmit={{handleSubmit}} style={{{{ width: '100%' }}}}>
                <div className="exact-layout-container" style={{{container_style}}}>
                    {''.join(section_bgs)}
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
        section_offsets, section_heights = self._compute_section_offsets(presentation)
        
        # Build section backgrounds
        section_bgs = []
        for sec_id, h in section_heights.items():
            if h > 0:
                bg_c = presentation.section_colors.get(sec_id) if hasattr(presentation, 'section_colors') else None
                if bg_c:
                    section_bgs.append(f"<div style={{{{ position: 'absolute', top: '{section_offsets[sec_id] // 14}px', left: 0, width: '100%', height: '{h // 14}px', backgroundColor: '{bg_c}', zIndex: 0 }}}}></div>")
        
        form_fields_jsx = self._build_form_fields_jsx(presentation.fields, section_offsets)
        
        max_height = 800
        max_width = 800
        for f in presentation.fields:
            if f.top is not None:
                max_height = max(max_height, (f.top + section_offsets.get(f.section or 0, section_offsets.get(0,0)) + (f.height or 0)) // 14 + 100)
            if f.label_top is not None:
                l_sec = f.label_section if f.label_section is not None else f.section
                max_height = max(max_height, (f.label_top + section_offsets.get(l_sec or 0, section_offsets.get(0,0)) + (f.label_height or 0)) // 14 + 100)
            if f.left is not None:
                max_width = max(max_width, (f.left + (f.width or 0)) // 14 + 50)

        bg_color = presentation.back_color or '#f0f0f0'
        container_style = f"{{ position: 'relative', width: '100%', minWidth: '{max_width}px', height: '{max_height}px', border: '1px solid #ccc', backgroundColor: '{bg_color}', overflow: 'auto' }}"
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
            <form onSubmit={{handleSubmit}} style={{{{ width: '100%' }}}}>
                <div className="exact-layout-container" style={{{container_style}}}>
                    {''.join(section_bgs)}
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
