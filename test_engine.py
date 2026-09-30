import json
from pathlib import Path
import sys

# Add converter path to sys
sys.path.append(r"c:\Users\Afzal\ZCodeProject\converter")

from app.access.parser import AccessParser
from app.generators.react.ui.engine import UITransformationEngine

def main():
    ir_path = r"c:\Users\Afzal\ZCodeProject\converter\outputs\8615d6a1\ir.json"
    if not Path(ir_path).exists():
        print(f"IR not found at {ir_path}")
        return

    with open(ir_path, 'r', encoding='utf-8') as f:
        ir_data = json.load(f)

    # Note: Assuming AccessApp from_ir or similar method exists, checking access parser
    # if it doesn't, we will see in the error
    try:
        from app.models.ir import AccessApp
        app = AccessApp.model_validate(ir_data)
    except Exception as e:
        print("Model validate error:", e)
        return

    print("Initializing engine...")
    try:
        engine = UITransformationEngine(
            app,
            ui_style="operations_workspace",
            ui_reasoning=True,
            ui_debug=True
        )
        print("Transforming all...")
        presentations = engine.transform_all()
        print(f"Transformed {len(presentations)} screens.")
    except Exception as e:
        import traceback
        traceback.print_exc()

if __name__ == '__main__':
    main()
