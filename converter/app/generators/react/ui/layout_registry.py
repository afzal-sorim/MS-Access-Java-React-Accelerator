"""Layout Registry — supported page types and layout configurations.

Provides validation and compatibility checking between page types,
layout types, and navigation patterns.
"""
from __future__ import annotations

from .models import PageType, LayoutType, NavigationType


# Which layouts are valid for each page type
PAGE_LAYOUT_COMPATIBILITY: dict[PageType, set[LayoutType]] = {
    PageType.DASHBOARD: {
        LayoutType.CARD_GRID, LayoutType.TWO_COLUMN, LayoutType.THREE_COLUMN,
        LayoutType.SINGLE_COLUMN,
    },
    PageType.LIST: {
        LayoutType.TABLE, LayoutType.CARD_GRID, LayoutType.SINGLE_COLUMN,
    },
    PageType.DETAIL: {
        LayoutType.SINGLE_COLUMN, LayoutType.TWO_COLUMN, LayoutType.TABS,
        LayoutType.ACCORDION,
    },
    PageType.FORM: {
        LayoutType.SINGLE_COLUMN, LayoutType.TWO_COLUMN, LayoutType.STEPPER,
        LayoutType.TABS, LayoutType.ACCORDION,
    },
    PageType.MASTER_DETAIL: {
        LayoutType.SPLIT_VIEW, LayoutType.SIDEBAR_DETAIL, LayoutType.TABS,
    },
    PageType.SEARCH: {
        LayoutType.SINGLE_COLUMN, LayoutType.TABLE, LayoutType.CARD_GRID,
    },
    PageType.WIZARD: {
        LayoutType.STEPPER, LayoutType.SINGLE_COLUMN,
    },
    PageType.SETTINGS: {
        LayoutType.SINGLE_COLUMN, LayoutType.TABS, LayoutType.ACCORDION,
    },
    PageType.REPORT: {
        LayoutType.TABLE, LayoutType.SINGLE_COLUMN,
    },
    PageType.PROFILE: {
        LayoutType.SINGLE_COLUMN, LayoutType.TWO_COLUMN, LayoutType.TABS,
    },
    PageType.KANBAN: {
        LayoutType.CARD_GRID, LayoutType.THREE_COLUMN,
    },
    PageType.CALENDAR: {
        LayoutType.SINGLE_COLUMN, LayoutType.CARD_GRID,
    },
    PageType.TIMELINE: {
        LayoutType.SINGLE_COLUMN,
    },
}


# Default layout for each page type
DEFAULT_LAYOUT: dict[PageType, LayoutType] = {
    PageType.DASHBOARD: LayoutType.CARD_GRID,
    PageType.LIST: LayoutType.TABLE,
    PageType.DETAIL: LayoutType.SINGLE_COLUMN,
    PageType.FORM: LayoutType.SINGLE_COLUMN,
    PageType.MASTER_DETAIL: LayoutType.SPLIT_VIEW,
    PageType.SEARCH: LayoutType.TABLE,
    PageType.WIZARD: LayoutType.STEPPER,
    PageType.SETTINGS: LayoutType.TABS,
    PageType.REPORT: LayoutType.TABLE,
    PageType.PROFILE: LayoutType.TWO_COLUMN,
    PageType.KANBAN: LayoutType.CARD_GRID,
    PageType.CALENDAR: LayoutType.SINGLE_COLUMN,
    PageType.TIMELINE: LayoutType.SINGLE_COLUMN,
}


# Default navigation for each page type
DEFAULT_NAVIGATION: dict[PageType, NavigationType] = {
    PageType.DASHBOARD: NavigationType.SIDEBAR,
    PageType.LIST: NavigationType.TOP_NAVBAR,
    PageType.DETAIL: NavigationType.BREADCRUMB,
    PageType.FORM: NavigationType.BREADCRUMB,
    PageType.MASTER_DETAIL: NavigationType.SIDEBAR,
    PageType.SEARCH: NavigationType.TOP_NAVBAR,
    PageType.WIZARD: NavigationType.TOP_NAVBAR,
    PageType.SETTINGS: NavigationType.SIDEBAR,
    PageType.REPORT: NavigationType.TOP_NAVBAR,
    PageType.PROFILE: NavigationType.TOP_NAVBAR,
}


def is_layout_compatible(page_type: PageType, layout: LayoutType) -> bool:
    """Check if a layout is valid for the given page type."""
    allowed = PAGE_LAYOUT_COMPATIBILITY.get(page_type, set())
    return layout in allowed


def get_default_layout(page_type: PageType) -> LayoutType:
    """Get the default layout for a page type."""
    return DEFAULT_LAYOUT.get(page_type, LayoutType.SINGLE_COLUMN)


def get_default_navigation(page_type: PageType) -> NavigationType:
    """Get the default navigation for a page type."""
    return DEFAULT_NAVIGATION.get(page_type, NavigationType.TOP_NAVBAR)


def get_compatible_layouts(page_type: PageType) -> list[LayoutType]:
    """Get all compatible layouts for a page type."""
    return sorted(PAGE_LAYOUT_COMPATIBILITY.get(page_type, set()), key=lambda x: x.value)
