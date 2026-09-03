"""BRD Generator Orchestrator.
Coordinates source analysis, static metric extraction, LLM narrative generation via Ollama,
and HTML template rendering to produce BRD/output/<project-name>/BRD.html.
"""
from __future__ import annotations

import asyncio
import logging
import os
import re
from pathlib import Path
from typing import Any, Dict, Optional
from sqlalchemy.ext.asyncio import AsyncSession

from .source_analyzer import extract_project_facts
from .static_analyzer import compute_static_metrics
from .ollama_client import OllamaClient, OllamaUnavailableError, OllamaModelError
from .template_renderer import render_brd_template

logger = logging.getLogger("converter.brd.generator")

BASE_BRD_DIR = Path(__file__).resolve().parent.parent
PROMPTS_DIR = BASE_BRD_DIR / "prompts"
OUTPUT_DIR = BASE_BRD_DIR / "output"


def sanitize_project_name(name: str) -> str:
    """Sanitize project name for directory creation."""
    sanitized = re.sub(r"[^a-zA-Z0-9_\-]", "_", name.strip())
    return sanitized or "ConvertedApplication"


async def generate_brd_for_job(
    job_id: str,
    session: Optional[AsyncSession] = None,
    facts: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Generate BRD HTML report for an analyzed job.
    
    If facts are not provided, extracts them quickly and releases any database session
    before calling the LLM to prevent SQLite transaction locking.
    """
    logger.info("Starting BRD generation for job ID: %s", job_id)

    # 1. Extract Project Facts from Job & Database Models (if not already provided)
    if facts is None:
        if session is not None:
            facts = await extract_project_facts(job_id, session)
        else:
            from converter.app.database import get_session
            async with get_session() as db_session:
                facts = await extract_project_facts(job_id, db_session)

    project_name = sanitize_project_name(facts.get("project_name", "ConvertedApplication"))

    # 2. Compute Static Metrics
    metrics = compute_static_metrics(facts)

    # 3. Read Prompts
    system_prompt_path = PROMPTS_DIR / "brd-system-prompt.txt"
    gen_prompt_path = PROMPTS_DIR / "brd-generation-prompt.txt"

    system_prompt = system_prompt_path.read_text(encoding="utf-8") if system_prompt_path.exists() else None
    prompt_template = gen_prompt_path.read_text(encoding="utf-8") if gen_prompt_path.exists() else ""

    # Format tables and queries for prompt
    table_names = [t.get("name", "") for t in facts.get("tables", [])[:15]]
    query_names = [q.get("name", "") for q in facts.get("queries", [])[:10]]
    form_names = [f.get("name", "") for f in facts.get("forms", [])[:10]]
    report_names = [r.get("name", "") for r in facts.get("reports", [])[:8]]
    macro_names = [m.get("name", "") for m in facts.get("macros", [])[:8]]
    vba_names = [v.get("name", "") for v in facts.get("vba_modules", [])[:8]]

    prompt = prompt_template.format(
        project_name=project_name,
        source_file=facts.get("source_file", "Database.accdb"),
        source_file_size=facts.get("source_file_size", 0),
        tables_count=facts.get("tables_count", 0),
        tables_list=", ".join(table_names) if table_names else "None",
        queries_count=facts.get("queries_count", 0),
        queries_list=", ".join(query_names) if query_names else "None",
        forms_count=facts.get("forms_count", 0),
        forms_list=", ".join(form_names) if form_names else "None",
        reports_count=facts.get("reports_count", 0),
        reports_list=", ".join(report_names) if report_names else "None",
        macros_count=facts.get("macros_count", 0),
        macros_list=", ".join(macro_names) if macro_names else "None",
        vba_modules_count=facts.get("vba_modules_count", 0),
        vba_list=", ".join(vba_names) if vba_names else "None",
        spring_boot_version=facts.get("spring_boot_version", "4.1.0"),
        java_version=facts.get("java_version", 25),
        react_version=facts.get("react_version", "19.2.8"),
        postgres_version=facts.get("postgres_version", "18"),
    )

    # 4. Call Ollama (deepseek-r1:1.5b) or use factual baseline narratives
    ollama_client = OllamaClient()
    narratives = {}
    try:
        narratives = await asyncio.to_thread(
            ollama_client.generate_narratives, prompt, system_prompt
        )
        logger.info("Successfully received structured narratives from Ollama.")
    except Exception as e:
        logger.warning("Ollama unavailable or error during BRD generation (%s); using factual baseline narratives.", e)
        narratives = {
            "doc_purpose_description": f"This document specifies the technical and business baseline for modernizing the {project_name} Access application.",
            "app_purpose_description": f"The {project_name} application manages operational business data across {facts.get('tables_count', 0)} data entities, {facts.get('queries_count', 0)} queries, and {facts.get('forms_count', 0)} user forms.",
            "app_modernization_context": f"Conversion of {project_name} to Spring Boot ({facts.get('spring_boot_version', '4.1.0')}) and React ({facts.get('react_version', '19.2.8')}) eliminates single-user file-locking limitations.",
            "detailed_purpose": f"Modernized platform architecture for {project_name} with automated database schema migration to PostgreSQL ({facts.get('postgres_version', '18')}).",
        }

    # 5. Render HTML Template
    rendered_html = render_brd_template(facts, metrics, narratives)

    # 6. Save to BRD/output/<project-name>/BRD.html AND BRD/output/<job_id>/BRD.html
    project_output_dir = OUTPUT_DIR / project_name
    project_output_dir.mkdir(parents=True, exist_ok=True)
    output_file = project_output_dir / "BRD.html"
    output_file.write_text(rendered_html, encoding="utf-8")

    job_output_dir = OUTPUT_DIR / job_id
    job_output_dir.mkdir(parents=True, exist_ok=True)
    job_output_file = job_output_dir / "BRD.html"
    job_output_file.write_text(rendered_html, encoding="utf-8")

    logger.info("BRD report successfully written to %s and %s", output_file, job_output_file)

    return {
        "success": True,
        "job_id": job_id,
        "project_name": project_name,
        "output_file": str(output_file.resolve()),
        "relative_path": f"BRD/output/{project_name}/BRD.html",
        "preview_url": f"/api/brd/{job_id}/preview",
        "download_url": f"/api/brd/{job_id}/download",
    }
