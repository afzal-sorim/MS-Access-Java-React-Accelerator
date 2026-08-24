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
                 max_rows_per_table: int = 5000):
        self.db_path = str(Path(db_path).resolve())
        self.workdir = Path(workdir)
        self.source_dir = self.workdir / "source"
        self.extract_data = extract_data
        self.max_rows = max_rows_per_table
        self.warnings: list[str] = []
        self.data: dict[str, list[dict]] = {}

    # ------------------------------------------------------------ entry
    def run(self) -> dict:
        import pythoncom
        import win32com.client

        pythoncom.CoInitialize()
        app = None
        try:
            app = win32com.client.DispatchEx("Access.Application")
            app.Visible = False
            app.OpenCurrentDatabase(self.db_path, False)
            payload = self._extract_all(app)
            app.CloseCurrentDatabase()
        finally:
            if app is not None:
                _safe(app.Quit)
                app = None
            pythoncom.CoUninitialize()
        payload["warnings"] = self.warnings
        payload["table_data"] = {
            name: rows for name, rows in self.data.items()
        }
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
        payload["relationships"] = self._extract_relationships(db)
        payload["queries"] = self._extract_queries(db)
        payload["forms"] = self._extract_forms(app)
        payload["reports"] = self._extract_reports(app)
        payload["macros"] = self._extract_macros(app)
        payload["modules"] = self._extract_modules(app)
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
            while not rs.EOF and len(rows) < self.max_rows:
                row = {}
                for col in table["columns"]:
                    row[col["name"]] = self._value(rs.Fields(col["name"]).Value)
                rows.append(row)
                rs.MoveNext()
        finally:
            _safe(rs.Close)
        self.data[name] = rows

    @staticmethod
    def _value(value: Any) -> Any:
        import datetime as dt
        if isinstance(value, (dt.datetime, dt.date)):
            return value.isoformat(sep=" ")
        if isinstance(value, bytes):
            return f"<binary {len(value)} bytes>"
        if isinstance(value, float):
            return round(value, 10)
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
                "has_module": False,
                "parent_links": {},
            }
            try:
                app.DoCmd.OpenForm(name, 1, None, None, -1, 4)  # design, hidden
                frm = app.Forms(name)
                form["record_source"] = _safe(lambda: frm.RecordSource) or None
                form["caption"] = _safe(lambda: frm.Caption) or None
                form["has_module"] = bool(_safe(lambda: frm.HasModule, False))
                if form["has_module"]:
                    form["module"] = f"Form_{name}"
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
                app = app  # keep reference; close attempt below
                _safe(lambda: app.DoCmd.Close(AC_FORM, name, 2))
            dump = self._save_as_text(app, AC_FORM, name, "forms")
            if dump:
                form["source_dump"] = dump
            forms.append(form)
        return forms

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
                "has_module": False,
            }
            try:
                app.DoCmd.OpenReport(name, 1, None, None, 4)  # design, hidden
                rpt = app.Reports(name)
                report["record_source"] = _safe(lambda: rpt.RecordSource) or None
                report["caption"] = _safe(lambda: rpt.Caption) or None
                report["has_module"] = bool(_safe(lambda: rpt.HasModule, False))
                if report["has_module"]:
                    report["module"] = f"Report_{name}"
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
            reports.append(report)
        return reports

    # ------------------------------------------------------------ macros
    def _extract_macros(self, app) -> list[dict]:
        macros = []
        all_macros = app.CurrentProject.AllMacros
        for i in range(all_macros.Count):
            name = all_macros(i).Name
            dump = self._save_as_text(app, AC_MACRO, name, "macros")
            macros.append({
                "name": name,
                "is_autoexec": name.lower() == "autoexec",
                "source_dump": dump,
            })
        return macros

    # ------------------------------------------------------------ modules
    def _extract_modules(self, app) -> list[dict]:
        modules = []
        all_modules = app.CurrentProject.AllModules
        for i in range(all_modules.Count):
            name = all_modules(i).Name
            module = {
                "name": name,
                "module_type": ("FORM" if name.startswith("Form_")
                                else "REPORT" if name.startswith("Report_")
                                else "STANDARD"),
                "source": "",
            }
            dump = self._save_as_text(app, AC_MODULE, name, "modules")
            if dump:
                try:
                    module["source"] = Path(dump).read_text(encoding="latin-1", errors="replace")
                except Exception as exc:
                    self.warnings.append(f"module {name}: read failed: {exc}")
            modules.append(module)
        return modules


def run_extraction(db_path: str, workdir: str | Path, **options) -> dict:
    """Entry point used by the pipeline. Returns the raw extraction payload."""
    return AccessExtractor(db_path, Path(workdir), **options).run()
