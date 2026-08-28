"""Conversion pipeline stages (plan §2).

Each source object moves through independent, recordable stages.  SupportStatus
describes *feasibility*; ConversionStage describes *progress*.  They must never
be conflated: an object can be SUPPORTED yet never GENERATED.
"""
from __future__ import annotations

from enum import Enum


class ConversionStage(str, Enum):
    DISCOVERED = "DISCOVERED"
    EXTRACTED = "EXTRACTED"
    ANALYZED = "ANALYZED"
    MAPPED = "MAPPED"
    GENERATED = "GENERATED"
    COMPILED = "COMPILED"
    RUNTIME_VALIDATED = "RUNTIME_VALIDATED"
    SEMANTICALLY_VALIDATED = "SEMANTICALLY_VALIDATED"
    FAILED = "FAILED"
    MANUAL_REVIEW = "MANUAL_REVIEW"
    UNSUPPORTED = "UNSUPPORTED"


# Ordered progression used to compare stages.
STAGE_ORDER: list[ConversionStage] = [
    ConversionStage.DISCOVERED,
    ConversionStage.EXTRACTED,
    ConversionStage.ANALYZED,
    ConversionStage.MAPPED,
    ConversionStage.GENERATED,
    ConversionStage.COMPILED,
    ConversionStage.RUNTIME_VALIDATED,
    ConversionStage.SEMANTICALLY_VALIDATED,
]

TERMINAL_NEGATIVE = {
    ConversionStage.FAILED,
    ConversionStage.UNSUPPORTED,
}


class StageTracker:
    """Records the furthest stage reached per source object."""

    def __init__(self) -> None:
        self._stages: dict[str, ConversionStage] = {}
        self._reasons: dict[str, list[str]] = {}

    def advance(self, object_id: str, stage: ConversionStage,
                reason: str = "") -> None:
        """Move an object to `stage` if it is further than its current one.

        FAILED/MANUAL_REVIEW/UNSUPPORTED never overwrite a positive stage
        reached earlier — they attach to the entry as annotations instead.
        """
        current = self._stages.get(object_id)
        if stage in TERMINAL_NEGATIVE or stage is ConversionStage.MANUAL_REVIEW:
            self._reasons.setdefault(object_id, []).append(
                f"{stage.value}: {reason}" if reason else stage.value)
            # Special case: nothing recorded yet means the terminal stage IS
            # the truth (e.g. extraction failure means never EXTRACTED).
            if current is None:
                self._stages[object_id] = stage
            return
        if current is None or (
                current in STAGE_ORDER and stage in STAGE_ORDER
                and STAGE_ORDER.index(stage) > STAGE_ORDER.index(current)):
            self._stages[object_id] = stage

    def stage_of(self, object_id: str) -> ConversionStage:
        return self._stages.get(object_id, ConversionStage.DISCOVERED)

    def reasons_for(self, object_id: str) -> list[str]:
        return list(self._reasons.get(object_id, []))

    def to_dict(self) -> dict[str, str]:
        return {k: v.value for k, v in sorted(self._stages.items())}


def stage_reached(object_id: str, tracker: StageTracker) -> str:
    return tracker.stage_of(object_id).value
