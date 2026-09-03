"""BRD API Router.
Provides endpoints for BRD report generation, HTML preview, and HTML download.
"""
from __future__ import annotations

import asyncio
import logging
from pathlib import Path
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import FileResponse, HTMLResponse
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from converter.app.database import get_db_session, get_session, JobModel
from BRD.services.source_analyzer import extract_project_facts
from BRD.services.brd_generator import generate_brd_for_job, sanitize_project_name, OUTPUT_DIR
from BRD.services.ollama_client import OllamaUnavailableError, OllamaModelError

logger = logging.getLogger("converter.brd.api")

router = APIRouter(prefix="/brd", tags=["BRD Report"])


class BRDGenerateRequest(BaseModel):
    job_id: str


class BRDGenerateResponse(BaseModel):
    success: bool
    job_id: str
    project_name: str
    preview_url: str
    download_url: str
    relative_path: str


@router.post("/generate", response_model=BRDGenerateResponse)
async def generate_brd(payload: BRDGenerateRequest):
    """Trigger BRD generation for an analyzed project/job."""
    job_id = payload.job_id.strip()
    if not job_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Please upload or select a project before generating the BRD.",
        )

    # STEP 0 — HARD SYNCHRONIZATION GATE:
    # If analysis is asynchronous, poll/await completion — never generate against a partial set.
    max_wait = 30.0
    poll_interval = 1.0
    elapsed = 0.0

    facts = None
    while True:
        async with get_session() as session:
            stmt = select(JobModel).where(JobModel.id == job_id)
            res = await session.execute(stmt)
            job = res.scalar_one_or_none()
            if not job:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Please upload or select a project before generating the BRD.",
                )

            current_state = str(getattr(job, "state", "")).upper()
            if current_state in ("EXTRACTING", "ANALYZING", "CREATED", "UPLOADED") and elapsed < max_wait:
                logger.info(
                    "Step 0 Gate: Job %s is currently in state '%s'. Awaiting analysis completion (elapsed: %.1fs)...",
                    job_id,
                    current_state,
                    elapsed,
                )
                await asyncio.sleep(poll_interval)
                elapsed += poll_interval
                continue

            facts = await extract_project_facts(job_id, session)
            break

    try:
        result = await generate_brd_for_job(job_id, facts=facts)
        return result
    except OllamaUnavailableError as e:
        logger.error("Ollama service unavailable: %s", e)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="BRD generation is unavailable because the local Ollama service could not be reached.",
        ) from e
    except OllamaModelError as e:
        logger.error("Ollama model error: %s", e)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        ) from e
    except ValueError as e:
        logger.error("Validation error during BRD generation: %s", e)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        ) from e
    except Exception as e:
        logger.exception("Unexpected error generating BRD: %s", e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Unable to generate the BRD. Please try again.",
        ) from e


def find_brd_html_for_job(job: JobModel) -> Path:
    """Locate the generated BRD.html file for a job."""
    # 1. Primary check: Exact job ID output path
    job_path = OUTPUT_DIR / job.id / "BRD.html"
    if job_path.exists():
        return job_path

    # 2. Secondary check: Sanitized project name path
    project_name = sanitize_project_name(job.project_name or "ConvertedApplication")
    expected_path = OUTPUT_DIR / project_name / "BRD.html"
    if expected_path.exists():
        return expected_path

    # Do NOT return a random BRD from another job. Raise 404 so caller knows to generate.
    raise HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail="BRD report has not been generated yet for this project. Please click 'BRD Report' first.",
    )


@router.get("/{job_id}/preview", response_class=HTMLResponse)
async def preview_brd(
    job_id: str,
    session: AsyncSession = Depends(get_db_session),
):
    """Preview the generated BRD.html directly in the browser."""
    stmt = select(JobModel).where(JobModel.id == job_id)
    res = await session.execute(stmt)
    job = res.scalar_one_or_none()
    if not job:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job not found.")

    html_path = find_brd_html_for_job(job)
    content = html_path.read_text(encoding="utf-8")
    return HTMLResponse(content=content, media_type="text/html")


@router.get("/{job_id}/download")
async def download_brd(
    job_id: str,
    session: AsyncSession = Depends(get_db_session),
):
    """Download the generated BRD report as '<ProjectName>-BRD-Report.html'."""
    stmt = select(JobModel).where(JobModel.id == job_id)
    res = await session.execute(stmt)
    job = res.scalar_one_or_none()
    if not job:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job not found.")

    html_path = find_brd_html_for_job(job)
    project_name = job.project_name or "ConvertedApplication"
    return FileResponse(
        path=str(html_path),
        filename=f"{project_name}-BRD-Report.html",
        media_type="text/html",
    )

