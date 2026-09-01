"""MS Access extraction via COM automation + DAO + SaveAsText (spec sections 5-7).

Strategy: ODBC alone cannot see forms/reports/VBA/macros, so we drive the real
Access Application object. The extractor emits plain JSON-able dicts plus
SaveAsText source dumps; it never builds IR models itself.

Must run on Windows with MS Access installed. COM is apartment-threaded, so
`run_extraction` initializes COM for the calling thread.
"""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Optional

# ---------------------------------------------------------------- manifest

# Strict extraction statuses (spec: "OBJECT DISCOVERED != EXTRACTED").
# "NOT_PRESENT" is only legal for object kinds the database genuinely lacks;
# a failed read must surface as PARTIAL/FAILED, never as absence.
EXTRACTION_STATUSES = ("SUCCESS", "PARTIAL", "FAILED", "UNSUPPORTED", "NOT_PRESENT")

AC_MODULE_CONST = 5  # DoCmd acModule


def _manifest_entry(name: str, obj_type: str, status: str,
                    source_available: bool, errors: Optional[list[str]] = None) -> dict:
    assert status in EXTRACTION_STATUSES, status
    return {
        "name": name,
        "type": obj_type,
        "extractionStatus": status,
        "sourceAvailable": source_available,
        "errors": errors or [],
    }


def read_text_auto(path: str | Path) -> str:
    """Read a SaveAsText dump with encoding detection.

    Access writes SaveAsText files as UTF-16LE (macros, some forms) or as
    8-bit text (modules exported via VBE). Reading everything as latin-1
    produced NUL-padded gibberish for the UTF-16 half, which silently broke
    every downstream parser.
    """
    data = Path(path).read_bytes()
    if data[:2] in (b"\xff\xfe", b"\xfe\xff"):
        # The 'utf-16' codec consumes the BOM itself.
        return data.decode("utf-16")
    if data.startswith(b"\xef\xbb\xbf"):
        return data.decode("utf-8-sig")
    for encoding in ("utf-8", "cp1252", "latin-1"):
        try:
            return data.decode(encoding)
        except UnicodeDecodeError:
            continue
    return data.decode("latin-1", errors="replace")

# ---------------------------------------------------------------- constants
# DAO DataTypeEnum
DAO_FIELD_TYPES = {
    1: "Yes/No", 2: "Byte", 3: "Integer (Short)", 4: "Long Integer", 5: "Currency",
    6: "Single", 7: "Double", 8: "Date/Time", 9: "Binary", 10: "Short Text",
    11: "OLE Object", 12: "Long Text", 15: "Replication ID", 16: "BigInt",
    17: "VarBinary", 18: "Char", 19: "Numeric", 20: "Decimal", 21: "Float",
    22: "Time", 23: "TimeStamp",
    101: "Attachment", 102: "Complex Byte", 103: "Complex Integer",
    104: "Complex Long", 105: "Complex Single", 106: "Complex Double",
    107: "Complex Decimal", 108: "Complex Text",
}
DB_AUTOINCR = 16  # Field.Attributes bit

# Access ControlType numbers -> names
CONTROL_TYPES = {
    100: "Label", 101: "Rectangle", 102: "Line", 103: "Image", 104: "CommandButton",
    105: "OptionButton", 106: "CheckBox", 107: "OptionGroup", 108: "BoundObjectFrame",
    109: "TextBox", 110: "ListBox", 111: "ComboBox", 112: "Subform",
    114: "ObjectFrame", 118: "PageBreak", 119: "CustomControl", 122: "ToggleButton",
    123: "TabControl", 124: "Page", 126: "Attachment", 127: "EmptyCell",
    128: "WebBrowser",
}

CONTROL_EVENTS = [
    "OnClick", "OnDblClick", "OnChange", "OnEnter", "OnExit", "OnGotFocus",
    "OnLostFocus", "BeforeUpdate", "AfterUpdate", "OnNotInList", "OnMouseDown",
]
FORM_EVENTS = [
    "OnLoad", "OnOpen", "OnClose", "OnUnload", "OnCurrent", "BeforeInsert",
    "AfterInsert", "AfterUpdate", "BeforeUpdate", "OnDirty", "OnTimer",
    "OnActivate", "OnDeactivate", "BeforeDelConfirm", "AfterDelConfirm",
]

AC_FORM, AC_MACRO, AC_MODULE, AC_QUERY, AC_REPORT = 2, 4, 5, 1, 3

SECRET_KEYS = {"pwd", "password", "jet oledb:password", "encryptedpwd"}


def sanitize_connect(connect: Optional[str]) -> Optional[str]:
    """Remove credential values from connection strings (spec section 8)."""
    if not connect:
        return None
    parts = []
    for token in connect.split(";"):
        if "=" in token:
            key, _, value = token.partition("=")
            if key.strip().lower() in SECRET_KEYS:
                value = "***REDACTED***"
            parts.append(f"{key}={value}")
        else:
            parts.append(token)
    return ";".join(parts)


def _prop(obj: Any, name: str, default: Any = None) -> Any:
    """Safe COM property read: missing properties raise COM errors."""
    try:
        value = obj.Properties(name).Value
        return value if value is not None else default
    except Exception:
        try:
            return getattr(obj, name, default)
        except Exception:
            return default


def _safe(fn, default=None):
    try:
        value = fn()
        return value if value is not None else default
    except Exception:
        return default


class AccessExtractor:
    """Drives MS Access via COM to produce a raw extraction payload."""

    def __init__(self, db_path: str, workdir: Path, *, extract_data: bool = True,
                 max_rows_per_table: int = 5000,
                 fallback_source_dir: str | Path | None = None):
        self.db_path = str(Path(db_path).resolve())
        # SaveAsText hands the path straight to the Access COM object, which
        # resolves it against Access's own CWD — a relative workdir produced
        # "Microsoft Access can't open the file 'outputs\...'" for every
        # single dump. Everything downstream must be absolute.
        self.workdir = Path(workdir).resolve()
        self.source_dir = self.workdir / "source"
        self.extract_data = extract_data
        self.max_rows = max_rows_per_table
        # Optional directory of previously captured SaveAsText/VBE dumps
        # (e.g. corpus saved-text or vbs_access_export output) used as the
        # last-resort extraction strategy.
        self.fallback_source_dir = Path(fallback_source_dir).resolve() if fallback_source_dir else None
        self.warnings: list[str] = []
        self.data: dict[str, list[dict]] = {}
        self.manifest: dict[str, list[dict]] = {
            "tables": [], "queries": [], "forms": [], "reports": [],
            "macros": [], "vbaModules": [], "relationships": [],
        }

    # ------------------------------------------------------------ entry
    def run(self) -> dict:
        import pythoncom
        import win32com.client

        try:
            pythoncom.CoInitializeEx(pythoncom.COINIT_APARTMENTTHREADED)
        except Exception:
            pythoncom.CoInitialize()

        app = None
        try:
            try:
                app = win32com.client.DispatchEx("Access.Application")
            except Exception:
                app = win32com.client.Dispatch("Access.Application")
            _safe(lambda: setattr(app, "Visible", False))
            app.OpenCurrentDatabase(self.db_path, False)
            payload = self._extract_all(app)
            _safe(app.CloseCurrentDatabase)
        finally:
            if app is not None:
                _safe(app.Quit)
                app = None
            try:
                pythoncom.CoUninitialize()
            except Exception:
                pass
        payload["warnings"] = self.warnings
        payload["table_data"] = {
            name: rows for name, rows in self.data.items()
        }
        payload["manifest"] = self.manifest
        self._write_json(payload)
        return payload

    # ------------------------------------------------------------ helpers
    def _write_json(self, payload: dict) -> None:
        self.workdir.mkdir(parents=True, exist_ok=True)
        (self.workdir / "extraction.json").write_text(
            json.dumps(payload, indent=2, default=str), encoding="utf-8")

    def _save_as_text(self, app, obj_type: int, name: str, subdir: str) -> Optional[str]:
        safe_name = re.sub(r"[^A-Za-z0-9_\-]", "_", name)
        folder = self.source_dir / subdir
        folder.mkdir(parents=True, exist_ok=True)
        path = folder / f"{safe_name}.txt"
        try:
            app.SaveAsText(obj_type, name, str(path))
            return str(path)
        except Exception as exc:
            self.warnings.append(f"SaveAsText failed for {subdir}/{name}: {exc}")
            return None

    def _read_dump(self, path: Optional[str]) -> Optional[str]:
        """Read a dump file with encoding detection; None if missing."""
        if not path:
            return None
        try:
            return read_text_auto(path)
        except Exception as exc:
            self.warnings.append(f"read failed for {path}: {exc}")
            return None

    # ------------------------------------------------------------ database
    def _extract_all(self, app) -> dict:
        db = app.CurrentDb()
        payload: dict[str, Any] = {
            "source_file": self.db_path,
            "database": self._database_info(db, app),
            "tables": [],
            "relationships": [],
            "queries": [],
            "forms": [],
            "reports": [],
            "macros": [],
            "modules": [],
            "source_dumps": {},
        }

        for table in self._extract_tables(db):
            payload["tables"].append(table)
            self.manifest["tables"].append(_manifest_entry(
                table["name"], "TABLE", "SUCCESS", True))
        payload["relationships"] = self._extract_relationships(db)
        self.manifest["relationships"] = [
            _manifest_entry(r["name"], "RELATIONSHIP", "SUCCESS", True)
            for r in payload["relationships"]]
        payload["queries"] = self._extract_queries(db)
        for query in payload["queries"]:
            status = "SUCCESS" if (query.get("sql") or "").strip() else "PARTIAL"
            self.manifest["queries"].append(_manifest_entry(
                query["name"], "QUERY", status, bool((query.get("sql") or "").strip()),
                [] if status == "SUCCESS" else ["query SQL is empty"]))
        payload["forms"] = self._extract_forms(app)
        payload["reports"] = self._extract_reports(app)
        payload["macros"] = self._extract_macros(app)
        payload["modules"] = self._extract_modules(app)

        # Form/report code-behind modules are not part of AllModules; fold
        # their captured sources into the modules payload so the IR sees a
        # single complete VBA inventory.
        for form in payload["forms"]:
            if form.get("has_module"):
                payload["modules"].append({
                    "name": form.get("module") or f"Form_{form['name']}",
                    "module_type": "FORM",
                    "source": form.get("module_source") or "",
                    "extraction_strategy": "FormModule" if form.get("module_source") else None,
                })
        for report in payload["reports"]:
            if report.get("has_module"):
                payload["modules"].append({
                    "name": report.get("module") or f"Report_{report['name']}",
                    "module_type": "REPORT",
                    "source": report.get("module_source") or "",
                    "extraction_strategy": "ReportModule" if report.get("module_source") else None,
                })
        return payload

    def _database_info(self, db, app) -> dict:
        info = {
            "name": Path(self.db_path).stem,
            "file_format": _safe(lambda: db.Properties("File Format").Value),
            "access_version": _safe(lambda: db.Properties("AccessVersion").Value),
            "connect": sanitize_connect(_safe(lambda: db.Connect, "") or None),
        }
        startup = {
            "startup_form": _prop(db, "StartupForm"),
            "application_title": _prop(db, "AppTitle"),
            "allow_full_menus": _prop(db, "AllowFullMenus", True),
            "startup_macro": _prop(db, "StartupModule"),
        }
        info["startup"] = {k: v for k, v in startup.items() if v is not None}
        return info

    # ------------------------------------------------------------ tables
    def _extract_tables(self, db) -> list[dict]:
        tables = []
        for i in range(db.TableDefs.Count):
            tdef = db.TableDefs(i)
            name = tdef.Name
            if name.startswith("MSys") or name.startswith("~"):
                continue
            connect = sanitize_connect(_safe(lambda: tdef.Connect, "") or None)
            table = {
                "name": name,
                "is_linked": bool(connect),
                "connect": connect,
                "source_table_name": _safe(lambda: tdef.SourceTableName),
                "row_count": _safe(lambda: tdef.RecordCount, None),
                "description": _prop(tdef, "Description"),
                "columns": [],
                "indexes": [],
            }
            for j in range(tdef.Fields.Count):
                field = tdef.Fields(j)
                table["columns"].append(self._column(field, name))
            for j in range(tdef.Indexes.Count):
                index = tdef.Indexes(j)
                table["indexes"].append({
                    "name": index.Name,
                    "primary": bool(index.Primary),
                    "unique": bool(index.Unique),
                    "columns": [
                        index.Fields(k).Name for k in range(index.Fields.Count)
                    ],
                })
            tables.append(table)
            if self.extract_data and not table["is_linked"]:
                self._extract_table_data(db, name, table)
        return tables

    def _column(self, field, table_name: str) -> dict:
        ftype = int(_safe(lambda: field.Type, 12))
        col = {
            "name": field.Name,
            "dao_type_code": ftype,
            "access_type": DAO_FIELD_TYPES.get(ftype, f"Unknown({ftype})"),
            "size": _safe(lambda: field.Size, None),
            "precision": _prop(field, "Precision"),
            "scale": _prop(field, "NumericScale"),
            "required": bool(field.Required),
            "allow_null": not bool(field.Required),
            "auto_number": bool(int(_safe(lambda: field.Attributes, 0)) & DB_AUTOINCR),
            "default_value": _safe(lambda: field.DefaultValue),
            "validation_rule": _safe(lambda: field.ValidationRule) or None,
            "validation_text": _safe(lambda: field.ValidationText) or None,
            "ordinal": int(_safe(lambda: field.OrdinalPosition, 0)),
            "description": _prop(field, "Description"),
            "is_lookup": False,
            "is_multivalue": ftype >= 101,
            "is_attachment": ftype == 101,
            "is_calculated": _prop(field, "Expression") is not None,
            "calculated_expression": _prop(field, "Expression"),
            "is_hyperlink": bool(_safe(lambda: field.Properties("AppendOnly").Value, 0) == 2)
                             or _prop(field, "HyperlinkPart") is not None,
            "lookup_row_source": None,
            "lookup_row_source_type": None,
        }
        try:
            if int(_safe(lambda: field.Properties("DisplayControl").Value, 0)) in (110, 111):
                col["is_lookup"] = True
                col["lookup_row_source"] = _prop(field, "RowSource")
                col["lookup_row_source_type"] = _prop(field, "RowSourceType", "Table/Query")
        except Exception:
            pass
        if col["is_calculated"] and not col["calculated_expression"]:
            self.warnings.append(
                f"{table_name}.{field.Name}: calculated field expression unreadable")
        return col

    def _extract_table_data(self, db, name: str, table: dict) -> None:
        if table["row_count"] is not None and table["row_count"] > self.max_rows:
            self.warnings.append(
                f"{name}: {table['row_count']} rows exceeds cap "
                f"{self.max_rows}; data not extracted (schema only)")
            return
        if any(c["is_attachment"] or c["dao_type_code"] == 11 for c in table["columns"]):
            self.warnings.append(f"{name}: attachment/OLE columns present; data skipped")
            return
        try:
            rs = db.OpenRecordset(f"SELECT * FROM [{name}]", 4)  # dbOpenSnapshot
        except Exception as exc:
            self.warnings.append(f"{name}: data extraction failed: {exc}")
            return

        rows: list[dict] = []
        try:
            # Use GetRows for batch extraction - significantly faster than MoveNext loop.
            # rs.GetRows(max_rows) returns a 2D tuple (columns, rows).
            if not rs.EOF:
                # We need to know column count for GetRows
                raw_data = rs.GetRows(self.max_rows)
                if raw_data:
                    num_cols = len(raw_data)
                    num_rows = len(raw_data[0])
                    col_names = [col["name"] for col in table["columns"]]

                    for r in range(num_rows):
                        row = {}
                        for c in range(num_cols):
                            if c < len(col_names):
                                name = col_names[c]
                                row[name] = self._value(raw_data[c][r])
                        rows.append(row)
        except Exception as exc:
            self.warnings.append(f"{name}: GetRows failed: {exc}")
        finally:
            _safe(rs.Close)
        self.data[table["name"]] = rows

    @staticmethod
    def _value(value: Any) -> Any:
        import datetime as dt
        from decimal import Decimal
        if isinstance(value, (dt.datetime, dt.date)):
            return value.isoformat(sep=" ")
        if isinstance(value, bytes):
            return f"<binary {len(value)} bytes>"
        if isinstance(value, (float, Decimal)):
            # Ensure it's a float for JSON serialization, but round to avoid
            # precision artifacts from COM/DAO.
            return round(float(value), 10)
        return value

    # ------------------------------------------------------------ relations
    def _extract_relationships(self, db) -> list[dict]:
        relations = []
        for i in range(db.Relations.Count):
            rel = db.Relations(i)
            parent_fields, child_fields = [], []
            for j in range(rel.Fields.Count):
                rfield = rel.Fields(j)
                parent_fields.append(rfield.Name)
                child_fields.append(rfield.ForeignName)
            relations.append({
                "name": rel.Name,
                "parent_table": rel.Table,
                "child_table": rel.ForeignTable,
                "parent_columns": parent_fields,
                "child_columns": child_fields,
                # DAO: 1=dbRelationUnique(1:1), 2=dontEnforce, 256=updCascade, 4096=delCascade
                "enforce_integrity": not bool(rel.Attributes & 2),
                "cascade_update": bool(rel.Attributes & 256),
                "cascade_delete": bool(rel.Attributes & 4096),
                "one_to_one": bool(rel.Attributes & 1),
            })
        return relations

    # ------------------------------------------------------------ queries
    def _extract_queries(self, db) -> list[dict]:
        queries = []
        for i in range(db.QueryDefs.Count):
            qdef = db.QueryDefs(i)
            name = qdef.Name
            if name.startswith("~"):
                continue
            params = []
            try:
                for j in range(qdef.Parameters.Count):
                    p = qdef.Parameters(j)
                    params.append({
                        "name": p.Name,
                        "type": DAO_FIELD_TYPES.get(int(_safe(lambda: p.Type, 12)), "Text"),
                    })
            except Exception:
                pass
            queries.append({
                "name": name,
                "sql": _safe(lambda: qdef.SQL, "") or "",
                "dao_type": int(_safe(lambda: qdef.Type, 0)),
                "parameters": params,
            })
        return queries

    # ------------------------------------------------------------ forms
    def _extract_forms(self, app) -> list[dict]:
        forms = []
        all_forms = app.CurrentProject.AllForms
        for i in range(all_forms.Count):
            name = all_forms(i).Name
            form = {
                "name": name,
                "is_subform": name.startswith("sub") or name.startswith("Sub"),
                "record_source": None,
                "caption": None,
                "controls": [],
                "events": {},
                "module": None,
                "module_source": None,
                "has_module": False,
                "parent_links": {},
            }
            opened = False
            try:
                app.DoCmd.OpenForm(name, 1, None, None, -1, 4)  # design, hidden
                opened = True
                frm = app.Forms(name)
                form["record_source"] = _safe(lambda: frm.RecordSource) or None
                form["caption"] = _safe(lambda: frm.Caption) or None
                form["has_module"] = bool(_safe(lambda: frm.HasModule, False))
                if form["has_module"]:
                    form["module"] = f"Form_{name}"
                    # Event-handler VBA lives in the form's code-behind.
                    # SaveAsText cannot reach it while hidden; the Module
                    # object is the authoritative source.
                    source = self._read_com_module(lambda: frm.Module)
                    if source:
                        form["module_source"] = source
                for event in FORM_EVENTS:
                    handler = _prop(frm, event)
                    if handler:
                        form["events"][event] = str(handler)
                for j in range(frm.Controls.Count):
                    ctl = frm.Controls(j)
                    form["controls"].append(self._control(ctl))
                app.DoCmd.Close(AC_FORM, name, 2)  # acSaveNo
            except Exception as exc:
                self.warnings.append(f"form {name}: extraction failed: {exc}")
                _safe(lambda: app.DoCmd.Close(AC_FORM, name, 2))
            dump = self._save_as_text(app, AC_FORM, name, "forms")
            if dump:
                form["source_dump"] = dump

            if not opened:
                self.manifest["forms"].append(_manifest_entry(
                    name, "FORM", "FAILED", dump is not None,
                    ["form could not be opened in design view"]))
            elif form["module_source"] is None and form["has_module"]:
                # Properties extracted but code-behind missing.
                self.manifest["forms"].append(_manifest_entry(
                    name, "FORM", "PARTIAL", dump is not None,
                    ["form module source not captured"]))
            else:
                self.manifest["forms"].append(_manifest_entry(
                    name, "FORM", "SUCCESS", dump is not None or not form["has_module"]))
            forms.append(form)
        return forms

    def _read_com_module(self, module_getter) -> Optional[str]:
        """Read all lines from a COM VBA Module object, safely."""
        try:
            module = module_getter()
            count = int(_safe(lambda: module.CountOfLines, 0) or 0)
            if count <= 0:
                return None
            lines = _safe(lambda: module.Lines(1, count))
            return str(lines) if lines else None
        except Exception as exc:
            self.warnings.append(f"module line read failed: {exc}")
            return None

    def _control(self, ctl) -> dict:
        ctype = int(_safe(lambda: ctl.ControlType, 0))
        control = {
            "name": ctl.Name,
            "control_type": CONTROL_TYPES.get(ctype, f"Type{ctype}"),
            "control_source": None,
            "row_source": None,
            "row_source_type": None,
            "caption": None,
            "format": None,
            "default_value": None,
            "validation_rule": None,
            "visible": bool(_safe(lambda: ctl.Visible, True)),
            "enabled": bool(_safe(lambda: ctl.Enabled, True)),
            "locked": bool(_safe(lambda: ctl.Locked, False)),
            "events": {},
        }
        if ctype == 112:  # Subform
            control["source_object"] = _safe(lambda: ctl.SourceObject)
            control["link_child_fields"] = _safe(lambda: ctl.LinkChildFields)
            control["link_master_fields"] = _safe(lambda: ctl.LinkMasterFields)
        for prop, key in (("ControlSource", "control_source"),
                          ("RowSource", "row_source"),
                          ("RowSourceType", "row_source_type"),
                          ("Caption", "caption"),
                          ("Format", "format"),
                          ("DefaultValue", "default_value"),
                          ("ValidationRule", "validation_rule")):
            control[key] = _safe(lambda p=prop: getattr(ctl, p, None)) or None
        for event in CONTROL_EVENTS:
            handler = _prop(ctl, event)
            if handler:
                control["events"][event] = str(handler)
        return control

    # ------------------------------------------------------------ reports
    def _extract_reports(self, app) -> list[dict]:
        reports = []
        all_reports = app.CurrentProject.AllReports
        for i in range(all_reports.Count):
            name = all_reports(i).Name
            report = {
                "name": name,
                "record_source": None,
                "caption": None,
                "groups": [],
                "controls": [],
                "summary_fields": [],
                "module": None,
                "module_source": None,
                "has_module": False,
            }
            opened = False
            try:
                app.DoCmd.OpenReport(name, 1, None, None, 4)  # design, hidden
                opened = True
                rpt = app.Reports(name)
                report["record_source"] = _safe(lambda: rpt.RecordSource) or None
                report["caption"] = _safe(lambda: rpt.Caption) or None
                report["has_module"] = bool(_safe(lambda: rpt.HasModule, False))
                if report["has_module"]:
                    report["module"] = f"Report_{name}"
                    source = self._read_com_module(lambda: rpt.Module)
                    if source:
                        report["module_source"] = source
                group_count = _safe(lambda: rpt.GroupCount, None)
                if group_count:
                    for g in range(int(group_count)):
                        level = rpt.GroupLevel(g)
                        report["groups"].append({
                            "expression": _safe(lambda: level.ControlSource),
                            "sort_order": "ASC" if not int(_safe(lambda: level.SortOrder, 0)) else "DESC",
                        })
                for j in range(rpt.Controls.Count):
                    ctl = rpt.Controls(j)
                    control = self._control(ctl)
                    source = control.get("control_source")
                    if source and source.startswith("="):
                        control["is_expression"] = True
                        if any(fn in source for fn in ("Sum", "Count", "Avg", "Min", "Max")):
                            report["summary_fields"].append(source)
                    report["controls"].append(control)
                app.DoCmd.Close(AC_REPORT, name, 2)
            except Exception as exc:
                self.warnings.append(f"report {name}: extraction failed: {exc}")
                _safe(lambda: app.DoCmd.Close(AC_REPORT, name, 2))
            dump = self._save_as_text(app, AC_REPORT, name, "reports")
            if dump:
                report["source_dump"] = dump

            if not opened:
                self.manifest["reports"].append(_manifest_entry(
                    name, "REPORT", "FAILED", dump is not None,
                    ["report could not be opened in design view"]))
            elif report["has_module"] and report["module_source"] is None:
                self.manifest["reports"].append(_manifest_entry(
                    name, "REPORT", "PARTIAL", dump is not None,
                    ["report module source not captured"]))
            else:
                self.manifest["reports"].append(_manifest_entry(
                    name, "REPORT", "SUCCESS", dump is not None or not report["has_module"]))
            reports.append(report)
        return reports

    # ------------------------------------------------------------ macros
    def _extract_macros(self, app) -> list[dict]:
        macros = []
        all_macros = app.CurrentProject.AllMacros
        for i in range(all_macros.Count):
            name = all_macros(i).Name
            dump = self._save_as_text(app, AC_MACRO, name, "macros")
            source = self._read_dump(dump)
            if source is None and self.fallback_source_dir:
                source = self._fallback_dump(name, ("macros", "Macros"))
            macros.append({
                "name": name,
                "is_autoexec": name.lower() == "autoexec",
                "source_dump": dump,
                "source": source,
            })
            if source:
                self.manifest["macros"].append(_manifest_entry(
                    name, "MACRO", "SUCCESS", True))
            else:
                self.manifest["macros"].append(_manifest_entry(
                    name, "MACRO", "FAILED", False,
                    ["macro source not captured (SaveAsText failed)"]))
        return macros

    # ------------------------------------------------------------ modules
    def _extract_modules(self, app) -> list[dict]:
        """Extract VBA modules using layered strategies (most reliable first).

        Strategy 1: SaveAsText — canonical, but fails with "Reserved Error"
                    on many databases (observed on the whole corpus).
        Strategy 2: DoCmd.OpenModule + Modules(name).Lines — reads the live
                    module through COM; works for standard and class modules.
        Strategy 3: VBE.ActiveVBProject.VBComponents export — requires
                    "Trust access to the VBA project object model".
        Strategy 4: previously captured dumps (fallback_source_dir), e.g.
                    corpus saved-text or vbs_access_export output.
        """
        modules = []
        all_modules = app.CurrentProject.AllModules
        for i in range(all_modules.Count):
            name = all_modules(i).Name
            module = {
                "name": name,
                "module_type": ("FORM" if name.startswith("Form_")
                                else "REPORT" if name.startswith("Report_")
                                else "CLASS" if name.startswith("cls")
                                else "STANDARD"),
                "source": "",
                "extraction_strategy": None,
                "extraction_error": None,
            }

            # Strategy 1: SaveAsText
            dump = self._save_as_text(app, AC_MODULE, name, "modules")
            if dump:
                content = self._read_dump(dump)
                if content and content.strip():
                    module["source"] = content
                    module["extraction_strategy"] = "SaveAsText"

            # Strategy 2: live module line read
            if not module["source"]:
                source = self._open_and_read_module(app, name)
                if source:
                    module["source"] = source
                    module["extraction_strategy"] = "ModulesLines"

            # Strategy 3: VBE export
            if not module["source"]:
                source = self._vbe_export(app, name)
                if source:
                    module["source"] = source
                    module["extraction_strategy"] = "VBEExport"

            # Strategy 4: previously captured dumps
            if not module["source"] and self.fallback_source_dir:
                source = self._fallback_dump(
                    name, ("modules", "Modules_VBA"),
                    extensions=(".bas", ".cls", ".txt"))
                if source:
                    module["source"] = source
                    module["extraction_strategy"] = "FallbackDumps"

            if module["source"].strip():
                self.manifest["vbaModules"].append(_manifest_entry(
                    name, "VBA_MODULE", "SUCCESS", True))
            else:
                module["extraction_error"] = (
                    "all extraction strategies failed: SaveAsText, module "
                    "line read, VBE export, fallback dumps")
                self.manifest["vbaModules"].append(_manifest_entry(
                    name, "VBA_MODULE", "FAILED", False,
                    [module["extraction_error"]]))
            modules.append(module)
        return modules

    def _open_and_read_module(self, app, name: str) -> Optional[str]:
        """Strategy 2: open the module and read its lines via COM."""
        try:
            app.DoCmd.OpenModule(name)
            try:
                module = app.Modules(name)
                count = int(_safe(lambda: module.CountOfLines, 0) or 0)
                if count <= 0:
                    return None
                lines = _safe(lambda: module.Lines(1, count))
                return str(lines) if lines else None
            finally:
                _safe(lambda: app.DoCmd.Close(AC_MODULE_CONST, name, 2))
        except Exception as exc:
            self.warnings.append(f"module {name}: line read failed: {exc}")
            return None

    def _vbe_export(self, app, name: str) -> Optional[str]:
        """Strategy 3: export through the VBE object model.

        Raises COM errors when the database is not trusted for programmatic
        VBA access; that is expected and simply falls through.
        """
        try:
            components = app.VBE.ActiveVBProject.VBComponents
            for i in range(components.Count):
                component = components.Item(i + 1)
                if _safe(lambda: component.Name) != name:
                    continue
                folder = self.source_dir / "vbe"
                folder.mkdir(parents=True, exist_ok=True)
                # vbext_ct_StdModule=1 -> .bas, vbext_ct_ClassModule=2 -> .cls
                ext = ".cls" if int(_safe(lambda: component.Type, 1)) == 2 else ".bas"
                path = folder / f"{re.sub(r'[^A-Za-z0-9_]', '_', name)}{ext}"
                component.Export(str(path))
                return self._read_dump(str(path))
        except Exception as exc:
            self.warnings.append(f"module {name}: VBE export failed: {exc}")
        return None

    def _fallback_dump(self, name: str, subdirs: tuple[str, ...],
                       extensions: tuple[str, ...] = (".txt",)) -> Optional[str]:
        """Strategy 4: read from previously captured dumps."""
        if not self.fallback_source_dir:
            return None
        safe_name = re.sub(r"[^A-Za-z0-9_\-]", "_", name)
        for subdir in subdirs:
            for ext in extensions:
                for candidate in (self.fallback_source_dir / subdir / f"{safe_name}{ext}",
                                  self.fallback_source_dir / f"{safe_name}{ext}"):
                    if candidate.exists():
                        content = self._read_dump(str(candidate))
                        if content and content.strip():
                            return content
        return None


def run_extraction(db_path: str, workdir: str | Path, **options) -> dict:
    """Entry point used by the pipeline. Returns the raw extraction payload."""
    workdir_path = Path(workdir).resolve()
    try:
        return AccessExtractor(db_path, workdir_path, **options).run()
    except Exception as exc:
        # If running inside an asyncio thread pool raises COM marshaling / execution failure,
        # run in an isolated Python process with its own main STA thread.
        import subprocess
        import sys
        
        script = f"""import sys
from pathlib import Path
from converter.app.access.extractor import AccessExtractor
ext = AccessExtractor(r'{Path(db_path).resolve()}', Path(r'{workdir_path}'))
ext.run()
"""
        res = subprocess.run(
            [sys.executable, "-c", script],
            capture_output=True,
            text=True
        )
        output_file = workdir_path / "extraction.json"
        if res.returncode == 0 and output_file.exists():
            return json.loads(output_file.read_text(encoding="utf-8"))
        raise RuntimeError(f"Extraction failed: {res.stderr or exc}") from exc