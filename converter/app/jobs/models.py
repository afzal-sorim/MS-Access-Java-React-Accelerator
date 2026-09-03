"""Migration Job State Machine - spec section 65.

Manages the lifecycle of a conversion job from creation to completion.
"""
from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any, Optional
from pydantic import BaseModel, Field


class JobState(str, Enum):
    """Migration job states (spec section 65)."""
    CREATED = "CREATED"
    UPLOADED = "UPLOADED"
    EXTRACTING = "EXTRACTING"
    ANALYZING = "ANALYZING"
    DEPENDENCIES_DISCOVERED = "DEPENDENCIES_DISCOVERED"
    IR_READY = "IR_READY"
    SUPPORTABILITY_ANALYZED = "SUPPORTABILITY_ANALYZED"
    READY_TO_GENERATE = "READY_TO_GENERATE"
    GENERATING_DATABASE = "GENERATING_DATABASE"
    GENERATING_BACKEND = "GENERATING_BACKEND"
    GENERATING_FRONTEND = "GENERATING_FRONTEND"
    RESOLVING_DEPENDENCIES = "RESOLVING_DEPENDENCIES"
    BUILDING = "BUILDING"
    REPAIRING = "REPAIRING"
    TESTING = "TESTING"
    VALIDATING = "VALIDATING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


class JobError(BaseModel):
    """Error information for a failed job."""
    code: str
    message: str
    details: Optional[dict[str, Any]] = None
    timestamp: datetime = Field(default_factory=datetime.utcnow)


class JobProgress(BaseModel):
    """Progress tracking for a job."""
    current_step: str = ""
    total_steps: int = 25
    completed_steps: int = 0
    percentage: float = 0.0
    started_at: Optional[datetime] = None
    estimated_remaining_seconds: Optional[int] = None


class JobResult(BaseModel):
    """Result of a completed job."""
    output_path: Optional[str] = None
    coverage: dict[str, float] = Field(default_factory=dict)
    statistics: dict[str, int] = Field(default_factory=dict)
    files_generated: int = 0
    unit_tests_count: int = 0
    dependency_count: int = 0
    repair_errors: int = 0
    build_success: bool = False
    test_success: bool = False
    warnings: list[str] = Field(default_factory=list)
    unsupported_objects: list[str] = Field(default_factory=list)


class MigrationJob(BaseModel):
    """A migration job with full state tracking."""
    id: str
    state: JobState = JobState.CREATED
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

    # Input
    source_file: Optional[str] = None
    source_file_size: Optional[int] = None

    # Configuration
    project_name: str = "ConvertedApplication"
    base_package: str = "com.generated.app"
    java_version: int = 25
    spring_boot_version: str = "4.1.0"
    react_version: str = "19.2.8"
    node_version: int = 24
    postgres_version: str = "18"

    # Progress
    progress: JobProgress = Field(default_factory=JobProgress)

    # Extracted data paths
    extraction_path: Optional[str] = None
    ir_path: Optional[str] = None
    output_path: Optional[str] = None

    # Results
    result: Optional[JobResult] = None
    error: Optional[JobError] = None

    # Statistics
    tables_count: int = 0
    queries_count: int = 0
    forms_count: int = 0
    reports_count: int = 0
    macros_count: int = 0
    vba_modules_count: int = 0

    def transition_to(self, new_state: JobState) -> None:
        """Transition to a new state."""
        self.state = new_state
        self.updated_at = datetime.utcnow()
        self.progress.completed_steps += 1
        self.progress.current_step = new_state.value
        self.progress.percentage = (self.progress.completed_steps / self.progress.total_steps) * 100

    def fail(self, code: str, message: str, details: Optional[dict] = None) -> None:
        """Mark the job as failed."""
        self.state = JobState.FAILED
        self.error = JobError(
            code=code,
            message=message,
            details=details,
        )
        self.updated_at = datetime.utcnow()


class JobStore:
    """In-memory job storage (use database for production)."""

    def __init__(self):
        self._jobs: dict[str, MigrationJob] = {}

    def create(self, job_id: str, **kwargs) -> MigrationJob:
        """Create a new job."""
        job = MigrationJob(id=job_id, **kwargs)
        self._jobs[job_id] = job
        return job

    def get(self, job_id: str) -> Optional[MigrationJob]:
        """Get a job by ID."""
        return self._jobs.get(job_id)

    def update(self, job: MigrationJob) -> None:
        """Update a job."""
        job.updated_at = datetime.utcnow()
        self._jobs[job.id] = job

    def delete(self, job_id: str) -> bool:
        """Delete a job."""
        if job_id in self._jobs:
            del self._jobs[job_id]
            return True
        return False

    def list_all(self, limit: int = 100) -> list[MigrationJob]:
        """List all jobs."""
        return list(self._jobs.values())[:limit]


# Global job store
job_store = JobStore()
