"""LLM-powered mock data generator for frontend fallback.

When the generated React frontend runs without a backend, API calls fail and
the UI shows JSON parse errors.  This module asks the LLM to produce realistic
sample data for every entity (table) so the generated ``api.js`` can fall back
to it automatically when the backend is unreachable.
"""
from __future__ import annotations

import json
import logging
import re
from typing import Optional

logger = logging.getLogger("converter.generators.react.mock_data")

# Realistic sample data pools for deterministic fallback
_FIRST_NAMES = ["James", "Maria", "Robert", "Sarah", "Michael", "Emily", "David", "Jessica", "William", "Ashley"]
_LAST_NAMES = ["Smith", "Johnson", "Williams", "Brown", "Jones", "Garcia", "Miller", "Davis", "Rodriguez", "Martinez"]
_GENDERS = ["Male", "Female", "Male", "Female", "Male"]
_SPECIALIZATIONS = ["Cardiology", "Neurology", "Orthopedics", "Pediatrics", "Dermatology"]
_DEPARTMENTS = ["Emergency", "Surgery", "Radiology", "Internal Medicine", "Psychiatry"]
_STATUSES = ["Scheduled", "Completed", "Cancelled", "In Progress", "Pending"]
_STREETS = ["123 Main St", "456 Oak Ave", "789 Pine Rd", "321 Elm Blvd", "654 Maple Dr"]
_CITIES = ["New York", "Los Angeles", "Chicago", "Houston", "Phoenix"]
_DESCRIPTIONS = ["Routine checkup", "Follow-up visit", "Initial consultation", "Emergency care", "Annual review"]


class MockDataGenerator:
    """Generate static mock JSON data per entity using the LLM provider."""

    DEFAULT_ROW_COUNT = 5

    def __init__(self):
        self._provider = None

    def _get_provider(self):
        """Lazy-load the existing LLM provider (same one used by LLMUIPlanner)."""
        if self._provider is None:
            try:
                from .....llm.provider import get_default_provider
                self._provider = get_default_provider()
                logger.info("MockDataGenerator connected to LLM provider: %s", self._provider.config.model)
            except Exception as e:
                logger.warning("MockDataGenerator: Could not initialize LLM provider: %s", e)
                raise
        return self._provider

    # ------------------------------------------------------------------ public

    def generate_mock_data(self, tables) -> dict[str, list[dict]]:
        """Return ``{entity_name: [row, …]}`` for every non-system table."""
        result: dict[str, list[dict]] = {}

        for table in tables:
            if table.role in ("SYSTEM", "INTERNAL"):
                continue

            entity = self._to_pascal(table.name)
            try:
                rows = self._generate_for_table(table)
                if rows:
                    result[entity] = rows
                    logger.info("LLM mock data generated for %s: %d rows", entity, len(rows))
                else:
                    result[entity] = self._deterministic_fallback(table)
                    logger.info("Deterministic mock data used for %s", entity)
            except Exception as e:
                logger.warning("Mock data generation failed for %s, using fallback: %s", entity, e)
                result[entity] = self._deterministic_fallback(table)

        return result

    # ------------------------------------------------------------------ LLM

    def _generate_for_table(self, table) -> Optional[list[dict]]:
        """Ask the LLM for realistic sample data for one table."""
        provider = self._get_provider()

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

        prompt = f"""Generate exactly {self.DEFAULT_ROW_COUNT} realistic sample data rows for a database table named "{table.name}".

Table columns:
{columns_text}

IMPORTANT RULES:
- Return ONLY a JSON array of {self.DEFAULT_ROW_COUNT} objects.
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
        content = self._clean_llm_response(content)

        try:
            parsed = json.loads(content)
            
            # Small LLMs sometimes return an object mapping IDs to rows instead of an array
            if isinstance(parsed, dict):
                # If it's {"rows": [...]}, extract it
                if "rows" in parsed and isinstance(parsed["rows"], list):
                    rows = parsed["rows"]
                else:
                    # Otherwise assume it's a dict of { "1": {row}, "2": {row} }
                    rows = list(parsed.values())
            elif isinstance(parsed, list):
                rows = parsed
            else:
                rows = []

            # Ensure all extracted rows are actually dicts and normalize them
            normalized_rows = []
            for i, r in enumerate(rows):
                if not isinstance(r, dict):
                    continue
                norm_r = {"id": i + 1}  # Guarantee 'id' exists
                for k, v in r.items():
                    if k.lower() == "id":
                        norm_r["id"] = v  # Prefer the LLM's ID if provided
                    else:
                        camel_k = self._to_camel(k)
                        norm_r[camel_k] = v
                normalized_rows.append(norm_r)

            if normalized_rows and len(normalized_rows) > 0:
                return normalized_rows[:self.DEFAULT_ROW_COUNT]
        except Exception as e:
            logger.warning("Failed to parse LLM JSON: %s\nContent: %s", e, content[:200])
            
        return None

    @staticmethod
    def _clean_llm_response(content: str) -> str:
        """Strip thinking tags, markdown fences, and other non-JSON from LLM output."""
        # Strip <think>...</think> blocks (deepseek-r1 model)
        content = re.sub(r'<think>.*?</think>', '', content, flags=re.DOTALL)

        # Strip markdown code fences
        if content.strip().startswith("```"):
            lines = content.split("\n")
            lines = [l for l in lines if not l.strip().startswith("```")]
            content = "\n".join(lines)

        content = content.strip()

        # Find the JSON array or object in the response
        arr_start = content.find('[')
        arr_end = content.rfind(']')
        obj_start = content.find('{')
        obj_end = content.rfind('}')

        # If it looks like a JSON array
        if arr_start != -1 and arr_end != -1 and arr_end > arr_start:
            # Check if there's an outer object wrapping it
            if obj_start != -1 and obj_start < arr_start and obj_end > arr_end:
                content = content[obj_start:obj_end + 1]
            else:
                content = content[arr_start:arr_end + 1]
        # If it looks like a JSON object
        elif obj_start != -1 and obj_end != -1 and obj_end > obj_start:
            content = content[obj_start:obj_end + 1]

        return content.strip()

    # ------------------------------------------------------------------ fallback

    def _deterministic_fallback(self, table) -> list[dict]:
        """Generate realistic placeholder data without the LLM.

        Uses domain-aware heuristics: column names like 'firstName' get real
        names, 'email' gets plausible emails, 'date' gets real dates, etc.
        """
        rows = []
        for i in range(self.DEFAULT_ROW_COUNT):
            row = {"id": i + 1}
            for col in table.columns:
                key = self._to_camel(col.name)
                if key == "id":
                    continue
                row[key] = self._generate_column_value(col, i)
            rows.append(row)
        return rows

    def _generate_column_value(self, col, index: int):
        """Generate a realistic value for a single column based on its name and type."""
        name_lower = col.name.lower()
        i = index  # 0-based

        # Primary key / auto-number → sequential
        if col.primary_key or col.auto_number:
            return i + 1

        # ---- Name-related columns ----
        if "firstname" in name_lower or "first_name" in name_lower:
            return _FIRST_NAMES[i % len(_FIRST_NAMES)]
        if "lastname" in name_lower or "last_name" in name_lower or "surname" in name_lower:
            return _LAST_NAMES[i % len(_LAST_NAMES)]
        if "fullname" in name_lower or "full_name" in name_lower:
            return f"{_FIRST_NAMES[i % len(_FIRST_NAMES)]} {_LAST_NAMES[i % len(_LAST_NAMES)]}"
        if "doctorname" in name_lower or "doctor_name" in name_lower:
            return f"Dr. {_FIRST_NAMES[i % len(_FIRST_NAMES)]} {_LAST_NAMES[i % len(_LAST_NAMES)]}"
        if "patientname" in name_lower or "patient_name" in name_lower:
            return f"{_FIRST_NAMES[i % len(_FIRST_NAMES)]} {_LAST_NAMES[i % len(_LAST_NAMES)]}"
        if name_lower == "name" or name_lower.endswith("name") or name_lower.endswith("_name"):
            # Generic name column — use full names
            return f"{_FIRST_NAMES[i % len(_FIRST_NAMES)]} {_LAST_NAMES[i % len(_LAST_NAMES)]}"

        # ---- Contact info ----
        if "email" in name_lower:
            fn = _FIRST_NAMES[i % len(_FIRST_NAMES)].lower()
            ln = _LAST_NAMES[i % len(_LAST_NAMES)].lower()
            return f"{fn}.{ln}@example.com"
        if "phone" in name_lower or "mobile" in name_lower or "tel" in name_lower:
            return f"(555) {100 + i:03d}-{1000 + i * 111:04d}"
        if "address" in name_lower or "street" in name_lower:
            return _STREETS[i % len(_STREETS)]
        if "city" in name_lower:
            return _CITIES[i % len(_CITIES)]
        if "zip" in name_lower or "postal" in name_lower:
            return f"{10001 + i * 1000}"
        if "state" in name_lower or "province" in name_lower:
            return ["NY", "CA", "IL", "TX", "AZ"][i % 5]
        if "country" in name_lower:
            return "United States"

        # ---- Medical / Domain ----
        if "gender" in name_lower or "sex" in name_lower:
            return _GENDERS[i % len(_GENDERS)]
        if "specializ" in name_lower or "specialty" in name_lower:
            return _SPECIALIZATIONS[i % len(_SPECIALIZATIONS)]
        if "department" in name_lower or "dept" in name_lower:
            return _DEPARTMENTS[i % len(_DEPARTMENTS)]
        if "status" in name_lower:
            return _STATUSES[i % len(_STATUSES)]
        if "diagnosis" in name_lower or "description" in name_lower or "notes" in name_lower:
            return _DESCRIPTIONS[i % len(_DESCRIPTIONS)]
        if "treatment" in name_lower or "procedure" in name_lower:
            return ["Physical Therapy", "Blood Test", "X-Ray", "MRI Scan", "Ultrasound"][i % 5]
        if "medication" in name_lower or "medicine" in name_lower or "drug" in name_lower:
            return ["Amoxicillin", "Ibuprofen", "Metformin", "Lisinopril", "Omeprazole"][i % 5]
        if "dosage" in name_lower:
            return ["500mg", "200mg", "250mg", "10mg", "20mg"][i % 5]
        if "room" in name_lower or "ward" in name_lower:
            return f"Room {101 + i}"
        if "bed" in name_lower:
            return f"Bed {chr(65 + i)}"

        # ---- Date/Time ----
        if "birth" in name_lower or "dob" in name_lower:
            return f"{1975 + i * 5}-{(i % 12) + 1:02d}-{(i * 7 % 28) + 1:02d}"
        if "date" in name_lower:
            return f"2026-{(i % 12) + 1:02d}-{(i * 3 % 28) + 1:02d}"
        if "time" in name_lower:
            return f"{9 + i}:00"

        # ---- Financial ----
        if "amount" in name_lower or "price" in name_lower or "cost" in name_lower or "fee" in name_lower:
            return round(50.0 + i * 75.5, 2)
        if "total" in name_lower or "balance" in name_lower:
            return round(150.0 + i * 120.0, 2)
        if "payment" in name_lower and "method" in name_lower:
            return ["Credit Card", "Cash", "Insurance", "Debit Card", "Check"][i % 5]
        if "insurance" in name_lower:
            return ["Aetna", "Blue Cross", "Cigna", "UnitedHealth", "Humana"][i % 5]

        # ---- Numeric foreign keys ----
        fk_patterns = ["_id", "id_", "patientid", "doctorid", "departmentid", "appointmentid"]
        if any(p in name_lower for p in fk_patterns) or (name_lower.endswith("id") and len(name_lower) > 2):
            return (i % 5) + 1

        # ---- Boolean ----
        at = col.access_type.lower()
        if at in ("yes/no", "boolean") or "active" in name_lower or "is_" in name_lower:
            return i % 2 == 0

        # ---- Numeric ----
        if at in ("long integer", "integer", "byte", "double", "single", "decimal", "currency"):
            return (i + 1) * 10

        # ---- Default: use column name as context ----
        return f"{col.name.replace('_', ' ').title()} {i + 1}"

    # ------------------------------------------------------------------ naming

    @staticmethod
    def _to_pascal(name: str) -> str:
        from .....naming import to_pascal
        return to_pascal(name)

    @staticmethod
    def _to_camel(name: str) -> str:
        from .....naming import to_camel
        return to_camel(name)
