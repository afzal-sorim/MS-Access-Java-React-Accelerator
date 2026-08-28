"""Direct local MS Access source discovery (spec sections 4-5).

The converter backend runs on the same Windows machine as MS Access, so the
database the user wants to convert is already on local disk. This module lets
the UI pick it directly — from the running Access instance, from Access's own
recent-files list, or by absolute path — instead of round-tripping the file
through an HTTP upload.

This module only *acquires* a source path. Extraction, IR, and generation are
untouched: `stage_local_source` hands a plain path to the same
`run_extraction` the upload path uses.

Safety: extraction is destructive to the source database. `AccessExtractor`
opens every form/report in design view, calls `DoCmd.OpenModule`, and runs
SaveAsText/VBE export — all of which write to the .accdb and leave a .laccdb
lock behind. The user's real database must therefore never be handed to the
extractor; `stage_local_source` copies it into the job workdir first and
everything downstream operates on that copy.

COM/registry imports are function-local (as in extractor.py) so this module
imports cleanly on non-Windows platforms and in CI.
"""
from __future__ import annotations

import os
import shutil
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

# Access database extensions we accept as a conversion source (spec section 4).
ACCESS_EXTENSIONS = (".accdb", ".mdb")

# Office versions that may have registered Access. 16.0 covers 2016/2019/365.
OFFICE_VERSIONS = ("16.0", "15.0", "14.0")

# Cap on the recent-files list handed to the UI.
MAX_RECENT = 15

SOURCE_MODE_UPLOAD = "UPLOAD"
SOURCE_MODE_LOCAL = "LOCAL_DIRECT"

# Env var holding an os.pathsep-separated allowlist of directories that local
# sources must live under. Unset (the default) allows any local path, which is
# correct for the single-user desktop deployment this feature targets.
LOCAL_ROOTS_ENV = "CONVERTER_LOCAL_ROOTS"


class LocalSourceError(ValueError):
    """A caller-supplied local path is not a usable Access database."""


# ---------------------------------------------------------------- formatting

def format_file_size(size: int) -> str:
    """Human-readable byte count, mirroring the UI's formatFileSize()."""
    if size <= 0:
        return "0 B"
    for unit in ("B", "KB", "MB", "GB"):
        if size < 1024 or unit == "GB":
            return f"{size:.0f} {unit}" if unit == "B" else f"{size:.2f} {unit}"
        size /= 1024.0
    return f"{size:.2f} GB"


def describe_format(extension: str) -> str:
    """Human-readable Access file-format label for an extension."""
    return ("Access 2007-2016+ (.accdb)" if extension.lower() == ".accdb"
            else "Access 2000-2003 (.mdb)")


# ---------------------------------------------------------------- capability

def probe_capability() -> dict:
    """Report whether direct local extraction is possible on this machine.

    Never raises: the UI calls this to decide whether to *offer* the direct
    mode, so a missing Access install has to come back as a plain answer with
    a reason rather than an error.

    Deliberately does NOT launch Access. Access COM is a machine-wide
    single-instance resource — corpus/runner.py documents real extraction
    failures caused by two instances contending — so spawning one just to read
    a version number could break a running conversion. Instead we resolve the
    ProgID through the registry, which proves Access is registered without
    starting it.
    """
    result: dict[str, Any] = {
        "available": False,
        "platform": sys.platform,
        "com_available": False,
        "access_installed": False,
        "access_version": None,
        "access_running": False,
        "reason": None,
    }

    if sys.platform != "win32":
        result["reason"] = (
            f"Direct MS Access extraction requires Windows; this backend is "
            f"running on {sys.platform}. Use file upload instead.")
        return result

    try:
        import pythoncom
        import win32com.client
    except ImportError as exc:
        result["reason"] = (
            f"pywin32 is not installed on the backend ({exc}), so MS Access "
            f"COM automation is unavailable. Use file upload instead.")
        return result

    result["com_available"] = True

    pythoncom.CoInitialize()
    try:
        # A running instance can answer the version directly, for free.
        try:
            running = win32com.client.GetActiveObject("Access.Application")
            result["access_running"] = True
            result["access_installed"] = True
            result["access_version"] = str(_safe(lambda: running.Version) or "")
            result["available"] = True
            return result
        except Exception:
            pass

        # Not running: prove registration without starting Access. Read the
        # registry directly rather than calling a COM ProgID-resolution API —
        # pythoncom does not expose CLSIDFromProgID, and guessing at that
        # surface is what made this probe report "not installed" whenever
        # Access happened to be closed.
        clsid = _registered_access_clsid()
        if clsid is None:
            result["reason"] = (
                "MS Access does not appear to be registered for COM automation "
                "on the converter machine. Confirm MS Access is installed, or "
                "use file upload instead.")
            return result

        result["access_installed"] = True
        result["available"] = True
        result["access_version"] = _registered_access_version()
    finally:
        pythoncom.CoUninitialize()

    return result


def _registered_access_clsid() -> Optional[str]:
    """The CLSID registered for Access.Application, or None if absent.

    This is the same lookup COM performs internally for a ProgID, so its
    presence is a reliable "Access is installed and automatable" signal
    without launching anything.
    """
    try:
        import winreg
    except ImportError:
        return None
    for progid in ("Access.Application", "Access.Application.16",
                   "Access.Application.15", "Access.Application.14"):
        try:
            with winreg.OpenKey(winreg.HKEY_CLASSES_ROOT,
                                rf"{progid}\CLSID") as handle:
                clsid = str(winreg.QueryValueEx(handle, "")[0]).strip()
                if clsid:
                    return clsid
        except OSError:
            continue
    return None


def _registered_access_version() -> Optional[str]:
    """Access version from the registry, e.g. '14.0'. None if undeterminable.

    Tries HKCR\\Access.Application\\CurVer (a versioned ProgID such as
    'Access.Application.14'), then falls back to probing versioned ProgIDs
    directly, since not every install writes CurVer. Returning None is fine —
    the version is display-only and never gates availability.
    """
    try:
        import winreg
    except ImportError:
        return None

    try:
        with winreg.OpenKey(winreg.HKEY_CLASSES_ROOT,
                            r"Access.Application\CurVer") as handle:
            prog_id = str(winreg.QueryValueEx(handle, "")[0])
        major = prog_id.rpartition(".")[2]
        if major.isdigit():
            return f"{major}.0"
    except OSError:
        pass

    for version in OFFICE_VERSIONS:
        major = version.split(".")[0]
        try:
            winreg.CloseKey(winreg.OpenKey(
                winreg.HKEY_CLASSES_ROOT, rf"Access.Application.{major}\CLSID"))
            return version
        except OSError:
            continue
    return None


def _safe(fn, default=None):
    """Call a COM accessor, swallowing COM errors (as in extractor.py)."""
    try:
        value = fn()
        return value if value is not None else default
    except Exception:
        return default


# ---------------------------------------------------------------- discovery

def discover_open_databases() -> list[dict]:
    """Databases open in a currently-running MS Access instance.

    Returns [] rather than raising when Access is closed or has nothing open —
    that is the normal case, not an error.
    """
    if sys.platform != "win32":
        return []
    try:
        import pythoncom
        import win32com.client
    except ImportError:
        return []

    pythoncom.CoInitialize()
    try:
        try:
            app = win32com.client.GetActiveObject("Access.Application")
        except Exception:
            return []  # Access not running

        full_name = _safe(lambda: app.CurrentProject.FullName)
        if not full_name:
            return []  # Access running with no database open

        path = Path(str(full_name))
        if path.suffix.lower() not in ACCESS_EXTENSIONS or not path.is_file():
            return []
        return [_source_entry(path, origin="OPEN_IN_ACCESS")]
    finally:
        pythoncom.CoUninitialize()


def parse_mru_value(value: str) -> Optional[str]:
    """Extract the file path from an Access File MRU registry value.

    Access stores entries as `[F00000000][T01D9...][O00000000]*C:\\path\\db.accdb`
    — flag blocks, then `*`, then the path. Some builds store a bare path.
    """
    if not value:
        return None
    text = str(value).strip()
    if "*" in text:
        text = text.split("*", 1)[1]
    elif text.startswith("["):
        # Bracketed prefix but no separator: unparseable.
        return None
    text = text.strip().strip('"')
    return text or None


def discover_recent_databases() -> list[dict]:
    """Access databases from Access's own File MRU list, newest first."""
    if sys.platform != "win32":
        return []
    try:
        import winreg
    except ImportError:
        return []

    entries: list[dict] = []
    seen: set[str] = set()

    for version in OFFICE_VERSIONS:
        key_path = rf"SOFTWARE\Microsoft\Office\{version}\Access\File MRU"
        try:
            handle = winreg.OpenKey(winreg.HKEY_CURRENT_USER, key_path)
        except OSError:
            continue
        try:
            value_count = winreg.QueryInfoKey(handle)[1]
            for index in range(value_count):
                try:
                    name, value, _ = winreg.EnumValue(handle, index)
                except OSError:
                    continue
                if not name.lower().startswith("item"):
                    continue
                raw_path = parse_mru_value(value)
                if not raw_path:
                    continue
                path = Path(raw_path)
                if path.suffix.lower() not in ACCESS_EXTENSIONS:
                    continue
                key = str(path).lower()
                if key in seen:
                    continue
                seen.add(key)
                if not path.is_file():
                    continue  # moved or on a disconnected drive
                entries.append(_source_entry(path, origin="RECENT"))
                if len(entries) >= MAX_RECENT:
                    return entries
        finally:
            winreg.CloseKey(handle)

    return entries


def _source_entry(path: Path, *, origin: str) -> dict:
    """Lightweight descriptor for a discovered database (no validation)."""
    entry = {
        "path": str(path),
        "name": path.name,
        "extension": path.suffix.lower(),
        "format": describe_format(path.suffix),
        "origin": origin,
        "size": None,
        "formatted_size": None,
        "last_modified": None,
    }
    try:
        stat = path.stat()
        entry["size"] = stat.st_size
        entry["formatted_size"] = format_file_size(stat.st_size)
        entry["last_modified"] = datetime.fromtimestamp(stat.st_mtime).isoformat(
            sep=" ", timespec="seconds")
    except OSError:
        pass
    return entry


# ---------------------------------------------------------------- validation

def _allowed_roots() -> list[Path]:
    """Directories local sources must live under, from CONVERTER_LOCAL_ROOTS."""
    raw = os.environ.get(LOCAL_ROOTS_ENV, "").strip()
    if not raw:
        return []
    roots = []
    for chunk in raw.split(os.pathsep):
        chunk = chunk.strip().strip('"')
        if chunk:
            try:
                roots.append(Path(chunk).resolve())
            except OSError:
                continue
    return roots


def resolve_local_source(path: str) -> dict:
    """Validate a caller-supplied local path and describe the database.

    This is the only place a caller-supplied path reaches the filesystem, so
    every check lives here. Raises LocalSourceError with a user-facing message
    on anything unusable.
    """
    if not path or not str(path).strip():
        raise LocalSourceError("No path provided.")

    try:
        resolved = Path(str(path).strip().strip('"')).expanduser().resolve()
    except OSError as exc:
        raise LocalSourceError(f"Path could not be resolved: {exc}") from exc

    if resolved.suffix.lower() not in ACCESS_EXTENSIONS:
        raise LocalSourceError(
            f"'{resolved.name}' is not an Access database. Expected one of: "
            f"{', '.join(ACCESS_EXTENSIONS)}.")

    if not resolved.exists():
        raise LocalSourceError(f"File not found on the backend machine: {resolved}")

    if not resolved.is_file():
        raise LocalSourceError(f"Not a file: {resolved}")

    roots = _allowed_roots()
    if roots and not any(_is_within(resolved, root) for root in roots):
        raise LocalSourceError(
            f"'{resolved}' is outside the directories allowed by "
            f"{LOCAL_ROOTS_ENV}.")

    try:
        stat = resolved.stat()
    except OSError as exc:
        raise LocalSourceError(f"File is not readable: {exc}") from exc

    # Fail here rather than deep inside COM extraction: an exclusive-locked or
    # permission-denied file produces an opaque COM error otherwise.
    try:
        with open(resolved, "rb") as handle:
            handle.read(1)
    except OSError as exc:
        raise LocalSourceError(
            f"File cannot be read (it may be locked exclusively or "
            f"permission-denied): {exc}") from exc

    warnings: list[str] = []
    is_locked = _lock_file_for(resolved) is not None
    if is_locked:
        warnings.append(
            "This database is currently open in MS Access. It will be copied "
            "before extraction, so unsaved design changes may not be included.")

    return {
        "path": str(resolved),
        "name": resolved.name,
        "extension": resolved.suffix.lower(),
        "format": describe_format(resolved.suffix),
        "size": stat.st_size,
        "formatted_size": format_file_size(stat.st_size),
        "last_modified": datetime.fromtimestamp(stat.st_mtime).isoformat(
            sep=" ", timespec="seconds"),
        "is_locked": is_locked,
        "warnings": warnings,
    }


def _is_within(candidate: Path, root: Path) -> bool:
    try:
        candidate.relative_to(root)
        return True
    except ValueError:
        return False


def _lock_file_for(path: Path) -> Optional[Path]:
    """The sibling .laccdb/.ldb lock file, when Access has the db open."""
    for suffix in (".laccdb", ".ldb"):
        candidate = path.with_suffix(suffix)
        if candidate.exists():
            return candidate
    return None


# ---------------------------------------------------------------- staging

def stage_local_source(path: str, workdir: str | Path) -> Path:
    """Copy a local database into `workdir` and return the copy's path.

    The safety boundary for this whole feature. Extraction writes to the
    database it opens, so the user's own file is never the one handed to the
    extractor — we snapshot it first, giving the direct mode the same
    isolation the upload path gets by construction.

    Any sibling .laccdb lock file is deliberately not copied; Access recreates
    its own lock next to the copy.
    """
    source = Path(path)
    destination_dir = Path(workdir).resolve() / "source"
    destination_dir.mkdir(parents=True, exist_ok=True)
    destination = destination_dir / source.name
    # copy2 preserves mtime so the staged copy still reports the original's
    # timestamps in the migration report.
    shutil.copy2(source, destination)
    return destination
