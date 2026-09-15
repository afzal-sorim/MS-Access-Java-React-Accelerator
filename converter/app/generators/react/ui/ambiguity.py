"""Ambiguity Analyzer — calculates complexity/ambiguity scores for Access forms.

Determines whether a form is simple enough for deterministic transformation
or complex enough to benefit from LLM-assisted UI planning.
"""
from __future__ import annotations

import re
from dataclasses import dataclass

from .models import UIScreen


@dataclass
class AmbiguityResult:
    """Result of ambiguity analysis for a single screen."""
    screen_id: str
    score: float                      # 0.0 to 1.0
    factors: dict[str, float]         # factor_name → contribution
    requires_llm: bool                # score >= threshold
    explanation: str                  # human-readable explanation

    @property
    def confidence_label(self) -> str:
        if self.score < 0.30:
            return "high_confidence"
        if self.score < 0.55:
            return "moderate_confidence"
        if self.score < 0.75:
            return "low_confidence"
        return "very_low_confidence"


# Default threshold: screens with ambiguity >= 0.55 get LLM assistance
DEFAULT_AMBIGUITY_THRESHOLD = 0.55


class AmbiguityAnalyzer:
    """Scores form complexity/ambiguity to decide deterministic vs LLM path."""

    def __init__(self, threshold: float = DEFAULT_AMBIGUITY_THRESHOLD):
        self.threshold = threshold

    def analyze(self, screen: UIScreen) -> AmbiguityResult:
        """Calculate the ambiguity score for a screen.

        Each factor contributes a weighted score. The total is clamped to [0, 1].
        """
        factors: dict[str, float] = {}

        # Factor 1: Unknown/ambiguous form type (no record source kind)
        if not screen.record_source_kind or screen.record_source_kind == "NONE":
            if screen.is_bound:
                factors["ambiguous_source"] = 0.10
            elif screen.field_count > 3 or screen.button_count > 3:
                factors["complex_unbound"] = 0.12

        # Factor 2: Multiple subforms (master-detail complexity)
        if screen.subform_count >= 3:
            factors["many_subforms"] = 0.18
        elif screen.subform_count == 2:
            factors["multiple_subforms"] = 0.12
        elif screen.subform_count == 1:
            factors["single_subform"] = 0.05

        # Factor 3: High field count
        if screen.field_count > 25:
            factors["very_high_fields"] = 0.15
        elif screen.field_count > 15:
            factors["high_fields"] = 0.10
        elif screen.field_count > 8:
            factors["moderate_fields"] = 0.05

        # Factor 4: Tab controls
        if screen.tabs > 3:
            factors["many_tabs"] = 0.12
        elif screen.tabs > 0:
            factors["has_tabs"] = 0.08

        # Factor 5: Many command buttons (complex UI interactions)
        if screen.button_count > 8:
            factors["many_buttons"] = 0.12
        elif screen.button_count > 5:
            factors["several_buttons"] = 0.08
        elif screen.button_count > 3:
            factors["some_buttons"] = 0.04

        # Factor 6: Complex VBA
        if screen.vba_complexity == "complex":
            factors["complex_vba"] = 0.12
        elif screen.vba_complexity == "moderate":
            factors["moderate_vba"] = 0.06

        # Factor 7: Many relationships
        if len(screen.relationships) > 4:
            factors["many_relationships"] = 0.10
        elif len(screen.relationships) > 2:
            factors["some_relationships"] = 0.05

        # Factor 8: Mixed bound/unbound controls
        bound = sum(1 for f in screen.fields if f.data_source)
        unbound = sum(1 for f in screen.fields if not f.data_source and f.field_type.value != "label")
        if bound > 0 and unbound > 0:
            mix_ratio = min(bound, unbound) / max(bound, unbound) if max(bound, unbound) > 0 else 0
            if mix_ratio > 0.3:
                factors["mixed_bound_unbound"] = 0.08

        # Factor 9: Computed/expression fields
        computed = sum(1 for f in screen.fields if f.is_expression)
        if computed > 5:
            factors["many_expressions"] = 0.08
        elif computed > 2:
            factors["some_expressions"] = 0.04

        # Factor 10: Events (beyond simple click handlers)
        if screen.has_events:
            event_count = len([a for a in screen.actions if a.vba_handler])
            if event_count > 5:
                factors["complex_events"] = 0.08
            elif event_count > 2:
                factors["some_events"] = 0.04

        # Calculate total score, clamped to [0, 1]
        total = min(sum(factors.values()), 1.0)
        requires_llm = total >= self.threshold

        # Build explanation
        if not factors:
            explanation = "Simple form — fully deterministic mapping."
        else:
            top_factors = sorted(factors.items(), key=lambda x: -x[1])[:3]
            factor_desc = ", ".join(f"{k}: {v:.0%}" for k, v in top_factors)
            if requires_llm:
                explanation = f"Complex form (score: {total:.2f}) — LLM-assisted layout recommended. Top factors: {factor_desc}"
            else:
                explanation = f"Moderate form (score: {total:.2f}) — deterministic mapping sufficient. Factors: {factor_desc}"

        return AmbiguityResult(
            screen_id=screen.id,
            score=total,
            factors=factors,
            requires_llm=requires_llm,
            explanation=explanation,
        )

    def analyze_all(self, screens: list[UIScreen]) -> list[AmbiguityResult]:
        """Analyze all screens and return sorted results."""
        results = [self.analyze(s) for s in screens]
        return sorted(results, key=lambda r: -r.score)
