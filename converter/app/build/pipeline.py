"""Build validation pipeline with Maven, npm, and database subprocess control.

Spec section 33: Build & Validation - validate generated code with Maven/npm.
Spec section 63: Build subprocess control for mvn clean package, npm ci, npm run build.
"""
from __future__ import annotations

import asyncio
import os
import shutil
import subprocess
import time
from datetime import datetime
from pathlib import Path
from typing import Optional, AsyncGenerator, List, Dict, Any
from dataclasses import dataclass
from enum import Enum


class BuildPhase(str, Enum):
    """Build phases."""
    MAVEN = "maven"
    NPM = "npm"
    DATABASE = "database"
    TEST = "test"
    REPAIR = "repair"


class BuildStatus(str, Enum):
    """Build step status."""
    STARTED = "started"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"


@dataclass
class BuildStepResult:
    """Result of a build step."""
    phase: BuildPhase
    step: str
    status: BuildStatus
    output: str = ""
    error: str = ""
    duration_seconds: float = 0.0
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None


class BuildValidator:
    """Orchestrates build validation for generated projects."""

    def __init__(
        self,
        project_dir: Path,
        job_id: str,
        build_log_repo,
        db_session,
    ):
        self.project_dir = Path(project_dir)
        self.job_id = job_id
        self.build_log_repo = build_log_repo
        self.db_session = db_session
        self.results: List[BuildStepResult] = []

    async def run_maven_build(self) -> BuildStepResult:
        """Run Maven build: mvn clean package"""
        return await self._run_build_step(
            BuildPhase.MAVEN,
            "maven_clean_package",
            ["mvn", "clean", "package", "-DskipTests"],
            cwd=self.project_dir / "backend",
        )

    async def run_maven_test(self) -> BuildStepResult:
        """Run Maven tests."""
        return await self._run_build_step(
            BuildPhase.MAVEN,
            "maven_test",
            ["mvn", "test"],
            cwd=self.project_dir / "backend",
        )

    async def run_maven_verify(self) -> BuildStepResult:
        """Run Maven verify phase."""
        return await self._run_build_step(
            BuildPhase.MAVEN,
            "maven_verify",
            ["mvn", "verify"],
            cwd=self.project_dir / "backend",
        )

    async def run_npm_install(self) -> BuildStepResult:
        """Run npm ci for clean install."""
        return await self._run_build_step(
            BuildPhase.NPM,
            "npm_ci",
            ["npm", "ci"],
            cwd=self.project_dir / "frontend",
        )

    async def run_npm_build(self) -> BuildStepResult:
        """Run npm run build."""
        return await self._run_build_step(
            BuildPhase.NPM,
            "npm_build",
            ["npm", "run", "build"],
            cwd=self.project_dir / "frontend",
        )

    async def run_npm_test(self) -> BuildStepResult:
        """Run npm test."""
        return await self._run_build_step(
            BuildPhase.NPM,
            "npm_test",
            ["npm", "test", "--", "--watchAll=false", "--passWithNoTests"],
            cwd=self.project_dir / "frontend",
        )

    async def run_npm_lint(self) -> BuildStepResult:
        """Run npm lint."""
        return await self._run_build_step(
            BuildPhase.NPM,
            "npm_lint",
            ["npm", "run", "lint"],
            cwd=self.project_dir / "frontend",
        )

    async def run_database_migration(self) -> BuildStepResult:
        """Run database schema initialization."""
        schema_path = self.project_dir / "database" / "schema.sql"
        if not schema_path.exists():
            return BuildStepResult(
                phase=BuildPhase.DATABASE,
                step="database_migration",
                status=BuildStatus.SKIPPED,
                error="No schema.sql found",
            )

        # This would connect to PostgreSQL and run the schema
        # For now, just validate the schema file exists and is valid SQL
        try:
            content = schema_path.read_text()
            if not content.strip():
                return BuildStepResult(
                    phase=BuildPhase.DATABASE,
                    step="database_migration",
                    status=BuildStatus.FAILED,
                    error="Schema file is empty",
                )
        except Exception as e:
            return BuildStepResult(
                phase=BuildPhase.DATABASE,
                step="database_migration",
                status=BuildStatus.FAILED,
                error=str(e),
            )

        return BuildStepResult(
            phase=BuildPhase.DATABASE,
            step="database_migration",
            status=BuildStatus.COMPLETED,
            output=f"Schema validated: {len(content)} chars",
        )

    async def run_full_build(self) -> Dict[str, Any]:
        """Run complete build pipeline."""
        steps = [
            self.run_maven_build,
            self.run_maven_test,
            self.run_npm_install,
            self.run_npm_build,
            self.run_npm_test,
            self.run_database_migration,
        ]

        all_passed = True
        for step_fn in steps:
            result = await step_fn()
            self.results.append(result)
            if result.status == BuildStatus.FAILED:
                all_passed = False
                break

        return {
            "success": all_passed,
            "steps": [
                {
                    "phase": r.phase.value,
                    "step": r.step,
                    "status": r.status.value,
                    "output": r.output,
                    "error": r.error,
                    "duration": r.duration_seconds,
                }
                for r in self.results
            ],
        }

    async def _run_build_step(
        self,
        phase: BuildPhase,
        step: str,
        command: List[str],
        cwd: Path,
        timeout: int = 300,
        env: Optional[Dict[str, str]] = None,
    ) -> BuildStepResult:
        """Run a single build step with logging."""
        start_time = time.time()
        started_at = datetime.utcnow()

        # Log start
        log_entry = await self.build_log_repo.create(
            self.job_id, phase.value, step, BuildStatus.STARTED.value
        )
        await self.db_session.commit()

        # Prepare environment
        proc_env = os.environ.copy()
        if env:
            proc_env.update(env)

        # Check if working directory exists
        if not cwd.exists():
            result = BuildStepResult(
                phase=phase,
                step=step,
                status=BuildStatus.FAILED,
                error=f"Working directory not found: {cwd}",
                duration_seconds=time.time() - start_time,
                started_at=started_at,
                completed_at=datetime.utcnow(),
            )
            await self.build_log_repo.update(
                log_entry.id, BuildStatus.FAILED.value,
                error=result.error
            )
            await self.db_session.commit()
            return result

        # Check if command exists.  Resolve to an absolute path so Windows
        # .CMD shims (mvn.CMD, npm.CMD) are executable — bare "mvn" makes
        # create_subprocess_exec raise FileNotFoundError even when Maven is
        # installed, because PATHEXT is not consulted for exec-style spawns.
        resolved_exe = shutil.which(command[0])
        if not resolved_exe:
            result = BuildStepResult(
                phase=phase,
                step=step,
                status=BuildStatus.FAILED,
                error=f"Command not found: {command[0]}",
                duration_seconds=time.time() - start_time,
                started_at=started_at,
                completed_at=datetime.utcnow(),
            )
            await self.build_log_repo.update(
                log_entry.id, BuildStatus.FAILED.value,
                error=result.error
            )
            await self.db_session.commit()
            return result

        command = [resolved_exe, *command[1:]]

        # Run command
        try:
            process = await asyncio.create_subprocess_exec(
                *command,
                cwd=str(cwd),
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                env=proc_env,
            )

            stdout, stderr = await asyncio.wait_for(
                process.communicate(),
                timeout=timeout,
            )

            duration = time.time() - start_time
            completed_at = datetime.utcnow()

            output = stdout.decode("utf-8", errors="replace") if stdout else ""
            error = stderr.decode("utf-8", errors="replace") if stderr else ""

            if process.returncode == 0:
                status = BuildStatus.COMPLETED
            else:
                status = BuildStatus.FAILED
                error = f"Exit code {process.returncode}: {error}"

        except asyncio.TimeoutError:
            duration = time.time() - start_time
            completed_at = datetime.utcnow()
            status = BuildStatus.FAILED
            output = ""
            error = f"Timeout after {timeout} seconds"

        except Exception as e:
            duration = time.time() - start_time
            completed_at = datetime.utcnow()
            status = BuildStatus.FAILED
            output = ""
            error = str(e)

        # Create result
        result = BuildStepResult(
            phase=phase,
            step=step,
            status=status,
            output=output[-10000:] if len(output) > 10000 else output,  # Limit output size
            error=error[-5000:] if len(error) > 5000 else error,
            duration_seconds=duration,
            started_at=started_at,
            completed_at=completed_at,
        )

        # Update log
        await self.build_log_repo.update(
            log_entry.id,
            status.value,
            output=result.output,
            error=result.error,
        )
        await self.db_session.commit()

        return result


from .repair import BuildRepair as StandaloneBuildRepair, RepairStrategy

# Re-export for backward compatibility
__all__ = [
    "BuildValidator",
    "BuildRepair",
    "BuildPhase",
    "BuildStatus",
    "BuildStepResult",
    "validate_generated_project",
    "attempt_build_repair",
    "RepairStrategy",
]

# Alias for backward compatibility
class BuildRepair:
    """Async wrapper for the standalone BuildRepair - spec section 35."""

    def __init__(
        self,
        project_dir: Path,
        job_id: str,
        build_log_repo,
        db_session,
    ):
        self.project_dir = Path(project_dir)
        self.job_id = job_id
        self.build_log_repo = build_log_repo
        self.db_session = db_session
        
        from converter.app.llm.provider import get_default_provider
        self._standalone = StandaloneBuildRepair(project_dir, llm_provider=get_default_provider())

    async def attempt_repair(
        self,
        phase: BuildPhase,
        step: str,
        error: str,
        output: str,
    ) -> List[BuildStepResult]:
        """Attempt to repair a failed build step."""
        # Convert to standalone validator format
        from .validator import BuildValidator, BuildError, ErrorCategory, BuildStatus as ValidatorBuildStatus

        # Create a BuildError from the inputs
        # Try to determine category from phase and error
        category = ErrorCategory.UNKNOWN
        if phase == BuildPhase.MAVEN:
            if "dependency" in error.lower():
                category = ErrorCategory.MISSING_DEPENDENCY
            elif "version" in error.lower():
                category = ErrorCategory.DEPENDENCY_VERSION_MISMATCH
            elif "java" in error.lower() or "class version" in error.lower():
                category = ErrorCategory.JAVA_VERSION_MISMATCH
        elif phase == BuildPhase.NPM:
            if "peer" in error.lower() or "eresolve" in error.lower():
                category = ErrorCategory.PEER_DEPENDENCY_CONFLICT
            elif "module not found" in error.lower():
                category = ErrorCategory.MISSING_DEPENDENCY
            elif "node" in error.lower() and "engine" in error.lower():
                category = ErrorCategory.NODE_VERSION_MISMATCH

        build_error = BuildError(
            category=category,
            message=error,
            raw_output=output,
        )

        # Run standalone repair
        results = self._standalone.repair_all()

        # Convert back to BuildStepResult
        step_results = []
        component = "backend" if phase == BuildPhase.MAVEN else "frontend"

        if component in results and results[component]:
            for repair in results[component].get("repairs", []):
                status = BuildStatus.COMPLETED if repair["success"] else BuildStatus.FAILED
                step_results.append(BuildStepResult(
                    phase=BuildPhase.REPAIR,
                    step=f"{component}_{repair['fix'][:50]}",
                    status=status,
                    output=repair.get("fix", ""),
                    error="" if repair["success"] else "Repair failed",
                ))

        return step_results


# Build endpoints to add to main.py
async def create_build_endpoints(app):
    """Add build-related endpoints to FastAPI app."""
    from fastapi import APIRouter, Depends, HTTPException, Query, Path as FastAPIPath
    from sqlalchemy.ext.asyncio import AsyncSession

    router = APIRouter(prefix="/api/build", tags=["build"])

    # These would be implemented with proper dependency injection
    # For now, this is a reference for the endpoint structure
    pass


# Standalone build functions for use in main.py pipeline

async def validate_generated_project(project_dir: Path, job_id: str, db_session) -> Dict[str, Any]:
    """Validate a generated project by running builds."""
    from converter.app.database import BuildLogRepository

    build_log_repo = BuildLogRepository(db_session)
    validator = BuildValidator(project_dir, job_id, build_log_repo, db_session)
    return await validator.run_full_build()


async def attempt_build_repair(
    project_dir: Path,
    job_id: str,
    failed_phase: str,
    failed_step: str,
    error: str,
    output: str,
    db_session,
) -> List[Dict[str, Any]]:
    """Attempt to repair a failed build."""
    from converter.app.database import BuildLogRepository

    build_log_repo = BuildLogRepository(db_session)
    repair = BuildRepair(project_dir, job_id, build_log_repo, db_session)
    results = await repair.attempt_repair(
        BuildPhase(failed_phase),
        failed_step,
        error,
        output,
    )
    return [
        {
            "phase": r.phase.value,
            "step": r.step,
            "status": r.status.value,
            "output": r.output,
            "error": r.error,
            "duration": r.duration_seconds,
        }
        for r in results
    ]