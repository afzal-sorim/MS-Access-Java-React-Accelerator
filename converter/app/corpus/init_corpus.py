"""Initialize the golden test corpus - spec sections 52, 53.

Declares all twenty spec §52 categories, then populates the ones backed by
a real Access application on this machine.  Categories without a source are
recorded as DECLARED so corpus runs report the coverage gap honestly rather
than implying full coverage.

Run:  python -m converter corpus init
"""
from __future__ import annotations

import shutil
from pathlib import Path

from converter.app.corpus.models import CorpusItem, CorpusRegistry, ItemStatus

# Corpus data lives at the project root (a sibling of converter/), not
# inside the package — the .accdb fixtures are test data, not code.
PROJECT_ROOT = Path(__file__).resolve().parents[3]
CORPUS_ROOT = PROJECT_ROOT / "corpus"

# Real sources available on this machine.
VBA_SOURCE = Path(r"C:\Users\Afzal\Downloads\Access_Example_VBA (1).accdb")
VBA_SAVED_TEXT = Path(r"C:\AccessMasterDump")
EMPLOYEE_SOURCE = CORPUS_ROOT / "employee-management" / "EmployeeManagement.accdb"

# The twenty categories named in spec §52, in spec order.
SPEC_CATEGORIES: list[tuple[str, str, list[str]]] = [
    ("basic-crud", "Minimal create/read/update/delete over a single table.",
     ["AutoNumber", "indexed fields", "bound form"]),
    ("employee-hr", "HR domain: employees, departments, leave with approval rules.",
     ["composite FK", "currency", "date/time", "validation rules", "unique indexes"]),
    ("inventory", "Stock items, movements and reorder logic.",
     ["calculated fields", "domain aggregate"]),
    ("sales", "Orders, order lines, customers, totals.",
     ["nested query", "calculated control"]),
    ("purchasing", "Purchase orders and supplier approval workflow.",
     ["action query", "status transitions"]),
    ("crm", "Contacts, activities and follow-up scheduling.",
     ["lookup fields", "combo row source"]),
    ("reporting", "Report-centric app: grouping, totals, parameters.",
     ["grouping", "sorting", "totals", "page headers", "footers"]),
    ("split-db", "Split front-end/back-end Access application.",
     ["Access backend", "linked tables"]),
    ("sql-server-linked", "Tables linked to SQL Server over ODBC.",
     ["SQL Server", "ODBC", "pass-through"]),
    ("excel-linked", "Tables and imports linked to Excel workbooks.",
     ["Excel", "CSV"]),
    ("vba-heavy", "Large real-world VBA surface across many modules.",
     ["Recordset", "DAO", "ADODB", "DoCmd", "CurrentDb", "Me", "error handling",
      "ByRef", "loops", "nested conditions", "functions", "Windows API",
      "Outlook", "dynamic SQL"]),
    ("macro-heavy", "Logic expressed mainly as Access macros.",
     ["AutoExec", "AutoKeys"]),
    ("subforms", "Forms embedding one or more subforms.",
     ["subform", "nested subform"]),
    ("subreports", "Reports embedding subreports.",
     ["subreports"]),
    ("parameter-query", "Queries driven by runtime parameters.",
     ["parameter query"]),
    ("crosstab", "Crosstab (pivot) queries.",
     ["crosstab"]),
    ("action-query", "INSERT/UPDATE/DELETE and make-table queries.",
     ["action query", "make-table"]),
    ("autoexec", "Startup automation via AutoExec.",
     ["AutoExec", "Startup/Application configuration"]),
    ("email-automation", "Outbound email through Outlook automation.",
     ["Outlook", "COM"]),
    ("complex-vba", "Class modules, callbacks and deep indirection in VBA.",
     ["Recordset", "Forms!", "Reports!", "external APIs"]),
]


def _populate_vba_heavy(root: Path) -> tuple[ItemStatus, str, str | None, str | None]:
    """Copy the real VBA-heavy application into the corpus."""
    item_dir = root / "vba-heavy"
    item_dir.mkdir(parents=True, exist_ok=True)

    if not VBA_SOURCE.exists():
        return (
            ItemStatus.DECLARED,
            f"source not found at {VBA_SOURCE}",
            None,
            None,
        )

    dest = item_dir / "source.accdb"
    if not dest.exists() or dest.stat().st_size != VBA_SOURCE.stat().st_size:
        shutil.copy2(VBA_SOURCE, dest)

    saved_text_rel = None
    if VBA_SAVED_TEXT.exists():
        saved_dest = item_dir / "saved-text"
        if saved_dest.exists():
            shutil.rmtree(saved_dest)
        shutil.copytree(VBA_SAVED_TEXT, saved_dest)
        saved_text_rel = "saved-text"

    return ItemStatus.NEEDS_BASELINE, "", "source.accdb", saved_text_rel


def _populate_employee_hr(root: Path) -> tuple[ItemStatus, str, str | None, str | None]:
    """Register the existing synthetic employee fixture."""
    if not EMPLOYEE_SOURCE.exists():
        return ItemStatus.DECLARED, f"source not found at {EMPLOYEE_SOURCE}", None, None

    item_dir = root / "employee-hr"
    item_dir.mkdir(parents=True, exist_ok=True)
    dest = item_dir / "source.accdb"
    if not dest.exists() or dest.stat().st_size != EMPLOYEE_SOURCE.stat().st_size:
        shutil.copy2(EMPLOYEE_SOURCE, dest)

    return ItemStatus.NEEDS_BASELINE, "", "source.accdb", None


POPULATORS = {
    "vba-heavy": _populate_vba_heavy,
    "employee-hr": _populate_employee_hr,
}

# Categories that cannot be produced on this machine, with the reason.
BLOCKED_REASONS = {
    "sql-server-linked": "requires a reachable SQL Server instance and ODBC DSN",
    "excel-linked": "requires linked .xlsx workbooks alongside the .accdb",
    "split-db": "requires a paired front-end/back-end .accdb set",
}


def _status_for_populated(root: Path, name: str) -> ItemStatus:
    """READY once expectations exist, otherwise NEEDS_BASELINE."""
    expected = root / name / "expected"
    if expected.is_dir() and any(expected.glob("*.json")):
        return ItemStatus.READY
    return ItemStatus.NEEDS_BASELINE


def init_corpus(root: Path | str = CORPUS_ROOT, *, verbose: bool = True) -> CorpusRegistry:
    """Create (or refresh) the corpus registry and populate available items."""
    root = Path(root)
    root.mkdir(parents=True, exist_ok=True)

    registry = CorpusRegistry(root=root)

    for name, description, covers in SPEC_CATEGORIES:
        status = ItemStatus.DECLARED
        reason = ""
        source = None
        saved_text = None

        populator = POPULATORS.get(name)
        if populator:
            status, reason, source, saved_text = populator(root)
            if status == ItemStatus.NEEDS_BASELINE:
                status = _status_for_populated(root, name)
        elif name in BLOCKED_REASONS:
            status = ItemStatus.BLOCKED
            reason = BLOCKED_REASONS[name]
        else:
            reason = "no source Access application available yet"

        registry.items.append(CorpusItem(
            name=name,
            category=name,
            status=status,
            source=source,
            saved_text=saved_text,
            description=description,
            reason=reason,
            covers=covers,
        ))

    path = registry.save()

    if verbose:
        runnable = registry.runnable
        print(f"Corpus registry written to {path}")
        print(f"  declared categories : {len(registry.items)}")
        print(f"  runnable items      : {len(runnable)}")
        for item in runnable:
            print(f"      + {item.name} ({item.source})")
        blocked = [i for i in registry.items if i.status == ItemStatus.BLOCKED]
        if blocked:
            print(f"  blocked             : {len(blocked)}")
            for item in blocked:
                print(f"      - {item.name}: {item.reason}")
        print(f"  declared-only       : {len(registry.declared_only)}")

    return registry


if __name__ == "__main__":
    init_corpus()
