import os
import re

THEMES_DIR = r"c:\Users\Afzal\ZCodeProject\converter\app\generators\react\themes"

def inject_styles_import(filepath):
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()

    # Regex to find export default function {page_name}Page()
    # and insert import styles just before it.
    
    # 1. Replace the className
    content = re.sub(r'<div className="\{page_name\.lower\(\)\}-page">', r'<div className={styles.pageContainer}>', content)
    content = re.sub(r'<div className="\{page_name\.lower\(\)\}-form">', r'<div className={styles.pageContainer}>', content)
    
    # 2. Inject import styles
    content = re.sub(
        r'(export default function \{page_name\}(?:Form)?Page\(\) \{)',
        r"import styles from './{page_name}Page.module.css';\n\n\1",
        content
    )
    
    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(content)

for filename in ['classic.py', 'material.py', 'modern_dashboard.py', 'operations_workspace.py', 'exact.py']:
    inject_styles_import(os.path.join(THEMES_DIR, filename))

print("Injected CSS Module imports.")
