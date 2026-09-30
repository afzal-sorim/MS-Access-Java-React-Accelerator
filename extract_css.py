import subprocess
import re
import json

themes = ['classic.py', 'exact.py', 'material.py', 'modern_dashboard.py', 'operations_workspace.py']
results = {}

for theme in themes:
    try:
        out = subprocess.check_output(['git', 'show', f'remotes/origin/demo-version:converter/app/generators/react/themes/{theme}']).decode('utf-8', errors='ignore')
        # Find get_css definition
        match = re.search(r'def get_css.*?return (f?\"\"\"(.*?)\"\"\")', out, re.DOTALL)
        if match:
            results[theme] = match.group(2).strip()
        else:
            # Maybe it returns something else, e.g. exact.py
            results[theme] = "NOT_FOUND - Check manually"
    except Exception as e:
        results[theme] = str(e)

with open('extracted_css.json', 'w', encoding='utf-8') as f:
    json.dump(results, f, indent=2)
