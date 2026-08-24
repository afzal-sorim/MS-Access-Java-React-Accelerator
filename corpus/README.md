# Golden Test Corpus

Reference corpus for the Access → Spring Boot + React + PostgreSQL converter
(spec sections 51, 52, 53).

Per spec §52, conversion quality is measured by re-running the converter over
real Access applications and diffing the result against recorded
expectations — not by checking that files were produced.

## Layout

```
corpus/
  registry.json              all 20 spec §52 categories + status
  <item>/
    source.accdb             the Access application
    saved-text/              optional SaveAsText export
    expected/
      inventory.json         object counts and names
      ir.json                IR fragments (tables, columns, query kinds)
      externals.json         external dependencies (spec §8)
      schema.json            generated PostgreSQL schema shape
      supportability.json    support-status distribution
```

## Commands

```bash
python -m converter corpus list       # every category and its status
python -m converter corpus run        # diff against expectations (exit 1 on regression)
python -m converter corpus capture    # (re)write baselines
python -m converter corpus init       # create/refresh the registry
python -m converter corpus run -i vba-heavy --report out.json
```

## Item status

| Status | Meaning |
|---|---|
| `READY` | Source present, expectations recorded — runs and is diffed. |
| `NEEDS_BASELINE` | Source present, no expectations yet — run `corpus capture`. |
| `DECLARED` | Spec category with no source yet. Reported as a coverage gap. |
| `BLOCKED` | Source cannot run here; `reason` says why. |

Coverage is reported honestly. A run over 2 populated items prints
`2 of 20 spec section 52 categories have a runnable source application` — it
never implies 20/20.

## Current coverage

Populated (2):

- **vba-heavy** — real-world app: 11 tables, 16 queries, 13 forms, 8 reports,
  3 macros, 12 VBA modules (~203 KB of VBA). Exercises 14 of the 17 spec §53
  VBA cases including DAO, ADODB, Recordset, DoCmd, CurrentDb, error handling,
  85 Win32 `Declare` statements, and Outlook automation.
- **employee-hr** — synthetic HR fixture: 5 tables with relationships,
  5 queries, 3 forms, 1 report, plus an auth table carrying deliberate
  plaintext-password security debt.

Blocked (3): `split-db`, `sql-server-linked`, `excel-linked` — each needs
external infrastructure (a FE/BE pair, SQL Server + ODBC DSN, or linked
workbooks).

Declared, not yet populated (15): `basic-crud`, `inventory`, `sales`,
`purchasing`, `crm`, `reporting`, `macro-heavy`, `subforms`, `subreports`,
`parameter-query`, `crosstab`, `action-query`, `autoexec`,
`email-automation`, `complex-vba`.

## Expectation files

Captured files are marked `"_status": "CAPTURED_UNREVIEWED"`. Review each
against the spec, then set `"_status": "REVIEWED"`. The status field is
metadata only — keys beginning with `_` are never compared.

Only keys present in an expectation file are checked, so adding a new field
to the IR does not break existing expectations.

### Recording a known defect

To document a converter bug without letting it mask real regressions, list
the affected key path in `_known_gaps`:

```json
{
  "_status": "REVIEWED",
  "_known_gaps": ["business_rule_count"],
  "business_rule_count": 3
}
```

That key reports as `KNOWN_GAP` and does not fail the run. Any *other*
mismatch in the same file still fails, and the failure names only the
genuine break.

## Adding an item

1. Put the application at `corpus/<category>/source.accdb`.
2. Register it in `converter/app/corpus/init_corpus.py` (`POPULATORS`), or
   edit `registry.json` directly to set `source` and `status`.
3. `python -m converter corpus capture -i <category>`
4. Review the generated `expected/*.json`, then mark them `REVIEWED`.

## CI

`converter/tests/test_corpus.py` gates on the corpus. Access-dependent tests
skip cleanly when MS Access COM is unavailable, so a non-Windows runner
reports "skipped" rather than a false pass.
