"""LLM Prompt Templates — versioned system and user prompts for UI planning.

The LLM receives normalized UIScreen metadata and style-specific design rules.
It returns a strict UILayoutPlan — never raw JSX or arbitrary strings.
"""
from __future__ import annotations

import json
from typing import Optional

from ..models import UIScreen


PROMPT_VERSION = "ui-planner-v1"


SYSTEM_PROMPT = """You are a UI transformation planner for a legacy MS Access to React modernization tool.

Your task: Given a normalized UI model of an Access form, determine the most appropriate
modern React page layout and structure.

CRITICAL RULES — You MUST follow these:

You are NOT allowed to:
- Change business logic or database behavior
- Invent API endpoints or database fields
- Remove any functionality (every field and action must be preserved)
- Use unsupported component types
- Invent field names or action names that don't exist in the source
- Generate JSX, CSS, or any code — you produce ONLY a structured plan
- Change CRUD semantics, validation rules, permissions, or SQL

You MAY:
- Classify the page type (dashboard, list, form, master_detail, etc.)
- Choose a layout pattern (single_column, two_column, card_grid, split_view, tabs, etc.)
- Group fields into logical sections
- Assign information hierarchy (primary, secondary, metadata)
- Choose navigation patterns
- Determine primary/secondary/danger action placement
- Recommend responsive behavior

Return ONLY valid JSON conforming to the required schema. No markdown, no explanation outside the JSON."""


def build_style_rules(style: str) -> dict:
    """Build style-specific design guidance for the LLM."""
    rules = {
        "classic": {
            "style": "classic",
            "navigation": "top_navbar",
            "preferred_layouts": ["single_column", "two_column", "table"],
            "form_style": "traditional",
            "density": "comfortable",
            "dark_mode": False,
            "design_notes": "Clean enterprise design. Traditional top navigation bar. Standard form layouts with labels above inputs.",
        },
        "modern_dashboard": {
            "style": "modern_dashboard",
            "navigation": "sidebar",
            "preferred_layouts": ["card_grid", "split_view", "table"],
            "form_style": "card",
            "density": "comfortable",
            "dark_mode": True,
            "design_notes": "Modern dashboard with dark sidebar. Use card-based layouts. Data tables with hover effects. Gradient accent colors.",
        },
        "material": {
            "style": "material",
            "navigation": "top_navbar",
            "preferred_layouts": ["single_column", "two_column", "table", "card_grid"],
            "form_style": "outlined",
            "density": "comfortable",
            "dark_mode": False,
            "design_notes": "Google Material Design. AppBar navigation. Elevation-based depth. Outlined inputs. FAB for primary add actions.",
        },
        "operations_workspace": {
            "style": "operations_workspace",
            "navigation": "top_navbar",
            "preferred_layouts": ["split_view", "two_column", "table", "card_grid"],
            "form_style": "sectioned_workspace",
            "dark_mode": False,
            "design_notes": "Access-to-web operations workspace. Translate continuous forms into a left record rail with a sectioned detail panel. Use compact white cards, navy table headers, grouped menu actions, explicit save/reset actions, and report-ready data tables.",
        },
    }
    return rules.get(style, rules["classic"])


def build_user_prompt(
    screen: UIScreen,
    style: str,
    supported_components: set[str],
) -> str:
    """Build the user prompt with screen metadata and constraints."""
    style_rules = build_style_rules(style)

    # Build screen summary (metadata only, no production data)
    screen_data = {
        "screen_name": screen.name,
        "source_form": screen.original_form_name,
        "is_bound": screen.is_bound,
        "record_source": screen.record_source,
        "field_count": screen.field_count,
        "button_count": screen.button_count,
        "subform_count": screen.subform_count,
        "tab_count": screen.tabs,
        "has_vba": screen.has_vba,
        "vba_complexity": screen.vba_complexity,
        "fields": [
            {
                "id": f.id,
                "label": f.label,
                "type": f.field_type.value,
                "required": f.required,
                "readonly": f.readonly,
                "visible": f.visible,
                "has_row_source": bool(f.row_source),
            }
            for f in screen.fields
        ],
        "actions": [
            {
                "id": a.id,
                "label": a.label,
                "intent": a.intent.value,
            }
            for a in screen.actions
        ],
        "subforms": [
            {
                "id": sf.id,
                "name": sf.name,
                "record_source": sf.record_source,
                "field_count": sf.field_count,
            }
            for sf in screen.subforms
        ],
        "relationships": [
            {
                "parent": r.parent,
                "child": r.child,
                "type": r.relationship_type,
            }
            for r in screen.relationships
        ],
    }

    # Build the output schema description
    output_schema = {
        "page_type": "One of: dashboard, list, detail, form, master_detail, search, wizard, settings, report, profile",
        "layout": "One of: single_column, two_column, three_column, card_grid, table, split_view, tabs, accordion, stepper, sidebar_detail",
        "navigation": "One of: top_navbar, sidebar, tabs, breadcrumb, drawer (or null)",
        "sections": [
            {
                "id": "unique section identifier",
                "title": "section title or null",
                "layout": "layout type for this section",
                "field_ids": ["list of field IDs from the source"],
                "component_type": "One of the supported components",
                "collapsible": "boolean",
                "default_collapsed": "boolean",
            }
        ],
        "actions": [
            {
                "action_id": "must match an action ID from the source",
                "priority": "primary | secondary | danger | tertiary",
                "placement": "toolbar | inline | fab | menu | footer",
            }
        ],
        "responsive": {
            "mobile": "stack | hide | drawer",
            "tablet": "split | stack | tabs",
            "desktop": "split | full | sidebar",
        },
        "confidence": "float 0.0-1.0",
        "reasoning": "brief explanation of your design decision",
    }

    return f"""Analyze this Access form and determine the best modern React page layout.

## Screen Information
{json.dumps(screen_data, indent=2)}

## Target Design Style
{json.dumps(style_rules, indent=2)}

## Supported Components (you may ONLY use these)
{json.dumps(sorted(supported_components), indent=2)}

## Required Output Schema
{json.dumps(output_schema, indent=2)}

IMPORTANT:
- Every field_id in sections must reference an actual field ID from the source.
- Every action_id must reference an actual action ID from the source.
- Do NOT invent new fields or actions.
- All fields must appear in at least one section.
- Return ONLY the JSON object, no other text."""
