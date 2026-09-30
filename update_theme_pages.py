import os
import re

THEMES_DIR = r"c:\Users\Afzal\ZCodeProject\converter\app\generators\react\themes"

def update_theme_pages(filepath):
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()

    # We will replace everything from `    def render_list_page` to `    def render_app_shell` 
    # with the component-based implementation.
    
    pages_pattern = re.compile(r'    def render_list_page.*?    def render_app_shell', re.DOTALL)
    
    if 'def render_list_page' not in content:
        return
        
    new_pages = '''    def render_list_page(self, presentation, endpoint, api_name, helper_imports):
        page_name = self._to_pascal(presentation.screen_id.replace("frm", ""))
        var_name = self._to_camel(page_name)
        
        return f"""import React from 'react';
import {{ useNavigate }} from 'react-router-dom';
import {{ getAll }} from '../services/{page_name}Service';
import {{ useApi }} from '../hooks/useApi';
import PageHeader from '../components/common/PageHeader';
import DataTable from '../components/common/DataTable';
import LoadingSpinner from '../components/common/LoadingSpinner';
import ErrorMessage from '../components/common/ErrorMessage';
import EmptyState from '../components/common/EmptyState';

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
            <PageHeader 
                title="{presentation.screen_name}" 
                action={{
                    label: "Add New",
                    onClick: () => navigate('/{endpoint}/new')
                }}
            />
            
            {{!{var_name} || {var_name}.length === 0 ? (
                <EmptyState message="No {page_name.lower()}s found." />
            ) : (
                <DataTable 
                    data={{{var_name}}} 
                    columns={{columns}} 
                    onRowClick={{(row) => navigate(`/{endpoint}/${{row.id}}`)}}
                />
            )}}
        </div>
    );
}}
"""

    def render_form_page(self, presentation, endpoint, api_name, helper_imports):
        page_name = self._to_pascal(presentation.screen_id.replace("frm", ""))
        form_fields_jsx = self._build_form_fields_jsx(presentation.fields)

        return f"""import React, {{ useState, useEffect }} from 'react';
import {{ useNavigate, useParams }} from 'react-router-dom';
import {{ getById, create, update }} from '../services/{page_name}Service';
import PageHeader from '../components/common/PageHeader';
import FormField from '../components/common/FormField';
import Button from '../components/common/Button';
import LoadingSpinner from '../components/common/LoadingSpinner';
import ErrorMessage from '../components/common/ErrorMessage';

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
            <PageHeader title="{{isEdit ? 'Edit' : 'Add'}} {presentation.screen_name}" />
            <form onSubmit={{handleSubmit}}>
{form_fields_jsx}
                <div style={{{{ display: 'flex', gap: '1rem', marginTop: '2rem' }}}}>
                    <Button type="submit">Save</Button>
                    <Button variant="secondary" onClick={{() => navigate('/{endpoint}')}}>Cancel</Button>
                </div>
            </form>
        </div>
    );
}}
"""

    def render_dashboard_page(self, presentation, endpoint, api_name, helper_imports):
        return self.render_list_page(presentation, endpoint, api_name, helper_imports)

    def render_detail_page(self, presentation, endpoint, api_name, helper_imports):
        return self.render_list_page(presentation, endpoint, api_name, helper_imports)

    def render_master_detail_page(self, presentation, endpoint, api_name, helper_imports):
        return self.render_list_page(presentation, endpoint, api_name, helper_imports)

    def render_app_shell'''
    
    content = pages_pattern.sub(new_pages, content)
        
    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(content)

for filename in ['classic.py', 'material.py', 'modern_dashboard.py', 'operations_workspace.py', 'exact.py']:
    update_theme_pages(os.path.join(THEMES_DIR, filename))

print("Updated theme pages successfully.")
