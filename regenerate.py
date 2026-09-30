import json
import sys
from pathlib import Path
sys.path.append(r'c:\Users\Afzal\ZCodeProject\converter')
from app.generators.react import generate_react

from converter.app.ir.models import ApplicationIR
ir_data = json.load(open(r'c:\Users\Afzal\ZCodeProject\converter\outputs\8615d6a1\application_ir.json', 'r', encoding='utf-8'))
app_ir = ApplicationIR.model_validate(ir_data)
frontend_dir = Path(r'c:\Users\Afzal\ZCodeProject\converter\outputs\8615d6a1\frontend')

print("Starting generate_react...")
react_gen = generate_react(
    app_ir,
    frontend_dir,
    form_conversions={},
    ui_style="operations_workspace",
    ui_reasoning="none",
    ui_debug=True,
)

print(f"Generated {len(react_gen)} files in memory. Writing...")
for file_path, content in react_gen.items():
    p = Path(file_path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(content, encoding="utf-8")
print("Done writing.")
