"""Deterministic Transformer — rule-based page type classification and layout assignment.

Uses heuristics derived from the Access form structure to classify pages
WITHOUT calling the LLM. This handles the majority of simple/standard forms
and serves as the fallback when the LLM is unavailable.
"""
from __future__ import annotations

from .models import (
    UIScreen, UIPresentation, UILayoutPlan, UISectionPlan, UIActionPlan,
    PageType, LayoutType, NavigationType, ResponsiveSpec,
    InfoLevel, ActionPriority,
)
from .layout_registry import get_default_layout, get_default_navigation


class DeterministicTransformer:
    """Rule-based UI transformation for simple/standard Access forms."""

    def transform(self, screen: UIScreen, style: str = "classic") -> UIPresentation:
        """Transform a UIScreen into a UIPresentation using deterministic rules."""
        page_type = self._classify_page_type(screen)
        layout = self._select_layout(screen, page_type)
        navigation = get_default_navigation(page_type)
        sections = self._build_sections(screen, page_type, layout)
        action_plans = self._plan_actions(screen, page_type)
        info_hierarchy = self._build_info_hierarchy(screen)
        responsive = self._build_responsive(page_type, layout)

        return UIPresentation(
            screen_id=screen.id,
            screen_name=screen.name,
            page_type=page_type,
            layout=layout,
            navigation=navigation,
            sections=sections,
            actions=screen.actions,
            fields=screen.fields,
            relationships=screen.relationships,
            subforms=screen.subforms,
            responsive=responsive,
            information_hierarchy=info_hierarchy,
            record_source=screen.record_source,
            is_bound=screen.is_bound,
            confidence=1.0,
            decision_mode="deterministic",
        )

    def _classify_page_type(self, screen: UIScreen) -> PageType:
        """Classify an Access form into a page archetype using heuristics."""
        # Rule 1: Unbound forms (no record source)
        if not screen.is_bound:
            if screen.button_count > 3 and screen.field_count < 5:
                return PageType.DASHBOARD  # switchboard / navigation form
            if screen.field_count == 0 and screen.button_count > 0:
                return PageType.DASHBOARD
            return PageType.SETTINGS  # utility / config form

        # Rule 2: Master-detail (has subforms with relationships)
        if screen.subform_count > 0 and screen.field_count > 3:
            return PageType.MASTER_DETAIL

        # Rule 3: List/datasheet forms
        has_list_controls = any(
            f.field_type.value == "select" and f.row_source
            for f in screen.fields
        )
        if has_list_controls and screen.field_count < 8:
            return PageType.LIST

        # Rule 4: Search forms (lots of filters + results)
        search_actions = [a for a in screen.actions if a.intent.value in ("search", "filter")]
        if len(search_actions) >= 2:
            return PageType.SEARCH

        # Rule 5: Tabbed forms → detail page
        if screen.is_tabbed:
            return PageType.DETAIL

        # Rule 6: Large forms → detail with sections
        if screen.field_count > 15:
            return PageType.DETAIL

        # Rule 7: Standard CRUD form
        if screen.is_bound and screen.field_count > 0:
            return PageType.FORM

        return PageType.FORM

    def _select_layout(self, screen: UIScreen, page_type: PageType) -> LayoutType:
        """Select the best layout for the classified page type."""
        if page_type == PageType.MASTER_DETAIL:
            return LayoutType.SPLIT_VIEW

        if page_type == PageType.LIST:
            return LayoutType.TABLE

        if page_type == PageType.DASHBOARD:
            if screen.button_count > 6:
                return LayoutType.CARD_GRID
            return LayoutType.CARD_GRID

        if page_type == PageType.DETAIL:
            if screen.is_tabbed:
                return LayoutType.TABS
            if screen.field_count > 20:
                return LayoutType.ACCORDION
            return LayoutType.TWO_COLUMN

        if page_type == PageType.FORM:
            if screen.field_count > 10:
                return LayoutType.TWO_COLUMN
            return LayoutType.SINGLE_COLUMN

        if page_type == PageType.SEARCH:
            return LayoutType.TABLE

        return get_default_layout(page_type)

    def _build_sections(
        self, screen: UIScreen, page_type: PageType, layout: LayoutType
    ) -> list[UISectionPlan]:
        """Build logical sections for the page layout."""
        sections = []

        # Group fields by info level
        primary_fields = [f for f in screen.fields if f.info_level == InfoLevel.PRIMARY]
        secondary_fields = [f for f in screen.fields if f.info_level == InfoLevel.SECONDARY]
        metadata_fields = [f for f in screen.fields if f.info_level == InfoLevel.METADATA]

        if page_type == PageType.MASTER_DETAIL:
            # Main form fields
            sections.append(UISectionPlan(
                id="main_details",
                title=screen.name,
                layout=LayoutType.TWO_COLUMN if len(primary_fields) > 4 else LayoutType.SINGLE_COLUMN,
                field_ids=[f.id for f in primary_fields],
                component_type="card",
            ))
            # Subform sections
            for sf in screen.subforms:
                sections.append(UISectionPlan(
                    id=f"related_{sf.id}",
                    title=sf.name,
                    layout=LayoutType.TABLE,
                    component_type="data_grid",
                    source=sf.record_source,
                ))

        elif page_type == PageType.DASHBOARD:
            sections.append(UISectionPlan(
                id="dashboard_actions",
                title="Quick Actions",
                layout=LayoutType.CARD_GRID,
                field_ids=[f.id for f in primary_fields],
                component_type="card",
            ))

        elif page_type in (PageType.FORM, PageType.DETAIL):
            # Primary fields section
            if primary_fields:
                sections.append(UISectionPlan(
                    id="primary_info",
                    title=f"{screen.name} Details" if page_type == PageType.DETAIL else None,
                    layout=LayoutType.TWO_COLUMN if len(primary_fields) > 6 else LayoutType.SINGLE_COLUMN,
                    field_ids=[f.id for f in primary_fields],
                    component_type="card",
                ))
            # Secondary fields section (collapsible)
            if secondary_fields:
                sections.append(UISectionPlan(
                    id="secondary_info",
                    title="Additional Information",
                    layout=LayoutType.TWO_COLUMN,
                    field_ids=[f.id for f in secondary_fields],
                    component_type="card",
                    collapsible=True,
                    default_collapsed=True,
                ))
            # Metadata section
            if metadata_fields:
                sections.append(UISectionPlan(
                    id="metadata",
                    title="Record Information",
                    layout=LayoutType.SINGLE_COLUMN,
                    field_ids=[f.id for f in metadata_fields],
                    component_type="card",
                    collapsible=True,
                    default_collapsed=True,
                ))

        elif page_type == PageType.LIST:
            sections.append(UISectionPlan(
                id="data_list",
                title=screen.name,
                layout=LayoutType.TABLE,
                field_ids=[f.id for f in primary_fields[:8]],
                component_type="data_grid",
            ))

        elif page_type == PageType.SEARCH:
            sections.append(UISectionPlan(
                id="search_filters",
                title="Search",
                layout=LayoutType.SINGLE_COLUMN,
                field_ids=[f.id for f in primary_fields if f.field_type.value == "select"],
                component_type="card",
            ))
            sections.append(UISectionPlan(
                id="search_results",
                title="Results",
                layout=LayoutType.TABLE,
                field_ids=[f.id for f in primary_fields if f.field_type.value != "select"],
                component_type="data_grid",
            ))

        else:
            # Fallback: single section with all primary fields
            sections.append(UISectionPlan(
                id="content",
                title=screen.name,
                layout=LayoutType.SINGLE_COLUMN,
                field_ids=[f.id for f in primary_fields],
                component_type="card",
            ))

        return sections

    def _plan_actions(self, screen: UIScreen, page_type: PageType) -> list[UIActionPlan]:
        """Assign placement to actions based on page type."""
        plans = []
        for action in screen.actions:
            if action.priority == ActionPriority.PRIMARY:
                placement = "toolbar" if page_type == PageType.LIST else "footer"
            elif action.priority == ActionPriority.DANGER:
                placement = "menu"  # hide dangerous actions in overflow menu
            elif action.priority == ActionPriority.TERTIARY:
                placement = "menu"
            else:
                placement = "toolbar"

            plans.append(UIActionPlan(
                action_id=action.id,
                priority=action.priority,
                placement=placement,
            ))
        return plans

    def _build_info_hierarchy(self, screen: UIScreen) -> dict[str, str]:
        """Build the information hierarchy mapping."""
        return {f.id: f.info_level.value for f in screen.fields}

    def _build_responsive(self, page_type: PageType, layout: LayoutType) -> ResponsiveSpec:
        """Build responsive behavior specification."""
        if page_type == PageType.MASTER_DETAIL:
            return ResponsiveSpec(mobile="stack", tablet="tabs", desktop="split")
        if layout in (LayoutType.TWO_COLUMN, LayoutType.SPLIT_VIEW):
            return ResponsiveSpec(mobile="stack", tablet="stack", desktop="split")
        if layout == LayoutType.THREE_COLUMN:
            return ResponsiveSpec(mobile="stack", tablet="stack", desktop="split")
        return ResponsiveSpec(mobile="stack", tablet="stack", desktop="stack")
