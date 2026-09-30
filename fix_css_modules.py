import os
import re

THEMES_DIR = r"c:\Users\Afzal\ZCodeProject\converter\app\generators\react\themes"

def fix_css_and_pages(filepath):
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()

    # 1. Fix get_css to use the correct class name for CSS module (e.g. pageContainer)
    # The previous script did this correctly for CSS, but we need to ensure it matches the JSX.
    # Actually, the CSS part is fine if the JSX uses styles.pageContainer!
    
    # Let's fix the JSX to import and use styles.pageContainer!
    
    # For render_list_page
    content = content.replace(
        """import React from 'react';
import { useNavigate } from 'react-router-dom';
import { getAll } from '../services/{page_name}Service';
import { useApi } from '../hooks/useApi';
import PageHeader from '../components/common/PageHeader';
import DataTable from '../components/common/DataTable';
import LoadingSpinner from '../components/common/LoadingSpinner';
import ErrorMessage from '../components/common/ErrorMessage';
import EmptyState from '../components/common/EmptyState';""",
        """import React from 'react';
import { useNavigate } from 'react-router-dom';
import { getAll } from '../services/{page_name}Service';
import { useApi } from '../hooks/useApi';
import PageHeader from '../components/common/PageHeader';
import DataTable from '../components/common/DataTable';
import LoadingSpinner from '../components/common/LoadingSpinner';
import ErrorMessage from '../components/common/ErrorMessage';
import EmptyState from '../components/common/EmptyState';
import styles from './{page_name}Page.module.css';"""
    )
    
    content = content.replace(
        '<div className="{page_name.lower()}-page">',
        '<div className={styles.pageContainer}>'
    )
    
    # For render_form_page
    content = content.replace(
        """import React, { useState, useEffect } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import { getById, create, update } from '../services/{page_name}Service';
import PageHeader from '../components/common/PageHeader';
import FormField from '../components/common/FormField';
import Button from '../components/common/Button';
import LoadingSpinner from '../components/common/LoadingSpinner';
import ErrorMessage from '../components/common/ErrorMessage';""",
        """import React, { useState, useEffect } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import { getById, create, update } from '../services/{page_name}Service';
import PageHeader from '../components/common/PageHeader';
import FormField from '../components/common/FormField';
import Button from '../components/common/Button';
import LoadingSpinner from '../components/common/LoadingSpinner';
import ErrorMessage from '../components/common/ErrorMessage';
import styles from './{page_name}Page.module.css';"""
    )
    
    content = content.replace(
        '<div className="{page_name.lower()}-form">',
        '<div className={styles.pageContainer}>'
    )
        
    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(content)

for filename in ['classic.py', 'material.py', 'modern_dashboard.py', 'operations_workspace.py', 'exact.py']:
    fix_css_and_pages(os.path.join(THEMES_DIR, filename))

print("Fixed CSS Modules imports in theme pages.")
