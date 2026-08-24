"""FastAPI Backend for MS Access Converter - spec section 63.

Provides REST API for:
- File upload
- Conversion orchestration
- Streaming progress
- Job management
- LLM orchestration
- Build subprocess control
- Report APIs
"""
from __future__ import annotations

import asyncio
import json
import shutil
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

from fastapi import (
    FastAPI, File, UploadFile, HTTPException, BackgroundTasks,
    WebSocket, WebSocketDisconnect, Depends, Query
)
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel, ConfigDict
from sqlalchemy.ext.asyncio import AsyncSession
from contextlib import asynccontextmanager

# Import converter modules
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from converter.app.database import (
    init_database, close_database, get_session,
    JobRepository, ExtractionRepository, IRRepository,
    DependencyGraphRepository, SupportabilityRepository,
    BuildLogRepository, LLMCacheRepository,
    ExternalDependencyRepository,
    JobModel, JobState, JobError, JobProgress, JobResult,
)
from converter.app.jobs.models import MigrationJob as PydanticMigrationJob
from converter.app.access.extractor import run_extraction
from converter.app.ir.builder import build_ir
from converter.app.graph.builder import build_dependency_graph, DependencyGraph
from converter.app.supportability.engine import analyze_supportability, SupportabilityEngine
from converter.app.generators.database.postgres import generate_schema
from converter.app.generators.spring import generate_spring_boot
from converter.app.generators.react import generate_react
from converter.app.analyzers.business_rules import extract_business_rules
from converter.app.build.validator import validate_project, BuildStatus as ValidatorBuildStatus
from converter.app.build.pipeline import (
    BuildValidator as PipelineBuildValidator,
    BuildRepair,
    BuildPhase,
    BuildStatus as PipelineBuildStatus,
    validate_generated_project,
    attempt_build_repair,
)


# ---------------------------------------------------------------- Lifespan

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan handler."""
    # Startup
    await init_database()
    yield
    # Shutdown
    await close_database()


# ---------------------------------------------------------------- models

class ConversionConfig(BaseModel):
    """Configuration for conversion."""
    project_name: str = "ConvertedApplication"
    base_package: str = "com.generated.app"
    java_version: int = 25
    spring_boot_version: str = "4.1.0"
    react_version: str = "19.2.8"
    node_version: int = 24
    postgres_version: str = "18"
    authentication_strategy: str = "jwt"
    report_strategy: str = "pdf"
    migration_strategy: str = "flyway"


class JobCreateRequest(BaseModel):
    """Request to create a new job."""
    config: ConversionConfig


class JobResponse(BaseModel):
    """Response with job details."""
    id: str
    state: JobState
    progress: JobProgress
    created_at: datetime
    source_file: Optional[str] = None
    result: Optional[JobResult] = None
    error: Optional[dict] = None
    statistics: dict[str, int] = {}

    model_config = ConfigDict(from_attributes=True)


# ---------------------------------------------------------------- app

app = FastAPI(
    title="MS Access Converter API",
    description="Convert MS Access applications to Spring Boot + React + PostgreSQL",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Paths
UPLOAD_DIR = Path("uploads")
OUTPUT_DIR = Path("outputs")
UPLOAD_DIR.mkdir(exist_ok=True)
OUTPUT_DIR.mkdir(exist_ok=True)


# ---------------------------------------------------------------- Database dependency

async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """Database session dependency."""
    async with get_session() as session:
        yield session


# ---------------------------------------------------------------- WebSocket manager

class ConnectionManager:
    """Manage WebSocket connections for progress updates."""

    def __init__(self):
        self.active_connections: dict[str, list[WebSocket]] = {}

    async def connect(self, websocket: WebSocket, job_id: str):
        await websocket.accept()
        if job_id not in self.active_connections:
            self.active_connections[job_id] = []
        self.active_connections[job_id].append(websocket)

    def disconnect(self, websocket: WebSocket, job_id: str):
        if job_id in self.active_connections:
            self.active_connections[job_id].remove(websocket)
            if not self.active_connections[job_id]:
                del self.active_connections[job_id]

    async def broadcast(self, job_id: str, message: dict):
        if job_id in self.active_connections:
            for connection in self.active_connections[job_id]:
                try:
                    await connection.send_json(message)
                except Exception:
                    pass


manager = ConnectionManager()


# ---------------------------------------------------------------- Conversion Pipeline

async def run_conversion_pipeline(job_id: str, db: AsyncSession):
    """Run the full conversion pipeline for a job using database repositories."""
    job_repo = JobRepository(db)
    extraction_repo = ExtractionRepository(db)
    ir_repo = IRRepository(db)
    graph_repo = DependencyGraphRepository(db)
    support_repo = SupportabilityRepository(db)
    build_log_repo = BuildLogRepository(db)

    try:
        job = await job_repo.get_simple(job_id)
        if not job:
            return

        job_dir = OUTPUT_DIR / job.id
        job_dir.mkdir(parents=True, exist_ok=True)

        # Helper to update job state and broadcast
        async def update_state(new_state: JobState, step: str = None):
            job.transition_to(new_state)
            await job_repo.update(job)
            await db.commit()
            await manager.broadcast(job.id, {"state": job.state, "step": step})

        def log_build(phase: str, step: str, status: str = "started", output: str = None, error: str = None):
            return build_log_repo.create(job.id, phase, step, status, output, error)

        async def update_build_log(log_id: str, status: str, output: str = None, error: str = None):
            await build_log_repo.update(log_id, status, output, error)
            await db.commit()

        # Step 1: Extract
        await update_state(JobState.EXTRACTING, "extracting")
        extract_log = log_build("extraction", "run_extraction")

        extract_dir = job_dir / ".extract"
        extraction = run_extraction(job.source_file, str(extract_dir))
        await extraction_repo.create(job.id, extraction)

        job.tables_count = len(extraction.get("tables", []))
        job.queries_count = len(extraction.get("queries", []))
        job.forms_count = len(extraction.get("forms", []))
        job.reports_count = len(extraction.get("reports", []))
        job.macros_count = len(extraction.get("macros", []))
        job.vba_modules_count = len(extraction.get("modules", []))
        job.extraction_path = str(extract_dir / "extraction.json")
        await update_build_log(extract_log.id, "completed", f"Extracted {job.tables_count} tables, {job.queries_count} queries")
        await update_state(JobState.EXTRACTING, "extracting")

        # Step 2: Build IR
        await update_state(JobState.ANALYZING, "building_ir")
        ir_log = log_build("ir", "build_ir")

        app_ir = build_ir(job.extraction_path)
        app_ir.application_name = job.project_name
        job.ir_path = str(job_dir / "application_ir.json")

        ir_data = app_ir.model_dump()
        await ir_repo.create(job.id, ir_data, app_ir.application_name)

        Path(job.ir_path).write_text(json.dumps(ir_data, indent=2, default=str))
        await update_build_log(ir_log.id, "completed", f"IR built: {app_ir.application_name}")
        await db.commit()

        # Step 3: Build dependency graph
        await update_state(JobState.DEPENDENCIES_DISCOVERED, "building_graph")
        graph_log = log_build("graph", "build_dependency_graph")

        graph = build_dependency_graph(app_ir)
        await graph_repo.create(
            job.id,
            nodes=[{"id": n.id, "type": n.type, "name": n.name} for n in graph.nodes.values()],
            edges=[{"from": e.from_node, "to": e.to_node, "type": e.edge_type} for e in graph.edges],
            cycles=[[n.id for n in c] for c in graph.find_cycles()],
            orphans=[n.id for n in graph.find_orphans()],
        )
        await update_build_log(graph_log.id, "completed", f"Graph: {len(graph.nodes)} nodes, {len(graph.find_cycles())} cycles")
        await db.commit()

        # Step 4: Analyze supportability
        await update_state(JobState.SUPPORTABILITY_ANALYZED, "analyzing_supportability")
        support_log = log_build("supportability", "analyze_supportability")

        support_results = analyze_supportability(app_ir)
        engine = SupportabilityEngine(app_ir)
        engine.results = support_results
        coverage = engine.calculate_coverage()

        await support_repo.create_batch(job.id, [
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
        ])
        await update_build_log(support_log.id, "completed", f"Analyzed {len(support_results)} objects")
        await db.commit()

        # Step 5: Generate database
        await update_state(JobState.GENERATING_DATABASE, "generating_database")
        db_log = log_build("database", "generate_schema")

        db_dir = job_dir / "database"
        db_dir.mkdir(exist_ok=True)
        app_ir._raw_data = extraction
        schema_path = db_dir / "schema.sql"
        generate_schema(app_ir, schema_path)
        await update_build_log(db_log.id, "completed", f"Schema: {schema_path}")
        await db.commit()

        # Step 6: Generate backend
        await update_state(JobState.GENERATING_BACKEND, "generating_backend")
        backend_log = log_build("backend", "generate_spring_boot")

        backend_dir = job_dir / "backend"
        spring_gen = generate_spring_boot(
            app_ir, backend_dir,
            base_package=job.base_package,
            app_name=job.project_name,
        )
        await update_build_log(backend_log.id, "completed", f"Generated {len(spring_gen)} backend files")
        await db.commit()

        # Step 7: Generate frontend
        await update_state(JobState.GENERATING_FRONTEND, "generating_frontend")
        frontend_log = log_build("frontend", "generate_react")

        frontend_dir = job_dir / "frontend"
        react_gen = generate_react(app_ir, frontend_dir)
        await update_build_log(frontend_log.id, "completed", f"Generated {len(react_gen)} frontend files")
        await db.commit()

        # Step 8: Generate migration report
        report_dir = job_dir / "migration-report"
        report_dir.mkdir(exist_ok=True)

        report = {
            "source": {
                "file": job.source_file,
                "application": app_ir.application_name,
            },
            "statistics": {
                "tables": job.tables_count,
                "queries": job.queries_count,
                "forms": job.forms_count,
                "reports": job.reports_count,
                "macros": job.macros_count,
                "vba_modules": job.vba_modules_count,
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
            "warnings": app_ir.warnings,
            "generated": {
                "backend_files": len(spring_gen),
                "frontend_files": len(react_gen),
                "database_file": str(schema_path),
            },
            "config": {
                "project_name": job.project_name,
                "base_package": job.base_package,
                "java_version": job.java_version,
                "spring_boot_version": job.spring_boot_version,
                "react_version": job.react_version,
                "authentication_strategy": job.authentication_strategy,
                "report_strategy": job.report_strategy,
                "migration_strategy": job.migration_strategy,
            },
        }

        report_path = report_dir / "migration-report.json"
        report_path.write_text(json.dumps(report, indent=2))

        # Generate HTML report
        html_report = generate_html_report(report)
        html_path = report_dir / "migration-report.html"
        html_path.write_text(html_report)
        await db.commit()

        # Step 9: Build validation
        await update_state(JobState.BUILDING, "validating_build")
        build_log = log_build("build", "validate_project")

        try:
            validation_result = validate_project(str(job_dir))
            await update_build_log(build_log.id, "completed", f"Build validation: {validation_result['status']}")

            build_success = validation_result["status"] == "success"
            job.build_validation = validation_result

            # Self-healing build repair if validation failed (spec section 35)
            if not build_success:
                await self_heal_build(job_id, job_dir, validation_result, db)
        except Exception as e:
            await update_build_log(build_log.id, "failed", error=str(e))
            build_success = False
            job.build_validation = {"status": "error", "error": str(e)}

        # Step 10: Complete
        await update_state(JobState.COMPLETED, "completed")
        job.output_path = str(job_dir)
        job.result = JobResult(
            output_path=str(job_dir),
            coverage=coverage,
            files_generated=len(spring_gen) + len(react_gen) + 1,
            build_success=build_success,
            test_success=False,
            warnings=app_ir.warnings,
            unsupported_objects=[
                r.object for r in support_results
                if r.status.value == "UNSUPPORTED"
            ],
        )
        await job_repo.update(job)
        await db.commit()

        await manager.broadcast(job.id, {
            "state": job.state.value,
            "step": "completed",
            "result": job.result.model_dump(),
        })

    except Exception as e:
        import traceback
        job = await job_repo.get_simple(job_id)
        if job:
            job.fail("CONVERSION_ERROR", str(e), {"traceback": traceback.format_exc()})
            await job_repo.update(job)
            await db.commit()
        await manager.broadcast(job_id, {
            "state": JobState.FAILED.value,
            "error": str(e),
        })


_COMPONENT_TO_BUILD_PHASE = {
    "backend": BuildPhase.MAVEN,
    "maven": BuildPhase.MAVEN,
    "frontend": BuildPhase.NPM,
    "npm": BuildPhase.NPM,
    "database": BuildPhase.DATABASE,
    "test": BuildPhase.TEST,
}


async def self_heal_build(job_id: str, job_dir: Path, validation_result: dict, db: AsyncSession):
    """Self-healing build repair - spec section 35.

    Attempts deterministic fixes for known build failures.
    If deterministic fixes don't work, LLM-based repair would be triggered.
    """
    from converter.app.database import BuildLogRepository, JobRepository

    build_log_repo = BuildLogRepository(db)

    # Find failed phases from validation result
    failed_phases = []
    for phase_name, phase_result in validation_result.get("results", {}).items():
        if phase_result.get("status") == "failed":
            for error in phase_result.get("errors", []):
                failed_phases.append({
                    "phase": phase_name,
                    "category": error.get("category"),
                    "message": error.get("message"),
                })

    if not failed_phases:
        return

    # Log repair attempt
    repair_log = await build_log_repo.create(job_id, "repair", "self_heal_start", "started",
                                             output=f"Attempting self-heal for {len(failed_phases)} failures")

    try:
        # Create pipeline validator and repair
        validator = PipelineBuildValidator(job_dir, job_id, build_log_repo, db)
        repair = BuildRepair(job_dir, job_id, build_log_repo, db)

        max_repair_attempts = 3
        repair_results = []

        for attempt in range(max_repair_attempts):
            attempt_log = await build_log_repo.create(job_id, "repair", f"attempt_{attempt + 1}", "started")

            for failure in failed_phases:
                # Map the validator's component name onto the build phase.
                # The validator reports components ("backend", "frontend",
                # "database") while BuildPhase is tool-oriented ("maven",
                # "npm", "database").  The previous `.upper()` lookup never
                # matched any enum value, so every failure — including
                # frontend ones — silently fell back to MAVEN and was
                # routed to the backend repair path.
                phase = _COMPONENT_TO_BUILD_PHASE.get(
                    failure["phase"].lower(), BuildPhase.MAVEN
                )
                step = failure["phase"]

                # Attempt repair
                repairs = await repair.attempt_repair(phase, step, failure["message"], "")
                repair_results.extend(repairs)

            # Re-validate after repair attempt
            revalidation = validate_project(str(job_dir))
            if revalidation["status"] == "success":
                await build_log_repo.update(attempt_log.id, "completed", output=f"Repair successful on attempt {attempt + 1}")
                await db.commit()

                # Update validation result
                job_repo = JobRepository(db)
                job = await job_repo.get_simple(job_id)
                if job:
                    job.build_validation = revalidation
                    await job_repo.update(job)
                    await db.commit()

                await build_log_repo.update(repair_log.id, "completed", output=f"Self-heal successful after {attempt + 1} attempts")
                return

            await build_log_repo.update(attempt_log.id, "failed", output=f"Repair attempt {attempt + 1} failed, revalidation still failing")

        await build_log_repo.update(repair_log.id, "completed", output=f"Self-heal exhausted {max_repair_attempts} attempts, manual review required")

    except Exception as e:
        await build_log_repo.update(repair_log.id, "failed", error=str(e))


def generate_html_report(report: dict) -> str:
    """Generate HTML migration report."""
    cov = report.get("coverage", {})
    stats = report.get("statistics", {})
    support = report.get("supportability", [])
    warnings = report.get("warnings", [])

    supported = sum(1 for s in support if s["status"] == "SUPPORTED")
    review = sum(1 for s in support if s["status"] == "SUPPORTED_WITH_REVIEW")
    unsupported = sum(1 for s in support if s["status"] == "UNSUPPORTED")

    rows = ""
    for s in support:
        status_class = s["status"].lower().replace("_", "-")
        rows += f"""
        <tr>
            <td>{s['object']}</td>
            <td>{s['category']}</td>
            <td><span class="badge {status_class}">{s['status']}</span></td>
            <td><span class="badge risk-{s['risk'].lower()}">{s['risk']}</span></td>
            <td>{s.get('confidence', 0):.0%}</td>
            <td>{s.get('reason', '')}</td>
        </tr>"""

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Migration Report - {report['source']['application']}</title>
    <style>
        body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; margin: 0; padding: 20px; background: #f5f5f5; }}
        .container {{ max-width: 1200px; margin: 0 auto; background: white; padding: 30px; border-radius: 8px; box-shadow: 0 2px 10px rgba(0,0,0,0.1); }}
        h1 {{ color: #333; border-bottom: 2px solid #007bff; padding-bottom: 10px; }}
        h2 {{ color: #555; margin-top: 30px; }}
        .stats {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 20px; margin: 20px 0; }}
        .stat-card {{ background: #f8f9fa; padding: 20px; border-radius: 8px; text-align: center; }}
        .stat-value {{ font-size: 2rem; font-weight: bold; color: #007bff; }}
        .stat-label {{ color: #666; margin-top: 5px; }}
        .coverage {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(150px, 1fr)); gap: 15px; margin: 20px 0; }}
        .cov-card {{ padding: 15px; border-radius: 8px; text-align: center; }}
        .cov-overall {{ background: #e3f2fd; }} .cov-supported {{ background: #e8f5e9; }} .cov-review {{ background: #fff3e0; }} .cov-unsupported {{ background: #ffebee; }}
        .cov-value {{ font-size: 1.5rem; font-weight: bold; }}
        table {{ width: 100%; border-collapse: collapse; margin-top: 20px; }}
        th, td {{ padding: 12px; text-align: left; border-bottom: 1px solid #eee; }}
        th {{ background: #f8f9fa; font-weight: 600; }}
        tr:hover {{ background: #f5f5f5; }}
        .badge {{ padding: 4px 8px; border-radius: 4px; font-size: 0.75rem; font-weight: 600; text-transform: uppercase; }}
        .badge-supported {{ background: #c8e6c9; color: #2e7d32; }}
        .badge-supported_with_review {{ background: #ffe0b2; color: #e65100; }}
        .badge-unsupported {{ background: #ffcdd2; color: #c62828; }}
        .risk-low {{ background: #c8e6c9; color: #2e7d32; }}
        .risk-medium {{ background: #ffe0b2; color: #e65100; }}
        .risk-high {{ background: #ffcdd2; color: #c62828; }}
        .risk-critical {{ background: #f8bbd0; color: #ad1457; }}
        .warnings {{ background: #fff3e0; padding: 15px; border-radius: 8px; margin-top: 20px; }}
        .warning-item {{ margin: 5px 0; }}
    </style>
</head>
<body>
    <div class="container">
        <h1>📊 Migration Report: {report['source']['application']}</h1>
        <p><strong>Source:</strong> {report['source']['file']}</p>
        <p><strong>Generated:</strong> {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')} UTC</p>

        <h2>📈 Statistics</h2>
        <div class="stats">
            <div class="stat-card"><div class="stat-value">{stats.get('tables', 0)}</div><div class="stat-label">Tables</div></div>
            <div class="stat-card"><div class="stat-value">{stats.get('queries', 0)}</div><div class="stat-label">Queries</div></div>
            <div class="stat-card"><div class="stat-value">{stats.get('forms', 0)}</div><div class="stat-label">Forms</div></div>
            <div class="stat-card"><div class="stat-value">{stats.get('reports', 0)}</div><div class="stat-label">Reports</div></div>
            <div class="stat-card"><div class="stat-value">{stats.get('macros', 0)}</div><div class="stat-label">Macros</div></div>
            <div class="stat-card"><div class="stat-value">{stats.get('vba_modules', 0)}</div><div class="stat-label">VBA Modules</div></div>
        </div>

        <h2>🎯 Coverage</h2>
        <div class="coverage">
            <div class="cov-card cov-overall"><div class="cov-value">{cov.get('overall', 0):.1f}%</div><div>Overall</div></div>
            <div class="cov-card cov-supported"><div class="cov-value">{cov.get('fully_supported_pct', 0):.1f}%</div><div>Fully Supported</div></div>
            <div class="cov-card cov-review"><div class="cov-value">{cov.get('supported_with_review_pct', 0):.1f}%</div><div>Needs Review</div></div>
            <div class="cov-card cov-unsupported"><div class="cov-value">{cov.get('unsupported_pct', 0):.1f}%</div><div>Unsupported</div></div>
        </div>

        <h2>📋 Object Supportability ({len(support)} objects)</h2>
        <div style="overflow-x: auto;">
        <table>
            <thead>
                <tr><th>Object</th><th>Category</th><th>Status</th><th>Risk</th><th>Confidence</th><th>Reason</th></tr>
            </thead>
            <tbody>
                {rows}
            </tbody>
        </table>
        </div>

        <h2>⚠️ Warnings ({len(warnings)})</h2>
        <div class="warnings">
            {''.join(f'<div class="warning-item">• {w}</div>' for w in warnings) if warnings else '<p>No warnings.</p>'}
        </div>

        <h2>⚙️ Configuration</h2>
        <pre style="background: #f8f9fa; padding: 15px; border-radius: 4px; overflow-x: auto;">{json.dumps(report.get('config', {}), indent=2)}</pre>
    </div>
</body>
</html>"""


# ---------------------------------------------------------------- Endpoints

@app.get("/")
async def root():
    """Root endpoint."""
    return {
        "name": "MS Access Converter API",
        "version": "1.0.0",
        "status": "running",
    }


@app.post("/api/jobs", response_model=JobResponse)
async def create_job(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    project_name: str = "ConvertedApplication",
    base_package: str = "com.generated.app",
    db: AsyncSession = Depends(get_db),
):
    """Create a new conversion job."""
    if not file.filename:
        raise HTTPException(status_code=400, detail="No file provided")

    if not file.filename.lower().endswith(('.accdb', '.mdb')):
        raise HTTPException(status_code=400, detail="File must be .accdb or .mdb")

    job_id = str(uuid.uuid4())[:8]

    # Save uploaded file
    upload_path = UPLOAD_DIR / f"{job_id}_{file.filename}"
    with open(upload_path, "wb") as f:
        shutil.copyfileobj(file.file, f)

    # Create job in database
    job_repo = JobRepository(db)
    job = JobModel(
        id=job_id,
        source_file=str(upload_path),
        source_file_size=upload_path.stat().st_size,
        project_name=project_name,
        base_package=base_package,
    )
    job.transition_to(JobState.UPLOADED)
    await job_repo.create(job)
    await db.commit()

    # Start conversion in background
    background_tasks.add_task(run_conversion_pipeline, job_id, db)

    return JobResponse(
        id=job.id,
        state=job.state,
        progress=job.progress,
        created_at=job.created_at,
        source_file=file.filename,
        statistics={},
    )


@app.get("/api/jobs", response_model=list[JobResponse])
async def list_jobs(limit: int = Query(50, le=100), db: AsyncSession = Depends(get_db)):
    """List all jobs."""
    job_repo = JobRepository(db)
    jobs = await job_repo.list_all(limit)
    return [
        JobResponse(
            id=job.id,
            state=job.state,
            progress=JobProgress(**job.progress) if job.progress else JobProgress(),
            created_at=job.created_at,
            source_file=Path(job.source_file).name if job.source_file else None,
            result=JobResult(**job.result) if job.result else None,
            error=job.error,
            statistics={
                "tables": job.tables_count,
                "queries": job.queries_count,
                "forms": job.forms_count,
                "reports": job.reports_count,
                "macros": job.macros_count,
                "vba_modules": job.vba_modules_count,
            },
        )
        for job in jobs
    ]


@app.get("/api/jobs/{job_id}", response_model=JobResponse)
async def get_job(job_id: str, db: AsyncSession = Depends(get_db)):
    """Get job details."""
    job_repo = JobRepository(db)
    job = await job_repo.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    return JobResponse(
        id=job.id,
        state=job.state,
        progress=JobProgress(**job.progress) if job.progress else JobProgress(),
        created_at=job.created_at,
        source_file=Path(job.source_file).name if job.source_file else None,
        result=JobResult(**job.result) if job.result else None,
        error=job.error,
        statistics={
            "tables": job.tables_count,
            "queries": job.queries_count,
            "forms": job.forms_count,
            "reports": job.reports_count,
            "macros": job.macros_count,
            "vba_modules": job.vba_modules_count,
        },
    )


@app.websocket("/ws/jobs/{job_id}")
async def websocket_progress(websocket: WebSocket, job_id: str):
    """WebSocket endpoint for real-time progress updates."""
    await manager.connect(websocket, job_id)
    try:
        while True:
            # Use a new session for polling
            async with get_session() as session:
                job_repo = JobRepository(session)
                job = await job_repo.get_simple(job_id)
                if job:
                    await websocket.send_json({
                        "state": job.state.value,
                        "progress": job.progress,
                    })
                    if job.state in (JobState.COMPLETED, JobState.FAILED):
                        break
            await asyncio.sleep(1)
    except WebSocketDisconnect:
        manager.disconnect(websocket, job_id)


@app.get("/api/jobs/{job_id}/download")
async def download_result(job_id: str, db: AsyncSession = Depends(get_db)):
    """Download the generated project as a ZIP file."""
    job_repo = JobRepository(db)
    job = await job_repo.get_simple(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    if job.state != JobState.COMPLETED:
        raise HTTPException(status_code=400, detail="Job not completed")

    if not job.output_path:
        raise HTTPException(status_code=404, detail="Output not found")

    output_dir = Path(job.output_path)
    zip_path = output_dir.with_suffix(".zip")

    # Create ZIP file
    shutil.make_archive(str(output_dir), "zip", output_dir)

    return FileResponse(
        path=zip_path,
        filename=f"{job.project_name}.zip",
        media_type="application/zip",
    )


@app.get("/api/jobs/{job_id}/report")
async def get_report(job_id: str, db: AsyncSession = Depends(get_db)):
    """Get the migration report."""
    job_repo = JobRepository(db)
    job = await job_repo.get_simple(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    report_path = Path(job.output_path) / "migration-report" / "migration-report.json"
    if not report_path.exists():
        raise HTTPException(status_code=404, detail="Report not found")

    return JSONResponse(content=json.loads(report_path.read_text()))


@app.get("/api/jobs/{job_id}/report/html")
async def get_report_html(job_id: str, db: AsyncSession = Depends(get_db)):
    """Get the migration report as HTML."""
    job_repo = JobRepository(db)
    job = await job_repo.get_simple(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    report_path = Path(job.output_path) / "migration-report" / "migration-report.html"
    if not report_path.exists():
        raise HTTPException(status_code=404, detail="HTML report not found")

    return FileResponse(path=report_path, media_type="text/html")


@app.delete("/api/jobs/{job_id}")
async def delete_job(job_id: str, db: AsyncSession = Depends(get_db)):
    """Delete a job and its files."""
    job_repo = JobRepository(db)
    job = await job_repo.get_simple(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    # Clean up files
    if job.source_file:
        upload_path = Path(job.source_file)
        if upload_path.exists():
            upload_path.unlink()

    if job.output_path:
        output_dir = Path(job.output_path)
        if output_dir.exists():
            shutil.rmtree(output_dir)
        zip_path = output_dir.with_suffix(".zip")
        if zip_path.exists():
            zip_path.unlink()

    await job_repo.delete(job_id)
    await db.commit()
    return {"status": "deleted"}


@app.get("/api/versions")
async def get_versions():
    """Get supported technology versions."""
    return {
        "backend": {
            "framework": "Spring Boot",
            "versions": ["4.1.0"],
            "java_versions": [17, 21, 25],
        },
        "frontend": {
            "framework": "React",
            "versions": ["19.2.8"],
            "node_versions": [20, 22, 24],
        },
        "database": {
            "engine": "PostgreSQL",
            "versions": ["16", "17", "18"],
        },
    }


# ---------------------------------------------------------------- LLM Orchestration Endpoints

class LLMRequest(BaseModel):
    """LLM generation request."""
    prompt: str
    system_prompt: Optional[str] = None
    json_mode: bool = False
    model: Optional[str] = None
    provider: str = "ollama"
    temperature: float = 0.1
    max_tokens: int = 4096


class LLMStructuredRequest(BaseModel):
    """LLM structured generation request."""
    prompt: str
    response_schema: dict
    system_prompt: Optional[str] = None
    model: Optional[str] = None
    provider: str = "ollama"
    temperature: float = 0.1
    max_tokens: int = 4096


@app.post("/api/llm/generate")
async def llm_generate(request: LLMRequest, db: AsyncSession = Depends(get_db)):
    """Generate text using LLM."""
    from converter.app.llm.provider import (
        LLMProviderFactory, LLMConfig, LLMProviderType
    )

    provider_type = LLMProviderType.OLLAMA if request.provider == "ollama" else LLMProviderType.OPENROUTER
    config = LLMConfig(
        provider_type=provider_type,
        model=request.model or "llama3.1:8b",
        temperature=request.temperature,
        max_tokens=request.max_tokens,
    )
    provider = LLMProviderFactory.create(config)
    response = provider.generate(
        request.prompt,
        system_prompt=request.system_prompt,
        json_mode=request.json_mode,
    )
    return {
        "content": response.content,
        "model": response.model,
        "tokens_used": response.tokens_used,
        "cached": response.cached,
    }


@app.post("/api/llm/generate_structured")
async def llm_generate_structured(request: LLMStructuredRequest, db: AsyncSession = Depends(get_db)):
    """Generate structured JSON using LLM."""
    from converter.app.llm.provider import (
        LLMProviderFactory, LLMConfig, LLMProviderType
    )

    provider_type = LLMProviderType.OLLAMA if request.provider == "ollama" else LLMProviderType.OPENROUTER
    config = LLMConfig(
        provider_type=provider_type,
        model=request.model or "llama3.1:8b",
        temperature=request.temperature,
        max_tokens=request.max_tokens,
    )
    provider = LLMProviderFactory.create(config)
    result = provider.generate_structured(
        request.prompt,
        request.response_schema,
        system_prompt=request.system_prompt,
    )
    return result


@app.get("/api/llm/cache")
async def llm_cache_stats(db: AsyncSession = Depends(get_db)):
    """Get LLM cache statistics."""
    from sqlalchemy import select, func
    from converter.app.database import LLMCacheModel

    result = await db.execute(
        select(
            func.count(LLMCacheModel.id),
            func.sum(LLMCacheModel.tokens_used),
            func.sum(LLMCacheModel.access_count),
        )
    )
    count, total_tokens, total_access = result.one()

    return {
        "entries": count or 0,
        "total_tokens": total_tokens or 0,
        "total_accesses": total_access or 0,
    }


@app.delete("/api/llm/cache")
async def llm_clear_cache(db: AsyncSession = Depends(get_db)):
    """Clear LLM cache."""
    from sqlalchemy import delete
    from converter.app.database import LLMCacheModel

    await db.execute(delete(LLMCacheModel))
    await db.commit()
    return {"status": "cleared"}


# ---------------------------------------------------------------- External Dependency Endpoints

@app.get("/api/jobs/{job_id}/dependencies")
async def get_external_dependencies(job_id: str, db: AsyncSession = Depends(get_db)):
    """Get external dependencies for a job."""
    ext_repo = ExternalDependencyRepository(db)
    deps = await ext_repo.get_by_job(job_id)
    return [
        {
            "id": str(d.id),
            "type": d.dependency_type,
            "connection_info": d.connection_info,
            "location": d.location,
            "source_table": d.source_table,
            "target_table": d.target_table,
            "migration_strategy": d.migration_strategy,
            "support_status": d.support_status,
            "risk_level": d.risk_level,
            "has_credentials": d.has_credentials,
            "details": d.details,
        }
        for d in deps
    ]


# ---------------------------------------------------------------- Build Logs Endpoints

@app.get("/api/jobs/{job_id}/build-logs")
async def get_build_logs(job_id: str, db: AsyncSession = Depends(get_db)):
    """Get build logs for a job."""
    build_log_repo = BuildLogRepository(db)
    logs = await build_log_repo.get_by_job(job_id)
    return [
        {
            "id": str(log.id),
            "phase": log.phase,
            "step": log.step,
            "status": log.status,
            "output": log.output,
            "error": log.error,
            "started_at": log.started_at.isoformat() if log.started_at else None,
            "completed_at": log.completed_at.isoformat() if log.completed_at else None,
        }
        for log in logs
    ]


# ---------------------------------------------------------------- main

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)