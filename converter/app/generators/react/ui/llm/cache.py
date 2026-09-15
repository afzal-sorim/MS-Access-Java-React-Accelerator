"""LLM Plan Cache — deterministic hash-based caching of UI plans.

Cache key = hash(UIScreen metadata + style + prompt_version).
Same Access app + same style = same plan without re-spending tokens.
"""
from __future__ import annotations

import hashlib
import json
import logging
from typing import Optional

from ..models import UIScreen, UILayoutPlan

logger = logging.getLogger("converter.ui.llm.cache")


class PlanCache:
    """In-memory cache for LLM-generated UI plans."""

    def __init__(self):
        self._cache: dict[str, UILayoutPlan] = {}

    def cache_key(self, screen: UIScreen, style: str, prompt_version: str) -> str:
        """Generate a deterministic cache key."""
        data = {
            "screen_id": screen.id,
            "field_count": screen.field_count,
            "fields": sorted(f.id for f in screen.fields),
            "actions": sorted(a.id for a in screen.actions),
            "subforms": sorted(sf.id for sf in screen.subforms),
            "is_bound": screen.is_bound,
            "record_source": screen.record_source,
            "tabs": screen.tabs,
            "style": style,
            "prompt_version": prompt_version,
        }
        serialized = json.dumps(data, sort_keys=True)
        return hashlib.sha256(serialized.encode()).hexdigest()

    def get(self, screen: UIScreen, style: str, prompt_version: str) -> Optional[UILayoutPlan]:
        """Retrieve a cached plan if available."""
        key = self.cache_key(screen, style, prompt_version)
        plan = self._cache.get(key)
        if plan:
            logger.info("UI plan cache hit for screen '%s' (style: %s)", screen.id, style)
        return plan

    def put(self, screen: UIScreen, style: str, prompt_version: str, plan: UILayoutPlan) -> None:
        """Store a plan in the cache."""
        key = self.cache_key(screen, style, prompt_version)
        self._cache[key] = plan
        logger.info("Cached UI plan for screen '%s' (style: %s)", screen.id, style)

    def clear(self) -> None:
        """Clear the entire cache."""
        self._cache.clear()

    @property
    def size(self) -> int:
        return len(self._cache)
