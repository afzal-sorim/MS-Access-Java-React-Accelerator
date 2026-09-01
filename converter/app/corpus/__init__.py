"""Golden test corpus infrastructure - spec sections 52, 53.

A corpus item pairs a real Access application with the expectations the
converter must satisfy for it.  Running the corpus re-extracts each source,
rebuilds the IR, and diffs the result against ``expected/``.

Key design rule (spec §52, §68): coverage is reported honestly.  Categories
listed in the spec but not yet populated are DECLARED, not counted as
passing.  A run over 2 populated items reports "2 runnable / 20 declared",
never "20/20".
"""
from .models import (
    CorpusItem,
    CorpusRegistry,
    ItemStatus,
    CheckOutcome,
    CheckResult,
    ItemResult,
    CorpusRunReport,
)
from .runner import CorpusRunner, run_corpus, capture_expectations

__all__ = [
    "CorpusItem",
    "CorpusRegistry",
    "ItemStatus",
    "CheckOutcome",
    "CheckResult",
    "ItemResult",
    "CorpusRunReport",
    "CorpusRunner",
    "run_corpus",
    "capture_expectations",
]
