"""Corpus runner - spec sections 51, 52.

Re-runs the converter over each populated corpus item and diffs the result
against the recorded expectations.

Pipeline exercised per item:

    .accdb  ->  extraction  ->  IR  ->  dependency graph
                                    ->  supportability
                                    ->  PostgreSQL schema

Expectation files live in ``<item>/expected/`` and are plain JSON so they
review as readable diffs:

    inventory.json      object counts and names
    ir.json             IR fragments (tables, columns, query kinds)
    externals.json      external dependencies (spec §8)
    schema.json         generated PostgreSQL schema shape
    supportability.json support-status distribution

An expectation file may carry ``"_known_gaps"`` — keys whose mismatch is a
documented converter defect rather than a regression.  Those report as
KNOWN_GAP and do not fail the run, so real regressions stay visible.
"""
from __future__ import annotations

import json
import logging
import tempfile
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

from .models import (
    CheckOutcome,
    CheckResult,
    CorpusItem,
    CorpusRegistry,
    CorpusRunReport,
    ItemResult,
    ItemStatus,
)

logger = logging.getLogger(__name__)

# Marker key inside an expectation file listing intentionally-failing keys.
KNOWN_GAPS_KEY = "_known_gaps"
STATUS_KEY = "_status"


class CorpusRunner:
    """Runs the converter over corpus items and diffs against expectations."""

    EXPECTATION_FILES = (
        "inventory",
        "ir",
        "externals",
        "schema",
        "supportability",
    )

    def __init__(self, registry: CorpusRegistry, *, workdir: Optional[Path] = None):
        self.registry = registry
        self._workdir = Path(workdir) if workdir else None

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def run(self, only: Optional[list[str]] = None) -> CorpusRunReport:
        """Run every runnable item (or just ``only``) and diff expectations."""
        report = CorpusRunReport(
            started_at=datetime.utcnow().isoformat(),
            corpus_root=str(self.registry.root),
        )

        for item in self.registry.items:
            if only and item.name not in only:
                continue

            if item.status == ItemStatus.DECLARED:
                report.declared_not_populated.append(item.name)
                continue
            if item.status == ItemStatus.BLOCKED:
                report.blocked.append({"item": item.name, "reason": item.reason})
                continue

            report.results.append(self._run_item(item))

        report.completed_at = datetime.utcnow().isoformat()
        return report

    def capture(self, only: Optional[list[str]] = None) -> CorpusRunReport:
        """Run items and (re)write expectation files from observed output.

        Used to establish or refresh a baseline.  Captured files are marked
        ``"_status": "CAPTURED_UNREVIEWED"`` so it stays obvious which
        expectations a human has actually vetted.
        """
        report = CorpusRunReport(
            started_at=datetime.utcnow().isoformat(),
            corpus_root=str(self.registry.root),
        )

        for item in self.registry.items:
            if only and item.name not in only:
                continue
            if item.status == ItemStatus.DECLARED:
                report.declared_not_populated.append(item.name)
                continue
            if item.status == ItemStatus.BLOCKED:
                report.blocked.append({"item": item.name, "reason": item.reason})
                continue

            report.results.append(self._run_item(item, capture=True))

        report.completed_at = datetime.utcnow().isoformat()
        return report

    # ------------------------------------------------------------------
    # Per-item execution
    # ------------------------------------------------------------------

    def _run_item(self, item: CorpusItem, *, capture: bool = False) -> ItemResult:
        start = time.time()
        result = ItemResult(item=item.name, status=item.status)

        source = self._resolve_source(item)
        if source is None:
            result.error = f"source not found for item '{item.name}'"
            result.duration_seconds = time.time() - start
            return result

        try:
            observed = self._observe_with_retry(source)
        except Exception as exc:                      # pragma: no cover - env dependent
            result.error = f"{type(exc).__name__}: {exc}"
            result.duration_seconds = time.time() - start
            return result

        result.observed = observed.get("inventory", {})

        expected_dir = self.registry.expected_dir(item)
        if capture:
            expected_dir.mkdir(parents=True, exist_ok=True)

        for name in self.EXPECTATION_FILES:
            actual = observed.get(name)
            if actual is None:
                continue
            path = expected_dir / f"{name}.json"

            if capture:
                self._write_expectation(path, actual)
                result.checks.append(CheckResult(
                    name=name,
                    outcome=CheckOutcome.BASELINE,
                    detail=f"captured -> {path.name}",
                ))
                continue

            result.checks.append(self._compare(name, path, actual))

        result.duration_seconds = time.time() - start
        return result

    def _resolve_source(self, item: CorpusItem) -> Optional[Path]:
        if not item.source:
            return None
        candidate = self.registry.item_dir(item) / item.source
        if candidate.exists():
            return candidate
        # Allow an absolute or project-relative path in the registry.
        direct = Path(item.source)
        return direct if direct.exists() else None

    # ------------------------------------------------------------------
    # Observation: run the real converter pipeline
    # ------------------------------------------------------------------

    # Access COM is a single-instance, machine-wide resource.  Two concurrent
    # extractions (e.g. a corpus run while the test suite is running) make the
    # Access automation object return None mid-call, surfacing as
    # "'NoneType' object has no attribute 'TableDefs'".  That is contention,
    # not a converter regression, so retry briefly before reporting.
    TRANSIENT_COM_MARKERS = (
        "nonetype",
        "rpc_e_",
        "call was rejected",
        "server is busy",
        "0x800ac472",
    )
    MAX_OBSERVE_ATTEMPTS = 3
    RETRY_BACKOFF_SECONDS = 5

    def _is_transient_com_error(self, exc: Exception) -> bool:
        blob = f"{type(exc).__name__}: {exc}".lower()
        return any(marker in blob for marker in self.TRANSIENT_COM_MARKERS)

    def _observe_with_retry(self, source: Path) -> dict[str, Any]:
        """Observe, retrying transient Access COM contention."""
        last: Optional[Exception] = None
        for attempt in range(1, self.MAX_OBSERVE_ATTEMPTS + 1):
            try:
                return self._observe(source)
            except Exception as exc:
                last = exc
                if attempt == self.MAX_OBSERVE_ATTEMPTS or not self._is_transient_com_error(exc):
                    raise
                logger.warning(
                    "transient Access COM error on %s (attempt %d/%d): %s — retrying",
                    source.name, attempt, self.MAX_OBSERVE_ATTEMPTS, exc,
                )
                time.sleep(self.RETRY_BACKOFF_SECONDS)
        raise last            # pragma: no cover - unreachable

    def _observe(self, source: Path) -> dict[str, Any]:
        """Run extraction -> IR -> graph/supportability/schema for a source."""
        from converter.app.access.extractor import run_extraction
        from converter.app.ir.builder import build_ir

        if self._workdir:
            self._workdir.mkdir(parents=True, exist_ok=True)
            workdir = Path(tempfile.mkdtemp(dir=self._workdir))
        else:
            workdir = Path(tempfile.mkdtemp())

        run_extraction(str(source), workdir)
        ir = build_ir(workdir / "extraction.json")

        return {
            "inventory": self._inventory(ir),
            "ir": self._ir_fragments(ir),
            "externals": self._externals(ir),
            "schema": self._schema(ir),
            "supportability": self._supportability(ir),
        }

    @staticmethod
    def _inventory(ir) -> dict[str, Any]:
        """Object counts and names — spec §52 'expected inventory'."""
        return {
            "application_name": ir.application_name,
            "counts": {
                "tables": len(ir.tables),
                "relationships": len(ir.relationships),
                "queries": len(ir.queries),
                "forms": len(ir.forms),
                "reports": len(ir.reports),
                "macros": len(ir.macros),
                "vba_modules": len(ir.vba_modules),
            },
            "tables": sorted(t.name for t in ir.tables),
            "queries": sorted(q.name for q in ir.queries),
            "forms": sorted(f.name for f in ir.forms),
            "reports": sorted(r.name for r in ir.reports),
            "macros": sorted(m.name for m in ir.macros),
            "vba_modules": sorted(m.name for m in ir.vba_modules),
        }

    @staticmethod
    def _ir_fragments(ir) -> dict[str, Any]:
        """Stable IR fragments — spec §52 'expected IR fragments'."""
        tables = {}
        for t in sorted(ir.tables, key=lambda x: x.name):
            tables[t.name] = {
                "columns": [
                    {
                        "name": c.name,
                        "access_type": c.access_type,
                        "required": bool(c.required),
                        "auto_number": bool(c.auto_number),
                        "primary_key": bool(c.primary_key),
                    }
                    for c in t.columns
                ],
                "is_linked": bool(getattr(t, "is_linked", False)),
            }

        queries = {}
        for q in sorted(ir.queries, key=lambda x: x.name):
            kind = getattr(q, "kind", None)
            queries[q.name] = {
                "kind": kind.value if hasattr(kind, "value") else str(kind),
                "references_tables": sorted(getattr(q, "references_tables", []) or []),
                "access_functions": sorted(getattr(q, "access_functions", []) or []),
                "parameter_count": len(getattr(q, "parameters", []) or []),
            }

        return {
            "tables": tables,
            "queries": queries,
            "business_rule_count": len(ir.business_rules),
            "vba_modules": {
                m.name: {
                    "module_type": m.module_type,
                    "procedure_count": len(getattr(m, "procedures", []) or []),
                    "has_source": bool(getattr(m, "source", "")),
                }
                for m in sorted(ir.vba_modules, key=lambda x: x.name)
            },
        }

    @staticmethod
    def _externals(ir) -> dict[str, Any]:
        """External dependencies — spec §8, §53."""
        deps = []
        for d in ir.external_dependencies:
            support = d.support
            deps.append({
                "kind": d.kind,
                "target": d.target,
                "connected_table": d.connected_table,
                "support": support.value if hasattr(support, "value") else str(support),
                "risk": d.risk,
            })
        deps.sort(key=lambda x: (x["kind"], x["target"]))
        return {"count": len(deps), "dependencies": deps}

    @staticmethod
    def _schema(ir) -> dict[str, Any]:
        """Generated PostgreSQL schema shape — spec §52 'expected database'."""
        from converter.app.generators.database.postgres import generate_schema

        try:
            sql = generate_schema(ir)
        except Exception as exc:
            return {"error": f"{type(exc).__name__}: {exc}"}

        lowered = sql.lower()
        return {
            "create_table_count": lowered.count("create table"),
            "primary_key_count": lowered.count("primary key"),
            "foreign_key_count": lowered.count("foreign key"),
            "index_count": lowered.count("create index")
            + lowered.count("create unique index"),
            "line_count": len(sql.splitlines()),
        }

    @staticmethod
    def _supportability(ir) -> dict[str, Any]:
        """Support-status distribution — spec §12, §13."""
        from converter.app.supportability.engine import analyze_supportability

        try:
            entries = analyze_supportability(ir)
        except Exception as exc:
            return {"error": f"{type(exc).__name__}: {exc}"}

        counts: dict[str, int] = {}
        for entry in entries:
            status = getattr(entry, "support", None) or getattr(entry, "status", None)
            key = status.value if hasattr(status, "value") else str(status)
            counts[key] = counts.get(key, 0) + 1

        return {"total": len(entries), "by_status": dict(sorted(counts.items()))}

    # ------------------------------------------------------------------
    # Expectation comparison
    # ------------------------------------------------------------------

    def _write_expectation(self, path: Path, actual: Any) -> None:
        existing_gaps = []
        if path.exists():
            try:
                prior = json.loads(path.read_text(encoding="utf-8"))
                existing_gaps = prior.get(KNOWN_GAPS_KEY, [])
            except (json.JSONDecodeError, OSError):
                pass

        payload = {
            STATUS_KEY: "CAPTURED_UNREVIEWED",
            "_comment": (
                "Captured from converter output; not yet human-reviewed. "
                "Verify against the spec, then set _status to REVIEWED."
            ),
        }
        if existing_gaps:
            payload[KNOWN_GAPS_KEY] = existing_gaps
        payload.update(actual if isinstance(actual, dict) else {"value": actual})
        path.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    def _compare(self, name: str, path: Path, actual: Any) -> CheckResult:
        if not path.exists():
            return CheckResult(
                name=name,
                outcome=CheckOutcome.SKIPPED,
                detail=f"no expectation file ({path.name}); run 'corpus capture'",
            )

        try:
            expected = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            return CheckResult(
                name=name,
                outcome=CheckOutcome.FAIL,
                detail=f"expectation file is not valid JSON: {exc}",
            )

        known_gaps = set(expected.get(KNOWN_GAPS_KEY, []))
        expected_body = {
            k: v for k, v in expected.items()
            if not k.startswith("_")
        }

        diffs = list(_diff(expected_body, actual, prefix=""))
        if not diffs:
            return CheckResult(name=name, outcome=CheckOutcome.PASS)

        gap_diffs, real_diffs = [], []
        for path_str, detail in diffs:
            if any(path_str == g or path_str.startswith(g + ".") for g in known_gaps):
                gap_diffs.append(f"{path_str}: {detail}")
            else:
                real_diffs.append(f"{path_str}: {detail}")

        if real_diffs:
            return CheckResult(
                name=name,
                outcome=CheckOutcome.FAIL,
                detail=f"{len(real_diffs)} unexpected difference(s)",
                diffs=real_diffs[:25],
            )

        return CheckResult(
            name=name,
            outcome=CheckOutcome.KNOWN_GAP,
            detail=f"{len(gap_diffs)} documented gap(s) only",
            diffs=gap_diffs[:25],
        )


def _diff(expected: Any, actual: Any, prefix: str = "") -> list[tuple[str, str]]:
    """Yield (dotted_path, description) for each mismatch.

    Only keys present in ``expected`` are checked, so adding a new observed
    field is not a failure — expectations stay stable as the IR grows.
    """
    out: list[tuple[str, str]] = []

    if isinstance(expected, dict):
        if not isinstance(actual, dict):
            out.append((prefix or "<root>", f"expected object, got {type(actual).__name__}"))
            return out
        for key, exp_val in expected.items():
            path = f"{prefix}.{key}" if prefix else key
            if key not in actual:
                out.append((path, "missing from output"))
                continue
            out.extend(_diff(exp_val, actual[key], path))
        return out

    if isinstance(expected, list):
        if not isinstance(actual, list):
            out.append((prefix or "<root>", f"expected list, got {type(actual).__name__}"))
            return out
        if len(expected) != len(actual):
            missing = [x for x in expected if x not in actual]
            added = [x for x in actual if x not in expected]
            detail = f"length {len(expected)} -> {len(actual)}"
            if missing:
                detail += f"; missing {_preview(missing)}"
            if added:
                detail += f"; unexpected {_preview(added)}"
            out.append((prefix or "<root>", detail))
            return out
        for i, (exp_val, act_val) in enumerate(zip(expected, actual)):
            out.extend(_diff(exp_val, act_val, f"{prefix}[{i}]"))
        return out

    if expected != actual:
        out.append((prefix or "<root>", f"expected {expected!r}, got {actual!r}"))
    return out


def _preview(values: list, limit: int = 4) -> str:
    shown = [str(v) for v in values[:limit]]
    if len(values) > limit:
        shown.append(f"...+{len(values) - limit}")
    return "[" + ", ".join(shown) + "]"


# ---------------------------------------------------------------------- entry points


def run_corpus(
    corpus_root: str | Path,
    only: Optional[list[str]] = None,
) -> CorpusRunReport:
    """Run the corpus and return the report."""
    registry = CorpusRegistry.load(corpus_root)
    return CorpusRunner(registry).run(only=only)


def capture_expectations(
    corpus_root: str | Path,
    only: Optional[list[str]] = None,
) -> CorpusRunReport:
    """Capture/refresh expectation baselines."""
    registry = CorpusRegistry.load(corpus_root)
    return CorpusRunner(registry).capture(only=only)
