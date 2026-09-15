"""UI Transformation Engine — central orchestrator for the UI modernization pipeline.

Orchestrates the full flow:
  UIScreen → Ambiguity Analysis → Deterministic or LLM → Validate → UIPresentation

Supports three reasoning modes:
  - "automatic": Use ambiguity score to decide (default)
  - "deterministic": Always use rule-based transformation
  - "llm": Always attempt LLM (with deterministic fallback)
"""
from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Optional

from ....ir.models import ApplicationIR
from .models import UIScreen, UIPresentation, InfoLevel
from .screen_builder import ScreenBuilder
from .ambiguity import AmbiguityAnalyzer, AmbiguityResult
from .deterministic import DeterministicTransformer
from .capability_validator import CapabilityValidator

logger = logging.getLogger("converter.ui.engine")


class UITransformationEngine:
    """Central orchestrator for the UI transformation pipeline.

    Usage:
        engine = UITransformationEngine(app_ir, ui_style="modern_dashboard")
        presentations = engine.transform_all()
    """

    def __init__(
        self,
        app_ir: ApplicationIR,
        ui_style: str = "classic",
        ui_reasoning: str = "automatic",
        ui_debug: bool = False,
    ):
        self.app_ir = app_ir
        self.ui_style = ui_style
        self.ui_reasoning = ui_reasoning
        self.ui_debug = ui_debug

        # Build subsystem instances
        self.screen_builder = ScreenBuilder(app_ir)
        self.ambiguity_analyzer = AmbiguityAnalyzer()
        self.deterministic = DeterministicTransformer()
        self.capability_validator = CapabilityValidator()
        self._llm_planner = None

        # Results storage
        self.screens: list[UIScreen] = []
        self.presentations: list[UIPresentation] = []
        self.ambiguity_results: list[AmbiguityResult] = []
        self.decisions: list[dict] = []

    def _get_llm_planner(self):
        """Lazy-load the LLM planner (only when needed)."""
        if self._llm_planner is None:
            try:
                from .llm.planner import LLMUIPlanner
                self._llm_planner = LLMUIPlanner()
            except Exception as e:
                logger.warning("Could not initialize LLM UI planner: %s", e)
                self._llm_planner = False  # Mark as unavailable
        return self._llm_planner if self._llm_planner is not False else None

    def transform_all(self) -> list[UIPresentation]:
        """Transform all forms in the ApplicationIR into UIPresentation models.

        Returns a list of UIPresentation models ready for theme rendering.
        """
        # Step 1: Build UIScreens from all forms
        self.screens = self.screen_builder.build_all()
        logger.info("Built %d UIScreens from ApplicationIR forms", len(self.screens))

        # Step 2: Analyze ambiguity for all screens
        self.ambiguity_results = self.ambiguity_analyzer.analyze_all(self.screens)

        # Step 3: Transform each screen
        self.presentations = []
        self.decisions = []
        ambiguity_map = {r.screen_id: r for r in self.ambiguity_results}

        for screen in self.screens:
            ambiguity = ambiguity_map.get(screen.id)
            presentation = self._transform_screen(screen, ambiguity)
            self.presentations.append(presentation)

        # Step 4: Validate capability preservation
        reports = self.capability_validator.validate_all(self.screens, self.presentations)
        for report in reports:
            if not report.is_complete:
                logger.warning(
                    "Capability gap in screen '%s': fields=%.0f%%, actions=%.0f%%, dropped_fields=%s",
                    report.screen_id,
                    report.field_coverage * 100,
                    report.action_coverage * 100,
                    report.dropped_fields[:3],
                )

        logger.info(
            "UI transformation complete: %d screens, style=%s, reasoning=%s",
            len(self.presentations), self.ui_style, self.ui_reasoning,
        )

        return self.presentations

    def _transform_screen(
        self, screen: UIScreen, ambiguity: Optional[AmbiguityResult]
    ) -> UIPresentation:
        """Transform a single screen using the configured reasoning mode."""
        decision = {
            "screen_id": screen.id,
            "screen_name": screen.name,
            "ambiguity_score": ambiguity.score if ambiguity else 0.0,
            "mode": "deterministic",
            "page_type": None,
            "confidence": 1.0,
            "llm_attempted": False,
            "llm_succeeded": False,
        }

        presentation = None

        # Decide whether to use LLM
        use_llm = False
        if self.ui_reasoning == "llm":
            use_llm = True
        elif self.ui_reasoning == "automatic" and ambiguity and ambiguity.requires_llm:
            use_llm = True

        if use_llm:
            decision["llm_attempted"] = True
            planner = self._get_llm_planner()

            if planner:
                try:
                    plan = planner.plan(screen, self.ui_style)
                    if plan:
                        # Build presentation from LLM plan
                        presentation = self._plan_to_presentation(screen, plan)
                        decision["mode"] = "llm"
                        decision["llm_succeeded"] = True
                        decision["confidence"] = plan.confidence
                        decision["reasoning"] = plan.reasoning
                        logger.info(
                            "LLM plan applied for screen '%s': page_type=%s",
                            screen.id, plan.page_type.value,
                        )
                except Exception as e:
                    logger.warning("LLM planning failed for screen '%s': %s", screen.id, e)

        # Fallback to deterministic
        if presentation is None:
            presentation = self.deterministic.transform(screen, self.ui_style)
            decision["mode"] = "deterministic"

        decision["page_type"] = presentation.page_type.value
        self.decisions.append(decision)

        return presentation

    def _plan_to_presentation(self, screen: UIScreen, plan) -> UIPresentation:
        """Convert a UILayoutPlan into a UIPresentation."""
        from .models import UILayoutPlan

        return UIPresentation(
            screen_id=screen.id,
            screen_name=screen.name,
            page_type=plan.page_type,
            layout=plan.layout,
            navigation=plan.navigation,
            sections=plan.sections,
            actions=screen.actions,
            fields=screen.fields,
            relationships=screen.relationships,
            subforms=screen.subforms,
            responsive=plan.responsive,
            information_hierarchy={f.id: f.info_level.value for f in screen.fields},
            record_source=screen.record_source,
            is_bound=screen.is_bound,
            back_color=screen.back_color,
            fore_color=screen.fore_color,
            section_colors=screen.section_colors,
            confidence=plan.confidence,
            decision_mode=plan.decision_mode,
        )

    def write_debug_artifacts(self, output_dir: Path) -> None:
        """Write debug artifacts for inspection (when ui_debug=true)."""
        if not self.ui_debug:
            return

        debug_dir = output_dir / ".ui"
        debug_dir.mkdir(parents=True, exist_ok=True)

        # Semantic models
        screens_data = [s.model_dump() for s in self.screens]
        (debug_dir / "semantic-model.json").write_text(
            json.dumps(screens_data, indent=2, default=str), encoding="utf-8"
        )

        # Transformation decisions
        (debug_dir / "transformation-decisions.json").write_text(
            json.dumps(self.decisions, indent=2, default=str), encoding="utf-8"
        )

        # Ambiguity scores
        ambiguity_data = [
            {
                "screen_id": r.screen_id,
                "score": r.score,
                "requires_llm": r.requires_llm,
                "confidence_label": r.confidence_label,
                "explanation": r.explanation,
                "factors": r.factors,
            }
            for r in self.ambiguity_results
        ]
        (debug_dir / "ambiguity-scores.json").write_text(
            json.dumps(ambiguity_data, indent=2, default=str), encoding="utf-8"
        )

        # Capability coverage
        reports = self.capability_validator.validate_all(self.screens, self.presentations)
        coverage_data = [
            {
                "screen_id": r.screen_id,
                "field_coverage": f"{r.field_coverage:.0%}",
                "action_coverage": f"{r.action_coverage:.0%}",
                "is_complete": r.is_complete,
                "dropped_fields": r.dropped_fields,
                "dropped_actions": r.dropped_actions,
            }
            for r in reports
        ]
        (debug_dir / "capability-coverage.json").write_text(
            json.dumps(coverage_data, indent=2, default=str), encoding="utf-8"
        )

        logger.info("Debug artifacts written to %s", debug_dir)
