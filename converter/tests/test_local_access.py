"""Tests for direct local MS Access source discovery.

COM and the registry are monkeypatched throughout so these run on any
platform: the point is the path-validation, MRU-parsing, and copy-safety
logic, none of which needs a real Access install.
"""
from __future__ import annotations

import os
from pathlib import Path

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from converter.app.access import local_source
from converter.app.access.local_source import (
    LocalSourceError,
    format_file_size,
    parse_mru_value,
    probe_capability,
    resolve_local_source,
    stage_local_source,
)


@pytest.fixture
def accdb(tmp_path: Path) -> Path:
    """A stand-in .accdb file with recognizable content."""
    path = tmp_path / "Employees.accdb"
    path.write_bytes(b"fake accdb payload" * 64)
    return path


# ---------------------------------------------------------------- MRU parsing

class TestParseMruValue:
    """Access stores MRU entries as flag blocks, then '*', then the path."""

    def test_standard_entry(self):
        value = r"[F00000000][T01D9A1B2C3D4E5F6][O00000000]*C:\Data\Leave.accdb"
        assert parse_mru_value(value) == r"C:\Data\Leave.accdb"

    def test_bare_path(self):
        assert parse_mru_value(r"C:\Data\Leave.accdb") == r"C:\Data\Leave.accdb"

    def test_path_containing_spaces_and_asterisk_only_splits_once(self):
        value = r"[F00000000]*C:\My Data\Q1 * Report.accdb"
        assert parse_mru_value(value) == r"C:\My Data\Q1 * Report.accdb"

    def test_unc_path(self):
        value = r"[F00000000][T01D9][O00000000]*\\server\share\HR.accdb"
        assert parse_mru_value(value) == r"\\server\share\HR.accdb"

    def test_bracketed_prefix_without_separator_is_unparseable(self):
        assert parse_mru_value("[F00000000][T01D9A1B2]") is None

    @pytest.mark.parametrize("value", ["", "   ", None])
    def test_empty_values(self, value):
        assert parse_mru_value(value) is None


# ---------------------------------------------------------------- validation

class TestResolveLocalSource:

    def test_accepts_accdb(self, accdb: Path):
        info = resolve_local_source(str(accdb))
        assert info["path"] == str(accdb)
        assert info["name"] == "Employees.accdb"
        assert info["extension"] == ".accdb"
        assert info["size"] == accdb.stat().st_size
        assert ".accdb" in info["format"]
        assert info["is_locked"] is False
        assert info["warnings"] == []

    def test_accepts_mdb(self, tmp_path: Path):
        path = tmp_path / "Legacy.mdb"
        path.write_bytes(b"old jet db")
        info = resolve_local_source(str(path))
        assert info["extension"] == ".mdb"
        assert "2000-2003" in info["format"]

    def test_strips_surrounding_quotes(self, accdb: Path):
        # Windows "Copy as path" wraps the path in double quotes.
        assert resolve_local_source(f'"{accdb}"')["path"] == str(accdb)

    def test_rejects_wrong_extension(self, tmp_path: Path):
        path = tmp_path / "notes.txt"
        path.write_text("hello")
        with pytest.raises(LocalSourceError, match="not an Access database"):
            resolve_local_source(str(path))

    def test_rejects_missing_file(self, tmp_path: Path):
        with pytest.raises(LocalSourceError, match="not found"):
            resolve_local_source(str(tmp_path / "ghost.accdb"))

    def test_rejects_directory(self, tmp_path: Path):
        directory = tmp_path / "database.accdb"
        directory.mkdir()
        with pytest.raises(LocalSourceError, match="Not a file"):
            resolve_local_source(str(directory))

    @pytest.mark.parametrize("value", ["", "   ", None])
    def test_rejects_empty_path(self, value):
        with pytest.raises(LocalSourceError, match="No path provided"):
            resolve_local_source(value)

    def test_detects_laccdb_lock(self, accdb: Path):
        accdb.with_suffix(".laccdb").write_bytes(b"lock")
        info = resolve_local_source(str(accdb))
        assert info["is_locked"] is True
        assert any("open in MS Access" in w for w in info["warnings"])

    def test_detects_ldb_lock_for_mdb(self, tmp_path: Path):
        path = tmp_path / "Legacy.mdb"
        path.write_bytes(b"old jet db")
        path.with_suffix(".ldb").write_bytes(b"lock")
        assert resolve_local_source(str(path))["is_locked"] is True


class TestLocalRootsAllowlist:
    """CONVERTER_LOCAL_ROOTS confines which directories may be read."""

    def test_allows_path_inside_root(self, accdb: Path, monkeypatch):
        monkeypatch.setenv(local_source.LOCAL_ROOTS_ENV, str(accdb.parent))
        assert resolve_local_source(str(accdb))["path"] == str(accdb)

    def test_allows_path_in_nested_subdirectory(self, tmp_path: Path, monkeypatch):
        nested = tmp_path / "projects" / "hr"
        nested.mkdir(parents=True)
        db = nested / "HR.accdb"
        db.write_bytes(b"db")
        monkeypatch.setenv(local_source.LOCAL_ROOTS_ENV, str(tmp_path))
        assert resolve_local_source(str(db))["path"] == str(db)

    def test_rejects_path_outside_root(self, accdb: Path, tmp_path: Path, monkeypatch):
        other = tmp_path / "elsewhere"
        other.mkdir()
        monkeypatch.setenv(local_source.LOCAL_ROOTS_ENV, str(other))
        with pytest.raises(LocalSourceError, match="outside the directories allowed"):
            resolve_local_source(str(accdb))

    def test_honours_multiple_roots(self, accdb: Path, tmp_path: Path, monkeypatch):
        other = tmp_path / "elsewhere"
        other.mkdir()
        monkeypatch.setenv(
            local_source.LOCAL_ROOTS_ENV,
            os.pathsep.join([str(other), str(accdb.parent)]),
        )
        assert resolve_local_source(str(accdb))["path"] == str(accdb)

    def test_unset_allows_any_path(self, accdb: Path, monkeypatch):
        monkeypatch.delenv(local_source.LOCAL_ROOTS_ENV, raising=False)
        assert resolve_local_source(str(accdb))["path"] == str(accdb)


# ---------------------------------------------------------------- staging

class TestStageLocalSource:
    """The safety boundary: extraction must never touch the user's own file."""

    def test_copy_is_byte_identical_and_original_untouched(self, accdb: Path, tmp_path: Path):
        original_bytes = accdb.read_bytes()
        original_mtime = accdb.stat().st_mtime

        staged = stage_local_source(str(accdb), tmp_path / "job")

        assert staged.exists()
        assert staged != accdb
        assert staged.read_bytes() == original_bytes
        # The guarantee this whole feature rests on.
        assert accdb.read_bytes() == original_bytes
        assert accdb.stat().st_mtime == original_mtime

    def test_staged_into_source_subdirectory_of_workdir(self, accdb: Path, tmp_path: Path):
        workdir = tmp_path / "job-abc"
        staged = stage_local_source(str(accdb), workdir)
        assert staged.parent == (workdir / "source").resolve()
        assert staged.name == accdb.name

    def test_mutating_the_copy_leaves_the_original_intact(self, accdb: Path, tmp_path: Path):
        """Simulates what extraction does to whatever file it opens."""
        original_bytes = accdb.read_bytes()
        staged = stage_local_source(str(accdb), tmp_path / "job")

        staged.write_bytes(b"extractor rewrote this")

        assert accdb.read_bytes() == original_bytes

    def test_creates_workdir_when_missing(self, accdb: Path, tmp_path: Path):
        staged = stage_local_source(str(accdb), tmp_path / "deep" / "nested" / "job")
        assert staged.exists()


# ---------------------------------------------------------------- capability

class TestProbeCapability:

    def test_reports_unavailable_without_raising_on_non_windows(self, monkeypatch):
        # Patch the attribute on the module's own `sys` reference. monkeypatch
        # restores it after the test, so the global sys.platform is intact.
        monkeypatch.setattr(local_source.sys, "platform", "linux", raising=True)
        result = probe_capability()
        assert result["available"] is False
        assert result["com_available"] is False
        assert "Windows" in result["reason"]

    def test_reports_unavailable_when_pywin32_missing(self, monkeypatch):
        monkeypatch.setattr(local_source.sys, "platform", "win32", raising=True)
        import builtins
        real_import = builtins.__import__

        def fake_import(name, *args, **kwargs):
            if name in ("pythoncom", "win32com.client", "win32com"):
                raise ImportError("no pywin32 here")
            return real_import(name, *args, **kwargs)

        monkeypatch.setattr(builtins, "__import__", fake_import)
        result = probe_capability()
        assert result["available"] is False
        assert "pywin32" in result["reason"]

    @pytest.mark.skipif(
        local_source.sys.platform != "win32", reason="requires Windows COM")
    def test_available_when_access_installed_but_not_running(self, monkeypatch):
        """Regression: the probe reported "not registered" whenever Access was
        closed, because the not-running branch called pythoncom.CLSIDFromProgID
        — an attribute pywin32 does not define. Availability must not depend on
        Access happening to be open.
        """
        import win32com.client

        def not_running(*args, **kwargs):
            raise Exception("no active object")

        monkeypatch.setattr(win32com.client, "GetActiveObject", not_running)

        result = probe_capability()

        assert result["access_running"] is False
        # Access 14.0 is installed on this machine, so the closed-Access path
        # must still resolve it via the registry.
        assert result["available"] is True, result["reason"]
        assert result["access_installed"] is True
        assert result["reason"] is None

    @pytest.mark.skipif(
        local_source.sys.platform != "win32", reason="requires Windows registry")
    def test_registered_clsid_and_version_resolve(self):
        assert local_source._registered_access_clsid() is not None
        version = local_source._registered_access_version()
        assert version is None or version.endswith(".0")

    @pytest.mark.skipif(
        local_source.sys.platform != "win32", reason="requires Windows COM")
    def test_does_not_launch_access_when_not_running(self, monkeypatch):
        """Probing must not spawn Access: COM is a single-instance resource
        and a spurious instance can break a concurrent extraction."""
        import win32com.client

        def fail_if_launched(*args, **kwargs):
            raise AssertionError("probe_capability must not Dispatch Access")

        monkeypatch.setattr(win32com.client, "DispatchEx", fail_if_launched)
        monkeypatch.setattr(win32com.client, "Dispatch", fail_if_launched)
        result = probe_capability()
        # On this machine Access is installed, so it should report available
        # without ever constructing an Access.Application object.
        assert result["com_available"] is True


class TestDiscoveryOnNonWindows:

    def test_open_databases_empty(self, monkeypatch):
        monkeypatch.setattr(local_source.sys, "platform", "linux", raising=True)
        assert local_source.discover_open_databases() == []

    def test_recent_databases_empty(self, monkeypatch):
        monkeypatch.setattr(local_source.sys, "platform", "linux", raising=True)
        assert local_source.discover_recent_databases() == []


class TestFormatFileSize:

    @pytest.mark.parametrize("size,expected", [
        (0, "0 B"),
        (512, "512 B"),
        (2048, "2.00 KB"),
        (5 * 1024 * 1024, "5.00 MB"),
    ])
    def test_formats(self, size, expected):
        assert format_file_size(size) == expected


# ---------------------------------------------------------------- API

@pytest_asyncio.fixture
async def client():
    from converter.app.api.main import app
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


class TestLocalAccessEndpoints:

    @pytest.mark.asyncio
    async def test_capability_returns_shape(self, client, monkeypatch):
        monkeypatch.setattr(
            "converter.app.api.main.probe_capability",
            lambda: {"available": True, "access_version": "14.0",
                     "access_running": False, "reason": None},
        )
        response = await client.get("/api/local-access/capability")
        assert response.status_code == 200
        assert response.json()["access_version"] == "14.0"

    @pytest.mark.asyncio
    async def test_sources_lists_open_and_recent(self, client, monkeypatch):
        monkeypatch.setattr(
            "converter.app.api.main.discover_open_databases",
            lambda: [{"path": r"C:\a.accdb", "name": "a.accdb"}],
        )
        monkeypatch.setattr(
            "converter.app.api.main.discover_recent_databases",
            lambda: [{"path": r"C:\b.accdb", "name": "b.accdb"}],
        )
        response = await client.get("/api/local-access/sources")
        assert response.status_code == 200
        body = response.json()
        assert body["open"][0]["name"] == "a.accdb"
        assert body["recent"][0]["name"] == "b.accdb"
        assert body["errors"] == []

    @pytest.mark.asyncio
    async def test_sources_survives_discovery_failure(self, client, monkeypatch):
        """A broken COM attach must not hide the recent-files list."""
        def boom():
            raise RuntimeError("COM exploded")

        monkeypatch.setattr("converter.app.api.main.discover_open_databases", boom)
        monkeypatch.setattr(
            "converter.app.api.main.discover_recent_databases",
            lambda: [{"path": r"C:\b.accdb", "name": "b.accdb"}],
        )
        response = await client.get("/api/local-access/sources")
        assert response.status_code == 200
        body = response.json()
        assert body["open"] == []
        assert body["recent"][0]["name"] == "b.accdb"
        assert any("COM exploded" in e for e in body["errors"])

    @pytest.mark.asyncio
    async def test_validate_accepts_real_file(self, client, accdb: Path):
        response = await client.post(
            "/api/local-access/validate", json={"path": str(accdb)})
        assert response.status_code == 200
        assert response.json()["name"] == "Employees.accdb"

    @pytest.mark.asyncio
    async def test_validate_rejects_bad_path(self, client, tmp_path: Path):
        response = await client.post(
            "/api/local-access/validate", json={"path": str(tmp_path / "nope.accdb")})
        assert response.status_code == 400
        assert "not found" in response.json()["detail"]

    @pytest.mark.asyncio
    async def test_create_local_job_rejects_bad_path(self, client, tmp_path: Path):
        response = await client.post(
            "/api/jobs/local", json={"path": str(tmp_path / "nope.accdb")})
        assert response.status_code == 400

    @pytest.mark.asyncio
    async def test_create_local_job_rejects_wrong_extension(self, client, tmp_path: Path):
        path = tmp_path / "data.csv"
        path.write_text("a,b")
        response = await client.post("/api/jobs/local", json={"path": str(path)})
        assert response.status_code == 400
        assert "not an Access database" in response.json()["detail"]
