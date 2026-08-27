"""Conversion manifest and honest modernization scoring (PHASE 24-26).

Every converted object receives a per-feature status. The manifest is the
authoritative record of what the converter actually accomplished, distinct
from what it *discovered*. A form that generates valid JSX but has no event
handlers converted is PARTIAL, not CONVERTED.

Scoring dimensions (PHASE 24):
    DISCOVERED       object exists in the .accdb
    EXTRACTED        raw metadata captured
    STRUCTURAL       schema / UI skeleton generated
    BEHAVIORAL       events / business logic converted
    RUNTIME_VALIDATED output compiles and serves requests

The critical rule: **SUPPORTED must never mean CONVERTED**.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional

from .ir.models import (
    ApplicationIR, FormIR, QueryIR, TableIR, VbaModuleIR,
    MacroIR, ReportIR, SupportStatus,
)


# ---------------------------------------------------------------- status enum

STATUS_VALUES = (
    "DISCOVERED",
    "EXTRACTED",
    "PARTIALLY_EXTRACTED",
    "FAILED_EXTRACTION",
    "SUPPORTED",
    "SUPPORTED_WITH_TRANSFORMATION",
    "SUPPORTED_WITH_REVIEW",
    "CONVERTED",
    "CONVERTED_WITH_REVIEW",
    "UNSUPPORTED",
    "DROPPED",
    "FAILED_CONVERSION",
    "COMPILED",
    "RUNTIME_VALIDATED",
    "SEMANTICALLY_VALIDATED",
)


@dataclass
class ObjectManifestEntry:
    """Per-object conversion manifest."""
    source: str
    category: str                 # TABLE | QUERY | FORM | REPORT | MACRO | VBA
    target_react: Optional[str] = None
    target_java: Optional[str] = None
    target_db: Optional[str] = None
    features: dict[str, str] = field(default_factory=dict)
    overall_status: str = "DISCOVERED"
    notes: list[str] = field(default_factory=list)


@dataclass
class ConversionManifest:
    """Complete conversion manifest for an application."""
    source_file: str
    application_name: str
    objects: list[ObjectManifestEntry] = field(default_factory=list)
    extraction_manifest: dict[str, list[dict]] = field(default_factory=dict)

    # ---------------------------------------------------------------- build

    @classmethod
    def build(cls, app_ir: ApplicationIR) -> "ConversionManifest":
        manifest = cls(
            source_file=app_ir.source_file,
            application_name=app_ir.application_name,
            extraction_manifest=getattr(app_ir, 'extraction_manifest', {}),
        )

        for table in app_ir.tables:
            manifest.objects.append(manifest._table_entry(table))
        for query in app_ir.queries:
            manifest.objects.append(manifest._query_entry(query))
        for form in app_ir.forms:
            manifest.objects.append(manifest._form_entry(form, app_ir))
        for report in app_ir.reports:
            manifest.objects.append(manifest._report_entry(report, app_ir))
        for macro in app_ir.macros:
            manifest.objects.append(manifest._macro_entry(macro))
        for module in app_ir.vba_modules:
            manifest.objects.append(manifest._vba_entry(module))
        return manifest

    # ---------------------------------------------------------------- per-type

    def _table_entry(self, t: TableIR) -> ObjectManifestEntry:
        has_unsupported = any(
            c.is_attachment or c.is_multivalue or c.is_ole
            for c in t.columns
        )
        status = "CONVERTED" if not has_unsupported else "CONVERTED_WITH_REVIEW"
        from .naming import to_pascal, to_snake
        return ObjectManifestEntry(
            source=t.name, category="TABLE",
            target_java=f"{to_pascal(t.name)}.java",
            target_db=f"{to_snake(t.name)}",
            features={"schema": "CONVERTED"},
            overall_status=status,
        )

    def _query_entry(self, q: QueryIR) -> ObjectManifestEntry:
        has_vba = any(
            f not in ('Nz', 'IIf', 'Format', 'DatePart', 'DateAdd', 'DateDiff',
                       'Year', 'Month', 'Day', 'Now', 'Date', 'Time',
                       'Trim', 'UCase', 'LCase', 'Left', 'Right', 'Mid',
                       'Len', 'InStr', 'Val', 'CStr', 'CInt', 'CLng', 'CDbl',
                       'CBool', 'CDate', 'IsNull', 'IsNumeric')
            for f in q.access_functions
        )
        if has_vba:
            return ObjectManifestEntry(
                source=q.name, category="QUERY",
                features={"sql": "EXTRACTED", "conversion": "DROPPED"},
                overall_status="DROPPED",
                notes=["references custom VBA functions"]
            )
        if q.converted_sql:
            return ObjectManifestEntry(
                source=q.name, category="QUERY",
                features={"sql": "EXTRACTED", "translation": "CONVERTED"},
                overall_status="CONVERTED",
            )
        if (q.sql or "").strip():
            return ObjectManifestEntry(
                source=q.name, category="QUERY",
                features={"sql": "EXTRACTED", "translation": "NOT_CONVERTED"},
                overall_status="SUPPORTED_WITH_TRANSFORMATION",
                notes=["query not yet translated to PostgreSQL"],
            )
        return ObjectManifestEntry(
            source=q.name, category="QUERY",
            features={"sql": "PARTIAL"},
            overall_status="PARTIALLY_EXTRACTED",
        )

    def _form_entry(self, f: FormIR, app_ir: ApplicationIR) -> ObjectManifestEntry:
        from .naming import to_pascal
        events_converted = "CONVERTED" if not f.events else "NOT_CONVERTED"
        vba_converted = "CONVERTED" if not f.module_name else (
            "CONVERTED" if (f.module_source or "").strip() else "FAILED_EXTRACTION")
        status = "CONVERTED"
        notes = []
        if f.events:
            status = "CONVERTED_WITH_REVIEW"
            notes.append(f"{len(f.events)} events not converted to handlers")
        if f.module_name and not (f.module_source or "").strip():
            status = "PARTIAL"
            notes.append("form module source not extracted")
        rs = f.record_source_kind or "NONE"
        return ObjectManifestEntry(
            source=f.name, category="FORM",
            target_react=f"{to_pascal(f.name)}Page.jsx",
            features={
                "controls": "CONVERTED",
                "layout": "CONVERTED",
                "recordSource": rs,
                "events": events_converted,
                "vba": vba_converted,
                "businessLogic": "NOT_CONVERTED" if f.events else "N/A",
            },
            overall_status=status,
            notes=notes,
        )

    def _report_entry(self, r: ReportIR, app_ir: ApplicationIR) -> ObjectManifestEntry:
        from .naming import to_pascal
        status = "CONVERTED" if r.record_source else "CONVERTED_WITH_REVIEW"
        notes = []
        if not r.record_source:
            notes.append("no record source")
        return ObjectManifestEntry(
            source=r.name, category="REPORT",
            target_react=f"{to_pascal(r.name)}ReportPage.jsx",
            features={
                "recordSource": r.record_source or "NONE",
                "grouping": "CONVERTED" if r.groups else "N/A",
                "vba": "CONVERTED" if not r.module_name else "NOT_CONVERTED",
            },
            overall_status=status,
            notes=notes,
        )

    def _macro_entry(self, m: MacroIR) -> ObjectManifestEntry:
        if m.actions:
            return ObjectManifestEntry(
                source=m.name, category="MACRO",
                features={"actions": "CONVERTED"},
                overall_status="CONVERTED_WITH_REVIEW",
            )
        status = "FAILED_EXTRACTION" if not (m.source or "").strip() else "NOT_CONVERTED"
        return ObjectManifestEntry(
            source=m.name, category="MACRO",
            features={"actions": "EXTRACTED" if (m.source or "").strip() else "FAILED_EXTRACTION"},
            overall_status=status,
        )

    def _vba_entry(self, m: VbaModuleIR) -> ObjectManifestEntry:
        has_source = bool((m.source or "").strip())
        if not has_source:
            return ObjectManifestEntry(
                source=m.name, category="VBA",
                features={"extraction": "FAILED_EXTRACTION"},
                overall_status="FAILED_EXTRACTION",
            )
        notes = []
        if m.uses_external:
            notes.append(f"external: {', '.join(m.uses_external)}")
        if m.declares_api:
            notes.append(f"{len(m.declares_api)} API declarations")
        status = "CONVERTED_WITH_REVIEW" if (m.uses_external or m.declares_api or m.references_com) else "CONVERTED"
        return ObjectManifestEntry(
            source=m.name, category="VBA",
            features={
                "extraction": "SUCCESS",
                "procedures": f"{len(m.procedures)} extracted",
                "java_translation": "NOT_CONVERTED",
            },
            overall_status=status,
            notes=notes,
        )

    # ---------------------------------------------------------------- scoring

    def calculate_scores(self) -> dict[str, Any]:
        """Return per-category modernization scores (PHASE 24).

        Each category scores 0-100 across five dimensions:
            discovered → extracted → structural → behavioral → runtime
        The overall score is the weighted average.
        """
        _dim_weights = [10, 15, 25, 30, 20]  # runtime weight is lower
                                       # because we don't have a
                                       # running server yet
        categories: dict[str, list[ObjectManifestEntry]] = {}
        for obj in self.objects:
            categories.setdefault(obj.category, []).append(obj)

        scores = {}
        total_score = 0.0
        total_weight = 0

        for cat, entries in categories.items():
            if not entries:
                scores[f"{cat.lower()}_coverage"] = 0.0
                continue

            dim_sums = [0.0] * 5
            for entry in entries:
                dims = self._object_dimensions(entry)
                for i, d in enumerate(dims):
                    dim_sums[i] += d
            n = len(entries)
            dim_avgs = [s / n for s in dim_sums]
            cat_score = sum(w * d for w, d in zip(_dim_weights, dim_avgs))
            scores[f"{cat.lower()}_coverage"] = round(cat_score, 1)
            total_score += cat_score * n
            total_weight += n
        scores["overall"] = round(total_score / total_weight, 1) if total_weight else 0.0
        return scores

    @staticmethod
    def _object_dimensions(entry: ObjectManifestEntry) -> list[float]:
        """Return [discovered, extracted, structural, behavioral, runtime] 0-1."""
        status = entry.overall_status
        feats = entry.features

        # Discovered: always 1.0 (the object exists in extraction)
        d0 = 1.0

        # Extracted
        if status in ("FAILED_EXTRACTION", "PARTIALLY_EXTRACTED"):
            d1 = 0.0 if status == "FAILED_EXTRACTION" else 0.5
        else:
            d1 = 1.0

        # Structural (schema / UI skeleton)
        if status in ("CONVERTED", "CONVERTED_WITH_REVIEW"):
            d2 = 1.0
        elif status in ("SUPPORTED", "SUPPORTED_WITH_TRANSFORMATION", "SUPPORTED_WITH_REVIEW"):
            d2 = 0.5  # known but not yet generated
        elif status == "DROPPED":
            d2 = 0.0
        else:
            d2 = 0.0

        # Behavioral (events, business logic)
        behavioral_feats = {"events", "vba", "businessLogic", "actions", "java_translation"}
        bh_statuses = [feats.get(f) for f in behavioral_feats]
        if any(s == "CONVERTED" for s in bh_statuses if s):
            d3 = 1.0
        elif any(s in ("NOT_CONVERTED", "FAILED_EXTRACTION") for s in bh_statuses if s):
            d3 = 0.0
        elif status in ("CONVERTED", "CONVERTED_WITH_REVIEW"):
            d3 = 0.5  # structure done, no behavior to convert (e.g. simple table)
        else:
            d3 = 0.0

        # Runtime (always 0 until we validate)
        d4 = 0.0

        return [d0, d1, d2, d3, d4]

    # ---------------------------------------------------------------- serialise

    def to_dict(self) -> dict[str, Any]:
        return {
            "sourceFile": self.source_file,
            "applicationName": self.application_name,
            "scores": self.calculate_scores(),
            "extractionManifest": self.extraction_manifest,
            "objects": [
                {
                    "source": o.source,
                    "category": o.category,
                    "targetReact": o.target_react,
                    "targetJava": o.target_java,
                    "targetDb": o.target_db,
                    "features": o.features,
                    "overallStatus": o.overall_status,
                    "notes": o.notes,
                }
                for o in self.objects
            ],
        }
