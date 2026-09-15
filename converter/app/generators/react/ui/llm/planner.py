"""LLM UI Planner — constrained LLM-assisted layout planning.

Uses the EXISTING LLM provider abstraction (converter.app.llm.provider)
to generate structured UILayoutPlans. Never generates JSX or code directly.

Includes:
- Prompt construction with screen metadata + style rules
- Structured JSON output parsing
- Validation and repair pipeline
- Caching to avoid redundant LLM calls
- Mandatory fallback to deterministic transformation on any failure
"""
from __future__ import annotations

import json
import logging
from typing import Optional

from ..models import (
    UIScreen, UILayoutPlan, UISectionPlan, UIActionPlan,
    PageType, LayoutType, NavigationType, ResponsiveSpec,
    ActionPriority,
)
from ..component_registry import SUPPORTED_COMPONENTS
from .prompts import SYSTEM_PROMPT, PROMPT_VERSION, build_user_prompt
from .validator import PlanValidator
from .cache import PlanCache

logger = logging.getLogger("converter.ui.llm.planner")

# Maximum LLM attempts before falling back to deterministic
MAX_LLM_ATTEMPTS = 2


class LLMUIPlanner:
    """Constrained LLM planner that produces UILayoutPlans.

    Uses the existing converter LLM provider — does NOT create its own client.
    """

    def __init__(self):
        self._validator = PlanValidator()
        self._cache = PlanCache()
        self._provider = None

    def _get_provider(self):
        """Lazy-load the existing LLM provider."""
        if self._provider is None:
            try:
                from .....llm.provider import get_default_provider
                self._provider = get_default_provider()
                logger.info("LLM UI Planner connected to provider: %s", self._provider.config.model)
            except Exception as e:
                logger.warning("Failed to initialize LLM provider: %s", e)
                raise
        return self._provider

    def plan(self, screen: UIScreen, style: str) -> Optional[UILayoutPlan]:
        """Generate a UILayoutPlan for a screen using the LLM.

        Returns None if all attempts fail (caller should fall back to deterministic).
        """
        # Check cache first
        cached = self._cache.get(screen, style, PROMPT_VERSION)
        if cached:
            return cached

        # Build prompt
        user_prompt = build_user_prompt(screen, style, SUPPORTED_COMPONENTS)

        for attempt in range(1, MAX_LLM_ATTEMPTS + 1):
            try:
                logger.info(
                    "LLM UI planning attempt %d/%d for screen '%s' (style: %s)",
                    attempt, MAX_LLM_ATTEMPTS, screen.id, style,
                )

                provider = self._get_provider()

                # Use structured generation
                response = provider.generate(
                    prompt=user_prompt,
                    system_prompt=SYSTEM_PROMPT,
                    json_mode=True,
                )

                # Parse JSON response
                raw_plan = json.loads(response.content)
                plan = self._parse_plan(raw_plan)

                if plan is None:
                    logger.warning("Failed to parse LLM response for screen '%s'", screen.id)
                    if attempt < MAX_LLM_ATTEMPTS:
                        # Add validation errors to retry prompt
                        user_prompt += "\n\nPrevious response was invalid JSON or missing required fields. Please try again."
                        continue
                    return None

                # Validate and repair
                repaired_plan, validation = self._validator.validate_and_repair(plan, screen)

                if validation.is_valid:
                    repaired_plan.decision_mode = "llm"
                    self._cache.put(screen, style, PROMPT_VERSION, repaired_plan)
                    logger.info(
                        "LLM plan accepted for screen '%s': page_type=%s, layout=%s, confidence=%.2f, repairs=%d",
                        screen.id, repaired_plan.page_type.value, repaired_plan.layout.value,
                        repaired_plan.confidence, len(validation.repairs_applied),
                    )
                    return repaired_plan
                else:
                    logger.warning(
                        "LLM plan validation failed for screen '%s' (attempt %d): %s",
                        screen.id, attempt, "; ".join(validation.errors),
                    )
                    if attempt < MAX_LLM_ATTEMPTS:
                        user_prompt += f"\n\nPrevious response had validation errors: {'; '.join(validation.errors)}. Please fix these issues."

            except json.JSONDecodeError as e:
                logger.warning("LLM returned invalid JSON for screen '%s': %s", screen.id, e)
            except Exception as e:
                logger.error("LLM call failed for screen '%s': %s", screen.id, e)
                return None  # Don't retry on connection/provider errors

        logger.warning("All LLM attempts exhausted for screen '%s', falling back to deterministic", screen.id)
        return None

    def _parse_plan(self, raw: dict) -> Optional[UILayoutPlan]:
        """Parse raw JSON dict into a UILayoutPlan model."""
        try:
            # Parse page type
            page_type = PageType(raw.get("page_type", "form"))

            # Parse layout
            layout = LayoutType(raw.get("layout", "single_column"))

            # Parse navigation
            nav_str = raw.get("navigation")
            navigation = NavigationType(nav_str) if nav_str else None

            # Parse sections
            sections = []
            for s in raw.get("sections", []):
                sections.append(UISectionPlan(
                    id=s.get("id", "unknown"),
                    title=s.get("title"),
                    layout=LayoutType(s.get("layout", "single_column")),
                    field_ids=s.get("field_ids", []),
                    component_type=s.get("component_type"),
                    collapsible=s.get("collapsible", False),
                    default_collapsed=s.get("default_collapsed", False),
                ))

            # Parse actions
            actions = []
            for a in raw.get("actions", []):
                actions.append(UIActionPlan(
                    action_id=a.get("action_id", ""),
                    priority=ActionPriority(a.get("priority", "secondary")),
                    placement=a.get("placement", "toolbar"),
                ))

            # Parse responsive
            responsive = None
            resp_raw = raw.get("responsive")
            if resp_raw and isinstance(resp_raw, dict):
                responsive = ResponsiveSpec(
                    mobile=resp_raw.get("mobile", "stack"),
                    tablet=resp_raw.get("tablet", "stack"),
                    desktop=resp_raw.get("desktop", "split"),
                )

            return UILayoutPlan(
                page_type=page_type,
                layout=layout,
                navigation=navigation,
                sections=sections,
                actions=actions,
                responsive=responsive,
                confidence=float(raw.get("confidence", 0.5)),
                reasoning=raw.get("reasoning"),
                decision_mode="llm",
            )

        except (ValueError, KeyError, TypeError) as e:
            logger.warning("Failed to parse UILayoutPlan from raw JSON: %s", e)
            return None
