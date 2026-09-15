"""Abstract Theme base class — defines the rendering contract for all themes.

Every theme must implement these methods to produce valid React JSX + CSS
from a UIPresentation model.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Optional

from ..ui.models import UIPresentation, UIScreen, UIField, UIAction, PageType


class Theme(ABC):
    """Abstract base for design system themes."""

    @property
    @abstractmethod
    def name(self) -> str:
        """Human-readable theme name."""
        ...

    @property
    @abstractmethod
    def key(self) -> str:
        """Unique theme identifier."""
        ...

    # ──────────────────────────────────── CSS generation

    @abstractmethod
    def get_css(self, app_name: str, presentations: list[UIPresentation]) -> str:
        """Generate the complete index.css for the application."""
        ...

    # ──────────────────────────────────── Page rendering

    @abstractmethod
    def render_list_page(
        self,
        presentation: UIPresentation,
        endpoint: str,
        api_name: str,
        helper_imports: str,
    ) -> str:
        """Render a list/table page."""
        ...

    @abstractmethod
    def render_form_page(
        self,
        presentation: UIPresentation,
        endpoint: str,
        api_name: str,
        helper_imports: str,
    ) -> str:
        """Render a CRUD form page."""
        ...

    @abstractmethod
    def render_dashboard_page(
        self,
        presentation: UIPresentation,
    ) -> str:
        """Render a dashboard/info page."""
        ...

    @abstractmethod
    def render_detail_page(
        self,
        presentation: UIPresentation,
        endpoint: str,
        api_name: str,
        helper_imports: str,
    ) -> str:
        """Render a detail view page (read-heavy with sections)."""
        ...

    @abstractmethod
    def render_master_detail_page(
        self,
        presentation: UIPresentation,
        endpoint: str,
        api_name: str,
        helper_imports: str,
    ) -> str:
        """Render a master-detail (split view) page."""
        ...

    @abstractmethod
    def render_app_shell(
        self,
        app_name: str,
        pages: list[dict],
        report_import: str,
        report_route: str,
        report_link: str,
    ) -> str:
        """Render the App.jsx with navigation shell and routing."""
        ...

    # ──────────────────────────────────── Helpers

    def render_page(
        self,
        presentation: UIPresentation,
        endpoint: str = "",
        api_name: str = "",
        helper_imports: str = "",
    ) -> str:
        """Route to the appropriate page renderer based on page type."""
        pt = presentation.page_type

        if pt in (PageType.DASHBOARD, PageType.SETTINGS):
            return self.render_dashboard_page(presentation)
        elif pt == PageType.LIST:
            return self.render_list_page(presentation, endpoint, api_name, helper_imports)
        elif pt == PageType.MASTER_DETAIL:
            return self.render_master_detail_page(presentation, endpoint, api_name, helper_imports)
        elif pt in (PageType.DETAIL, PageType.PROFILE):
            return self.render_detail_page(presentation, endpoint, api_name, helper_imports)
        else:
            return self.render_form_page(presentation, endpoint, api_name, helper_imports)

    @staticmethod
    def _to_pascal(name: str) -> str:
        from ....naming import to_pascal
        return to_pascal(name)

    @staticmethod
    def _to_camel(name: str) -> str:
        from ....naming import to_camel
        return to_camel(name)

    @staticmethod
    def _to_kebab(name: str) -> str:
        from ....naming import to_kebab
        return to_kebab(name)

    @staticmethod
    def _sanitize_field(source: str) -> str:
        """Sanitize a field name for use as a JS identifier."""
        from ....expressions import _to_js_identifier
        return _to_js_identifier(source)

    def _build_form_fields_jsx(self, fields: list[UIField]) -> str:
        """Generate form input fields JSX from UIField list."""
        parts = []
        for field in fields:
            if field.field_type.value == "label" or field.is_expression:
                continue
            if not field.visible:
                continue

            field_name = self._to_camel(self._sanitize_field(field.data_source or field.id))
            label = field.label or field.id
            disabled = " disabled" if field.readonly else ""

            if field.field_type.value == "checkbox":
                parts.append(f"""
            <div className="form-group">
                <label>
                    <input
                        type="checkbox"
                        name="{field_name}"
                        checked={{formData.{field_name} || false}}
                        onChange={{handleChange}}{disabled}
                    />
                    {label}
                </label>
            </div>""")
            elif field.field_type.value == "select":
                parts.append(f"""
            <div className="form-group">
                <label htmlFor="{field_name}">{label}</label>
                <select
                    id="{field_name}"
                    name="{field_name}"
                    value={{formData.{field_name} || ''}}
                    onChange={{handleChange}}{disabled}
                >
                    <option value="">Select...</option>
                </select>
            </div>""")
            elif field.field_type.value == "textarea":
                parts.append(f"""
            <div className="form-group">
                <label htmlFor="{field_name}">{label}</label>
                <textarea
                    id="{field_name}"
                    name="{field_name}"
                    value={{formData.{field_name} || ''}}
                    onChange={{handleChange}}{disabled}
                    rows="4"
                />
            </div>""")
            else:
                input_type = self._field_type_to_input(field)
                parts.append(f"""
            <div className="form-group">
                <label htmlFor="{field_name}">{label}</label>
                <input
                    type="{input_type}"
                    id="{field_name}"
                    name="{field_name}"
                    value={{formData.{field_name} || ''}}
                    onChange={{handleChange}}{disabled}
                />
            </div>""")
        return "\n".join(parts)

    @staticmethod
    def _field_type_to_input(field: UIField) -> str:
        """Map UIFieldType to HTML input type."""
        mapping = {
            "text": "text",
            "number": "number",
            "date": "date",
            "datetime": "datetime-local",
            "email": "email",
            "phone": "tel",
            "url": "url",
            "password": "password",
            "currency": "number",
            "percent": "number",
        }
        return mapping.get(field.field_type.value, "text")

    def _build_table_columns(self, fields: list[UIField], max_cols: int = 6) -> list[UIField]:
        """Select fields suitable for table column display."""
        display_fields = [
            f for f in fields
            if f.visible
            and f.field_type.value not in ("label", "hidden", "computed", "textarea")
            and not f.is_expression
            and not (f.data_source or f.id).lower().endswith("id")
        ]
        return display_fields[:max_cols]

    def set_route_map(self, route_map: dict[str, str]):
        """Set the route map for resolving dashboard navigation targets.

        The route map is built by the ReactGenerator and maps form/screen names
        to their actual route paths (e.g. {'PatientsForm': '/patients-form'}).
        """
        self._route_map = route_map

    def _resolve_action_route(self, action: UIAction) -> str:
        """Resolve a UIAction to a React Router route path.

        Uses the route map (set by the generator) to map form targets to actual
        routes. Falls back to inferring from labels when no direct target exists.

        Returns an empty string if no route can be determined.
        """
        import re

        route_map = getattr(self, '_route_map', {})
        target = action.target
        intent = action.intent

        # If we have a direct target from VBA parsing (e.g. "frmPatientsForm")
        if target:
            # Try exact match first
            if target in route_map:
                return route_map[target]
            # Try without frm prefix
            cleaned = re.sub(r"^(frm|Form_|sub)", "", target, flags=re.IGNORECASE)
            if cleaned in route_map:
                return route_map[cleaned]
            # Try fuzzy match — look for a route whose key contains the target
            target_lower = cleaned.lower().replace("_", "").replace(" ", "")
            for key, route in route_map.items():
                key_lower = key.lower().replace("_", "").replace(" ", "")
                if target_lower in key_lower or key_lower in target_lower:
                    return route
            # Fall back to kebab-case
            return "/" + self._to_kebab(cleaned)

        # Infer from intent + label for open_form / navigate actions
        if intent in ("open_form", "navigate"):
            label = action.label or action.id
            # Strip ALL non-ASCII characters (emojis, special chars)
            label = re.sub(r'[^\x00-\x7F]+', '', label).strip()
            # Remove action verbs
            cleaned = re.sub(
                r"^(open|go\s+to|show|view|navigate\s+to)\s+",
                "", label, flags=re.IGNORECASE,
            )
            # Remove trailing "Form" or "Page"
            cleaned = re.sub(r"\s*(form|page)$", "", cleaned, flags=re.IGNORECASE)
            cleaned = cleaned.strip()
            if not cleaned:
                return ""

            # Try matching cleaned label against route map keys
            cleaned_lower = cleaned.lower().replace(" ", "")
            for key, route in route_map.items():
                key_lower = key.lower().replace("_", "").replace(" ", "")
                if cleaned_lower in key_lower or key_lower in cleaned_lower:
                    return route

            # Fall back to kebab-case
            return "/" + self._to_kebab(cleaned)

        return ""

