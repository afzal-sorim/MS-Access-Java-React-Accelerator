"""Database layer with SQLAlchemy async and pgvector support.

Spec section 63: Use PostgreSQL with pgvector for migration jobs, Access IR,
object metadata, dependency graph, LLM cache, embeddings, build logs, reports.

The layer is portable: it runs on PostgreSQL (set CONVERTER_DATABASE_URL,
e.g. postgresql+asyncpg://...) and falls back to an embedded SQLite database
(sqlite+aiosqlite) so the converter works out of the box without an external
server. JSON columns use a JSONB variant on PostgreSQL and plain JSON on
SQLite; IDs are 36-char strings on both.
"""
from __future__ import annotations

import json
import os
from contextlib import asynccontextmanager
from datetime import datetime
from typing import Optional, List, Dict, Any
from uuid import uuid4

from sqlalchemy import (
    Column, String, Text, DateTime, Integer, Float, Boolean,
    ForeignKey, Index, select, func, delete, update, JSON
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.ext.asyncio import (
    create_async_engine, AsyncSession, async_sessionmaker, AsyncEngine
)
from sqlalchemy.orm import declarative_base, relationship, selectinload

from .jobs.models import JobState, JobError, JobProgress, JobResult

# Base for declarative models
Base = declarative_base()

def _json_serializable(obj):
    """Custom JSON serializer for types not supported by standard json module."""
    from decimal import Decimal
    from datetime import datetime, date
    if isinstance(obj, Decimal):
        return float(obj)
    if isinstance(obj, (datetime, date)):
        return obj.isoformat()
    raise TypeError(f"Object of type {obj.__class__.__name__} is not JSON serializable")

def _json_dumps(obj, **kwargs):
    return json.dumps(obj, default=_json_serializable, **kwargs)

# Portable column types: JSONB on PostgreSQL, JSON elsewhere.
JSONType = JSON().with_variant(JSONB, "postgresql")
# Primary/foreign keys as 36-char UUID strings (portable across backends).
KeyColumn = String(36)

DEFAULT_DATABASE_URL = "sqlite+aiosqlite:///./converter_jobs_v2.db"


class JobModel(Base):
    """SQLAlchemy model for migration jobs."""
    __tablename__ = "migration_jobs"

    id = Column(KeyColumn, primary_key=True, default=lambda: str(uuid4()))
    state = Column(String(50), nullable=False, default=JobState.CREATED.value)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Input
    source_file = Column(String(500), nullable=True)
    source_file_size = Column(Integer, nullable=True)
    # How the source was acquired: UPLOAD (multipart) or LOCAL_DIRECT (picked
    # from the local machine / running Access). For LOCAL_DIRECT, source_file
    # points at the staged copy the extractor consumed, so source_origin keeps
    # the user's real path for the migration report.
    source_mode = Column(String(20), nullable=True, default="UPLOAD")
    source_origin = Column(String(500), nullable=True)

    # Configuration
    project_name = Column(String(200), nullable=False, default="ConvertedApplication")
    base_package = Column(String(200), nullable=False, default="com.generated.app")
    java_version = Column(Integer, nullable=False, default=25)
    spring_boot_version = Column(String(50), nullable=False, default="4.1.0")
    react_version = Column(String(50), nullable=False, default="19.2.8")
    node_version = Column(Integer, nullable=False, default=24)
    postgres_version = Column(String(50), nullable=False, default="18")

    # Progress (stored as JSONB)
    progress = Column(JSONType, nullable=False, default={
        "current_step": "",
        "total_steps": 25,
        "completed_steps": 0,
        "percentage": 0.0,
        "started_at": None,
        "estimated_remaining_seconds": None,
    })

    # Extracted data paths
    extraction_path = Column(String(500), nullable=True)
    ir_path = Column(String(500), nullable=True)
    output_path = Column(String(500), nullable=True)

    # Results (stored as JSONB)
    result = Column(JSONType, nullable=True)
    error = Column(JSONType, nullable=True)
    build_validation = Column(JSONType, nullable=True)

    # Statistics
    tables_count = Column(Integer, nullable=False, default=0)
    queries_count = Column(Integer, nullable=False, default=0)
    forms_count = Column(Integer, nullable=False, default=0)
    reports_count = Column(Integer, nullable=False, default=0)
    macros_count = Column(Integer, nullable=False, default=0)
    vba_modules_count = Column(Integer, nullable=False, default=0)

    # Relationships
    extraction_data = relationship("ExtractionDataModel", back_populates="job", uselist=False, cascade="all, delete-orphan")
    ir_data = relationship("IRDataModel", back_populates="job", uselist=False, cascade="all, delete-orphan")
    dependency_graph = relationship("DependencyGraphModel", back_populates="job", uselist=False, cascade="all, delete-orphan")
    supportability_results = relationship("SupportabilityResultModel", back_populates="job", cascade="all, delete-orphan")
    build_logs = relationship("BuildLogModel", back_populates="job", cascade="all, delete-orphan")
    llm_cache_entries = relationship("LLMCacheModel", back_populates="job", cascade="all, delete-orphan")

    # Indexes
    __table_args__ = (
        Index("ix_job_state", "state"),
        Index("ix_job_created_at", "created_at"),
    )

    def transition_to(self, new_state: "JobState") -> None:
        """Transition to a new state, updating progress metadata."""
        self.state = new_state.value
        self.updated_at = datetime.utcnow()
        # progress is a JSON dict column — copy, mutate, reassign so SQLAlchemy tracks the change
        progress = dict(self.progress or {})
        progress["completed_steps"] = progress.get("completed_steps", 0) + 1
        progress["current_step"] = new_state.value
        total_steps = progress.get("total_steps", 25) or 25
        progress["percentage"] = round((progress["completed_steps"] / total_steps) * 100, 1)
        self.progress = progress


class ExtractionDataModel(Base):
    """Extracted Access database data."""
    __tablename__ = "extraction_data"

    id = Column(KeyColumn, primary_key=True, default=lambda: str(uuid4()))
    job_id = Column(KeyColumn, ForeignKey("migration_jobs.id", ondelete="CASCADE"), unique=True, nullable=False)
    data = Column(JSONType, nullable=False)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)

    job = relationship("JobModel", back_populates="extraction_data")


class IRDataModel(Base):
    """Access Intermediate Representation."""
    __tablename__ = "ir_data"

    id = Column(KeyColumn, primary_key=True, default=lambda: str(uuid4()))
    job_id = Column(KeyColumn, ForeignKey("migration_jobs.id", ondelete="CASCADE"), unique=True, nullable=False)
    data = Column(JSONType, nullable=False)
    application_name = Column(String(200), nullable=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)

    job = relationship("JobModel", back_populates="ir_data")


class DependencyGraphModel(Base):
    """Dependency graph for Access objects."""
    __tablename__ = "dependency_graphs"

    id = Column(KeyColumn, primary_key=True, default=lambda: str(uuid4()))
    job_id = Column(KeyColumn, ForeignKey("migration_jobs.id", ondelete="CASCADE"), unique=True, nullable=False)
    nodes = Column(JSONType, nullable=False, default=[])
    edges = Column(JSONType, nullable=False, default=[])
    cycles = Column(JSONType, nullable=False, default=[])
    orphans = Column(JSONType, nullable=False, default=[])
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)

    job = relationship("JobModel", back_populates="dependency_graph")


class SupportabilityResultModel(Base):
    """Supportability analysis results for each Access object."""
    __tablename__ = "supportability_results"

    id = Column(KeyColumn, primary_key=True, default=lambda: str(uuid4()))
    job_id = Column(KeyColumn, ForeignKey("migration_jobs.id", ondelete="CASCADE"), nullable=False)
    object_name = Column(String(500), nullable=False)
    category = Column(String(100), nullable=False)
    status = Column(String(50), nullable=False)
    complexity = Column(String(50), nullable=True)
    risk = Column(String(50), nullable=True)
    conversion = Column(String(100), nullable=True)
    confidence = Column(Float, nullable=True)
    reason = Column(Text, nullable=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)

    job = relationship("JobModel", back_populates="supportability_results")

    __table_args__ = (
        Index("ix_supportability_job_object", "job_id", "object_name"),
        Index("ix_supportability_status", "status"),
    )


class BuildLogModel(Base):
    """Build logs for Maven, npm, database operations."""
    __tablename__ = "build_logs"

    id = Column(KeyColumn, primary_key=True, default=lambda: str(uuid4()))
    job_id = Column(KeyColumn, ForeignKey("migration_jobs.id", ondelete="CASCADE"), nullable=False)
    phase = Column(String(100), nullable=False)  # maven, npm, database, test, repair
    step = Column(String(100), nullable=False)
    status = Column(String(50), nullable=False)  # started, completed, failed
    output = Column(Text, nullable=True)
    error = Column(Text, nullable=True)
    started_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    completed_at = Column(DateTime, nullable=True)

    job = relationship("JobModel", back_populates="build_logs")

    __table_args__ = (
        Index("ix_build_logs_job_phase", "job_id", "phase"),
    )


class LLMCacheModel(Base):
    """LLM response cache with embeddings support."""
    __tablename__ = "llm_cache"

    id = Column(KeyColumn, primary_key=True, default=lambda: str(uuid4()))
    job_id = Column(KeyColumn, ForeignKey("migration_jobs.id", ondelete="CASCADE"), nullable=True)
    cache_key = Column(String(64), nullable=False, unique=True)  # SHA256 hash
    prompt_hash = Column(String(64), nullable=False)
    system_prompt_hash = Column(String(64), nullable=True)
    response = Column(JSONType, nullable=False)
    model = Column(String(100), nullable=False)
    tokens_used = Column(Integer, nullable=True)
    provider_type = Column(String(50), nullable=False)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    access_count = Column(Integer, nullable=False, default=1)
    last_accessed = Column(DateTime, nullable=False, default=datetime.utcnow)

    job = relationship("JobModel", back_populates="llm_cache_entries")

    __table_args__ = (
        Index("ix_llm_cache_key", "cache_key"),
        Index("ix_llm_cache_prompt_hash", "prompt_hash"),
    )


class ExternalDependencyModel(Base):
    """External dependencies discovered during extraction."""
    __tablename__ = "external_dependencies"

    id = Column(KeyColumn, primary_key=True, default=lambda: str(uuid4()))
    job_id = Column(KeyColumn, ForeignKey("migration_jobs.id", ondelete="CASCADE"), nullable=False)
    dependency_type = Column(String(100), nullable=False)  # access_backend, sql_server, mysql, postgresql, odbc, excel, csv, etc.
    connection_info = Column(JSONType, nullable=False)  # connection string, server, database, credentials presence
    location = Column(String(500), nullable=True)
    source_table = Column(String(200), nullable=True)
    target_table = Column(String(200), nullable=True)
    migration_strategy = Column(String(100), nullable=True)  # migrate, link, manual, skip
    support_status = Column(String(50), nullable=False)  # supported, unsupported, review_needed
    risk_level = Column(String(50), nullable=False)  # low, medium, high, critical
    has_credentials = Column(Boolean, nullable=False, default=False)
    details = Column(Text, nullable=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)

    __table_args__ = (
        Index("ix_ext_dep_job_type", "job_id", "dependency_type"),
    )


# Database engine and session management
_engine: Optional[AsyncEngine] = None
_session_factory: Optional[async_sessionmaker[AsyncSession]] = None
_init_lock: Optional["asyncio.Lock"] = None


async def init_database(database_url: Optional[str] = None) -> None:
    """Initialize database engine and create tables.

    URL resolution order: explicit argument, CONVERTER_DATABASE_URL env var,
    embedded SQLite fallback. PostgreSQL still gets pooling; SQLite does not
    support pool_size arguments.
    """
    global _engine, _session_factory, _init_lock
    import asyncio

    if _init_lock is None:
        _init_lock = asyncio.Lock()
    async with _init_lock:
        if _session_factory is not None:
            return

        url = database_url or os.environ.get("CONVERTER_DATABASE_URL") or DEFAULT_DATABASE_URL
        engine_kwargs: Dict[str, Any] = {
            "echo": False,
            "pool_pre_ping": True,
            "json_serializer": _json_dumps
        }
        if url.startswith("postgresql"):
            engine_kwargs.update(pool_size=10, max_overflow=20)
        elif url.startswith("sqlite"):
            # Default SQLite (journal_mode=DELETE) takes an exclusive lock on
            # every write and raises "database is locked" immediately if a
            # second connection tries to write at the same time - which
            # happens routinely here (pipeline commits + 1s WS polling loop +
            # any duplicate request). connect_args timeout makes aiosqlite
            # retry/wait instead of failing instantly; WAL mode (set below)
            # lets reads proceed concurrently with a writer so contention is
            # rare in the first place.
            engine_kwargs["connect_args"] = {"timeout": 30}

        _engine = create_async_engine(url, **engine_kwargs)

        if url.startswith("sqlite"):
            from sqlalchemy import event

            @event.listens_for(_engine.sync_engine, "connect")
            def _set_sqlite_pragma(dbapi_connection, connection_record):
                cursor = dbapi_connection.cursor()
                cursor.execute("PRAGMA journal_mode=WAL")
                cursor.execute("PRAGMA synchronous=NORMAL")
                cursor.execute("PRAGMA busy_timeout=30000")
                cursor.close()

        _session_factory = async_sessionmaker(
            _engine,
            class_=AsyncSession,
            expire_on_commit=False,
        )

        # Create tables
        async with _engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
            await conn.run_sync(_apply_additive_migrations)


# Columns added after the first release. create_all() only ever CREATEs — it
# never ALTERs an existing table — so a database created by an earlier version
# is missing these and every query against JobModel would fail. Each entry is
# (table, column, DDL type) and must be nullable or carry a default so it can
# be added to a populated table.
_ADDITIVE_COLUMNS: list[tuple[str, str, str]] = [
    ("migration_jobs", "source_mode", "VARCHAR(20)"),
    ("migration_jobs", "source_origin", "VARCHAR(500)"),
]


def _apply_additive_migrations(connection) -> None:
    """Add missing nullable columns to existing tables (idempotent).

    Runs on every startup inside the same transaction as create_all. Uses the
    SQLAlchemy inspector so it works on both SQLite and PostgreSQL.
    """
    from sqlalchemy import inspect, text

    inspector = inspect(connection)
    existing_tables = set(inspector.get_table_names())

    for table, column, ddl_type in _ADDITIVE_COLUMNS:
        if table not in existing_tables:
            continue  # create_all just made it with the column present
        columns = {col["name"] for col in inspector.get_columns(table)}
        if column in columns:
            continue
        connection.execute(
            text(f"ALTER TABLE {table} ADD COLUMN {column} {ddl_type}"))


from contextlib import asynccontextmanager


@asynccontextmanager
async def get_session() -> AsyncSession:
    """Get a database session as async context manager."""
    if _session_factory is None:
        await init_database()
    async with _session_factory() as session:
        yield session


async def close_database() -> None:
    """Close database connections."""
    global _engine
    if _engine:
        await _engine.dispose()
        _engine = None


# Repository classes for data access

class JobRepository:
    """Repository for migration job operations."""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def create(self, job: JobModel) -> JobModel:
        self.session.add(job)
        await self.session.flush()
        return job

    async def get(self, job_id: str) -> Optional[JobModel]:
        result = await self.session.execute(
            select(JobModel)
            .options(
                selectinload(JobModel.extraction_data),
                selectinload(JobModel.ir_data),
                selectinload(JobModel.dependency_graph),
                selectinload(JobModel.supportability_results),
                selectinload(JobModel.build_logs),
                selectinload(JobModel.llm_cache_entries),
            )
            .where(JobModel.id == job_id)
        )
        return result.scalar_one_or_none()

    async def get_simple(self, job_id: str) -> Optional[JobModel]:
        result = await self.session.execute(
            select(JobModel).where(JobModel.id == job_id)
        )
        return result.scalar_one_or_none()

    async def update(self, job: JobModel) -> JobModel:
        job.updated_at = datetime.utcnow()
        await self.session.flush()
        return job

    async def delete(self, job_id: str) -> bool:
        result = await self.session.execute(
            delete(JobModel).where(JobModel.id == job_id)
        )
        return result.rowcount > 0

    async def list_all(self, limit: int = 50, offset: int = 0) -> List[JobModel]:
        result = await self.session.execute(
            select(JobModel)
            .order_by(JobModel.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
        return list(result.scalars().all())

    async def list_by_state(self, state: JobState, limit: int = 100) -> List[JobModel]:
        result = await self.session.execute(
            select(JobModel)
            .where(JobModel.state == state.value)
            .order_by(JobModel.created_at.desc())
            .limit(limit)
        )
        return list(result.scalars().all())


class ExtractionRepository:
    """Repository for extraction data."""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def create(self, job_id: str, data: dict) -> ExtractionDataModel:
        extraction = ExtractionDataModel(job_id=job_id, data=data)
        self.session.add(extraction)
        await self.session.flush()
        return extraction

    async def get(self, job_id: str) -> Optional[ExtractionDataModel]:
        result = await self.session.execute(
            select(ExtractionDataModel).where(ExtractionDataModel.job_id == job_id)
        )
        return result.scalar_one_or_none()

    async def update(self, job_id: str, data: dict) -> ExtractionDataModel:
        extraction = await self.get(job_id)
        if extraction:
            extraction.data = data
            await self.session.flush()
        return extraction


class IRRepository:
    """Repository for IR data."""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def create(self, job_id: str, data: dict, application_name: str) -> IRDataModel:
        ir = IRDataModel(job_id=job_id, data=data, application_name=application_name)
        self.session.add(ir)
        await self.session.flush()
        return ir

    async def get(self, job_id: str) -> Optional[IRDataModel]:
        result = await self.session.execute(
            select(IRDataModel).where(IRDataModel.job_id == job_id)
        )
        return result.scalar_one_or_none()


class DependencyGraphRepository:
    """Repository for dependency graph."""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def create(self, job_id: str, nodes: list, edges: list, cycles: list, orphans: list) -> DependencyGraphModel:
        graph = DependencyGraphModel(
            job_id=job_id,
            nodes=nodes,
            edges=edges,
            cycles=cycles,
            orphans=orphans,
        )
        self.session.add(graph)
        await self.session.flush()
        return graph

    async def get(self, job_id: str) -> Optional[DependencyGraphModel]:
        result = await self.session.execute(
            select(DependencyGraphModel).where(DependencyGraphModel.job_id == job_id)
        )
        return result.scalar_one_or_none()


class SupportabilityRepository:
    """Repository for supportability results."""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def create_batch(self, job_id: str, results: list) -> list:
        models = [
            SupportabilityResultModel(
                job_id=job_id,
                object_name=r.get("object", ""),
                category=r.get("category", ""),
                status=r.get("status", ""),
                complexity=r.get("complexity"),
                risk=r.get("risk"),
                conversion=r.get("conversion"),
                confidence=r.get("confidence"),
                reason=r.get("reason"),
            )
            for r in results
        ]
        self.session.add_all(models)
        await self.session.flush()
        return models

    async def get_by_job(self, job_id: str) -> List[SupportabilityResultModel]:
        result = await self.session.execute(
            select(SupportabilityResultModel)
            .where(SupportabilityResultModel.job_id == job_id)
            .order_by(SupportabilityResultModel.created_at)
        )
        return list(result.scalars().all())


class BuildLogRepository:
    """Repository for build logs."""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def create(self, job_id: str, phase: str, step: str, status: str = "started", output: str = None, error: str = None) -> BuildLogModel:
        log = BuildLogModel(
            job_id=job_id,
            phase=phase,
            step=step,
            status=status,
            output=output,
            error=error,
        )
        self.session.add(log)
        await self.session.flush()
        return log

    async def update(self, log_id: str, status: str, output: str = None, error: str = None) -> Optional[BuildLogModel]:
        result = await self.session.execute(
            select(BuildLogModel).where(BuildLogModel.id == log_id)
        )
        log = result.scalar_one_or_none()
        if log:
            log.status = status
            if output:
                log.output = output
            if error:
                log.error = error
            if status in ("completed", "failed"):
                log.completed_at = datetime.utcnow()
            await self.session.flush()
        return log

    async def get_by_job(self, job_id: str) -> List[BuildLogModel]:
        result = await self.session.execute(
            select(BuildLogModel)
            .where(BuildLogModel.job_id == job_id)
            .order_by(BuildLogModel.started_at)
        )
        return list(result.scalars().all())


class LLMCacheRepository:
    """Repository for LLM cache with embeddings."""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def get(self, cache_key: str) -> Optional[LLMCacheModel]:
        result = await self.session.execute(
            select(LLMCacheModel).where(LLMCacheModel.cache_key == cache_key)
        )
        return result.scalar_one_or_none()

    async def set(self, cache_key: str, prompt_hash: str, system_prompt_hash: Optional[str], response: dict, model: str, tokens_used: int, provider_type: str, job_id: Optional[str] = None) -> LLMCacheModel:
        cached = await self.get(cache_key)
        if cached:
            cached.access_count += 1
            cached.last_accessed = datetime.utcnow()
            await self.session.flush()
            return cached

        entry = LLMCacheModel(
            job_id=job_id,
            cache_key=cache_key,
            prompt_hash=prompt_hash,
            system_prompt_hash=system_prompt_hash,
            response=response,
            model=model,
            tokens_used=tokens_used,
            provider_type=provider_type,
        )
        self.session.add(entry)
        await self.session.flush()
        return entry


class ExternalDependencyRepository:
    """Repository for external dependencies."""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def create_batch(self, job_id: str, dependencies: list) -> list:
        models = [
            ExternalDependencyModel(
                job_id=job_id,
                dependency_type=dep.get("type", ""),
                connection_info=dep.get("connection_info", {}),
                location=dep.get("location"),
                source_table=dep.get("source_table"),
                target_table=dep.get("target_table"),
                migration_strategy=dep.get("migration_strategy"),
                support_status=dep.get("support_status", "unsupported"),
                risk_level=dep.get("risk_level", "high"),
                has_credentials=dep.get("has_credentials", False),
                details=dep.get("details"),
            )
            for dep in dependencies
        ]
        self.session.add_all(models)
        await self.session.flush()
        return models

    async def get_by_job(self, job_id: str) -> List[ExternalDependencyModel]:
        result = await self.session.execute(
            select(ExternalDependencyModel)
            .where(ExternalDependencyModel.job_id == job_id)
            .order_by(ExternalDependencyModel.created_at)
        )
        return list(result.scalars().all())


# Helper function to convert SQLAlchemy models to Pydantic models
def job_model_to_pydantic(job: JobModel):
    """Convert JobModel to Pydantic MigrationJob for API compatibility."""
    from .jobs.models import MigrationJob, JobState, JobProgress, JobResult, JobError
    from pydantic import BaseModel

    progress_data = job.progress or {}
    progress = JobProgress(**progress_data) if progress_data else JobProgress()

    result_data = job.result
    result = JobResult(**result_data) if result_data else None

    error_data = job.error
    error = JobError(**error_data) if error_data else None

    return MigrationJob(
        id=str(job.id),
        state=JobState(job.state),
        created_at=job.created_at,
        updated_at=job.updated_at,
        source_file=job.source_file,
        source_file_size=job.source_file_size,
        project_name=job.project_name,
        base_package=job.base_package,
        java_version=job.java_version,
        spring_boot_version=job.spring_boot_version,
        react_version=job.react_version,
        node_version=job.node_version,
        postgres_version=job.postgres_version,
        progress=progress,
        extraction_path=job.extraction_path,
        ir_path=job.ir_path,
        output_path=job.output_path,
        result=result,
        error=error,
        tables_count=job.tables_count,
        queries_count=job.queries_count,
        forms_count=job.forms_count,
        reports_count=job.reports_count,
        macros_count=job.macros_count,
        vba_modules_count=job.vba_modules_count,
    )