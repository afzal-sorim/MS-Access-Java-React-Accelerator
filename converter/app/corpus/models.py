"""Corpus data model - spec section 52.

Each corpus item declares:

* the source Access application
* expected inventory
* expected IR fragments
* expected database schema
* expected APIs
* expected business rules
* expected build result
* expected tests

Items the spec names but which have no source yet are ``DECLARED``.  They
are reported as coverage gaps rather than silently omitted, so the corpus
never overstates what it actually verifies.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field, asdict
from enum import Enum
from pathlib import Path
from typing import Any, Optional


class ItemStatus(str, Enum):
    """Lifecycle state of a corpus item."""

    # Source present and expectations captured — participates in runs.
    READY = "READY"
    # Source present but no expectations yet — run captures a baseline.
    NEEDS_BASELINE = "NEEDS_BASELINE"
    # Spec category with no source on this machine — a known coverage gap.
    DECLARED = "DECLARED"
    # Source present but cannot run here (e.g. needs SQL Server, or Access
    # Trust Center blocks VBA injection).  Skipped with the reason recorded.
    BLOCKED = "BLOCKED"


class CheckOutcome(str, Enum):
    """Result of a single expectation check."""

    PASS = "PASS"
    FAIL = "FAIL"
    # Expected value intentionally records a converter defect.  Reported
    # separately so real regressions are never hidden inside a fail count.
    KNOWN_GAP = "KNOWN_GAP"
    # Baseline captured this run; nothing to compare against yet.
    BASELINE = "BASELINE"
    SKIPPED = "SKIPPED"


@dataclass
class CorpusItem:
    """One corpus category (spec §52)."""

    name: str
    category: str
    status: ItemStatus = ItemStatus.DECLARED
    source: Optional[str] = None          # relative to the item directory
    saved_text: Optional[str] = None      # SaveAsText companion export
    description: str = ""
    reason: str = ""                      # why BLOCKED / DECLARED
    # spec §53 edge cases this item is intended to exercise
    covers: list[str] = field(default_factory=list)
    tags: list[str] = field(default_factory=list)

    @property
    def is_runnable(self) -> bool:
        return self.status in (ItemStatus.READY, ItemStatus.NEEDS_BASELINE)

    def to_dict(self) -> dict:
        d = asdict(self)
        d["status"] = self.status.value
        return d

    @classmethod
    def from_dict(cls, data: dict) -> "CorpusItem":
        raw_status = data.get("status", ItemStatus.DECLARED.value)
        try:
            status = ItemStatus(raw_status)
        except ValueError:
            status = ItemStatus.DECLARED
        return cls(
            name=data["name"],
            category=data.get("category", data["name"]),
            status=status,
            source=data.get("source"),
            saved_text=data.get("saved_text"),
            description=data.get("description", ""),
            reason=data.get("reason", ""),
            covers=list(data.get("covers", [])),
            tags=list(data.get("tags", [])),
        )


@dataclass
class CorpusRegistry:
    """The full corpus: every spec §52 category, populated or not."""

    root: Path
    items: list[CorpusItem] = field(default_factory=list)
    schema_version: str = "1.0"

    REGISTRY_FILENAME = "registry.json"

    @classmethod
    def load(cls, root: str | Path) -> "CorpusRegistry":
        root = Path(root)
        path = root / cls.REGISTRY_FILENAME
        if not path.exists():
            raise FileNotFoundError(
                f"No corpus registry at {path}. "
                f"Run 'python -m converter corpus init' to create one."
            )
        data = json.loads(path.read_text(encoding="utf-8"))
        return cls(
            root=root,
            schema_version=data.get("schema_version", "1.0"),
            items=[CorpusItem.from_dict(d) for d in data.get("items", [])],
        )

    def save(self) -> Path:
        self.root.mkdir(parents=True, exist_ok=True)
        path = self.root / self.REGISTRY_FILENAME
        payload = {
            "schema_version": self.schema_version,
            "comment": (
                "Golden test corpus (spec §52). Items with status DECLARED have "
                "no source application yet and are reported as coverage gaps, "
                "not as passes."
            ),
            "items": [item.to_dict() for item in self.items],
        }
        path.write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")
        return path

    def get(self, name: str) -> Optional[CorpusItem]:
        for item in self.items:
            if item.name == name:
                return item
        return None

    def item_dir(self, item: CorpusItem) -> Path:
        return self.root / item.name

    def expected_dir(self, item: CorpusItem) -> Path:
        return self.item_dir(item) / "expected"

    @property
    def runnable(self) -> list[CorpusItem]:
        return [i for i in self.items if i.is_runnable]

    @property
    def declared_only(self) -> list[CorpusItem]:
        return [i for i in self.items if i.status == ItemStatus.DECLARED]


@dataclass
class CheckResult:
    """Outcome of comparing one expectation file."""

    name: str
    outcome: CheckOutcome
    detail: str = ""
    diffs: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "outcome": self.outcome.value,
            "detail": self.detail,
            "diffs": self.diffs,
        }


@dataclass
class ItemResult:
    """Aggregate result for one corpus item."""

    item: str
    status: ItemStatus
    checks: list[CheckResult] = field(default_factory=list)
    error: str = ""
    duration_seconds: float = 0.0
    # Inventory actually observed this run, for reporting.
    observed: dict[str, Any] = field(default_factory=dict)

    @property
    def failed(self) -> list[CheckResult]:
        return [c for c in self.checks if c.outcome == CheckOutcome.FAIL]

    @property
    def known_gaps(self) -> list[CheckResult]:
        return [c for c in self.checks if c.outcome == CheckOutcome.KNOWN_GAP]

    @property
    def passed(self) -> bool:
        return not self.failed and not self.error

    def to_dict(self) -> dict:
        return {
            "item": self.item,
            "status": self.status.value,
            "passed": self.passed,
            "error": self.error,
            "duration_seconds": round(self.duration_seconds, 2),
            "observed": self.observed,
            "checks": [c.to_dict() for c in self.checks],
        }


@dataclass
class CorpusRunReport:
    """Report for a full corpus run (spec §52, §66)."""

    started_at: str = ""
    completed_at: str = ""
    corpus_root: str = ""
    results: list[ItemResult] = field(default_factory=list)
    declared_not_populated: list[str] = field(default_factory=list)
    blocked: list[dict] = field(default_factory=list)

    @property
    def total_declared(self) -> int:
        return (
            len(self.results)
            + len(self.declared_not_populated)
            + len(self.blocked)
        )

    @property
    def items_passed(self) -> int:
        return sum(1 for r in self.results if r.passed)

    @property
    def items_failed(self) -> int:
        return sum(1 for r in self.results if not r.passed)

    @property
    def total_known_gaps(self) -> int:
        return sum(len(r.known_gaps) for r in self.results)

    @property
    def ok(self) -> bool:
        """True when nothing regressed.

        Known gaps do not fail the run — they are pre-existing defects the
        corpus documents on purpose.  A newly broken expectation does.
        """
        return self.items_failed == 0

    def to_dict(self) -> dict:
        return {
            "schema_version": "1.0",
            "started_at": self.started_at,
            "completed_at": self.completed_at,
            "corpus_root": self.corpus_root,
            "summary": {
                "declared_categories": self.total_declared,
                "runnable_items": len(self.results),
                "items_passed": self.items_passed,
                "items_failed": self.items_failed,
                "known_gaps": self.total_known_gaps,
                "declared_not_populated": len(self.declared_not_populated),
                "blocked": len(self.blocked),
                "coverage_note": (
                    f"{len(self.results)} of {self.total_declared} spec section 52 "
                    f"categories have a runnable source application."
                ),
                "ok": self.ok,
            },
            "results": [r.to_dict() for r in self.results],
            "declared_not_populated": self.declared_not_populated,
            "blocked": self.blocked,
        }
