"""Functionality Summarizer — generates business-logic descriptions using LLM.

Uses the connected LLM provider to transform technical Access object metadata
into human-readable business-language descriptions.  Falls back to deterministic
descriptions built from IR metadata when the LLM is unavailable.

Called during the conversion pipeline after supportability analysis and before
code generation so that the migration report includes rich functional context.
"""
from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field, asdict
from typing import Any, Optional

logger = logging.getLogger("converter.analyzers.functionality_summarizer")

# ── Conversion strategy → human-readable target mapping ──────────────────────

_CONVERSION_TARGET_LABELS: dict[str, str] = {
    "JPA_ENTITY": "JPA Entity + Repository + REST Controller",
    "JPA_ENTITY_WITH_WARNINGS": "JPA Entity (with manual review notes)",
    "LINKED_ACCESS_TABLE": "JPA Entity (linked-table migration needed)",
    "EXTERNAL_SOURCE": "Integration Layer (external data source)",
    "REPOSITORY_METHOD": "Spring Data JPA Repository Method",
    "REST_ENDPOINT": "REST API Endpoint",
    "REACT_PAGE": "React Page Component",
    "REPORT_ENDPOINT": "PDF Report Service Endpoint",
    "SERVICE_METHOD": "Spring Service Method",
    "SPRING_SERVICE": "Spring Boot Service Bean",
    "INTEGRATION_LAYER": "Integration Adapter Layer",
    "MANUAL": "Manual Implementation Required",
}

_CATEGORY_LABELS: dict[str, str] = {
    "TABLE": "Data Store",
    "QUERY": "Data Query / API",
    "FORM": "User Interface",
    "REPORT": "Report",
    "MACRO": "Automation",
    "VBA": "Business Logic",
    "EXTERNAL": "External Integration",
}

_CATEGORY_SOURCE_LABELS: dict[str, str] = {
    "TABLE": "Access Table",
    "QUERY": "Access Query",
    "FORM": "Access Form",
    "REPORT": "Access Report",
    "MACRO": "Access Macro",
    "VBA": "VBA Module",
    "EXTERNAL": "External Dependency",
}

_CATEGORY_TARGET_LABELS: dict[str, str] = {
    "TABLE": "PostgreSQL Table + JPA Entity",
    "QUERY": "REST API Endpoint",
    "FORM": "React Page Component",
    "REPORT": "PDF Report Service",
    "MACRO": "Spring Service Method",
    "VBA": "Spring Boot Service",
    "EXTERNAL": "Integration Layer",
}

_STATUS_LABELS: dict[str, str] = {
    "SUPPORTED": "fully_automated",
    "SUPPORTED_WITH_TRANSFORMATION": "fully_automated",
    "SUPPORTED_WITH_REVIEW": "needs_review",
    "UNSUPPORTED": "manual_required",
    "FAILED_EXTRACTION": "manual_required",
}


@dataclass
class FunctionalitySummary:
    """A single functionality's business-level summary."""
    object_name: str
    category: str
    business_name: str
    description: str
    what_it_does: str
    conversion_target: str
    status: str                         # fully_automated | needs_review | manual_required
    human_action: Optional[str] = None
    confidence: float = 1.0
    risk: str = "LOW"
    complexity: str = "LOW"
    source_label: str = ""
    target_label: str = ""
    detail_counts: str = ""             # e.g. "15 columns, 1250 rows"
    reason: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


# ── Deterministic fallback descriptions ──────────────────────────────────────

def _humanize_name(name: str) -> str:
    """Convert a technical name like 'tblCustomerOrders' to 'Customer Orders'."""
    import re
    # Strip common prefixes
    for prefix in ("tbl", "qry", "frm", "rpt", "mcr", "bas", "mod", "cls"):
        if name.lower().startswith(prefix) and len(name) > len(prefix):
            name = name[len(prefix):]
            break
    # Split on camel case and underscores
    name = re.sub(r'([a-z])([A-Z])', r'\1 \2', name)
    name = name.replace("_", " ")
    return name.strip().title()


def _build_deterministic_summary(
    obj_name: str,
    category: str,
    support_result: dict,
    ir_context: dict,
) -> FunctionalitySummary:
    """Build a summary without LLM, using only IR metadata."""
    status_key = support_result.get("status", "SUPPORTED")
    mapped_status = _STATUS_LABELS.get(status_key, "needs_review")
    conversion = support_result.get("conversion", "")
    reason = support_result.get("reason", "")
    confidence = support_result.get("confidence", 1.0)
    risk = support_result.get("risk", "LOW")
    complexity = support_result.get("complexity", "LOW")

    business_name = _humanize_name(obj_name)
    source_label = _CATEGORY_SOURCE_LABELS.get(category, category)
    target_label = _CONVERSION_TARGET_LABELS.get(conversion, _CATEGORY_TARGET_LABELS.get(category, "Modern equivalent"))

    # Build category-specific descriptions
    if category == "TABLE":
        col_count = ir_context.get("column_count", 0)
        row_count = ir_context.get("row_count")
        col_names = ir_context.get("column_names", [])[:5]
        cols_str = ", ".join(col_names) if col_names else "various fields"
        detail_counts = f"{col_count} columns"
        if row_count is not None:
            detail_counts += f", {row_count:,} rows"
        description = f"Stores data with {col_count} fields including {cols_str}."
        what_it_does = f"A data table used to store records with fields like {cols_str}."

    elif category == "QUERY":
        kind = ir_context.get("kind", "SELECT")
        tables = ir_context.get("references_tables", [])
        tables_str = ", ".join(tables[:3]) if tables else "application data"
        detail_counts = f"{kind} query"
        if tables:
            detail_counts += f", references {len(tables)} table(s)"
        description = f"A {kind.lower()} query that operates on {tables_str}."
        what_it_does = f"Retrieves or modifies data from {tables_str}."

    elif category == "FORM":
        control_count = ir_context.get("control_count", 0)
        record_source = ir_context.get("record_source")
        event_count = ir_context.get("event_count", 0)
        detail_counts = f"{control_count} controls"
        if event_count:
            detail_counts += f", {event_count} events"
        if record_source:
            description = f"A data entry form bound to {record_source} with {control_count} input controls."
            what_it_does = f"Allows users to view, create, and edit records from {record_source}."
        else:
            description = f"A user interface form with {control_count} controls (not bound to a specific data source)."
            what_it_does = f"Provides a user interface with {control_count} interactive elements."

    elif category == "REPORT":
        record_source = ir_context.get("record_source")
        group_count = ir_context.get("group_count", 0)
        detail_counts = f"{group_count} group(s)" if group_count else "flat layout"
        if record_source:
            description = f"A printable report based on {record_source}."
            what_it_does = f"Generates a formatted report from {record_source} data."
        else:
            description = f"A report template with {group_count} grouping level(s)."
            what_it_does = f"Produces a formatted output document."

    elif category == "MACRO":
        action_count = ir_context.get("action_count", 0)
        is_autoexec = ir_context.get("is_autoexec", False)
        detail_counts = f"{action_count} action(s)"
        description = f"An automation macro with {action_count} action(s)."
        if is_autoexec:
            description += " Runs automatically when the database opens."
            what_it_does = "Automates startup tasks when the application loads."
        else:
            what_it_does = f"Automates a sequence of {action_count} operations."

    elif category == "VBA":
        proc_count = ir_context.get("procedure_count", 0)
        module_type = ir_context.get("module_type", "STANDARD")
        detail_counts = f"{proc_count} procedure(s)"
        description = f"A {module_type.lower()} VBA module containing {proc_count} procedure(s)."
        what_it_does = f"Contains {proc_count} programmatic routine(s) implementing application logic."

    else:
        detail_counts = ""
        description = f"{category} component: {obj_name}."
        what_it_does = f"An application component of type {category}."

    # Build human action message if needed
    human_action = None
    if mapped_status == "needs_review":
        human_action = reason if reason else "Review the converted output for correctness."
    elif mapped_status == "manual_required":
        human_action = reason if reason else "This component requires manual implementation."

    return FunctionalitySummary(
        object_name=obj_name,
        category=category,
        business_name=business_name,
        description=description,
        what_it_does=what_it_does,
        conversion_target=target_label,
        status=mapped_status,
        human_action=human_action,
        confidence=confidence,
        risk=risk,
        complexity=complexity,
        source_label=source_label,
        target_label=target_label,
        detail_counts=detail_counts,
        reason=reason,
    )


# ── IR context extraction helpers ────────────────────────────────────────────

def _extract_ir_context(app_ir, obj_name: str, category: str) -> dict:
    """Pull relevant metadata from the ApplicationIR for a specific object."""
    ctx: dict[str, Any] = {}

    if category == "TABLE":
        tbl = app_ir.table(obj_name)
        if tbl:
            ctx["column_count"] = len(tbl.columns)
            ctx["row_count"] = tbl.row_count
            ctx["column_names"] = [c.name for c in tbl.columns]
            ctx["is_linked"] = tbl.is_linked
            ctx["description"] = tbl.description

    elif category == "QUERY":
        qry = app_ir.query(obj_name)
        if qry:
            ctx["kind"] = qry.kind.value if hasattr(qry.kind, "value") else str(qry.kind)
            ctx["references_tables"] = qry.references_tables
            ctx["sql_snippet"] = (qry.sql or "")[:200]
            ctx["access_functions"] = qry.access_functions

    elif category == "FORM":
        frm = app_ir.form(obj_name)
        if frm:
            ctx["control_count"] = len(frm.controls)
            ctx["record_source"] = frm.record_source
            ctx["event_count"] = len(frm.events)
            ctx["has_vba"] = bool(frm.module_name)
            ctx["caption"] = frm.caption
            ctx["control_names"] = [c.name for c in frm.controls[:8]]

    elif category == "REPORT":
        rpt = next((r for r in app_ir.reports if r.name.lower() == obj_name.lower()), None)
        if rpt:
            ctx["record_source"] = rpt.record_source
            ctx["group_count"] = len(rpt.groups)
            ctx["control_count"] = len(rpt.controls)
            ctx["has_subreports"] = bool(rpt.subreports)

    elif category == "MACRO":
        macro = next((m for m in app_ir.macros if m.name.lower() == obj_name.lower()), None)
        if macro:
            ctx["action_count"] = len(macro.actions)
            ctx["is_autoexec"] = macro.is_autoexec
            ctx["action_names"] = [a.action for a in macro.actions[:5]]

    elif category == "VBA":
        mod = next((m for m in app_ir.vba_modules if m.name.lower() == obj_name.lower()), None)
        if mod:
            ctx["procedure_count"] = len(mod.procedures)
            ctx["module_type"] = mod.module_type
            ctx["proc_names"] = [p.name for p in mod.procedures[:5]]
            ctx["uses_external"] = mod.uses_external

    return ctx


# ── LLM-powered summarization ───────────────────────────────────────────────

_LLM_SYSTEM_PROMPT = """You are an expert software migration consultant analyzing a Microsoft Access database application being modernized to a Spring Boot + React + PostgreSQL technology stack.

Your task is to describe each application component in plain business language that a non-technical project manager or stakeholder can understand. Focus on WHAT the component does for the business, not HOW it works technically.

Rules:
- business_name: A short, clear name (2-5 words) describing the function, e.g. "Customer Records Management" not "tblCustomers Table"
- description: 1-2 sentences explaining what this does for the business
- what_it_does: What the user/business achieves with this functionality
- human_action: If status is not "fully_automated", explain specifically what a developer needs to do, in plain language

Respond ONLY with valid JSON."""


def _build_llm_prompt(objects_batch: list[dict]) -> str:
    """Build the LLM prompt for a batch of objects."""
    lines = ["Analyze these Microsoft Access application components and describe each in business language:\n"]

    for i, obj in enumerate(objects_batch, 1):
        lines.append(f"{i}. {obj['category']} \"{obj['object_name']}\"")
        if obj.get("detail_counts"):
            lines.append(f"   Details: {obj['detail_counts']}")
        if obj.get("reason"):
            lines.append(f"   Technical note: {obj['reason']}")
        lines.append(f"   Conversion status: {obj['status']} → {obj.get('conversion_target', 'N/A')}")
        lines.append("")

    lines.append("Respond with a JSON array of objects with these exact fields:")
    lines.append('  [{"object_name": "...", "business_name": "...", "description": "...", "what_it_does": "...", "human_action": "..." or null}]')

    return "\n".join(lines)


def _llm_batch_summarize(
    provider,
    objects_batch: list[dict],
) -> list[dict]:
    """Call the LLM to generate business descriptions for a batch of objects."""
    if not objects_batch:
        return []

    prompt = _build_llm_prompt(objects_batch)

    try:
        response = provider.generate(
            prompt,
            system_prompt=_LLM_SYSTEM_PROMPT,
            json_mode=True,
        )
        content = response.content.strip()

        # Parse JSON — handle both array and wrapped formats
        parsed = json.loads(content)
        if isinstance(parsed, dict):
            # Some LLMs wrap in {"results": [...]}
            for key in ("results", "summaries", "components", "items"):
                if key in parsed and isinstance(parsed[key], list):
                    parsed = parsed[key]
                    break
            else:
                parsed = [parsed]

        if not isinstance(parsed, list):
            logger.warning("LLM returned non-list JSON, falling back")
            return []

        return parsed

    except Exception as e:
        logger.warning("LLM summarization failed: %s — using deterministic fallback", e)
        return []


# ── Main entry point ─────────────────────────────────────────────────────────

def summarize_functionalities(
    app_ir,
    support_results: list[dict],
    use_llm: bool = True,
    max_batch_size: int = 15,
) -> list[dict]:
    """Generate business-logic functionality summaries.

    Args:
        app_ir: The ApplicationIR object
        support_results: List of supportability result dicts
            (each has: object, category, status, complexity, risk, conversion, confidence, reason)
        use_llm: Whether to attempt LLM-powered descriptions
        max_batch_size: Max objects per LLM call

    Returns:
        List of FunctionalitySummary dicts
    """
    # Step 1: Build deterministic summaries for all objects
    summaries: list[FunctionalitySummary] = []
    for sr in support_results:
        obj_name = sr.get("object", "")
        category = sr.get("category", "")
        ir_ctx = _extract_ir_context(app_ir, obj_name, category)

        summary = _build_deterministic_summary(obj_name, category, sr, ir_ctx)
        summaries.append(summary)

    # Step 2: Attempt LLM enhancement if enabled
    if use_llm:
        try:
            from converter.app.llm.provider import get_default_provider
            provider = get_default_provider()

            # Prepare batch data
            batch_input = []
            for s in summaries:
                batch_input.append({
                    "object_name": s.object_name,
                    "category": s.category,
                    "detail_counts": s.detail_counts,
                    "reason": s.reason,
                    "status": s.status,
                    "conversion_target": s.conversion_target,
                })

            # Process in batches
            llm_results: list[dict] = []
            for i in range(0, len(batch_input), max_batch_size):
                batch = batch_input[i:i + max_batch_size]
                results = _llm_batch_summarize(provider, batch)
                llm_results.extend(results)

            # Merge LLM results into deterministic summaries
            llm_by_name = {r.get("object_name", ""): r for r in llm_results if isinstance(r, dict)}
            for summary in summaries:
                llm_data = llm_by_name.get(summary.object_name)
                if llm_data:
                    if llm_data.get("business_name"):
                        summary.business_name = llm_data["business_name"]
                    if llm_data.get("description"):
                        summary.description = llm_data["description"]
                    if llm_data.get("what_it_does"):
                        summary.what_it_does = llm_data["what_it_does"]
                    if llm_data.get("human_action"):
                        summary.human_action = llm_data["human_action"]

            logger.info(
                "LLM enhanced %d / %d functionality summaries",
                len(llm_by_name), len(summaries),
            )

        except Exception as e:
            logger.warning("LLM enhancement skipped: %s — using deterministic descriptions", e)

    return [s.to_dict() for s in summaries]
