"""LLM Plan Validator — validates and repairs LLM-generated UI layout plans.

Checks that:
- All referenced fields exist in the source UIScreen
- All referenced actions exist in the source UIScreen
- All components are in the supported registry
- Layout types are valid for the page type
- No source fields/actions are silently dropped
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Optional

from ..models import (
    UIScreen, UILayoutPlan, UISectionPlan, UIActionPlan,
    PageType, LayoutType, ActionPriority,
)
from ..component_registry import SUPPORTED_COMPONENTS
from ..layout_registry import is_layout_compatible, get_default_layout

logger = logging.getLogger("converter.ui.llm.validator")


@dataclass
class ValidationResult:
    """Result of validating a UILayoutPlan against a UIScreen."""
    is_valid: bool = True
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    repairs_applied: list[str] = field(default_factory=list)


class PlanValidator:
    """Validates LLM-generated UILayoutPlans against the source UIScreen."""

    def validate(self, plan: UILayoutPlan, screen: UIScreen) -> ValidationResult:
        """Validate a plan without modifying it."""
        result = ValidationResult()
        source_field_ids = {f.id for f in screen.fields}
        source_action_ids = {a.id for a in screen.actions}

        # Check page type is valid enum
        try:
            PageType(plan.page_type) if isinstance(plan.page_type, str) else plan.page_type
        except ValueError:
            result.errors.append(f"Invalid page_type: {plan.page_type}")
            result.is_valid = False

        # Check layout compatibility
        if not is_layout_compatible(plan.page_type, plan.layout):
            result.warnings.append(
                f"Layout '{plan.layout.value}' is unusual for page type '{plan.page_type.value}'"
            )

        # Check section field references
        all_plan_field_ids = set()
        for section in plan.sections:
            for fid in section.field_ids:
                all_plan_field_ids.add(fid)
                if fid not in source_field_ids:
                    result.errors.append(f"Section '{section.id}' references unknown field: {fid}")
                    result.is_valid = False

            # Check component type
            if section.component_type and section.component_type not in SUPPORTED_COMPONENTS:
                result.errors.append(
                    f"Section '{section.id}' uses unsupported component: {section.component_type}"
                )
                result.is_valid = False

        # Check action references
        all_plan_action_ids = set()
        for action_plan in plan.actions:
            all_plan_action_ids.add(action_plan.action_id)
            if action_plan.action_id not in source_action_ids:
                result.errors.append(f"Action plan references unknown action: {action_plan.action_id}")
                result.is_valid = False

        # Check for dropped fields (warning, not error — some may be labels/hidden)
        visible_field_ids = {f.id for f in screen.fields if f.visible and f.field_type.value != "label"}
        missing_fields = visible_field_ids - all_plan_field_ids
        if missing_fields:
            result.warnings.append(
                f"{len(missing_fields)} visible field(s) not placed in any section: {sorted(missing_fields)[:5]}"
            )

        # Check for dropped actions
        missing_actions = source_action_ids - all_plan_action_ids
        if missing_actions:
            result.warnings.append(
                f"{len(missing_actions)} action(s) not placed: {sorted(missing_actions)[:5]}"
            )

        return result

    def validate_and_repair(self, plan: UILayoutPlan, screen: UIScreen) -> tuple[UILayoutPlan, ValidationResult]:
        """Validate a plan and attempt deterministic repairs for common issues.

        Returns the (possibly repaired) plan and the validation result.
        """
        result = self.validate(plan, screen)

        if result.is_valid and not result.warnings:
            return plan, result

        # Attempt repairs
        repaired = plan.model_copy(deep=True)

        # Repair 1: Remove unknown field references
        source_field_ids = {f.id for f in screen.fields}
        for section in repaired.sections:
            original_count = len(section.field_ids)
            section.field_ids = [fid for fid in section.field_ids if fid in source_field_ids]
            removed = original_count - len(section.field_ids)
            if removed:
                result.repairs_applied.append(
                    f"Removed {removed} unknown field(s) from section '{section.id}'"
                )

        # Repair 2: Remove unknown action references
        source_action_ids = {a.id for a in screen.actions}
        original_actions = len(repaired.actions)
        repaired.actions = [a for a in repaired.actions if a.action_id in source_action_ids]
        removed_actions = original_actions - len(repaired.actions)
        if removed_actions:
            result.repairs_applied.append(f"Removed {removed_actions} unknown action reference(s)")

        # Repair 3: Replace unsupported components with defaults
        for section in repaired.sections:
            if section.component_type and section.component_type not in SUPPORTED_COMPONENTS:
                old = section.component_type
                section.component_type = "card"
                result.repairs_applied.append(
                    f"Replaced unsupported component '{old}' with 'card' in section '{section.id}'"
                )

        # Repair 4: Add missing visible fields to a catch-all section
        all_placed = set()
        for section in repaired.sections:
            all_placed.update(section.field_ids)

        visible_missing = {
            f.id for f in screen.fields
            if f.visible and f.field_type.value != "label" and f.id not in all_placed
        }
        if visible_missing:
            repaired.sections.append(UISectionPlan(
                id="additional_fields",
                title="Additional Information",
                field_ids=sorted(visible_missing),
                component_type="card",
                collapsible=True,
                default_collapsed=True,
            ))
            result.repairs_applied.append(
                f"Added {len(visible_missing)} missing field(s) to 'Additional Information' section"
            )

        # Repair 5: Add missing actions
        placed_actions = {a.action_id for a in repaired.actions}
        missing_action_ids = source_action_ids - placed_actions
        for aid in missing_action_ids:
            repaired.actions.append(UIActionPlan(
                action_id=aid,
                priority=ActionPriority.SECONDARY,
                placement="toolbar",
            ))
            result.repairs_applied.append(f"Added missing action '{aid}' to toolbar")

        # Re-validate after repairs
        re_result = self.validate(repaired, screen)
        result.is_valid = re_result.is_valid
        result.errors = re_result.errors

        if result.repairs_applied:
            logger.info(
                "Applied %d repair(s) to LLM plan for screen '%s'",
                len(result.repairs_applied), screen.id,
            )

        return repaired, result
