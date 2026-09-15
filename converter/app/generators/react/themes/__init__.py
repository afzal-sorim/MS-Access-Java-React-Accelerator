"""Design System Themes — pluggable UI rendering for generated React apps.

Each theme transforms UIPresentation into concrete JSX + CSS code.
"""
from __future__ import annotations

from .base import Theme
from .classic import ClassicTheme
from .modern_dashboard import ModernDashboardTheme
from .material import MaterialTheme
from .exact import ExactLayoutTheme


_THEME_REGISTRY: dict[str, type[Theme]] = {
    "classic": ClassicTheme,
    "modern_dashboard": ModernDashboardTheme,
    "material": MaterialTheme,
    "exact": ExactLayoutTheme,
}


def get_theme(style_key: str) -> Theme:
    """Get a theme instance by style key.

    Falls back to ClassicTheme if the requested style is unknown.
    """
    theme_cls = _THEME_REGISTRY.get(style_key.lower().strip(), ClassicTheme)
    return theme_cls()


def list_themes() -> list[dict[str, str]]:
    """List all available themes with metadata."""
    return [
        {
            "key": "classic",
            "name": "Classic Enterprise",
            "description": "Clean, professional design with top navigation and traditional data tables.",
        },
        {
            "key": "modern_dashboard",
            "name": "Modern Dashboard",
            "description": "Dark sidebar navigation with card-based layouts, gradient accents, and stat widgets.",
        },
        {
            "key": "material",
            "name": "Material Design",
            "description": "Google Material-inspired with elevation shadows, outlined inputs, and responsive grid.",
        },
        {
            "key": "exact",
            "name": "Exact Layout (Access replica)",
            "description": "1:1 pixel-perfect replication of MS Access layouts using absolute positioning.",
        },
    ]
