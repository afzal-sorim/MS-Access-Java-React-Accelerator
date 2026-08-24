"""CLI entry point for the MS Access converter.

Usage:
    python -m converter convert <input.accdb> --output <output_dir>
    python -m converter extract <input.accdb> --output <output_dir>
    python -m converter analyze <extraction.json>
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Optional


def cmd_convert(args) -> int:
    """Run full conversion pipeline."""
    input_path = Path(args.input)
    output_dir = Path(args.output)

    if not input_path.exists():
        print(f"Error: Input file not found: {input_path}", file=sys.stderr)
        return 1

    print(f"Converting {input_path.name}...")
    print(f"Output directory: {output_dir}")

    # Step 1: Extract
    print("\n[1/7] Extracting Access database...")
    from ..access.extractor import run_extraction

    extract_dir = output_dir / ".extract"
    extract_dir.mkdir(parents=True, exist_ok=True)

    try:
        extraction = run_extraction(str(input_path), str(extract_dir))
        print(f"  - Tables: {len(extraction.get('tables', []))}")
        print(f"  - Queries: {len(extraction.get('queries', []))}")
        print(f"  - Forms: {len(extraction.get('forms', []))}")
        print(f"  - Reports: {len(extraction.get('reports', []))}")
        print(f"  - Macros: {len(extraction.get('macros', []))}")
        print(f"  - Warnings: {len(extraction.get('warnings', []))}")
    except Exception as e:
        print(f"Error during extraction: {e}", file=sys.stderr)
        return 1

    # Step 2: Build IR
    print("\n[2/7] Building Intermediate Representation...")
    from ..ir.builder import build_ir

    extraction_path = extract_dir / "extraction.json"
    app_ir = build_ir(extraction_path)
    print(f"  - Application: {app_ir.application_name}")
    print(f"  - Source: {app_ir.source_file}")

    # Step 3: Build dependency graph
    print("\n[3/7] Building dependency graph...")
    from ..graph.builder import build_dependency_graph

    graph = build_dependency_graph(app_ir)
    cycles = graph.find_cycles()
    orphans = graph.find_orphans()
    print(f"  - Nodes: {len(graph.nodes)}")
    print(f"  - Cycles: {len(cycles)}")
    print(f"  - Orphans: {len(orphans)}")

    # Step 4: Analyze supportability
    print("\n[4/7] Analyzing supportability...")
    from ..supportability.engine import analyze_supportability, SupportabilityEngine

    support_results = analyze_supportability(app_ir)
    engine = SupportabilityEngine(app_ir)
    engine.results = support_results
    coverage = engine.calculate_coverage()

    print(f"  - Overall coverage: {coverage.get('overall', 0)}%")
    print(f"  - Fully supported: {coverage.get('fully_supported_pct', 0)}%")
    print(f"  - Needs review: {coverage.get('supported_with_review_pct', 0)}%")
    print(f"  - Unsupported: {coverage.get('unsupported_pct', 0)}%")

    # Step 5: Generate PostgreSQL schema
    print("\n[5/7] Generating PostgreSQL schema...")
    from ..generators.database.postgres import generate_schema

    db_dir = output_dir / "database"
    db_dir.mkdir(parents=True, exist_ok=True)

    # Store raw data for seed generation
    app_ir._raw_data = extraction

    schema_path = db_dir / "schema.sql"
    generate_schema(app_ir, schema_path)
    print(f"  - Schema written to: {schema_path}")

    # Step 6: Generate Spring Boot backend
    print("\n[6/7] Generating Spring Boot backend...")
    from ..generators.spring import SpringBootGenerator

    backend_dir = output_dir / "backend"
    base_package = args.package or "com.generated.app"

    spring_generator = SpringBootGenerator(
        app_ir,
        base_package=base_package,
        app_name=app_ir.application_name,
        report_strategy=args.report_strategy,
    )
    spring_gen = spring_generator.generate(backend_dir)
    print(f"  - Generated {len(spring_gen)} files")
    print(f"  - Base package: {base_package}")

    report_definitions = spring_generator.report_definitions
    generated_reports = [d for d in report_definitions if d.generatable]
    if report_definitions:
        print(f"  - Reports: {len(generated_reports)}/{len(report_definitions)} converted")
        for warning in spring_generator.warnings:
            print(f"    ! {warning}")

    # Step 7: Generate React frontend
    print("\n[7/7] Generating React frontend...")
    from ..generators.react import generate_react

    frontend_dir = output_dir / "frontend"

    react_gen = generate_react(
        app_ir, frontend_dir, report_strategy=args.report_strategy
    )
    print(f"  - Generated {len(react_gen)} files")

    # Generate migration report
    print("\nGenerating migration report...")
    report_dir = output_dir / "migration-report"
    report_dir.mkdir(parents=True, exist_ok=True)

    from ..app.reporting import report_migration_summary, write_report_manifest

    reports_summary = report_migration_summary(report_definitions)
    if report_definitions:
        write_report_manifest(report_definitions, report_dir / "reports.json")

    report = {
        "source": {
            "file": str(input_path),
            "application": app_ir.application_name,
        },
        "statistics": {
            "tables": len(app_ir.tables),
            "queries": len(app_ir.queries),
            "forms": len(app_ir.forms),
            "reports": len(app_ir.reports),
            "macros": len(app_ir.macros),
            "vba_modules": len(app_ir.vba_modules),
        },
        "coverage": coverage,
        "supportability": [
            {
                "object": r.object,
                "category": r.category,
                "status": r.status.value,
                "complexity": r.complexity,
                "risk": r.risk,
                "conversion": r.conversion,
                "confidence": r.confidence,
                "reason": r.reason,
            }
            for r in support_results
        ],
        "warnings": app_ir.warnings + spring_generator.warnings,
        "reports": reports_summary,
        "generated": {
            "backend_files": len(spring_gen),
            "frontend_files": len(react_gen),
            "database_file": str(schema_path),
            "reports_generated": reports_summary["generated"],
        },
    }

    report_path = report_dir / "migration-report.json"
    report_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(f"  - Report written to: {report_path}")

    print("\n" + "=" * 60)
    print("Conversion complete!")
    print(f"  Output: {output_dir}")
    print(f"  Coverage: {coverage.get('overall', 0)}%")
    if report_definitions:
        print(
            f"  Reports: {reports_summary['generated']}/{reports_summary['total']} "
            f"({reports_summary['coverage_pct']}%)"
        )
    print("=" * 60)

    return 0


def cmd_extract(args) -> int:
    """Run extraction only."""
    input_path = Path(args.input)
    output_dir = Path(args.output)

    if not input_path.exists():
        print(f"Error: Input file not found: {input_path}", file=sys.stderr)
        return 1

    print(f"Extracting {input_path.name}...")

    from ..access.extractor import run_extraction

    output_dir.mkdir(parents=True, exist_ok=True)
    extraction = run_extraction(str(input_path), str(output_dir))

    print(f"Tables: {len(extraction.get('tables', []))}")
    print(f"Queries: {len(extraction.get('queries', []))}")
    print(f"Forms: {len(extraction.get('forms', []))}")
    print(f"Reports: {len(extraction.get('reports', []))}")
    print(f"Macros: {len(extraction.get('macros', []))}")

    if extraction.get("warnings"):
        print(f"\nWarnings ({len(extraction['warnings'])}):")
        for w in extraction["warnings"][:10]:
            print(f"  - {w}")
        if len(extraction["warnings"]) > 10:
            print(f"  ... and {len(extraction['warnings']) - 10} more")

    print(f"\nExtraction saved to: {output_dir / 'extraction.json'}")
    return 0


def cmd_analyze(args) -> int:
    """Analyze an extraction JSON file."""
    extraction_path = Path(args.input)

    if not extraction_path.exists():
        print(f"Error: File not found: {extraction_path}", file=sys.stderr)
        return 1

    print(f"Analyzing {extraction_path}...")

    from ..ir.builder import build_ir
    from ..graph.builder import build_dependency_graph
    from ..supportability.engine import analyze_supportability, SupportabilityEngine

    app_ir = build_ir(extraction_path)
    graph = build_dependency_graph(app_ir)
    support_results = analyze_supportability(app_ir)

    engine = SupportabilityEngine(app_ir)
    engine.results = support_results
    coverage = engine.calculate_coverage()

    print(f"\nApplication: {app_ir.application_name}")
    print(f"\nObjects:")
    print(f"  Tables: {len(app_ir.tables)}")
    print(f"  Queries: {len(app_ir.queries)}")
    print(f"  Forms: {len(app_ir.forms)}")
    print(f"  Reports: {len(app_ir.reports)}")
    print(f"  Macros: {len(app_ir.macros)}")
    print(f"  VBA Modules: {len(app_ir.vba_modules)}")

    print(f"\nDependency Graph:")
    print(f"  Nodes: {len(graph.nodes)}")
    print(f"  Cycles: {len(graph.find_cycles())}")
    print(f"  Orphans: {len(graph.find_orphans())}")

    print(f"\nCoverage:")
    print(f"  Overall: {coverage.get('overall', 0)}%")
    for cat in ["table", "query", "form", "report", "macro", "vba"]:
        key = f"{cat}_coverage"
        if key in coverage:
            print(f"  {cat.title()}: {coverage[key]}%")

    print(f"\nUnsupported objects:")
    unsupported = [r for r in support_results if r.status.value == "UNSUPPORTED"]
    for r in unsupported[:10]:
        print(f"  - {r.object} ({r.category}): {r.reason}")
    if len(unsupported) > 10:
        print(f"  ... and {len(unsupported) - 10} more")

    return 0


def cmd_repair(args) -> int:
    """Run self-healing build repair on a generated project."""
    project_dir = Path(args.project)

    if not project_dir.exists():
        print(f"Error: Project directory not found: {project_dir}", file=sys.stderr)
        return 1

    print(f"Running self-healing build repair on {project_dir}...")
    print("=" * 60)

    from converter.app.build.repair import repair_project

    try:
        result = repair_project(project_dir)

        print(f"\nRepair Results:")
        print(f"  Final Status: {result['final_status']}")
        print(f"  Total Attempts: {result['total_attempts']}")

        for component in ["backend", "frontend", "database"]:
            if result[component]:
                comp_result = result[component]
                print(f"\n  {component.title()}:")
                print(f"    Original Errors: {comp_result.get('original_errors', 0)}")
                print(f"    Repair Attempts: {comp_result.get('attempts', 0)}")
                print(f"    Success: {comp_result.get('success', False)}")
                for repair in comp_result.get("repairs", []):
                    status = "[OK]" if repair["success"] else "[FAIL]"
                    print(f"    {status} [{repair['strategy']}] {repair['fix']}")
                    if repair.get("files_changed"):
                        for f in repair["files_changed"]:
                            print(f"       → {f}")

        print("\n  Repair History:")
        for attempt in result["attempts"]:
            status = "[OK]" if attempt["success"] else "[FAIL]"
            print(f"    {status} [{attempt['strategy']}] {attempt['category']}: {attempt['fix']}")

        if result["final_status"] == "success":
            print("\n" + "=" * 60)
            print("[OK] Build repair successful! Project is now buildable.")
            print("=" * 60)
            return 0
        else:
            print("\n" + "=" * 60)
            print("[FAIL] Build repair incomplete. Manual intervention required.")
            print("=" * 60)
            return 1

    except Exception as e:
        print(f"Error during repair: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        return 1


def cmd_corpus(args) -> int:
    """Run, capture, or initialize the golden test corpus (spec §52)."""
    from converter.app.corpus.models import CorpusRegistry, CheckOutcome

    default_root = Path(__file__).resolve().parent.parent / "corpus"
    root = Path(args.root) if args.root else default_root

    # ---- init ----
    if args.action == "init":
        from converter.app.corpus.init_corpus import init_corpus
        init_corpus(root)
        return 0

    # ---- list ----
    if args.action == "list":
        try:
            registry = CorpusRegistry.load(root)
        except FileNotFoundError as exc:
            print(f"Error: {exc}", file=sys.stderr)
            return 1
        print(f"Corpus at {root}  ({len(registry.items)} declared categories)")
        print("=" * 66)
        for item in registry.items:
            mark = "+" if item.is_runnable else "-"
            line = f"  {mark} {item.name:20s} {item.status.value:15s}"
            if item.reason:
                line += f" {item.reason[:28]}"
            print(line)
        print("=" * 66)
        print(f"  runnable: {len(registry.runnable)} / {len(registry.items)}")
        return 0

    # ---- run / capture ----
    from converter.app.corpus import capture_expectations, run_corpus

    only = args.item or None
    try:
        if args.action == "capture":
            print(f"Capturing corpus expectations from {root}...")
            report = capture_expectations(root, only=only)
        else:
            print(f"Running corpus at {root}...")
            report = run_corpus(root, only=only)
    except FileNotFoundError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1

    data = report.to_dict()
    summary = data["summary"]

    print("=" * 66)
    for result in data["results"]:
        flag = "[OK]" if result["passed"] else "[FAIL]"
        print(f"{flag} {result['item']}  ({result['duration_seconds']}s)")
        if result["error"]:
            print(f"       error: {result['error']}")
        for check in result["checks"]:
            outcome = check["outcome"]
            if outcome == CheckOutcome.PASS.value:
                continue
            print(f"       {outcome:9s} {check['name']}: {check['detail']}")
            for diff in check["diffs"][:8]:
                print(f"           - {diff[:110]}")

    if data["blocked"]:
        print("\n  Blocked (cannot run on this machine):")
        for entry in data["blocked"]:
            print(f"    - {entry['item']}: {entry['reason']}")

    if data["declared_not_populated"]:
        names = ", ".join(data["declared_not_populated"])
        print(f"\n  Declared but not populated ({len(data['declared_not_populated'])}):")
        print(f"    {names}")

    print("=" * 66)
    print(f"  {summary['coverage_note']}")
    print(f"  passed={summary['items_passed']} failed={summary['items_failed']} "
          f"known_gaps={summary['known_gaps']}")

    if args.report:
        out = Path(args.report)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(data, indent=2), encoding="utf-8")
        print(f"  report written to {out}")

    if args.action == "capture":
        print("\n  Baselines captured. Review each expected/*.json, then set")
        print('  "_status": "REVIEWED" once verified against the spec.')
        return 0

    return 0 if summary["ok"] else 1


def main(argv: Optional[list[str]] = None) -> int:
    """Main CLI entry point."""
    parser = argparse.ArgumentParser(
        prog="converter",
        description="MS Access to Spring Boot + React + PostgreSQL Converter",
    )

    subparsers = parser.add_subparsers(dest="command", required=True)

    # convert command
    convert_parser = subparsers.add_parser(
        "convert",
        help="Convert an Access database to Spring Boot + React + PostgreSQL",
    )
    convert_parser.add_argument("input", help="Path to .accdb or .mdb file")
    convert_parser.add_argument(
        "-o", "--output",
        required=True,
        help="Output directory for generated project",
    )
    convert_parser.add_argument(
        "-p", "--package",
        default="com.generated.app",
        help="Base Java package name (default: com.generated.app)",
    )
    convert_parser.add_argument(
        "--report-strategy",
        default="pdf",
        choices=["pdf", "csv", "both"],
        help="Report output formats to generate. 'csv' omits the PDF library "
             "dependency (default: pdf, which also generates CSV)",
    )
    convert_parser.set_defaults(func=cmd_convert)

    # extract command
    extract_parser = subparsers.add_parser(
        "extract",
        help="Extract metadata from an Access database",
    )
    extract_parser.add_argument("input", help="Path to .accdb or .mdb file")
    extract_parser.add_argument(
        "-o", "--output",
        required=True,
        help="Output directory for extraction results",
    )
    extract_parser.set_defaults(func=cmd_extract)

    # analyze command
    analyze_parser = subparsers.add_parser(
        "analyze",
        help="Analyze an extraction JSON file",
    )
    analyze_parser.add_argument("input", help="Path to extraction.json")
    analyze_parser.set_defaults(func=cmd_analyze)

    # repair command
    repair_parser = subparsers.add_parser(
        "repair",
        help="Run self-healing build repair on a generated project",
    )
    repair_parser.add_argument("project", help="Path to generated project directory")
    repair_parser.set_defaults(func=cmd_repair)

    # corpus command (spec §52)
    corpus_parser = subparsers.add_parser(
        "corpus",
        help="Run the golden test corpus against the converter",
    )
    corpus_parser.add_argument(
        "action",
        choices=["run", "capture", "init", "list"],
        help="run: diff against expectations; capture: (re)write baselines; "
             "init: create/refresh the registry; list: show all categories",
    )
    corpus_parser.add_argument(
        "-i", "--item",
        action="append",
        help="Limit to a corpus item (repeatable)",
    )
    corpus_parser.add_argument(
        "--root",
        help="Corpus root directory (default: <project>/corpus)",
    )
    corpus_parser.add_argument(
        "--report",
        help="Write the full JSON run report to this path",
    )
    corpus_parser.set_defaults(func=cmd_corpus)

    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
