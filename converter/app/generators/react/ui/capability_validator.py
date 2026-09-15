"""Capability Validator — ensures no source fields/actions are dropped during transformation.

Before-and-after validation that every field and action from the source UIScreen
is preserved in the output UIPresentation.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from .models import UIScreen, UIPresentation


@dataclass
class CapabilityReport:
    """Report on capability preservation."""
    screen_id: str
    total_source_fields: int = 0
    total_source_actions: int = 0
    preserved_fields: int = 0
    preserved_actions: int = 0
    dropped_fields: list[str] = field(default_factory=list)
    dropped_actions: list[str] = field(default_factory=list)
    field_coverage: float = 1.0
    action_coverage: float = 1.0
    is_complete: bool = True


class CapabilityValidator:
    """Validates that all source capabilities survive transformation."""

    def validate(self, screen: UIScreen, presentation: UIPresentation) -> CapabilityReport:
        """Validate field and action preservation."""
        report = CapabilityReport(screen_id=screen.id)

        # Check fields
        source_field_ids = {f.id for f in screen.fields if f.visible and f.field_type.value != "label"}
        presentation_field_ids = {f.id for f in presentation.fields}

        report.total_source_fields = len(source_field_ids)
        report.preserved_fields = len(source_field_ids & presentation_field_ids)
        report.dropped_fields = sorted(source_field_ids - presentation_field_ids)

        if source_field_ids:
            report.field_coverage = report.preserved_fields / len(source_field_ids)

        # Check actions
        source_action_ids = {a.id for a in screen.actions}
        presentation_action_ids = {a.id for a in presentation.actions}

        report.total_source_actions = len(source_action_ids)
        report.preserved_actions = len(source_action_ids & presentation_action_ids)
        report.dropped_actions = sorted(source_action_ids - presentation_action_ids)

        if source_action_ids:
            report.action_coverage = report.preserved_actions / len(source_action_ids)

        report.is_complete = (
            report.field_coverage >= 1.0 and report.action_coverage >= 1.0
        )

        return report

    def validate_all(
        self, screens: list[UIScreen], presentations: list[UIPresentation]
    ) -> list[CapabilityReport]:
        """Validate all screens against their presentations."""
        pres_map = {p.screen_id: p for p in presentations}
        reports = []
        for screen in screens:
            pres = pres_map.get(screen.id)
            if pres:
                reports.append(self.validate(screen, pres))
        return reports
