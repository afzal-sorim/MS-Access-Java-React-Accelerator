"""Intent Analyzer — converts Access button captions + VBA events into semantic ActionIntent.

Uses a layered approach:
  1. VBA event code analysis (most reliable)
  2. Button caption keyword matching
  3. Control name pattern matching
"""
from __future__ import annotations

import re
from typing import Optional

from .models import ActionIntent, ActionPriority


# ────────────────────────────────────── VBA patterns → intent

_VBA_INTENT_PATTERNS: list[tuple[str, ActionIntent]] = [
    # Save / update
    (r"acCmdSaveRecord", ActionIntent.SAVE),
    (r"DoCmd\.Save\b", ActionIntent.SAVE),
    (r"\.Update\b", ActionIntent.SAVE),
    (r"CurrentDb\.Execute.*INSERT", ActionIntent.SAVE),
    (r"CurrentDb\.Execute.*UPDATE", ActionIntent.SAVE),

    # Delete
    (r"acCmdDeleteRecord", ActionIntent.DELETE),
    (r"DoCmd\.RunSQL.*DELETE", ActionIntent.DELETE),
    (r"\.Delete\b", ActionIntent.DELETE),

    # Navigation / open form
    (r"DoCmd\.OpenForm", ActionIntent.OPEN_FORM),
    (r"DoCmd\.OpenReport", ActionIntent.PRINT),
    (r"DoCmd\.GoToRecord.*acNewRec", ActionIntent.ADD_NEW),
    (r"DoCmd\.GoToRecord", ActionIntent.NAVIGATE),
    (r"DoCmd\.FindRecord", ActionIntent.SEARCH),

    # Close
    (r"DoCmd\.Close", ActionIntent.CLOSE),
    (r"DoCmd\.Quit", ActionIntent.CLOSE),

    # Refresh / requery
    (r"\.Requery\b", ActionIntent.REFRESH),
    (r"DoCmd\.RefreshRecord", ActionIntent.REFRESH),

    # Filter / search
    (r"DoCmd\.ApplyFilter", ActionIntent.FILTER),
    (r"DoCmd\.ShowAllRecords", ActionIntent.FILTER),
    (r"DoCmd\.FindNext", ActionIntent.SEARCH),

    # Export / print
    (r"DoCmd\.OutputTo", ActionIntent.EXPORT),
    (r"DoCmd\.TransferSpreadsheet", ActionIntent.EXPORT),
    (r"DoCmd\.TransferText", ActionIntent.EXPORT),
    (r"DoCmd\.PrintOut", ActionIntent.PRINT),
    (r"DoCmd\.SendObject", ActionIntent.EXPORT),

    # Run macro / query
    (r"DoCmd\.RunMacro", ActionIntent.RUN_MACRO),
    (r"DoCmd\.OpenQuery", ActionIntent.RUN_QUERY),
    (r"DoCmd\.RunSQL", ActionIntent.RUN_QUERY),
]

# ────────────────────────────────────── Caption keywords → intent

_CAPTION_KEYWORDS: dict[str, ActionIntent] = {
    # Save
    "save": ActionIntent.SAVE,
    "submit": ActionIntent.SAVE,
    "ok": ActionIntent.SAVE,
    "apply": ActionIntent.SAVE,
    "confirm": ActionIntent.SAVE,
    "update": ActionIntent.SAVE,

    # Delete
    "delete": ActionIntent.DELETE,
    "remove": ActionIntent.DELETE,
    "erase": ActionIntent.DELETE,

    # Cancel / close
    "cancel": ActionIntent.CANCEL,
    "close": ActionIntent.CLOSE,
    "exit": ActionIntent.CLOSE,
    "quit": ActionIntent.CLOSE,
    "back": ActionIntent.NAVIGATE,

    # Search
    "search": ActionIntent.SEARCH,
    "find": ActionIntent.SEARCH,
    "lookup": ActionIntent.SEARCH,

    # Navigation
    "next": ActionIntent.NAVIGATE,
    "previous": ActionIntent.NAVIGATE,
    "prev": ActionIntent.NAVIGATE,
    "first": ActionIntent.NAVIGATE,
    "last": ActionIntent.NAVIGATE,
    "go to": ActionIntent.NAVIGATE,
    "open": ActionIntent.OPEN_FORM,

    # Add new
    "new": ActionIntent.ADD_NEW,
    "add": ActionIntent.ADD_NEW,
    "create": ActionIntent.ADD_NEW,
    "insert": ActionIntent.ADD_NEW,

    # Edit
    "edit": ActionIntent.EDIT,
    "modify": ActionIntent.EDIT,
    "change": ActionIntent.EDIT,

    # Export / print
    "export": ActionIntent.EXPORT,
    "print": ActionIntent.PRINT,
    "report": ActionIntent.PRINT,
    "download": ActionIntent.EXPORT,

    # Filter
    "filter": ActionIntent.FILTER,
    "sort": ActionIntent.SORT,
    "clear filter": ActionIntent.FILTER,

    # Refresh
    "refresh": ActionIntent.REFRESH,
    "reload": ActionIntent.REFRESH,
}


# ────────────────────────────────────── Intent → default priority

_INTENT_PRIORITIES: dict[ActionIntent, ActionPriority] = {
    ActionIntent.SAVE: ActionPriority.PRIMARY,
    ActionIntent.ADD_NEW: ActionPriority.PRIMARY,
    ActionIntent.DELETE: ActionPriority.DANGER,
    ActionIntent.CANCEL: ActionPriority.SECONDARY,
    ActionIntent.CLOSE: ActionPriority.SECONDARY,
    ActionIntent.SEARCH: ActionPriority.SECONDARY,
    ActionIntent.NAVIGATE: ActionPriority.TERTIARY,
    ActionIntent.OPEN_FORM: ActionPriority.SECONDARY,
    ActionIntent.PRINT: ActionPriority.TERTIARY,
    ActionIntent.EXPORT: ActionPriority.TERTIARY,
    ActionIntent.REFRESH: ActionPriority.TERTIARY,
    ActionIntent.EDIT: ActionPriority.SECONDARY,
    ActionIntent.FILTER: ActionPriority.TERTIARY,
    ActionIntent.SORT: ActionPriority.TERTIARY,
    ActionIntent.RUN_MACRO: ActionPriority.SECONDARY,
    ActionIntent.RUN_QUERY: ActionPriority.SECONDARY,
    ActionIntent.CUSTOM: ActionPriority.SECONDARY,
}


def analyze_intent(
    caption: Optional[str] = None,
    control_name: Optional[str] = None,
    vba_code: Optional[str] = None,
    events: Optional[dict[str, str]] = None,
) -> tuple[ActionIntent, ActionPriority]:
    """Determine the semantic intent of a button/action.

    Uses all available evidence in priority order:
      1. VBA event code (most reliable signal)
      2. Button caption keywords
      3. Control name patterns

    Returns:
        (intent, priority) tuple
    """
    # Layer 1: VBA code analysis (highest confidence)
    if vba_code:
        for pattern, intent in _VBA_INTENT_PATTERNS:
            if re.search(pattern, vba_code, re.IGNORECASE):
                return intent, _INTENT_PRIORITIES.get(intent, ActionPriority.SECONDARY)

    # Layer 2: Caption keyword matching
    if caption:
        caption_lower = caption.lower().strip()
        # Check multi-word phrases first
        for keyword, intent in sorted(_CAPTION_KEYWORDS.items(), key=lambda x: -len(x[0])):
            if keyword in caption_lower:
                return intent, _INTENT_PRIORITIES.get(intent, ActionPriority.SECONDARY)

    # Layer 3: Control name pattern matching
    if control_name:
        name_lower = control_name.lower()
        for keyword, intent in _CAPTION_KEYWORDS.items():
            if keyword.replace(" ", "") in name_lower:
                return intent, _INTENT_PRIORITIES.get(intent, ActionPriority.SECONDARY)

    return ActionIntent.CUSTOM, ActionPriority.SECONDARY


def get_default_priority(intent: ActionIntent) -> ActionPriority:
    """Get the default visual priority for an intent."""
    return _INTENT_PRIORITIES.get(intent, ActionPriority.SECONDARY)
