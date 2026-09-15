import sys
import logging
import json

# Setup basic logging to see the logger output
logging.basicConfig(level=logging.INFO)

# Add app to path
import sys
from pathlib import Path
sys.path.insert(0, str(Path("c:/Users/Afzal/ZCodeProject/converter/app").parent))

from app.generators.react.ui.llm.mock_data import MockDataGenerator

class DummyColumn:
    def __init__(self, name, access_type, primary_key=False, required=False, auto_number=False):
        self.name = name
        self.access_type = access_type
        self.primary_key = primary_key
        self.required = required
        self.auto_number = auto_number

class DummyTable:
    def __init__(self, name, role="DATA"):
        self.name = name
        self.role = role
        self.columns = [
            DummyColumn("ID", "AutoNumber", primary_key=True),
            DummyColumn("PatientName", "Short Text", required=True),
            DummyColumn("DOB", "Date/Time"),
            DummyColumn("IsActive", "Yes/No"),
        ]

def test():
    generator = MockDataGenerator()
    table = DummyTable("Patients")
    
    # Try generating
    try:
        print("--- Testing LLM Generation ---")
        provider = generator._get_provider()
        
        col_descriptions = []
        for col in table.columns:
            parts = [col.name, f"({col.access_type})"]
            if col.primary_key:
                parts.append("PK")
            if col.required:
                parts.append("required")
            if col.auto_number:
                parts.append("auto")
            col_descriptions.append(" ".join(parts))

        columns_text = "\n".join(f"  - {d}" for d in col_descriptions)

        prompt = f"""Generate exactly 5 realistic sample data rows for a database table named "{table.name}".

Table columns:
{columns_text}

IMPORTANT RULES:
- Return ONLY a JSON array of 5 objects.
- Each object must have keys matching the column names using camelCase (e.g. "appointmentDate" for "AppointmentDate").
- Include an "id" field with sequential integers starting from 1.
- Use realistic, diverse data (real-sounding names, valid dates in YYYY-MM-DD format, plausible values).
- For numeric IDs that reference other tables, use small integers (1-5).
- For boolean fields, use true/false.
- For date fields, use ISO 8601 format strings.
- Do NOT include any explanation, markdown, code fences, or thinking. Return ONLY the raw JSON array."""

        system_prompt = "You are a test data generator. Return only valid JSON arrays with no surrounding text, no thinking, no explanation."

        response = provider.generate(
            prompt=prompt,
            system_prompt=system_prompt,
            json_mode=True,
        )

        content = response.content.strip()
        print("--- RAW LLM OUTPUT ---")
        print(content)
        print("--- CLEANED LLM OUTPUT ---")
        print(generator._clean_llm_response(content))
        
    except Exception as e:
        print(f"LLM Generation failed: {e}")

if __name__ == "__main__":
    test()
