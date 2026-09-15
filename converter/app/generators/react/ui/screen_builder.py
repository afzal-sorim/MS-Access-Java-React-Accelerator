"""Screen Builder — converts FormIR + ApplicationIR context into UIScreen.

This is the bridge between the Access IR layer and the UI transformation layer.
It normalizes raw Access metadata into the clean UIScreen model that the
deterministic transformer and LLM planner both consume.
"""
from __future__ import annotations

import re
from typing import Optional

from ....ir.models import (
    ApplicationIR, FormIR, ControlIR, RelationshipIR, ColumnIR,
)
from .models import (
    UIScreen, UIField, UIAction, UISubform, UIRelationship,
    UIFieldType, InfoLevel,
)
from .intent_analyzer import analyze_intent


# Access type → UIFieldType mapping
_ACCESS_TYPE_MAP: dict[str, UIFieldType] = {
    "Yes/No": UIFieldType.CHECKBOX,
    "Date/Time": UIFieldType.DATE,
    "Currency": UIFieldType.CURRENCY,
    "Long Text": UIFieldType.TEXTAREA,
    "Short Text": UIFieldType.TEXT,
    "Long Integer": UIFieldType.NUMBER,
    "Integer (Short)": UIFieldType.NUMBER,
    "Byte": UIFieldType.NUMBER,
    "Single": UIFieldType.NUMBER,
    "Double": UIFieldType.NUMBER,
    "Decimal": UIFieldType.NUMBER,
    "BigInt": UIFieldType.NUMBER,
    "Replication ID": UIFieldType.HIDDEN,
    "OLE Object": UIFieldType.FILE,
    "Attachment": UIFieldType.FILE,
    "Hyperlink": UIFieldType.URL,
}

# Control type → UIFieldType mapping
_CONTROL_TYPE_MAP: dict[str, UIFieldType] = {
    "TextBox": UIFieldType.TEXT,
    "ComboBox": UIFieldType.SELECT,
    "ListBox": UIFieldType.SELECT,
    "CheckBox": UIFieldType.CHECKBOX,
    "OptionButton": UIFieldType.RADIO,
    "OptionGroup": UIFieldType.RADIO,
    "ToggleButton": UIFieldType.TOGGLE,
    "Label": UIFieldType.LABEL,
    "Image": UIFieldType.LABEL,
}


class ScreenBuilder:
    """Builds UIScreen models from Access IR forms.

    Usage:
        builder = ScreenBuilder(app_ir)
        screens = builder.build_all()
    """

    def __init__(self, app_ir: ApplicationIR):
        self.app = app_ir
        self._column_map: dict[str, dict[str, ColumnIR]] = {}
        self._build_column_map()

    def _build_column_map(self) -> None:
        """Build lookup: table_name.lower() → {col_name.lower() → ColumnIR}."""
        for table in self.app.tables:
            cols = {}
            for col in table.columns:
                cols[col.name.lower()] = col
            self._column_map[table.name.lower()] = cols

    def build_all(self) -> list[UIScreen]:
        """Convert all forms in the ApplicationIR to UIScreens."""
        screens = []
        for form in self.app.forms:
            screens.append(self.build_screen(form))
        return screens

    # Control types that are decorative/structural and should NOT become fields
    _DECORATIVE_TYPES = frozenset({
        "Line", "Rectangle", "PageBreak", "CustomControl",
    })

    def build_screen(self, form: FormIR) -> UIScreen:
        """Convert a single FormIR into a UIScreen."""
        fields = []
        actions = []
        subforms = []
        tab_count = 0

        # Pre-build label→input caption map so input controls get human labels
        label_map = self._build_label_map(form.controls)

        for ctrl in form.controls:
            if ctrl.control_type == "CommandButton":
                actions.append(self._build_action(ctrl, form))
            elif ctrl.control_type == "Subform":
                subforms.append(self._build_subform(ctrl, form))
            elif ctrl.control_type == "TabControl":
                tab_count += 1
            elif ctrl.control_type == "Page":
                # Tab pages increment tab count
                tab_count = max(tab_count, 1)
            elif ctrl.control_type in ("Label",):
                # Only include labels with control sources (bound labels)
                if ctrl.control_source:
                    fields.append(self._build_field(ctrl, form, label_map))
            elif ctrl.control_type in self._DECORATIVE_TYPES:
                # Skip decorative/structural controls entirely
                continue
            elif ctrl.control_type == "Image" and not ctrl.control_source:
                # Skip unbound images (decorative)
                continue
            else:
                fields.append(self._build_field(ctrl, form, label_map))

        # Resolve relationships from ApplicationIR
        relationships = self._resolve_relationships(form)

        # Determine VBA complexity
        vba_complexity = self._assess_vba_complexity(form)

        # Clean display name
        display_name = form.caption or self._clean_form_name(form.name)

        return UIScreen(
            id=form.name,
            name=display_name,
            source_type="access_form",
            record_source=form.record_source,
            record_source_kind=form.record_source_kind,
            is_bound=bool(form.record_source),
            fields=fields,
            actions=actions,
            subforms=subforms,
            relationships=relationships,
            tabs=tab_count,
            is_tabbed=form.tabbed or tab_count > 0,
            field_count=len(fields),
            control_count=len(form.controls),
            button_count=len(actions),
            subform_count=len(subforms),
            has_vba=bool(form.module_source and form.module_source.strip()),
            vba_complexity=vba_complexity,
            has_events=bool(form.events),
            original_form_name=form.name,
            module_name=form.module_name,
        )

    @staticmethod
    def _build_label_map(controls: list[ControlIR]) -> dict[str, ControlIR]:
        label_map: dict[str, ControlIR] = {}  # input_name -> Label control

        labels: list[ControlIR] = [
            c for c in controls
            if c.control_type == "Label" and c.caption
        ]

        _INPUT_PREFIXES = ("txt", "cbo", "chk", "opt", "tgl", "lst")
        _LABEL_PREFIXES = ("lbl",)
        _LABEL_COL_PREFIXES = ("lblcol",)

        input_suffix_map: dict[str, list[str]] = {}
        for c in controls:
            if c.control_type in ("TextBox", "ComboBox", "CheckBox",
                                  "OptionButton", "ListBox", "ToggleButton"):
                name_lower = c.name.lower()
                for pfx in _INPUT_PREFIXES:
                    if name_lower.startswith(pfx):
                        suffix = name_lower[len(pfx):]
                        input_suffix_map.setdefault(suffix, []).append(c.name)
                        break
                else:
                    input_suffix_map.setdefault(name_lower, []).append(c.name)

        for lbl in labels:
            lbl_name_lower = lbl.name.lower()
            suffix = None

            for pfx in _LABEL_COL_PREFIXES:
                if lbl_name_lower.startswith(pfx):
                    suffix = lbl_name_lower[len(pfx):]
                    break

            if suffix is None:
                for pfx in _LABEL_PREFIXES:
                    if lbl_name_lower.startswith(pfx):
                        suffix = lbl_name_lower[len(pfx):]
                        break

            if suffix and suffix in input_suffix_map:
                for input_name in input_suffix_map[suffix]:
                    label_map[input_name] = lbl

        for i, ctrl in enumerate(controls):
            if (ctrl.control_type == "Label" and ctrl.caption
                    and i + 1 < len(controls)):
                next_ctrl = controls[i + 1]
                if (next_ctrl.control_type in ("TextBox", "ComboBox", "CheckBox",
                                               "OptionButton", "ListBox", "ToggleButton")
                        and next_ctrl.name not in label_map):
                    label_map[next_ctrl.name] = ctrl

        return label_map

    def _build_field(self, ctrl: ControlIR, form: FormIR,
                     label_map: Optional[dict[str, ControlIR]] = None) -> UIField:
        """Convert a ControlIR into a UIField."""
        field_type = self._resolve_field_type(ctrl, form)
        is_expression = self._is_access_expression(ctrl.control_source or "")
        data_type = self._resolve_data_type(ctrl, form)
        info_level = self._classify_info_level(ctrl, form)

        label_ctrl = None
        if label_map and ctrl.name in label_map:
            label_ctrl = label_map[ctrl.name]
            label = label_ctrl.caption.rstrip(":") if label_ctrl.caption else ""
        elif ctrl.caption:
            label = ctrl.caption
        else:
            label = self._humanize_control_name(ctrl.name)

        return UIField(
            id=ctrl.name,
            label=label,
            field_type=field_type,
            data_source=ctrl.control_source,
            required=not self._is_nullable(ctrl, form),
            readonly=ctrl.locked,
            visible=ctrl.visible,
            enabled=ctrl.enabled,
            data_type=data_type,
            default_value=ctrl.default_value,
            validation_rule=ctrl.validation_rule,
            row_source=ctrl.row_source,
            info_level=info_level,
            format=ctrl.format,
            is_expression=is_expression,
            left=ctrl.left,
            top=ctrl.top,
            width=ctrl.width,
            height=ctrl.height,
            label_left=label_ctrl.left if label_ctrl else None,
            label_top=label_ctrl.top if label_ctrl else None,
            label_width=label_ctrl.width if label_ctrl else None,
            label_height=label_ctrl.height if label_ctrl else None,
            label_section=label_ctrl.section if label_ctrl else None,
            section=ctrl.section,
        )

    def _build_action(self, ctrl: ControlIR, form: FormIR) -> UIAction:
        """Convert a CommandButton ControlIR into a UIAction."""
        # Get VBA code for this button's click event
        vba_code = self._get_button_vba(ctrl, form)

        intent, priority = analyze_intent(
            caption=ctrl.caption,
            control_name=ctrl.name,
            vba_code=vba_code,
            events=ctrl.events,
        )

        return UIAction(
            id=ctrl.name,
            label=ctrl.caption or ctrl.name,
            intent=intent,
            priority=priority,
            target=self._extract_navigation_target(vba_code),
            vba_handler=ctrl.events.get("OnClick", ctrl.events.get("Click")),
            enabled=ctrl.enabled,
            left=ctrl.left,
            top=ctrl.top,
            width=ctrl.width,
            height=ctrl.height,
            section=ctrl.section,
        )

    def _build_subform(self, ctrl: ControlIR, form: FormIR) -> UISubform:
        """Convert a Subform ControlIR into a UISubform."""
        # Try to find the subform definition in app_ir
        sub_form = None
        source_object = ctrl.row_source or ctrl.control_source or ctrl.name
        for f in self.app.forms:
            if f.name.lower() == source_object.lower() or f.is_subform:
                if f.name.lower().replace("frm", "") in ctrl.name.lower().replace("frm", ""):
                    sub_form = f
                    break

        record_source = sub_form.record_source if sub_form else None
        field_count = len(sub_form.controls) if sub_form else 0

        # Build relationship if parent links exist
        relationship = None
        if sub_form and sub_form.parent_links:
            for child_field, master_field in sub_form.parent_links.items():
                relationship = UIRelationship(
                    parent=form.record_source or form.name,
                    child=record_source or ctrl.name,
                    relationship_type="one_to_many",
                    parent_field=master_field,
                    child_field=child_field,
                )
                break

        return UISubform(
            id=ctrl.name,
            name=ctrl.caption or ctrl.name,
            record_source=record_source,
            relationship=relationship,
            field_count=field_count,
        )

    def _resolve_field_type(self, ctrl: ControlIR, form: FormIR) -> UIFieldType:
        """Determine UIFieldType from control type, data source, and column metadata."""
        # First: use control type mapping
        base_type = _CONTROL_TYPE_MAP.get(ctrl.control_type, UIFieldType.TEXT)

        # If it's a TextBox, refine based on column data type
        if ctrl.control_type == "TextBox" and ctrl.control_source and form.record_source:
            col = self._find_column(form.record_source, ctrl.control_source)
            if col:
                db_type = _ACCESS_TYPE_MAP.get(col.access_type)
                if db_type:
                    return db_type
                # Infer from field name
                name_lower = ctrl.control_source.lower()
                if "email" in name_lower:
                    return UIFieldType.EMAIL
                if "phone" in name_lower or "tel" in name_lower:
                    return UIFieldType.PHONE
                if "url" in name_lower or "website" in name_lower or "link" in name_lower:
                    return UIFieldType.URL
                if "date" in name_lower:
                    return UIFieldType.DATE
                if "password" in name_lower:
                    return UIFieldType.PASSWORD

        # Check for Access expressions
        if self._is_access_expression(ctrl.control_source or ""):
            return UIFieldType.COMPUTED

        return base_type

    def _resolve_data_type(self, ctrl: ControlIR, form: FormIR) -> Optional[str]:
        """Resolve the underlying database data type."""
        if ctrl.control_source and form.record_source:
            col = self._find_column(form.record_source, ctrl.control_source)
            if col:
                return col.access_type
        return None

    def _find_column(self, table_name: str, col_name: str) -> Optional[ColumnIR]:
        """Find a column by table and column name."""
        cols = self._column_map.get(table_name.lower(), {})
        return cols.get(col_name.lower())

    def _is_nullable(self, ctrl: ControlIR, form: FormIR) -> bool:
        """Check if the field allows null values."""
        if ctrl.control_source and form.record_source:
            col = self._find_column(form.record_source, ctrl.control_source)
            if col:
                return col.allow_null
        return True

    def _classify_info_level(self, ctrl: ControlIR, form: FormIR) -> InfoLevel:
        """Classify where in the information hierarchy a field belongs."""
        source = (ctrl.control_source or ctrl.name).lower()

        # Metadata fields: audit trail, system fields
        metadata_patterns = [
            "created", "modified", "updated", "timestamp",
            "created_by", "modified_by", "updated_by",
            "date_created", "date_modified",
        ]
        if any(p in source for p in metadata_patterns):
            return InfoLevel.METADATA

        # ID fields are usually hidden or metadata
        if source.endswith("id") and source != "id":
            if ctrl.visible:
                return InfoLevel.SECONDARY
            return InfoLevel.METADATA

        # Hidden/disabled fields go to advanced
        if not ctrl.visible:
            return InfoLevel.ADVANCED
        if not ctrl.enabled and ctrl.locked:
            return InfoLevel.SECONDARY

        return InfoLevel.PRIMARY

    def _resolve_relationships(self, form: FormIR) -> list[UIRelationship]:
        """Find all relationships involving this form's record source."""
        if not form.record_source:
            return []

        relationships = []
        source_lower = form.record_source.lower()

        for rel in self.app.relationships:
            if rel.parent_table.lower() == source_lower:
                relationships.append(UIRelationship(
                    parent=rel.parent_table,
                    child=rel.child_table,
                    relationship_type="one_to_one" if rel.one_to_one else "one_to_many",
                    parent_field=rel.parent_columns[0] if rel.parent_columns else None,
                    child_field=rel.child_columns[0] if rel.child_columns else None,
                ))
            elif rel.child_table.lower() == source_lower:
                relationships.append(UIRelationship(
                    parent=rel.parent_table,
                    child=rel.child_table,
                    relationship_type="one_to_one" if rel.one_to_one else "one_to_many",
                    parent_field=rel.parent_columns[0] if rel.parent_columns else None,
                    child_field=rel.child_columns[0] if rel.child_columns else None,
                ))

        return relationships

    def _assess_vba_complexity(self, form: FormIR) -> str:
        """Assess the complexity of the form's VBA code."""
        if not form.module_source or not form.module_source.strip():
            return "none"

        line_count = len(form.module_source.strip().splitlines())
        has_error_handling = "On Error" in form.module_source
        has_recordset = "Recordset" in form.module_source or "DAO" in form.module_source
        has_api_calls = "Declare" in form.module_source or "CreateObject" in form.module_source
        proc_count = len(re.findall(r"\b(Sub|Function)\b", form.module_source, re.IGNORECASE))

        complexity_score = 0
        if line_count > 200:
            complexity_score += 3
        elif line_count > 50:
            complexity_score += 2
        elif line_count > 10:
            complexity_score += 1

        if has_recordset:
            complexity_score += 2
        if has_error_handling:
            complexity_score += 1
        if has_api_calls:
            complexity_score += 2
        if proc_count > 10:
            complexity_score += 2
        elif proc_count > 5:
            complexity_score += 1

        if complexity_score >= 5:
            return "complex"
        elif complexity_score >= 2:
            return "moderate"
        elif complexity_score >= 1:
            return "simple"
        return "none"

    def _get_button_vba(self, ctrl: ControlIR, form: FormIR) -> Optional[str]:
        """Extract VBA code for a button's click event handler."""
        if not form.module_source:
            return None

        # Look for Sub cmdName_Click() or Sub btnName_Click()
        handler_name = ctrl.events.get("OnClick", ctrl.events.get("Click", ""))
        if not handler_name:
            handler_name = f"{ctrl.name}_Click"

        # Extract the procedure body from the module source
        pattern = rf"(?:Private\s+|Public\s+)?Sub\s+{re.escape(handler_name)}\s*\(.*?\)(.*?)End\s+Sub"
        match = re.search(pattern, form.module_source, re.DOTALL | re.IGNORECASE)
        if match:
            return match.group(1).strip()
        return None

    @staticmethod
    def _extract_navigation_target(vba_code: Optional[str]) -> Optional[str]:
        """Extract navigation target from VBA code (e.g., DoCmd.OpenForm target)."""
        if not vba_code:
            return None
        match = re.search(r'DoCmd\.OpenForm\s+"([^"]+)"', vba_code, re.IGNORECASE)
        if match:
            return match.group(1)
        return None

    @staticmethod
    def _is_access_expression(value: str) -> bool:
        """Check if a value is an Access calculated expression."""
        if not value:
            return False
        stripped = value.strip()
        return stripped.startswith("=") or ("(" in stripped and ")" in stripped)

    @staticmethod
    def _clean_form_name(name: str) -> str:
        """Clean an Access form name into a display name."""
        # Remove common prefixes
        cleaned = re.sub(r"^(frm|Form_|sub)", "", name, flags=re.IGNORECASE)
        # Convert CamelCase/PascalCase to spaces
        cleaned = re.sub(r"(?<=[a-z])(?=[A-Z])", " ", cleaned)
        # Convert underscores to spaces
        cleaned = cleaned.replace("_", " ")
        return cleaned.strip() or name

    @staticmethod
    def _humanize_control_name(name: str) -> str:
        """Convert an Access control name like ``txtClosedBy`` into ``Closed By``."""
        # Strip common Access prefixes
        cleaned = re.sub(
            r"^(txt|cbo|chk|opt|tgl|lst|lbl|cmd|btn|frm|sub|img)",
            "", name, flags=re.IGNORECASE,
        )
        if not cleaned:
            return name
        # Insert spaces before uppercase letters (CamelCase → words)
        cleaned = re.sub(r"(?<=[a-z0-9])(?=[A-Z])", " ", cleaned)
        # Replace underscores with spaces
        cleaned = cleaned.replace("_", " ")
        return cleaned.strip() or name
