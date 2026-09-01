"""Tests for the golden test corpus infrastructure - spec sections 52, 53.

Two layers:

1. Unit tests for the registry, diff engine and known-gap handling.  These
   run everywhere and need no Access installation.
2. Corpus gate tests that run the real converter over the registered
   Access applications.  These require MS Access COM and are skipped
   cleanly when it is unavailable, so CI on a non-Windows runner reports
   "skipped", never a false pass.
"""
from __future__ import annotations

import json
import tempfile
from pathlib import Path

import pytest

from converter.app.corpus.models import (
    CheckOutcome,
    CorpusItem,
    CorpusRegistry,
    CorpusRunReport,
    ItemResult,
    ItemStatus,
)
from converter.app.corpus.runner import CorpusRunner, _diff

PROJECT_ROOT = Path(__file__).resolve().parents[2]
CORPUS_ROOT = PROJECT_ROOT / "corpus"


def _access_available() -> bool:
    """True when MS Access COM automation can be used on this machine."""
    try:
        import win32com.client  # noqa: F401
    except ImportError:
        return False
    try:
        import pythoncom
        pythoncom.CoInitialize()
        try:
            import win32com.client
            win32com.client.gencache.EnsureDispatch("Access.Application").Quit()
        finally:
            pythoncom.CoUninitialize()
        return True
    except Exception:
        return False


requires_access = pytest.mark.skipif(
    not _access_available(),
    reason="MS Access COM automation unavailable",
)

requires_corpus = pytest.mark.skipif(
    not (CORPUS_ROOT / CorpusRegistry.REGISTRY_FILENAME).exists(),
    reason="corpus registry not initialized (run: python -m converter corpus init)",
)


# ======================================================================
# Diff engine
# ======================================================================

class TestDiffEngine:
    """The diff engine decides pass vs fail, so it needs to be exact."""

    def test_identical_scalars_produce_no_diff(self):
        assert _diff({"a": 1}, {"a": 1}) == []

    def test_changed_scalar_is_reported_with_path(self):
        diffs = _diff({"count": 2}, {"count": 0})
        assert len(diffs) == 1
        path, detail = diffs[0]
        assert path == "count"
        assert "2" in detail and "0" in detail

    def test_nested_path_is_dotted(self):
        diffs = _diff(
            {"by_status": {"UNSUPPORTED": 11}},
            {"by_status": {"UNSUPPORTED": 9}},
        )
        assert diffs[0][0] == "by_status.UNSUPPORTED"

    def test_missing_key_is_reported(self):
        diffs = _diff({"tables": []}, {})
        assert diffs[0][0] == "tables"
        assert "missing" in diffs[0][1]

    def test_extra_observed_key_is_not_a_failure(self):
        """Expectations pin what matters; new IR fields must not break them."""
        assert _diff({"a": 1}, {"a": 1, "b": 2}) == []

    def test_list_length_change_reports_missing_members(self):
        diffs = _diff(["Outlook", "DLL"], ["Outlook"])
        assert len(diffs) == 1
        assert "missing" in diffs[0][1]
        assert "DLL" in diffs[0][1]

    def test_type_change_is_reported(self):
        diffs = _diff({"a": {"b": 1}}, {"a": [1]})
        assert diffs
        assert "expected object" in diffs[0][1]


# ======================================================================
# Registry
# ======================================================================

class TestCorpusRegistry:

    def test_roundtrip_preserves_items(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            reg = CorpusRegistry(root=root, items=[
                CorpusItem(name="vba-heavy", category="vba-heavy",
                           status=ItemStatus.READY, source="source.accdb",
                           covers=["Outlook"]),
                CorpusItem(name="crosstab", category="crosstab"),
            ])
            reg.save()

            loaded = CorpusRegistry.load(root)
            assert len(loaded.items) == 2
            assert loaded.get("vba-heavy").status == ItemStatus.READY
            assert loaded.get("vba-heavy").covers == ["Outlook"]
            assert loaded.get("crosstab").status == ItemStatus.DECLARED

    def test_missing_registry_raises_actionable_error(self):
        with tempfile.TemporaryDirectory() as tmp:
            with pytest.raises(FileNotFoundError, match="corpus init"):
                CorpusRegistry.load(tmp)

    def test_runnable_excludes_declared_and_blocked(self):
        reg = CorpusRegistry(root=Path("."), items=[
            CorpusItem(name="a", category="a", status=ItemStatus.READY),
            CorpusItem(name="b", category="b", status=ItemStatus.NEEDS_BASELINE),
            CorpusItem(name="c", category="c", status=ItemStatus.DECLARED),
            CorpusItem(name="d", category="d", status=ItemStatus.BLOCKED),
        ])
        assert {i.name for i in reg.runnable} == {"a", "b"}
        assert {i.name for i in reg.declared_only} == {"c"}

    def test_unknown_status_degrades_to_declared(self):
        """A hand-edited registry must not crash the runner."""
        item = CorpusItem.from_dict({"name": "x", "status": "NONSENSE"})
        assert item.status == ItemStatus.DECLARED


# ======================================================================
# Honest coverage reporting (spec §52, §68)
# ======================================================================

class TestCoverageReporting:

    def test_declared_categories_counted_but_not_passed(self):
        """A 2-item run must never look like 20/20."""
        report = CorpusRunReport(
            results=[
                ItemResult(item="vba-heavy", status=ItemStatus.READY),
                ItemResult(item="employee-hr", status=ItemStatus.READY),
            ],
            declared_not_populated=["crosstab", "sales", "crm"],
            blocked=[{"item": "split-db", "reason": "needs FE/BE pair"}],
        )
        summary = report.to_dict()["summary"]

        assert summary["runnable_items"] == 2
        assert summary["declared_categories"] == 6
        assert summary["items_passed"] == 2
        assert summary["declared_not_populated"] == 3
        assert summary["blocked"] == 1
        assert "2 of 6" in summary["coverage_note"]

    def test_failed_item_makes_run_not_ok(self):
        bad = ItemResult(item="x", status=ItemStatus.READY)
        bad.error = "extraction blew up"
        report = CorpusRunReport(results=[bad])
        assert report.ok is False
        assert report.items_failed == 1

    def test_known_gap_does_not_fail_the_run(self):
        """Documented defects are tracked, not treated as regressions."""
        from converter.app.corpus.models import CheckResult

        result = ItemResult(item="x", status=ItemStatus.READY, checks=[
            CheckResult(name="externals", outcome=CheckOutcome.KNOWN_GAP,
                        detail="1 documented gap"),
        ])
        report = CorpusRunReport(results=[result])
        assert report.ok is True
        assert report.total_known_gaps == 1


# ======================================================================
# Expectation comparison
# ======================================================================

class TestExpectationComparison:

    @pytest.fixture
    def runner(self):
        with tempfile.TemporaryDirectory() as tmp:
            reg = CorpusRegistry(root=Path(tmp))
            yield CorpusRunner(reg), Path(tmp)

    def test_matching_expectation_passes(self, runner):
        run, tmp = runner
        path = tmp / "inventory.json"
        path.write_text(json.dumps({"_status": "REVIEWED", "count": 3}))
        check = run._compare("inventory", path, {"count": 3})
        assert check.outcome == CheckOutcome.PASS

    def test_mismatch_fails_with_diff_detail(self, runner):
        run, tmp = runner
        path = tmp / "inventory.json"
        path.write_text(json.dumps({"count": 3}))
        check = run._compare("inventory", path, {"count": 5})
        assert check.outcome == CheckOutcome.FAIL
        assert any("count" in d for d in check.diffs)

    def test_known_gap_key_downgrades_failure(self, runner):
        run, tmp = runner
        path = tmp / "externals.json"
        path.write_text(json.dumps({
            "_known_gaps": ["count"],
            "count": 2,
        }))
        check = run._compare("externals", path, {"count": 0})
        assert check.outcome == CheckOutcome.KNOWN_GAP

    def test_gap_marker_does_not_mask_other_regressions(self, runner):
        """A known gap on one key must not hide a real break elsewhere."""
        run, tmp = runner
        path = tmp / "externals.json"
        path.write_text(json.dumps({
            "_known_gaps": ["count"],
            "count": 2,
            "total": 65,
        }))
        check = run._compare("externals", path, {"count": 0, "total": 63})
        assert check.outcome == CheckOutcome.FAIL
        assert any("total" in d for d in check.diffs)

    def test_underscore_metadata_is_not_compared(self, runner):
        run, tmp = runner
        path = tmp / "x.json"
        path.write_text(json.dumps({
            "_status": "REVIEWED",
            "_comment": "notes",
            "count": 1,
        }))
        check = run._compare("x", path, {"count": 1})
        assert check.outcome == CheckOutcome.PASS

    def test_missing_expectation_file_is_skipped_not_passed(self, runner):
        run, tmp = runner
        check = run._compare("inventory", tmp / "absent.json", {"count": 1})
        assert check.outcome == CheckOutcome.SKIPPED

    def test_corrupt_expectation_file_fails_loudly(self, runner):
        run, tmp = runner
        path = tmp / "bad.json"
        path.write_text("{not json")
        check = run._compare("bad", path, {"count": 1})
        assert check.outcome == CheckOutcome.FAIL
        assert "valid JSON" in check.detail


# ======================================================================
# Corpus gate — runs the real converter (needs MS Access)
# ======================================================================

@requires_corpus
class TestCorpusRegistryOnDisk:
    """Checks the committed registry without needing Access."""

    def test_all_twenty_spec_categories_declared(self):
        from converter.app.corpus.init_corpus import SPEC_CATEGORIES

        registry = CorpusRegistry.load(CORPUS_ROOT)
        assert len(registry.items) == len(SPEC_CATEGORIES) == 20

        declared = {i.name for i in registry.items}
        expected = {name for name, _, _ in SPEC_CATEGORIES}
        assert declared == expected

    def test_runnable_items_have_an_existing_source(self):
        registry = CorpusRegistry.load(CORPUS_ROOT)
        runner = CorpusRunner(registry)
        for item in registry.runnable:
            assert runner._resolve_source(item) is not None, (
                f"item '{item.name}' is runnable but its source is missing"
            )

    def test_non_runnable_items_explain_themselves(self):
        """Every gap must carry a reason, so coverage is auditable."""
        registry = CorpusRegistry.load(CORPUS_ROOT)
        for item in registry.items:
            if not item.is_runnable:
                assert item.reason, f"item '{item.name}' has no reason recorded"


@requires_access
@requires_corpus
class TestCorpusGate:
    """Runs the converter over every registered corpus item."""

    def test_corpus_has_no_regressions(self):
        from converter.app.corpus import run_corpus

        report = run_corpus(CORPUS_ROOT)
        data = report.to_dict()

        if not report.results:
            pytest.skip("no runnable corpus items")

        failures = []
        for result in data["results"]:
            if result["passed"]:
                continue
            detail = [f"{result['item']}: {result['error'] or 'checks failed'}"]
            for check in result["checks"]:
                if check["outcome"] == CheckOutcome.FAIL.value:
                    detail.append(f"  {check['name']}: {check['detail']}")
                    detail.extend(f"    - {d}" for d in check["diffs"][:5])
            failures.append("\n".join(detail))

        assert not failures, "corpus regressions:\n" + "\n".join(failures)

    def test_vba_heavy_detects_outlook_external_dependency(self):
        """Guards the fix for early-bound COM detection (spec §8, §53).

        modOutlook uses `Dim x As New Outlook.Application`.  The extractor
        originally scanned only for CreateObject, and the IR builder only
        looked at linked tables, so this reported zero externals.
        """
        registry = CorpusRegistry.load(CORPUS_ROOT)
        item = registry.get("vba-heavy")
        if item is None or not item.is_runnable:
            pytest.skip("vba-heavy corpus item not populated")

        runner = CorpusRunner(registry)
        observed = runner._observe(runner._resolve_source(item))

        kinds = {d["kind"] for d in observed["externals"]["dependencies"]}
        assert "OUTLOOK" in kinds, f"Outlook not detected; got {kinds}"
        assert "DLL" in kinds, f"Win32 declarations not detected; got {kinds}"

    def test_vba_heavy_does_not_report_phantom_word_excel(self):
        """`Dim Word As String` and "Excel Files" must not become deps."""
        registry = CorpusRegistry.load(CORPUS_ROOT)
        item = registry.get("vba-heavy")
        if item is None or not item.is_runnable:
            pytest.skip("vba-heavy corpus item not populated")

        runner = CorpusRunner(registry)
        observed = runner._observe(runner._resolve_source(item))

        targets = " ".join(d["target"] for d in observed["externals"]["dependencies"])
        assert "Word automation" not in targets, (
            "phantom Word dependency from a variable named Word or comment prose"
        )
        assert "Excel automation" not in targets, (
            'phantom Excel dependency from the "Excel Files" dialog filter'
        )


class TestTransientComRetry:
    """Access COM is machine-wide; contention must not read as a regression."""

    @pytest.fixture
    def runner(self):
        with tempfile.TemporaryDirectory() as tmp:
            yield CorpusRunner(CorpusRegistry(root=Path(tmp)))

    @pytest.mark.parametrize("exc", [
        AttributeError("'NoneType' object has no attribute 'TableDefs'"),
        Exception("Call was rejected by callee"),
        Exception("The server is busy"),
    ])
    def test_com_contention_is_transient(self, runner, exc):
        assert runner._is_transient_com_error(exc) is True

    @pytest.mark.parametrize("exc", [
        ValueError("expected 5 tables, got 3"),
        FileNotFoundError("missing.accdb"),
        KeyError("tables"),
    ])
    def test_real_errors_are_not_retried(self, runner, exc):
        assert runner._is_transient_com_error(exc) is False

    def test_retry_succeeds_after_transient_failure(self, runner, monkeypatch):
        monkeypatch.setattr(runner, "RETRY_BACKOFF_SECONDS", 0)
        calls = {"n": 0}

        def flaky(source):
            calls["n"] += 1
            if calls["n"] == 1:
                raise AttributeError("'NoneType' object has no attribute 'TableDefs'")
            return {"inventory": {"counts": {}}}

        monkeypatch.setattr(runner, "_observe", flaky)
        observed = runner._observe_with_retry(Path("x.accdb"))
        assert calls["n"] == 2
        assert "inventory" in observed

    def test_real_error_raises_without_retrying(self, runner, monkeypatch):
        monkeypatch.setattr(runner, "RETRY_BACKOFF_SECONDS", 0)
        calls = {"n": 0}

        def broken(source):
            calls["n"] += 1
            raise ValueError("schema generator crashed")

        monkeypatch.setattr(runner, "_observe", broken)
        with pytest.raises(ValueError):
            runner._observe_with_retry(Path("x.accdb"))
        assert calls["n"] == 1, "a real error must not be retried"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
