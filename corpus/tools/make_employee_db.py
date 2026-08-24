"""Builds corpus/employee-management/EmployeeManagement.accdb via Access COM.

First-milestone fixture (spec section 70): 5 tables, relationships, 5 queries,
3 forms, 1 report, 2 VBA modules, AutoExec macro, seeded data including an
auth Users table with plaintext demo passwords (deliberate source security
debt the converter must detect and classify).

VBA injection requires the Office "trust access to VBA project object model"
setting; when unavailable the fixture degrades gracefully and records it in
fixture-meta.json.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

CORPUS_DIR = Path(__file__).resolve().parent.parent
DB_PATH = CORPUS_DIR / "employee-management" / "EmployeeManagement.accdb"

DDL = [
    """CREATE TABLE Departments (
        DepartmentID COUNTER PRIMARY KEY,
        DepartmentName TEXT(50) NOT NULL,
        Location TEXT(50))""",
    """CREATE TABLE Employees (
        EmployeeID COUNTER PRIMARY KEY,
        FirstName TEXT(50) NOT NULL,
        LastName TEXT(50) NOT NULL,
        Email TEXT(100),
        DepartmentID LONG NOT NULL,
        HireDate DATETIME,
        Salary CURRENCY,
        IsActive YESNO)""",
    """CREATE TABLE LeaveTypes (
        LeaveTypeID COUNTER PRIMARY KEY,
        TypeName TEXT(30) NOT NULL,
        IsPaid YESNO)""",
    """CREATE TABLE Leaves (
        LeaveID COUNTER PRIMARY KEY,
        EmployeeID LONG NOT NULL,
        LeaveTypeID LONG NOT NULL,
        StartDate DATETIME NOT NULL,
        EndDate DATETIME NOT NULL,
        LeaveDays LONG,
        Status TEXT(20),
        Notes MEMO)""",
    """CREATE TABLE Users (
        UserID COUNTER PRIMARY KEY,
        Username TEXT(50) NOT NULL,
        PasswordPlain TEXT(100),
        Role TEXT(20),
        EmployeeID LONG,
        CONSTRAINT UniqueUser UNIQUE (Username))""",
]

# Jet DDL via DAO rejects DEFAULT and CHECK clauses; apply them as DAO field
# properties after table creation instead (also exercises the extractor's
# validation-rule/default extraction path).
FIELD_DEFAULTS = {
    "Employees": {"IsActive": "True"},
    "LeaveTypes": {"IsPaid": "True"},
    "Leaves": {"Status": "'Pending'"},
    "Users": {"Role": "'User'"},
}
FIELD_VALIDATION = {
    ("Employees", "Salary"): (">= 0", "Salary must be zero or more"),
    ("Employees", "Email"): ("Is Null Or Like '*@*'", "Email must contain @"),
}

RELATIONS = [
    # name, parent, child, field, attrs
    # DAO bits: 1=one-to-one, 2=dontEnforce, 256=updateCascade, 4096=deleteCascade.
    # Enforced 1:many is the default (0).
    ("DepartmentsEmployees", "Departments", "Employees", "DepartmentID", 256),
    ("EmployeesLeaves", "Employees", "Leaves", "EmployeeID", 256 | 4096),
    ("LeaveTypesLeaves", "LeaveTypes", "Leaves", "LeaveTypeID", 0),
    ("EmployeesUsers", "Employees", "Users", "EmployeeID", 0),
]

QUERIES = [
    ("qryEmployeeList", """SELECT e.EmployeeID, e.FirstName, e.LastName, e.Email,
        d.DepartmentName, e.HireDate, e.Salary, e.IsActive
        FROM Employees AS e INNER JOIN Departments AS d ON e.DepartmentID = d.DepartmentID
        ORDER BY e.LastName, e.FirstName"""),
    ("qryPendingLeaves", """SELECT l.LeaveID, e.FirstName & ' ' & e.LastName AS EmployeeName,
        t.TypeName, l.StartDate, l.EndDate, l.LeaveDays, l.Status
        FROM (Leaves AS l INNER JOIN Employees AS e ON l.EmployeeID = e.EmployeeID)
        INNER JOIN LeaveTypes AS t ON l.LeaveTypeID = t.LeaveTypeID
        WHERE l.Status = 'Pending'
        ORDER BY l.StartDate"""),
    ("qryEmployeeLeaveSummary", """PARAMETERS DeptID LONG;
        SELECT d.DepartmentName, e.FirstName & ' ' & e.LastName AS EmployeeName,
        Count(l.LeaveID) AS LeaveCount, Sum(l.LeaveDays) AS TotalDays
        FROM ((Employees AS e INNER JOIN Departments AS d ON e.DepartmentID = d.DepartmentID)
        INNER JOIN Leaves AS l ON e.EmployeeID = l.EmployeeID)
        WHERE d.DepartmentID = [DeptID]
        GROUP BY d.DepartmentName, e.FirstName & ' ' & e.LastName
        ORDER BY d.DepartmentName"""),
    ("qryActiveEmployees", """SELECT EmployeeID, FirstName, LastName, Email, DepartmentID
        FROM Employees WHERE IsActive = True ORDER BY LastName"""),
    ("qryApproveLeave", """PARAMETERS LID LONG;
        UPDATE Leaves SET Status = 'Approved' WHERE LeaveID = [LID]"""),
]

ROWS = {
    "Departments": [
        "(1, 'Engineering', 'Berlin')", "(2, 'Sales', 'Munich')",
        "(3, 'Human Resources', 'Berlin')", "(4, 'Finance', 'Hamburg')"],
    "LeaveTypes": [
        "(1, 'Annual', True)", "(2, 'Sick', True)", "(3, 'Unpaid', False)"],
    "Employees": [
        "(1, 'Alice', 'Anders', 'alice@example.com', 1, #2020-01-15#, 62000, True)",
        "(2, 'Bob', 'Brown', 'bob@example.com', 1, #2021-03-01#, 54000, True)",
        "(3, 'Clara', 'Chen', 'clara@example.com', 2, #2019-07-20#, 48000, True)",
        "(4, 'David', 'Duarte', 'david@example.com', 3, #2022-11-05#, 51000, False)",
        "(5, 'Elena', 'Fischer', 'elena@example.com', 4, #2018-05-30#, 67000, True)"],
    "Leaves": [
        "(1, 1, 1, #2026-09-01#, #2026-09-03#, 3, 'Pending', null)",
        "(2, 2, 2, #2026-08-10#, #2026-08-14#, 5, 'Manager Approval', 'doctor note')",
        "(3, 3, 1, #2026-07-01#, #2026-07-15#, 15, 'Approved', 'summer vacation')",
        "(4, 5, 1, #2026-10-05#, #2026-10-07#, 3, 'Pending', null)"],
    "Users": [
        "(1, 'admin', 'admin123', 'Admin', null)",
        "(2, 'alice', 'alice123', 'User', 1)",
        "(3, 'bob', 'bob123', 'User', 2)"],
}

MOD_BUSINESS = '''Option Compare Database
Option Explicit

Public Function CalculateLeaveDays(startDate As Date, endDate As Date) As Long
    If endDate < startDate Then
        CalculateLeaveDays = 0
    Else
        CalculateLeaveDays = DateDiff("d", startDate, endDate) + 1
    End If
End Function

Public Function DetermineLeaveStatus(leaveDays As Long) As String
    If leaveDays > 3 Then
        DetermineLeaveStatus = "Manager Approval"
    Else
        DetermineLeaveStatus = "Pending"
    End If
End Function
'''

MOD_MAIN = '''Option Compare Database
Option Explicit

Public Sub ShowWelcome()
    MsgBox "Welcome to Employee Management", vbInformation, "Welcome"
End Sub

Public Function CurrentUserName() As String
    CurrentUserName = Environ("USERNAME")
End Function
'''

AUTOEXEC_MACRO = '''Version =196611
ColumnsShown =8
Begin
    Action ="OpenForm"
    Argument ="frmLogin"
    Argument ="0"
    Argument =""
    Argument =""
    Argument ="-1"
    Argument ="0"
End
'''

META: dict = {"db_path": str(DB_PATH), "capabilities": {}, "warnings": []}


def safe(fn, *args):
    try:
        return fn(*args)
    except Exception as exc:
        META["warnings"].append(f"{exc}")
        return None


def force_quit(app) -> None:
    """Quit Access; if that fails (error state), terminate only our instance.

    A leaked zombie Access process corrupts later COM runs, so PID-scoped
    termination is the last resort.
    """
    try:
        app.Quit()
        return
    except Exception:
        pass
    try:
        app.CloseCurrentDatabase()
    except Exception:
        pass
    try:
        import ctypes
        pid = ctypes.c_ulong()
        hwnd = app.hWndAccessApp
        ctypes.windll.user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
        if pid.value:
            handle = ctypes.windll.kernel32.OpenProcess(1, False, pid.value)
            if handle:
                ctypes.windll.kernel32.TerminateProcess(handle, 1)
    except Exception as exc:
        META["warnings"].append(f"force quit failed: {exc}")


def log_step(msg: str) -> None:
    from pathlib import Path as P

    target = DB_PATH.parent / "fixture-gen.log"
    with P.open(target, "a", encoding="utf-8") as fh:
        fh.write(msg + "\n")


def main() -> int:
    import pythoncom
    import win32com.client

    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    (DB_PATH.parent / "fixture-gen.log").unlink(missing_ok=True)
    if DB_PATH.exists():
        DB_PATH.unlink()

    pythoncom.CoInitialize()
    app = win32com.client.DispatchEx("Access.Application")
    app.Visible = False
    try:
        app.NewCurrentDatabase(str(DB_PATH))
        db = app.CurrentDb()

        for stmt in DDL:
            db.Execute(stmt, 128)
        META["capabilities"]["tables"] = True

        apply_field_properties(db)

        db.TableDefs.Refresh()
        for name, parent, child, field, attrs in RELATIONS:
            rel = db.CreateRelation(name, parent, child, attrs)
            fld = rel.CreateField(field)
            fld.ForeignName = field
            rel.Fields.Append(fld)
            db.Relations.Append(rel)
        META["capabilities"]["relationships"] = True

        for table, inserts in ROWS.items():
            for row in inserts:
                db.Execute(f"INSERT INTO {table} VALUES {row}", 128)
        META["capabilities"]["data"] = True

        for qname, sql in QUERIES:
            qdef = db.CreateQueryDef(qname, sql)
            del qdef
        db.QueryDefs.Refresh()
        META["capabilities"]["queries"] = True
        log_step('step: queries done')

        create_forms(app)
        log_step('step: forms done')
        create_report(app)
        log_step('step: report done')
        create_autoexec(app)
        log_step('step: autoexec done')
        create_modules(app)
        log_step('step: modules done')

        # Startup: launch login form when the database opens.
        safe(set_property, db, "StartupForm", "frmLogin")
        app.CloseCurrentDatabase()
    finally:
        force_quit(app)
        pythoncom.CoUninitialize()

    (DB_PATH.parent / "fixture-meta.json").write_text(
        json.dumps(META, indent=2), encoding="utf-8")
    print(json.dumps(META, indent=2))
    return 0


def apply_field_properties(db) -> None:
    db.TableDefs.Refresh()
    for table, defaults in FIELD_DEFAULTS.items():
        for field_name, value in defaults.items():
            field = db.TableDefs(table).Fields(field_name)
            field.DefaultValue = value
    for (table, field_name), (rule, text) in FIELD_VALIDATION.items():
        field = db.TableDefs(table).Fields(field_name)
        field.ValidationRule = rule
        field.ValidationText = text
    META["capabilities"]["field_rules"] = True


def set_property(db, name: str, value):
    prop = db.CreateProperty(name, 10, value, True)  # dbText
    db.Properties.Append(prop)


def create_forms(app) -> None:
    # --- frmEmployee: bound CRUD form with department lookup combo ---------
    frm = create_form(app)
    frm.RecordSource = "Employees"
    frm.Caption = "Employee"
    add_textbox(app, frm, "FirstName", "First Name", 400, 400, 3000)
    add_textbox(app, frm, "LastName", "Last Name", 400, 1000, 3000)
    add_textbox(app, frm, "Email", "Email", 400, 1600, 4400)
    add_datebox(app, frm, "HireDate", "Hire Date", 400, 2200)
    combo = app.CreateControl(frm.Name, 111, 0, "", "DepartmentID", 400, 2800, 3000, 400)
    combo.Properties("RowSource").Value = (
        "SELECT DepartmentID, DepartmentName FROM Departments ORDER BY DepartmentName")
    combo.Properties("RowSourceType").Value = "Table/Query"
    combo.Properties("ColumnCount").Value = 2
    combo.Properties("ColumnWidths").Value = "0;2in"
    label_for(app, frm, combo, "Department")
    close_and_rename(app, frm, "frmEmployee"); frm = None

    # --- frmLeaveApplication: bound leave form feeding the business rule ---
    frm = create_form(app)
    frm.RecordSource = "Leaves"
    frm.Caption = "Leave Application"
    add_datebox(app, frm, "StartDate", "Start Date", 400, 400)
    add_datebox(app, frm, "EndDate", "End Date", 400, 1000)
    add_textbox(app, frm, "LeaveDays", "Leave Days", 400, 1600, 1500)
    status = add_textbox(app, frm, "Status", "Status", 400, 2200, 2400)
    set_ctl_prop(status, "Locked", True)
    emp = app.CreateControl(frm.Name, 111, 0, "", "EmployeeID", 400, 2800, 3000, 400)
    emp.Properties("RowSource").Value = "qryActiveEmployees"
    emp.Properties("RowSourceType").Value = "Table/Query"
    emp.Properties("ColumnCount").Value = 3
    label_for(app, frm, emp, "Employee")
    btn = app.CreateControl(frm.Name, 104, 0, "", "", 3600, 2800, 2400, 500)
    btn.Properties("Caption").Value = "Submit Leave"
    close_and_rename(app, frm, "frmLeaveApplication"); frm = None

    # --- frmLogin: unbound login form (auth path) --------------------------
    frm = create_form(app)
    frm.Caption = "Login"
    frm.RecordSource = ""
    user = add_unbound_textbox(app, frm, "txtUsername", "Username", 400, 400)
    pwd = add_unbound_textbox(app, frm, "txtPassword", "Password", 400, 1000)
    set_ctl_prop(pwd, "InputMask", "PASSWORD")
    login = app.CreateControl(frm.Name, 104, 0, "", "", 400, 1600, 2400, 500)
    login.Properties("Caption").Value = "Log In"
    close_and_rename(app, frm, "frmLogin"); frm = None
    META["capabilities"]["forms"] = True


def set_ctl_prop(ctl, name, value):
    try:
        ctl.Properties(name).Value = value
    except Exception as exc:
        META["warnings"].append(f"control property {name}: {exc}")


def add_label(app, frm, caption, left, top, width):
    label = app.CreateControl(frm.Name, 100, 0, "", "", left, top, width, 300)
    label.Properties("Caption").Value = caption
    return label


def add_textbox(app, frm, source, caption, left, top, width):
    add_label(app, frm, caption, left, top - 350, width)
    return app.CreateControl(frm.Name, 109, 0, "", source, left, top, width, 400)


def add_datebox(app, frm, source, caption, left, top):
    ctl = add_textbox(app, frm, source, caption, left, top, 2000)
    set_ctl_prop(ctl, "Format", "Short Date")
    return ctl


def add_unbound_textbox(app, frm, name, caption, left, top):
    add_label(app, frm, caption, left, top - 350, 3000)
    ctl = app.CreateControl(frm.Name, 109, 0, "", "", left, top, 3000, 400)
    ctl.Name = name
    return ctl


def label_for(app, frm, ctl, caption):
    label = app.CreateControl(frm.Name, 100, 0, ctl.Name, "", 400, ctl.Top - 300, 3000, 300)
    label.Properties("Caption").Value = caption
    return label


def create_form(app, attempts: int = 4):
    """CreateForm fails with an RPC error if a previously closed form's COM
    reference is still live; pump messages and retry."""
    import time

    import pythoncom

    for attempt in range(attempts):
        try:
            return app.CreateForm()
        except Exception:
            if attempt == attempts - 1:
                raise
            pythoncom.PumpWaitingMessages()
            time.sleep(1.0)


def close_and_rename(app, frm, new_name):
    old_name = frm.Name
    app.DoCmd.Close(2, old_name, 1)  # acForm, acSaveYes
    app.DoCmd.Rename(new_name, 2, old_name)
    import gc

    import pythoncom

    del frm
    gc.collect()
    pythoncom.PumpWaitingMessages()


def create_report(app) -> None:
    rpt = app.CreateReport()
    rpt.RecordSource = "qryEmployeeLeaveSummary"
    rpt.Caption = "Employee Leave Summary"
    fields = [("DepartmentName", "Department"), ("EmployeeName", "Employee"),
              ("LeaveCount", "Leaves"), ("TotalDays", "Total Days")]
    for i, (source, caption) in enumerate(fields):
        header_label = app.CreateReportControl(
            rpt.Name, 100, 3, "", "", 400 + i * 2200, 200, 2100, 300)
        header_label.Properties("Caption").Value = caption
        app.CreateReportControl(
            rpt.Name, 109, 0, "", source, 400 + i * 2200, 600, 2100, 400)
    try:
        app.CreateGroupLevel(rpt.Name, "DepartmentName", True, True)
        META["capabilities"]["report_groups"] = True
    except Exception as exc:
        META["warnings"].append(f"group level: {exc}")
    old_name = rpt.Name
    app.DoCmd.Close(3, old_name, 1)  # acReport, acSaveYes
    app.DoCmd.Rename("rptLeaveSummary", 3, old_name)
    import gc

    import pythoncom

    del rpt
    gc.collect()
    pythoncom.PumpWaitingMessages()
    META["capabilities"]["report"] = True


def create_autoexec(app) -> None:
    macro_file = DB_PATH.parent / "_autoexec.txt"
    macro_file.write_text(AUTOEXEC_MACRO, encoding="latin-1")
    try:
        app.LoadFromText(4, "AutoExec", str(macro_file))  # acMacro
        app.DoCmd.Save(4, "AutoExec")
        META["capabilities"]["autoexec_macro"] = True
    except Exception as exc:
        META["warnings"].append(f"macro creation failed: {exc}")
    finally:
        macro_file.unlink(missing_ok=True)


def vbe_access_enabled() -> bool:
    """Trust access to the VBA project object model (else VBE hangs on a modal)."""
    import winreg

    try:
        with winreg.OpenKey(
                winreg.HKEY_CURRENT_USER,
                r"Software\Microsoft\Office\14.0\Access\Security") as key:
            value, _ = winreg.QueryValueEx(key, "AccessVBOM")
            return value == 1
    except OSError:
        return False


def create_modules(app) -> None:
    if not vbe_access_enabled():
        META["warnings"].append(
            "VBA modules skipped: 'Trust access to the VBA project object model' "
            "is disabled in the Access Trust Center (enabling it would otherwise "
            "hang on a hidden modal dialog).")
        return
    try:
        project = app.VBE.ActiveVBProject
        for name, source in (("modBusiness", MOD_BUSINESS), ("modMain", MOD_MAIN)):
            component = project.VBComponents.Add(1)  # vbext_ct_StdModule
            component.Name = name
            component.CodeModule.AddFromString(source)
        META["capabilities"]["vba_modules"] = True
    except Exception as exc:
        META["warnings"].append(f"VBA module creation failed: {exc}")


if __name__ == "__main__":
    sys.exit(main())
