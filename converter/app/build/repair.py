"""Self-Healing Build Pipeline - spec sections 35, 54, 57, 58, 59.

Attempts to automatically fix build errors:
- Deterministic fixes for known errors (up to MAX_DETERMINISTIC_ATTEMPTS)
- LLM-assisted repair for unknown issues (up to MAX_LLM_ATTEMPTS)
- Maximum retry limits with loop termination
- Sandbox/rollback safety: LLM patches are reverted if they increase errors
- Build report generation (migration-report/build.json)
- Dependency graph output (generated-dependency-graph.json)
"""
from __future__ import annotations

import re
import json
import subprocess
import shutil
import time
import logging
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Optional, Dict, List, Any
from enum import Enum

logger = logging.getLogger(__name__)

from .validator import (
    BuildValidator, BuildResult, BuildError, BuildStatus, ErrorCategory,
    resolve_executable, normalize_reported_path,
)


class RepairStrategy(str, Enum):
    """Repair strategy types."""
    DETERMINISTIC = "deterministic"
    LLM_ASSISTED = "llm_assisted"
    MANUAL = "manual"


@dataclass
class RepairAttempt:
    """A single repair attempt."""
    error_category: ErrorCategory
    fix_applied: str
    strategy: RepairStrategy
    success: bool
    output: str = ""
    files_changed: List[str] = field(default_factory=list)
    confidence: float = 0.0


@dataclass
class RepairPlan:
    """A plan for repairing a build error."""
    error: BuildError
    strategy: RepairStrategy
    description: str
    commands: List[List[str]] = field(default_factory=list)
    file_changes: Dict[str, str] = field(default_factory=dict)
    confidence: float = 0.0
    requires_rebuild: bool = True
    reason: str = ""
    affected_component: str = ""


@dataclass
class RepairSession:
    """Complete audit trail for a repair session (spec §59)."""
    started_at: str = ""
    completed_at: str = ""
    project_dir: str = ""
    total_attempts: int = 0
    deterministic_attempts: int = 0
    llm_attempts: int = 0
    attempts: List[Dict[str, Any]] = field(default_factory=list)
    initial_errors: Dict[str, int] = field(default_factory=dict)
    final_errors: Dict[str, int] = field(default_factory=dict)
    rollbacks: int = 0
    final_status: str = "unknown"
    components: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "started_at": self.started_at,
            "completed_at": self.completed_at,
            "project_dir": self.project_dir,
            "total_attempts": self.total_attempts,
            "deterministic_attempts": self.deterministic_attempts,
            "llm_attempts": self.llm_attempts,
            "rollbacks": self.rollbacks,
            "final_status": self.final_status,
            "initial_errors": self.initial_errors,
            "final_errors": self.final_errors,
            "attempts": self.attempts,
            "components": self.components,
        }


class BuildRepair:
    """Self-healing build pipeline (spec §35, §54, §57, §59).

    Pipeline flow:
        Build → Capture error → Classify error → Known deterministic fix?
        YES → apply deterministic fix → Rebuild → Retest
        NO  → LLM diagnosis → Generate patch → Apply in sandbox → Rebuild
             → Compare error count → Accept or Rollback

    Limits:
        max deterministic repair attempts = 3
        max LLM repair attempts = 3
        max total attempts = 5
    """

    MAX_DETERMINISTIC_ATTEMPTS = 3
    MAX_LLM_ATTEMPTS = 3
    MAX_TOTAL_ATTEMPTS = 5

    def __init__(self, project_dir: Path, llm_provider=None):
        self.project_dir = Path(project_dir)
        self.validator = BuildValidator(project_dir)
        self.llm_provider = llm_provider
        self.attempts: List[RepairAttempt] = []
        self.backend_dir = self.project_dir / "backend"
        self.frontend_dir = self.project_dir / "frontend"
        self._snapshots: Dict[str, str] = {}  # path -> original content

    # ============================================================
    # Sandbox / Rollback (spec §59)
    # ============================================================

    def _snapshot_files(self, file_paths: List[str]) -> Dict[str, str]:
        """Back up file contents before applying a patch.

        Every LLM patch must be applied in a sandbox.  If the patch
        increases the number of failures, it is reverted (spec §59).
        """
        snapshot = {}
        for rel_path in file_paths:
            full_path = self.project_dir / rel_path
            if full_path.exists():
                snapshot[rel_path] = full_path.read_text(encoding="utf-8")
            else:
                # Mark as "file did not exist" so we can delete on restore
                snapshot[rel_path] = None
        return snapshot

    def _restore_snapshot(self, snapshot: Dict[str, Optional[str]]) -> None:
        """Revert files to their snapshotted state."""
        for rel_path, original_content in snapshot.items():
            full_path = self.project_dir / rel_path
            if original_content is None:
                # File didn't exist before — remove it
                if full_path.exists():
                    full_path.unlink()
            else:
                full_path.parent.mkdir(parents=True, exist_ok=True)
                full_path.write_text(original_content, encoding="utf-8")

    # ============================================================
    # Repair loop (spec §35)
    # ============================================================

    def repair_loop(self) -> RepairSession:
        """Full Build → Error → Classify → Fix → Rebuild → Retest loop.

        This is the primary entry point for self-healing.  It replaces
        the simpler ``repair_all()`` with a proper iterating loop that
        respects attempt limits, performs rollback on regression, and
        generates a complete audit trail.

        Returns a ``RepairSession`` with the full history.
        """
        session = RepairSession(
            started_at=datetime.utcnow().isoformat(),
            project_dir=str(self.project_dir),
        )

        # Step 1: Initial validation to discover errors
        validation = self.validator.validate_all()
        session.initial_errors = {
            name: len(result.errors)
            for name, result in validation.items()
            if result.status == BuildStatus.FAILED
        }

        # Step 2: Repair each component using the loop
        for component in ["backend", "frontend", "database"]:
            if component not in validation:
                continue
            result = validation[component]
            if result.status != BuildStatus.FAILED:
                # Include the same keys the repair path emits so consumers
                # (CLI, report) don't read a missing "success" as False for
                # a component that never needed repair.
                session.components[component] = {
                    "status": result.status.value.lower(),
                    "repairs": [],
                    "error_count": 0,
                    "original_errors": 0,
                    "attempts": 0,
                    "success": result.status == BuildStatus.SUCCESS,
                    "skipped": result.status == BuildStatus.SKIPPED,
                    "remaining_errors": [],
                    "rollbacks": 0,
                }
                continue

            if component == "database":
                comp_result = self._repair_database(result)
            else:
                comp_result = self._repair_component_loop(result, component, session)
            session.components[component] = comp_result

        # Step 3: Final validation
        final_validation = self.validator.validate_all()
        session.final_errors = {
            name: len(result.errors)
            for name, result in final_validation.items()
            if result.status == BuildStatus.FAILED
        }

        all_ok = all(
            r.status == BuildStatus.SUCCESS
            for r in final_validation.values()
        )
        session.final_status = "success" if all_ok else "GENERATED_PROJECT_REQUIRES_REVIEW"
        session.total_attempts = len(self.attempts)
        session.completed_at = datetime.utcnow().isoformat()

        # Step 4: Generate reports (resilient: don't let report failures crash the loop)
        try:
            self._generate_build_report(session)
        except Exception as e:
            logger.warning(f"Failed to generate build report: {e}")
            if "components" not in session.components:
                session.components["report"] = {}
            session.components["report"] = {"status": "failed", "error": str(e)}

        try:
            self._generate_dependency_graph()
        except Exception as e:
            logger.warning(f"Failed to generate dependency graph: {e}")
            if "components" not in session.components:
                session.components["dependency_graph"] = {}
            session.components["dependency_graph"] = {"status": "failed", "error": str(e)}

        return session

    def repair_all(self) -> dict:
        """Attempt to repair all build issues (legacy entry point).

        Delegates to ``repair_loop()`` and converts to the original
        dict format for backward compatibility.
        """
        session = self.repair_loop()

        # Convert to legacy dict format
        results = {
            "backend": session.components.get("backend"),
            "frontend": session.components.get("frontend"),
            "database": session.components.get("database"),
            "attempts": [
                {
                    "category": a.error_category.value,
                    "fix": a.fix_applied,
                    "strategy": a.strategy.value,
                    "success": a.success,
                    "files_changed": a.files_changed,
                    "confidence": a.confidence,
                }
                for a in self.attempts
            ],
            "final_status": session.final_status,
            "total_attempts": session.total_attempts,
        }
        return results

    def _repair_component_loop(
        self,
        initial_result: BuildResult,
        component: str,
        session: RepairSession,
    ) -> dict:
        """Repair loop for a single component (backend or frontend).

        Implements the spec §35 flow with separate counters for
        deterministic and LLM attempts.
        """
        comp_result = {
            "original_errors": len(initial_result.errors),
            "repairs": [],
            "success": False,
            "attempts": 0,
            "remaining_errors": [],
            "rollbacks": 0,
        }

        deterministic_count = 0
        llm_count = 0
        current_errors = list(initial_result.errors)
        addressed_errors: set = set()

        # ---- Phase 1: Deterministic fixes ----
        pre_error_count = len(current_errors)
        while deterministic_count < self.MAX_DETERMINISTIC_ATTEMPTS and current_errors:
            fix_plans = self._get_deterministic_fixes(current_errors, component)
            fix_plans.sort(key=lambda p: p.confidence, reverse=True)

            applied_any = False
            for fix_plan in fix_plans:
                if deterministic_count >= self.MAX_DETERMINISTIC_ATTEMPTS:
                    break

                error_key = f"{fix_plan.error.category.value}:{fix_plan.error.message[:50]}"
                if error_key in addressed_errors:
                    continue

                # Snapshot before applying.  Deterministic fixes are
                # heuristic rewrites (casts, annotation insertion, paren
                # balancing) that can make a build worse, so they get the
                # same regression guard as LLM patches (spec §57, §59).
                snapshot = self._snapshot_files(list(fix_plan.file_changes.keys()))

                attempt = self._apply_repair_plan(fix_plan, component)
                self.attempts.append(attempt)
                session.deterministic_attempts += 1
                deterministic_count += 1
                comp_result["attempts"] += 1
                addressed_errors.add(error_key)
                applied_any = True

                rolled_back = False
                if attempt.success:
                    new_result = self._revalidate_component(component)
                    post_error_count = len(new_result.errors)

                    if new_result.status == BuildStatus.SUCCESS:
                        comp_result["success"] = True
                        comp_result["remaining_errors"] = []
                        comp_result["repairs"].append({
                            "error": fix_plan.error.message[:100],
                            "strategy": fix_plan.strategy.value,
                            "fix": fix_plan.description,
                            "success": True,
                            "files_changed": attempt.files_changed,
                            "confidence": fix_plan.confidence,
                        })
                        session.attempts.append({
                            "component": component,
                            "category": fix_plan.error.category.value,
                            "fix": fix_plan.description,
                            "strategy": "deterministic",
                            "success": True,
                            "confidence": fix_plan.confidence,
                        })
                        return comp_result

                    if post_error_count > pre_error_count and snapshot:
                        logger.warning(
                            "Deterministic fix caused regression (%d -> %d errors), rolling back: %s",
                            pre_error_count, post_error_count, fix_plan.description,
                        )
                        self._restore_snapshot(snapshot)
                        attempt.success = False
                        attempt.output = "Rolled back: fix increased error count"
                        comp_result["rollbacks"] += 1
                        session.rollbacks += 1
                        rolled_back = True
                        # Errors revert to the pre-patch set.
                        current_errors = self._revalidate_component(component).errors
                        pre_error_count = len(current_errors)
                    else:
                        current_errors = new_result.errors
                        pre_error_count = post_error_count

                comp_result["repairs"].append({
                    "error": fix_plan.error.message[:100],
                    "strategy": fix_plan.strategy.value,
                    "fix": fix_plan.description,
                    "success": attempt.success,
                    "files_changed": attempt.files_changed,
                    "confidence": fix_plan.confidence,
                    "rolled_back": rolled_back,
                })
                session.attempts.append({
                    "component": component,
                    "category": fix_plan.error.category.value,
                    "fix": fix_plan.description,
                    "strategy": "deterministic",
                    "success": attempt.success,
                    "confidence": fix_plan.confidence,
                    "rolled_back": rolled_back,
                })

                if attempt.success:
                    break  # Re-enter loop with fresh errors

            if not applied_any:
                break  # No more deterministic fixes available

        # ---- Phase 2: LLM-assisted fixes with sandbox ----
        if (
            not comp_result["success"]
            and self.llm_provider
            and (deterministic_count + llm_count) < self.MAX_TOTAL_ATTEMPTS
        ):
            # Refresh current errors
            current_result = self._revalidate_component(component)
            current_errors = current_result.errors
            pre_error_count = len(current_errors)

            llm_fixes = self._get_llm_fixes(current_errors, component)
            for fix_plan in llm_fixes:
                if llm_count >= self.MAX_LLM_ATTEMPTS:
                    break
                if (deterministic_count + llm_count) >= self.MAX_TOTAL_ATTEMPTS:
                    break

                error_key = f"{fix_plan.error.category.value}:{fix_plan.error.message[:50]}"
                if error_key in addressed_errors:
                    continue

                # Sandbox: snapshot files before LLM patch
                snapshot = self._snapshot_files(list(fix_plan.file_changes.keys()))

                attempt = self._apply_repair_plan(fix_plan, component)
                self.attempts.append(attempt)
                session.llm_attempts += 1
                llm_count += 1
                comp_result["attempts"] += 1
                addressed_errors.add(error_key)

                # Check for regression (spec §59)
                if attempt.success:
                    new_result = self._revalidate_component(component)
                    post_error_count = len(new_result.errors)

                    if post_error_count > pre_error_count:
                        # Regression — rollback
                        logger.warning(
                            "LLM patch caused regression (%d -> %d errors), rolling back",
                            pre_error_count, post_error_count,
                        )
                        self._restore_snapshot(snapshot)
                        attempt.success = False
                        attempt.output = "Rolled back: patch increased error count"
                        comp_result["rollbacks"] += 1
                        session.rollbacks += 1
                    elif new_result.status == BuildStatus.SUCCESS:
                        comp_result["success"] = True
                        comp_result["remaining_errors"] = []
                        comp_result["repairs"].append({
                            "error": fix_plan.error.message[:100],
                            "strategy": fix_plan.strategy.value,
                            "fix": fix_plan.description,
                            "success": True,
                            "files_changed": attempt.files_changed,
                            "confidence": fix_plan.confidence,
                        })
                        session.attempts.append({
                            "component": component,
                            "category": fix_plan.error.category.value,
                            "fix": fix_plan.description,
                            "strategy": "llm_assisted",
                            "success": True,
                            "confidence": fix_plan.confidence,
                        })
                        return comp_result
                    else:
                        current_errors = new_result.errors
                        pre_error_count = post_error_count

                comp_result["repairs"].append({
                    "error": fix_plan.error.message[:100],
                    "strategy": fix_plan.strategy.value,
                    "fix": fix_plan.description,
                    "success": attempt.success,
                    "files_changed": attempt.files_changed,
                    "confidence": fix_plan.confidence,
                })
                session.attempts.append({
                    "component": component,
                    "category": fix_plan.error.category.value,
                    "fix": fix_plan.description,
                    "strategy": "llm_assisted",
                    "success": attempt.success,
                    "confidence": fix_plan.confidence,
                })

        # Capture remaining errors
        final_result = self._revalidate_component(component)
        comp_result["remaining_errors"] = [
            {"category": e.category.value, "message": e.message[:100], "file": e.file}
            for e in final_result.errors
        ]

        return comp_result

    def _repair_component(self, result: BuildResult, component: str) -> dict:
        """Attempt to repair a component's build errors.

        Legacy method — creates a temporary RepairSession and delegates
        to ``_repair_component_loop``.
        """
        session = RepairSession()
        return self._repair_component_loop(result, component, session)

    def _repair_database(self, result: BuildResult) -> dict:
        """Attempt to repair database schema errors."""
        repair_result = {
            "original_errors": len(result.errors),
            "repairs": [],
            "success": False,
        }

        for error in result.errors:
            fix_plan = self._get_database_fix(error)
            if fix_plan:
                attempt = self._apply_repair_plan(fix_plan, "database")
                self.attempts.append(attempt)
                repair_result["repairs"].append({
                    "error": error.message[:100],
                    "fix": fix_plan.description,
                    "success": attempt.success,
                })

        # Re-validate
        new_result = self.validator.validate_database()
        repair_result["success"] = new_result.status == BuildStatus.SUCCESS

        return repair_result

    def _revalidate_component(self, component: str) -> BuildResult:
        """Re-validate a specific component."""
        if component == "backend":
            return self.validator.build_backend()
        elif component == "frontend":
            return self.validator.build_frontend()
        elif component == "database":
            return self.validator.validate_database()
        return BuildResult(status=BuildStatus.FAILED, errors=[
            BuildError(category=ErrorCategory.UNKNOWN, message=f"Unknown component: {component}")
        ])

    def _get_deterministic_fixes(self, errors: List[BuildError], component: str) -> List[RepairPlan]:
        """Get deterministic fix plans for known errors."""
        plans = []

        for error in errors:
            # Java/Maven fixes
            if error.category == ErrorCategory.JAVA_VERSION_MISMATCH:
                plans.append(self._create_java_version_fix(error))

            elif error.category == ErrorCategory.MISSING_DEPENDENCY:
                plans.append(self._create_missing_dependency_fix(error, component))

            elif error.category == ErrorCategory.DEPENDENCY_VERSION_MISMATCH:
                plans.append(self._create_version_mismatch_fix(error, component))

            elif error.category == ErrorCategory.DEPENDENCY_CONVERGENCE:
                plans.append(self._create_convergence_fix(error, component))

            # Node/npm fixes
            elif error.category == ErrorCategory.NODE_VERSION_MISMATCH:
                plans.append(self._create_node_version_fix(error))

            elif error.category == ErrorCategory.PEER_DEPENDENCY_CONFLICT:
                plans.append(self._create_peer_dep_fix(error))

            # Compilation/type errors
            elif error.category == ErrorCategory.IMPORT_FAILURE:
                plans.append(self._create_import_fix(error, component))

            elif error.category == ErrorCategory.TYPE_MISMATCH:
                plans.append(self._create_type_mismatch_fix(error, component))

            elif error.category == ErrorCategory.ANNOTATION_MISMATCH:
                plans.append(self._create_annotation_fix(error))

            elif error.category == ErrorCategory.GENERATED_CODE_ERROR:
                plans.append(self._create_generated_code_fix(error, component))

            # Spring specific
            elif error.category == ErrorCategory.SPRING_CONFIG_ERROR:
                plans.append(self._create_spring_config_fix(error))

            # JPA/Database
            elif error.category == ErrorCategory.JPA_MAPPING_ERROR:
                plans.append(self._create_jpa_mapping_fix(error))

            elif error.category == ErrorCategory.SCHEMA_ERROR:
                plans.append(self._create_schema_fix(error))

            # React specific
            elif error.category == ErrorCategory.REACT_COMPILE_ERROR:
                plans.append(self._create_react_compile_fix(error))

        return [p for p in plans if p is not None]

    def _get_llm_fixes(self, errors: List[BuildError], component: str) -> List[RepairPlan]:
        """Get LLM-assisted fix plans for unknown errors."""
        if not self.llm_provider:
            return []

        plans = []
        # Prioritize errors by category - some are more amenable to LLM fixes
        priority_categories = [
            ErrorCategory.GENERATED_CODE_ERROR,
            ErrorCategory.TYPE_MISMATCH,
            ErrorCategory.REACT_COMPILE_ERROR,
            ErrorCategory.IMPORT_FAILURE,
            ErrorCategory.ANNOTATION_MISMATCH,
            ErrorCategory.JPA_MAPPING_ERROR,
            ErrorCategory.SPRING_CONFIG_ERROR,
            ErrorCategory.SQL_SYNTAX_ERROR,
        ]

        # Sort errors by priority
        def error_priority(e):
            try:
                return priority_categories.index(e.category)
            except ValueError:
                return len(priority_categories)

        sorted_errors = sorted(errors, key=error_priority)

        # Only use LLM for the first few errors to avoid token limits
        for error in sorted_errors[:3]:
            fix_plan = self._llm_diagnose_error(error, component)
            if fix_plan:
                plans.append(fix_plan)
        return plans

    def _get_database_fix(self, error: BuildError) -> Optional[RepairPlan]:
        """Get fix for database schema errors."""
        if error.category == ErrorCategory.SQL_SYNTAX_ERROR:
            schema_file = self.project_dir / "database" / "schema.sql"
            if schema_file.exists():
                content = schema_file.read_text()

                # Fix unbalanced parentheses
                if "unbalanced" in error.message.lower() or content.count("(") != content.count(")"):
                    return RepairPlan(
                        error=error,
                        strategy=RepairStrategy.DETERMINISTIC,
                        description="Fix unbalanced parentheses in schema.sql",
                        file_changes={"database/schema.sql": self._balance_parentheses(content)},
                        confidence=0.7,
                    )

                # Fix undefined values
                if "undefined" in error.message.lower():
                    fixed = content.replace("undefined", "NULL")
                    return RepairPlan(
                        error=error,
                        strategy=RepairStrategy.DETERMINISTIC,
                        description="Replace 'undefined' with NULL in schema.sql",
                        file_changes={"database/schema.sql": fixed},
                        confidence=0.8,
                    )

        return None

    def _balance_parentheses(self, content: str) -> str:
        """Balance parentheses in SQL content."""
        open_count = content.count("(")
        close_count = content.count(")")
        if open_count > close_count:
            content += ")" * (open_count - close_count)
        elif close_count > open_count:
            # Remove extra closing parens from end
            content = content[:content.rfind(")") + 1]
        return content

    # ============================================================
    # Java/Maven Fix Plans
    # ============================================================

    def _resolve_error_file(self, error: BuildError) -> Optional[Path]:
        """Resolve ``error.file`` to an existing path inside the project.

        Handles the URI-style ``/C:/...`` paths Maven emits on Windows and
        paths reported relative to a component directory rather than the
        project root.  Returns ``None`` when the file cannot be located, so
        callers skip the fix instead of writing to a bogus path.
        """
        if not error.file:
            return None

        raw = normalize_reported_path(error.file)
        candidate = Path(raw)
        if candidate.is_absolute():
            return candidate if candidate.exists() else None

        # Try project root, then each component directory.
        for base in (self.project_dir, self.backend_dir, self.frontend_dir):
            resolved = base / candidate
            if resolved.exists():
                return resolved
        return None

    def _rel_to_project(self, file_path: Path) -> str:
        """Return a project-relative POSIX path for use as a file_changes key."""
        try:
            return file_path.resolve().relative_to(self.project_dir.resolve()).as_posix()
        except ValueError:
            return file_path.as_posix()

    def _create_java_version_fix(self, error: BuildError) -> Optional[RepairPlan]:
        """Fix Java version mismatch in pom.xml."""
        pom_path = self.backend_dir / "pom.xml"
        if not pom_path.exists():
            return None

        content = pom_path.read_text()

        # Detect the required version from the error.  Search both the raw
        # output and the message, since classification may summarise into
        # the message and leave raw_output empty.
        haystack = f"{error.raw_output}\n{error.message}"
        target_version: Optional[str] = None

        # "Unsupported class file major version 69" -> major - 44 = Java 25.
        # Computed rather than table-driven so future Java releases work
        # without another code change.
        major_match = re.search(r'major version[:\s]+(\d+)', haystack, re.IGNORECASE)
        if major_match:
            major = int(major_match.group(1))
            if 45 <= major <= 99:
                target_version = str(major - 44)

        # "invalid target release: 25" / "invalid source release: 25"
        if target_version is None:
            release_match = re.search(
                r'invalid (?:target|source) release:?\s*(\d+)',
                haystack,
                re.IGNORECASE,
            )
            if release_match:
                target_version = release_match.group(1)

        # "class file version 69.0" (JVM-style with minor component)
        if target_version is None:
            cf_match = re.search(r'class file version (\d+)(?:\.\d+)?', haystack, re.IGNORECASE)
            if cf_match:
                major = int(cf_match.group(1))
                if 45 <= major <= 99:
                    target_version = str(major - 44)

        if target_version is None:
            # Fall back to the version the local JDK actually provides, so
            # we align the pom with a toolchain that exists on this machine
            # rather than guessing a hardcoded default (spec §30).
            target_version = self._detect_local_java_version() or "17"

        # Update java.version property
        new_content = re.sub(
            r'<java\.version>\d+</java\.version>',
            f'<java.version>{target_version}</java.version>',
            content,
        )

        # Also update maven.compiler.source/target if present
        new_content = re.sub(
            r'<maven\.compiler\.source>\d+</maven\.compiler\.source>',
            f'<maven.compiler.source>{target_version}</maven.compiler.source>',
            new_content,
        )
        new_content = re.sub(
            r'<maven\.compiler\.target>\d+</maven\.compiler\.target>',
            f'<maven.compiler.target>{target_version}</maven.compiler.target>',
            new_content,
        )
        # Modern Spring Boot poms use <maven.compiler.release> and/or a
        # <release> element inside the compiler plugin; without these the
        # rewrite silently no-ops on the projects we actually generate.
        new_content = re.sub(
            r'<maven\.compiler\.release>\d+</maven\.compiler\.release>',
            f'<maven.compiler.release>{target_version}</maven.compiler.release>',
            new_content,
        )
        new_content = re.sub(
            r'<release>\d+</release>',
            f'<release>{target_version}</release>',
            new_content,
        )

        if new_content != content:
            return RepairPlan(
                error=error,
                strategy=RepairStrategy.DETERMINISTIC,
                description=f"Update Java version to {target_version} in pom.xml",
                file_changes={"backend/pom.xml": new_content},
                confidence=0.9,
            )
        return None

    def _detect_local_java_version(self) -> Optional[str]:
        """Return the local JDK feature version (e.g. "25"), or None.

        Used when a Java version mismatch is reported but the required
        version cannot be parsed out of the build output (spec §30).
        """
        try:
            result = self._run_tool(["java", "-version"], cwd=self.project_dir, timeout=30)
        except (FileNotFoundError, subprocess.TimeoutExpired, OSError):
            return None
        if result is None:
            return None
        # `java -version` writes to stderr on most JDKs.
        blob = f"{result.stderr}\n{result.stdout}"
        match = re.search(r'version "(\d+)(?:[.\-_][\w.\-]*)?"', blob)
        if match:
            return match.group(1)
        return None

    def _create_missing_dependency_fix(self, error: BuildError, component: str) -> Optional[RepairPlan]:
        """Attempt to add missing dependency based on error."""
        # For Maven, we can try to extract missing artifact from error
        if component == "backend":
            # Pattern: Could not find artifact group:artifact:version
            match = re.search(r'Could not find artifact\s+([^:]+):([^:]+):([^:]+)', error.raw_output)
            if match:
                group_id, artifact_id, version = match.groups()
                pom_path = self.backend_dir / "pom.xml"
                if pom_path.exists():
                    content = pom_path.read_text()
                    # Add dependency before </dependencies>
                    dep_xml = f"""        <dependency>
            <groupId>{group_id}</groupId>
            <artifactId>{artifact_id}</artifactId>
            <version>{version}</version>
        </dependency>"""
                    new_content = content.replace("</dependencies>", f"{dep_xml}\n    </dependencies>")
                    if new_content != content:
                        return RepairPlan(
                            error=error,
                            strategy=RepairStrategy.DETERMINISTIC,
                            description=f"Add missing Maven dependency: {group_id}:{artifact_id}:{version}",
                            file_changes={"backend/pom.xml": new_content},
                            confidence=0.6,
                        )

        elif component == "frontend":
            # For npm, try to extract missing package
            # Pattern: "npm ERR! 404 Not Found - GET https://registry.npmjs.org/package-name"
            match = re.search(r'registry\.npmjs\.org/([^/\s]+)', error.raw_output)
            if not match:
                # Alternative pattern: "Module not found: ... 'package-name'"
                match = re.search(r"Can't resolve '([^']+)'", error.raw_output)
            if not match:
                match = re.search(r'npm ERR! code E404.*?([\w@][\w./-]+)', error.raw_output, re.DOTALL)
            if match:
                package = match.group(1)
                package_json = self.frontend_dir / "package.json"
                if package_json.exists():
                    content = json.loads(package_json.read_text())
                    if "dependencies" not in content:
                        content["dependencies"] = {}
                    # Spec §57: do NOT use "*".  Use "latest" with an explicit
                    # logged warning so the version is resolved at install time
                    # and then pinned in package-lock.json.
                    content["dependencies"][package] = "latest"
                    logger.warning(
                        "Adding npm dependency '%s' with 'latest' — pin after install (spec §57)",
                        package,
                    )
                    return RepairPlan(
                        error=error,
                        strategy=RepairStrategy.DETERMINISTIC,
                        description=f"Add missing npm dependency: {package}",
                        file_changes={"frontend/package.json": json.dumps(content, indent=2)},
                        confidence=0.5,
                        reason=f"Package '{package}' is required but not in package.json",
                        affected_component="frontend",
                    )

        return None

    def _create_version_mismatch_fix(self, error: BuildError, component: str) -> Optional[RepairPlan]:
        """Fix dependency version mismatch."""
        if component == "backend":
            pom_path = self.backend_dir / "pom.xml"
            if pom_path.exists():
                content = pom_path.read_text()
                # Try to use dependency management from Spring Boot BOM
                # Add dependencyManagement if not present
                if "dependencyManagement" not in content:
                    # This is a more complex fix - for now, just note it
                    return RepairPlan(
                        error=error,
                        strategy=RepairStrategy.DETERMINISTIC,
                        description="Run mvn dependency:resolve to fetch managed versions",
                        commands=[["mvn", "dependency:resolve"]],
                        confidence=0.5,
                    )
        return None

    def _create_convergence_fix(self, error: BuildError, component: str) -> Optional[RepairPlan]:
        """Fix dependency convergence conflicts.

        Attempts to parse the error output to find conflicting artifacts
        and add <exclusion> blocks to pom.xml (spec §27, §57).
        """
        if component != "backend":
            return None

        pom_path = self.backend_dir / "pom.xml"
        if not pom_path.exists():
            return None

        content = pom_path.read_text()

        # Try to parse conflicting artifact from the error output
        # Pattern: "Dependency convergence error for group:artifact:version"
        conflict_match = re.search(
            r'(?:conflict|convergence)[^:]*:\s*([^:]+):([^:]+):([^\s]+)',
            error.raw_output,
            re.IGNORECASE,
        )

        if conflict_match:
            group_id = conflict_match.group(1).strip()
            artifact_id = conflict_match.group(2).strip()
            # Add an exclusion to the first dependency that transitively pulls it in
            exclusion_xml = f"""            <exclusions>
                <exclusion>
                    <groupId>{group_id}</groupId>
                    <artifactId>{artifact_id}</artifactId>
                </exclusion>
            </exclusions>"""

            # Find the first <dependency> block that doesn't already exclude this artifact
            dep_pattern = re.compile(
                r'(<dependency>\s*<groupId>[^<]+</groupId>\s*'
                r'<artifactId>[^<]+</artifactId>)'
                r'((?:(?!</dependency>).)*?)(</dependency>)',
                re.DOTALL,
            )
            for match in dep_pattern.finditer(content):
                dep_block = match.group(0)
                # Don't add exclusion if it already exists for this artifact
                if artifact_id in dep_block and "exclusion" in dep_block:
                    continue
                # Don't exclude the artifact from itself
                if f"<artifactId>{artifact_id}</artifactId>" in match.group(1):
                    continue
                # Insert exclusion before </dependency>
                new_dep = dep_block.replace(
                    match.group(3),
                    f"\n{exclusion_xml}\n        {match.group(3)}",
                )
                new_content = content.replace(dep_block, new_dep, 1)
                return RepairPlan(
                    error=error,
                    strategy=RepairStrategy.DETERMINISTIC,
                    description=f"Add exclusion for {group_id}:{artifact_id} to resolve convergence",
                    file_changes={"backend/pom.xml": new_content},
                    confidence=0.6,
                    reason=f"Dependency convergence conflict for {group_id}:{artifact_id}",
                    affected_component="backend",
                )

        # Fallback: just run dependency:tree for diagnostics
        return RepairPlan(
            error=error,
            strategy=RepairStrategy.DETERMINISTIC,
            description="Run mvn dependency:tree to analyze convergence",
            commands=[["mvn", "dependency:tree"]],
            confidence=0.4,
        )

    # ============================================================
    # Node/npm Fix Plans
    # ============================================================

    def _create_node_version_fix(self, error: BuildError) -> Optional[RepairPlan]:
        """Fix Node version mismatch in package.json."""
        package_json = self.frontend_dir / "package.json"
        if not package_json.exists():
            return None

        content = json.loads(package_json.read_text())

        # Extract required version from error
        match = re.search(r'required.*?node[^\d]*(\d+)', error.raw_output, re.IGNORECASE)
        if not match:
            match = re.search(r'engine.*?node[^\d]*(\d+)', error.raw_output, re.IGNORECASE)

        required_version = match.group(1) if match else "24"

        if "engines" not in content:
            content["engines"] = {}
        content["engines"]["node"] = f">={required_version} <{int(required_version) + 1}"

        return RepairPlan(
            error=error,
            strategy=RepairStrategy.DETERMINISTIC,
            description=f"Update Node engine requirement to {required_version}",
            file_changes={"frontend/package.json": json.dumps(content, indent=2)},
            confidence=0.7,
        )

    def _create_peer_dep_fix(self, error: BuildError) -> Optional[RepairPlan]:
        """Fix peer dependency conflicts.

        BUG FIX: the old code wrote .npmrc as a side effect during plan
        creation (before the plan was approved/applied).  Now the file
        write only happens inside ``_apply_repair_plan``.
        """
        return RepairPlan(
            error=error,
            strategy=RepairStrategy.DETERMINISTIC,
            description="Enable legacy peer deps resolution",
            file_changes={"frontend/.npmrc": "legacy-peer-deps=true\n"},
            confidence=0.8,
            reason="Peer dependency conflict requires --legacy-peer-deps as last resort (spec §28)",
            affected_component="frontend",
        )

    # ============================================================
    # Compilation/Code Fix Plans
    # ============================================================

    def _create_import_fix(self, error: BuildError, component: str) -> Optional[RepairPlan]:
        """Fix missing imports."""
        file_path = self._resolve_error_file(error)
        if file_path is None:
            return None

        content = file_path.read_text()
        lines = content.splitlines()

        # Try to infer missing import from error message
        match = re.search(r'cannot find symbol:?\s*(?:class|interface|variable|method|enum)?\s*(\w+)', error.message)
        if not match:
            match = re.search(r'is not defined.*?(\w+)', error.message)
        if not match:
            match = re.search(r"import.*?(\w+)", error.message)

        if match:
            symbol = match.group(1)
            # Common mappings for Java
            if component == "backend" and file_path.suffix == ".java":
                import_map = {
                    "List": "java.util.List",
                    "ArrayList": "java.util.ArrayList",
                    "Optional": "java.util.Optional",
                    "BigDecimal": "java.math.BigDecimal",
                    "LocalDateTime": "java.time.LocalDateTime",
                    "Entity": "jakarta.persistence.Entity",
                    "Table": "jakarta.persistence.Table",
                    "Id": "jakarta.persistence.Id",
                    "Column": "jakarta.persistence.Column",
                    "GeneratedValue": "jakarta.persistence.GeneratedValue",
                    "GenerationType": "jakarta.persistence.GenerationType",
                    "ManyToOne": "jakarta.persistence.ManyToOne",
                    "JoinColumn": "jakarta.persistence.JoinColumn",
                    "Autowired": "org.springframework.beans.factory.annotation.Autowired",
                    "Service": "org.springframework.stereotype.Service",
                    "Repository": "org.springframework.stereotype.Repository",
                    "RestController": "org.springframework.web.bind.annotation.RestController",
                    "RequestMapping": "org.springframework.web.bind.annotation.RequestMapping",
                    "GetMapping": "org.springframework.web.bind.annotation.GetMapping",
                    "PostMapping": "org.springframework.web.bind.annotation.PostMapping",
                    "PutMapping": "org.springframework.web.bind.annotation.PutMapping",
                    "DeleteMapping": "org.springframework.web.bind.annotation.DeleteMapping",
                    "RequestBody": "org.springframework.web.bind.annotation.RequestBody",
                    "PathVariable": "org.springframework.web.bind.annotation.PathVariable",
                    "ResponseEntity": "org.springframework.http.ResponseEntity",
                    "CrossOrigin": "org.springframework.web.bind.annotation.CrossOrigin",
                    "Transactional": "org.springframework.transaction.annotation.Transactional",
                }

                if symbol in import_map:
                    import_stmt = f"import {import_map[symbol]};"
                    # Skip if the import is already present.
                    if import_stmt in content:
                        return None
                    # Add import after package declaration
                    for i, line in enumerate(lines):
                        if line.startswith("package "):
                            lines.insert(i + 1, import_stmt)
                            break

                    return RepairPlan(
                        error=error,
                        strategy=RepairStrategy.DETERMINISTIC,
                        description=f"Add missing import for {symbol}",
                        file_changes={self._rel_to_project(file_path): "\n".join(lines)},
                        confidence=0.8,
                    )

        return None

    def _create_type_mismatch_fix(self, error: BuildError, component: str) -> Optional[RepairPlan]:
        """Fix type mismatches."""
        file_path = self._resolve_error_file(error)
        if file_path is None:
            return None

        content = file_path.read_text()

        # Java type mismatch - common pattern: incompatible types
        if component == "backend" and file_path.suffix == ".java":
            # Pattern: incompatible types: X cannot be converted to Y
            match = re.search(r'incompatible types:\s*(\w+)\s*cannot be converted to\s*(\w+)', error.message)
            if match:
                from_type, to_type = match.groups()
                # Common fix: add cast or change variable type
                lines = content.splitlines()
                # Look for the line with the assignment
                if error.line and error.line <= len(lines):
                    line_idx = error.line - 1
                    line = lines[line_idx]
                    # Try to add explicit cast
                    if from_type in line and "=" in line:
                        # Add cast before the value
                        new_line = line.replace(from_type, f"({to_type}) {from_type}")
                        lines[line_idx] = new_line
                        return RepairPlan(
                            error=error,
                            strategy=RepairStrategy.DETERMINISTIC,
                            description=f"Add explicit cast from {from_type} to {to_type}",
                            file_changes={self._rel_to_project(file_path): "\n".join(lines)},
                            confidence=0.6,
                        )

        # TypeScript/React type mismatch
        if component == "frontend" and file_path.suffix in (".ts", ".tsx", ".js", ".jsx"):
            # Pattern: Type 'X' is not assignable to type 'Y'
            # No safe deterministic rewrite exists for this — returning None
            # defers to LLM repair.  (Previously this returned a plan whose
            # only action was `echo`, which reported success without editing
            # anything, burned a deterministic attempt, and marked the error
            # as addressed so the real fix never ran.)
            return None

        return None

    def _create_annotation_fix(self, error: BuildError) -> Optional[RepairPlan]:
        """Fix annotation mismatches - missing JPA/Spring annotations."""
        file_path = self._resolve_error_file(error)
        if file_path is None or file_path.suffix != ".java":
            return None

        content = file_path.read_text()
        lines = content.splitlines()

        # Check for missing @Id (more specific - check first)
        if "identifier" in error.message.lower() and "id" in error.message.lower():
            # Check if @Id already exists
            if "@Id" in content:
                return None  # Already has @Id

            # Find the primary key field
            for i, line in enumerate(lines):
                if "private" in line and ("Long" in line or "Integer" in line or "String" in line):
                    field_name = line.split()[-1].rstrip(";")
                    if "id" in field_name.lower():
                        # Add @Id before the field
                        lines.insert(i, "    @Id")
                        if "GeneratedValue" not in content:
                            lines.insert(i + 1, '    @GeneratedValue(strategy = GenerationType.IDENTITY)')
                        # Add import for GenerationType if needed
                        if "GenerationType" not in content:
                            for j, l in enumerate(lines):
                                if l.startswith("package "):
                                    if "import jakarta.persistence.GenerationType;" not in content:
                                        lines.insert(j + 1, "import jakarta.persistence.GenerationType;")
                                    break
                        return RepairPlan(
                            error=error,
                            strategy=RepairStrategy.DETERMINISTIC,
                            description="Add missing @Id and @GeneratedValue annotations",
                            file_changes={self._rel_to_project(file_path): "\n".join(lines)},
                            confidence=0.7,
                        )

        # Check if it's a class missing @Entity annotation
        if ("entity" in error.message.lower() or "not a managed type" in error.message.lower()) and "@Entity" not in content:
            # Find class declaration
            for i, line in enumerate(lines):
                if line.strip().startswith("public class "):
                    # Add @Entity and @Table annotations before class
                    class_name = line.split()[2].split("{")[0]
                    table_name = class_name[0].lower() + class_name[1:]
                    imports_to_add = [
                        "import jakarta.persistence.Entity;",
                        "import jakarta.persistence.Table;",
                    ]
                    # Add imports after package (avoid duplicates)
                    for j, l in enumerate(lines):
                        if l.startswith("package "):
                            for idx, imp in enumerate(imports_to_add):
                                if imp not in content:
                                    lines.insert(j + 1 + idx, imp)
                            break
                    # Add annotations before class
                    lines.insert(i, f'@Table(name = "{table_name}")')
                    lines.insert(i, '@Entity')
                    return RepairPlan(
                        error=error,
                        strategy=RepairStrategy.DETERMINISTIC,
                        description="Add missing @Entity and @Table annotations",
                        file_changes={self._rel_to_project(file_path): "\n".join(lines)},
                        confidence=0.7,
                    )

        # Missing @Column annotation for nullable/unique
        if "nullable" in error.message.lower() or "unique" in error.message.lower():
            # This is more complex - let LLM handle
            pass

        return None

    def _create_generated_code_fix(self, error: BuildError, component: str) -> Optional[RepairPlan]:
        """Fix generated code errors - often missing getters/setters or wrong types."""
        file_path = self._resolve_error_file(error)
        if file_path is None:
            return None

        content = file_path.read_text()
        lines = content.splitlines()

        # Java: Common pattern: missing getter/setter for a field
        if component == "backend" and file_path.suffix == ".java":
            # Pattern: cannot find symbol: method getXxx()
            field_match = re.search(r'get(\w+)', error.message)
            if field_match and "cannot find symbol" in error.message:
                field_name = field_match.group(1)
                # Find the field declaration (camelCase)
                field_camel = field_name[0].lower() + field_name[1:]
                field_pattern = rf'private\s+\w+\s+{re.escape(field_camel)};'
                for i, line in enumerate(lines):
                    if re.search(field_pattern, line):
                        # Add getter/setter after the field
                        indent = "    "
                        # Extract type from field declaration
                        parts = line.strip().split()
                        if len(parts) >= 2:
                            field_type = parts[1]
                            getter = f"{indent}public {field_type} get{field_name}() {{ return {field_camel}; }}"
                            setter = f"{indent}public void set{field_name}({field_type} {field_camel}) {{ this.{field_camel} = {field_camel}; }}"
                            lines.insert(i + 1, "")
                            lines.insert(i + 2, getter)
                            lines.insert(i + 3, setter)

                            return RepairPlan(
                                error=error,
                                strategy=RepairStrategy.DETERMINISTIC,
                                description=f"Add getter/setter for {field_name}",
                                file_changes={self._rel_to_project(file_path): "\n".join(lines)},
                                confidence=0.7,
                            )

            # Missing setter
            field_match = re.search(r'set(\w+)', error.message)
            if field_match and "cannot find symbol" in error.message:
                field_name = field_match.group(1)
                field_camel = field_name[0].lower() + field_name[1:]
                field_pattern = rf'private\s+\w+\s+{re.escape(field_camel)};'
                for i, line in enumerate(lines):
                    if re.search(field_pattern, line):
                        # Check if getter exists but not setter
                        getter_exists = any(f"get{field_name}()" in l for l in lines)
                        setter_exists = any(f"set{field_name}(" in l for l in lines)
                        if getter_exists and not setter_exists:
                            indent = "    "
                            parts = line.strip().split()
                            if len(parts) >= 2:
                                field_type = parts[1]
                                setter = f"{indent}public void set{field_name}({field_type} {field_camel}) {{ this.{field_camel} = {field_camel}; }}"
                                lines.insert(i + 2 if getter_exists else i + 1, setter)
                                return RepairPlan(
                                    error=error,
                                    strategy=RepairStrategy.DETERMINISTIC,
                                    description=f"Add setter for {field_name}",
                                    file_changes={self._rel_to_project(file_path): "\n".join(lines)},
                                    confidence=0.6,
                                )

            # Constructor issues
            msg_lower = error.message.lower()
            if "constructor" in msg_lower and (
                "not found" in msg_lower or "undefined" in msg_lower or "cannot be applied" in msg_lower
                or "no suitable constructor" in msg_lower
                or "incompatible types" in msg_lower
            ):
                # Add a no-arg (default) constructor if one is missing
                class_match = re.search(r'public class (\w+)', content)
                if class_match:
                    class_name = class_match.group(1)
                    # Check if a no-arg constructor already exists
                    has_no_arg_ctor = any(
                        re.search(rf'public\s+{re.escape(class_name)}\s*\(\s*\)', l) for l in lines
                    )
                    if not has_no_arg_ctor:
                        # Find class opening brace
                        for i, line in enumerate(lines):
                            if line.strip().startswith(f"public class {class_name}"):
                                # Find the opening brace
                                for j in range(i, min(i + 5, len(lines))):
                                    if "{" in lines[j]:
                                        lines.insert(j + 1, f"    public {class_name}() {{}}")
                                        lines.insert(j + 2, "")
                                        return RepairPlan(
                                            error=error,
                                            strategy=RepairStrategy.DETERMINISTIC,
                                            description=f"Add default constructor for {class_name}",
                                            file_changes={self._rel_to_project(file_path): "\n".join(lines)},
                                            confidence=0.6,
                                        )
                                break

        # React/TypeScript: Missing component export
        if component == "frontend" and file_path.suffix in (".jsx", ".tsx", ".js", ".ts"):
            if "export" in error.message and ("not found" in error.message or "undefined" in error.message):
                match = re.search(r"'(\w+)' is not defined", error.message)
                if match and match.group(1)[0].isupper():
                    component_name = match.group(1)
                    # Check if component is defined but not exported
                    if f"function {component_name}" in content or f"const {component_name}" in content:
                        if f"export" not in content.split(component_name)[1][:50]:
                            # Add default export at end
                            lines.append(f"\nexport default {component_name};")
                            return RepairPlan(
                                error=error,
                                strategy=RepairStrategy.DETERMINISTIC,
                                description=f"Add default export for {component_name}",
                                file_changes={self._rel_to_project(file_path): "\n".join(lines)},
                                confidence=0.5,
                            )

        return None

    def _create_spring_config_fix(self, error: BuildError) -> Optional[RepairPlan]:
        """Fix Spring configuration errors.

        BUG FIX: the old code had an undefined variable (``new_content``)
        when ``fixed`` was set to ``True`` via the YAML colon-fix path
        but the datasource branch was not taken.  Now ``final_content``
        is always defined before use.
        """
        if "application.yml" in error.raw_output or "application.properties" in error.raw_output:
            yml_path = self.backend_dir / "src" / "main" / "resources" / "application.yml"
            if yml_path.exists():
                content = yml_path.read_text()
                lines = content.splitlines()
                fixed = False
                new_lines = []

                for line in lines:
                    # Fix common YAML issues: missing colons, incorrect indentation
                    stripped = line.strip()
                    if stripped and ":" not in stripped and not stripped.startswith("#") and not stripped.startswith("-"):
                        # Might be a key without value
                        if " " in stripped:
                            # Try to add colon
                            parts = stripped.split(" ", 1)
                            line = line.replace(stripped, f"{parts[0]}: {parts[1]}")
                            fixed = True
                    new_lines.append(line)

                # Start from the (possibly fixed) lines
                final_content = "\n".join(new_lines)

                # Fix missing required properties
                if "datasource:" not in final_content and ("url:" in final_content or "jdbc:" in error.raw_output):
                    # Add basic datasource config
                    if "spring:" not in final_content:
                        final_content = (
                            "spring:\n"
                            "  datasource:\n"
                            "    url: jdbc:postgresql://localhost:5432/db\n"
                            "    username: postgres\n"
                            "    password: postgres\n"
                            "    driver-class-name: org.postgresql.Driver\n"
                            "  jpa:\n"
                            "    hibernate:\n"
                            "      ddl-auto: validate\n"
                            "    show-sql: false\n"
                        ) + final_content
                        fixed = True

                if fixed or new_lines != lines:
                    return RepairPlan(
                        error=error,
                        strategy=RepairStrategy.DETERMINISTIC,
                        description="Fix Spring application.yml configuration",
                        file_changes={
                            yml_path.relative_to(self.project_dir).as_posix(): final_content,
                        },
                        confidence=0.6,
                    )

        # Handle case where file doesn't exist but error mentions it
        if "driver-class-name" in error.raw_output or "driver-class-name" in error.message:
            yml_path = self.backend_dir / "src" / "main" / "resources" / "application.yml"
            yml_path.parent.mkdir(parents=True, exist_ok=True)
            content = yml_path.read_text() if yml_path.exists() else ""
            if "driver-class-name" not in content:
                # Add or fix driver-class-name
                if "spring:" in content and "datasource:" in content:
                    # Find datasource section and add driver-class-name
                    lines = content.splitlines()
                    for i, line in enumerate(lines):
                        if "datasource:" in line and "driver-class-name" not in content:
                            # Find next non-indented line or end of datasource section
                            insert_idx = i + 1
                            while insert_idx < len(lines) and (lines[insert_idx].startswith("  ") or lines[insert_idx].startswith("\t")):
                                insert_idx += 1
                            lines.insert(insert_idx, "    driver-class-name: org.postgresql.Driver")
                            break
                    return RepairPlan(
                        error=error,
                        strategy=RepairStrategy.DETERMINISTIC,
                        description="Add missing driver-class-name to datasource",
                        file_changes={yml_path.relative_to(self.project_dir).as_posix(): "\n".join(lines)},
                        confidence=0.8,
                    )

        return None

    def _create_jpa_mapping_fix(self, error: BuildError) -> Optional[RepairPlan]:
        """Fix JPA mapping errors."""
        file_path = self._resolve_error_file(error)
        if file_path is None or file_path.suffix != ".java":
            return None

        content = file_path.read_text()
        lines = content.splitlines()

        # Missing @ManyToOne, @OneToMany, @JoinColumn
        if "ManyToOne" in error.message or "OneToMany" in error.message or "JoinColumn" in error.message:
            # Try to add the missing import and annotation
            import_map = {
                "ManyToOne": "jakarta.persistence.ManyToOne",
                "OneToMany": "jakarta.persistence.OneToMany",
                "JoinColumn": "jakarta.persistence.JoinColumn",
            }

            for ann_name, import_path in import_map.items():
                if ann_name in error.message and import_path not in content:
                    # Add import
                    for i, line in enumerate(lines):
                        if line.startswith("package "):
                            lines.insert(i + 1, f"import {import_path};")
                            break

            return RepairPlan(
                error=error,
                strategy=RepairStrategy.DETERMINISTIC,
                description="Add missing JPA relationship annotations and imports",
                file_changes={self._rel_to_project(file_path): "\n".join(lines)},
                confidence=0.6,
            )

        # Unknown mappedBy — resolving this requires cross-entity analysis,
        # so defer to LLM repair rather than reporting a no-op success.
        if "mappedBy" in error.message:
            return None

        # Cascade type issues
        if "cascade" in error.message.lower():
            if "CascadeType" not in content:
                for i, line in enumerate(lines):
                    if line.startswith("package "):
                        lines.insert(i + 1, "import jakarta.persistence.CascadeType;")
                        break
            return RepairPlan(
                error=error,
                strategy=RepairStrategy.DETERMINISTIC,
                description="Add CascadeType import for cascade configuration",
                file_changes={self._rel_to_project(file_path): "\n".join(lines)},
                confidence=0.5,
            )

        return self._create_import_fix(error, "backend")

    def _create_schema_fix(self, error: BuildError) -> Optional[RepairPlan]:
        """Fix database schema errors."""
        return self._get_database_fix(error)

    def _create_react_compile_fix(self, error: BuildError) -> Optional[RepairPlan]:
        """Fix React compilation errors."""
        file_path = self._resolve_error_file(error)
        if file_path is None:
            return None

        content = file_path.read_text()
        lines = content.splitlines()

        # Common React fixes
        if "is not defined" in error.message:
            # Missing import
            match = re.search(r"'(\w+)' is not defined", error.message)
            if match:
                component_name = match.group(1)
                # Try to add import
                if component_name[0].isupper():
                    # Component import
                    import_line = f"import {component_name} from './{component_name}';"
                else:
                    # Hook or utility
                    import_line = f"import {component_name} from '../hooks/{component_name}';"

                # Add after existing imports
                for i, line in enumerate(lines):
                    if line.startswith("import "):
                        continue
                    elif line and not line.startswith("import "):
                        lines.insert(i, import_line)
                        break

                return RepairPlan(
                    error=error,
                    strategy=RepairStrategy.DETERMINISTIC,
                    description=f"Add missing import for {component_name}",
                    file_changes={self._rel_to_project(file_path): "\n".join(lines)},
                    confidence=0.5,
                )

        # Missing React import
        if "React" in error.message and ("is not defined" in error.message or "must be in scope" in error.message):
            if "import React" not in content:
                # Add React import at top
                for i, line in enumerate(lines):
                    if line.startswith("import "):
                        lines.insert(i, "import React from 'react';")
                        break
                else:
                    # No imports found, add at the beginning
                    lines.insert(0, "import React from 'react';")
                return RepairPlan(
                    error=error,
                    strategy=RepairStrategy.DETERMINISTIC,
                    description="Add missing React import",
                    file_changes={self._rel_to_project(file_path): "\n".join(lines)},
                    confidence=0.8,
                )

        # Missing useState, useEffect, etc. hooks
        hook_match = re.search(r"'use(\w+)' is not defined", error.message)
        if hook_match:
            hook_name = f"use{hook_match.group(1)}"
            if f"import {{{hook_name}}}" not in content and f"import {hook_name}" not in content:
                for i, line in enumerate(lines):
                    if "from 'react'" in line:
                        if "{" in line:
                            line = line.replace("}", f", {hook_name}}}")
                        else:
                            line = line.replace("from 'react'", f"{{ {hook_name} }} from 'react'")
                        lines[i] = line
                        break
                else:
                    # Add new import
                    for i, line in enumerate(lines):
                        if line.startswith("import "):
                            lines.insert(i, f"import {{ {hook_name} }} from 'react';")
                            break
                return RepairPlan(
                    error=error,
                    strategy=RepairStrategy.DETERMINISTIC,
                    description=f"Add missing React hook import: {hook_name}",
                    file_changes={self._rel_to_project(file_path): "\n".join(lines)},
                    confidence=0.8,
                )

        # Missing prop types or TypeScript interface — editing an interface
        # safely needs type context, so defer to LLM repair.
        if "Property" in error.message and "does not exist" in error.message:
            return None

        # JSX syntax errors (e.g. unclosed tag) have no safe deterministic
        # rewrite; defer to LLM repair.
        if "expected" in error.message and ("/" in error.message or ">" in error.message):
            return None

        return None

    def _llm_diagnose_error(self, error: BuildError, component: str) -> Optional[RepairPlan]:
        """Use LLM to diagnose and suggest a fix."""
        if not self.llm_provider:
            return None

        try:
            # Get file context if available
            file_context = ""
            if error.file:
                file_path = self._resolve_error_file(error)
                if file_path is not None:
                    content = file_path.read_text()
                    # Show relevant lines around error
                    lines = content.splitlines()
                    start = max(0, (error.line or 1) - 10)
                    end = min(len(lines), (error.line or 1) + 10)
                    file_context = f"\nFile context ({file_path.name}):\n" + "\n".join(
                        f"{i+1:4d}: {lines[i]}" for i in range(start, end)
                    )

            # Build comprehensive prompt
            prompt = f"""You are an expert software engineer fixing build errors in a generated Spring Boot (backend) / React (frontend) application.

Build Error Details:
- Component: {component}
- Error Category: {error.category.value}
- Error Message: {error.message}
- File: {error.file or 'unknown'}
- Line: {error.line or 'unknown'}

Raw Build Output (truncated):
{error.raw_output[:4000]}

{file_context}

Your task: Analyze the error and provide a precise fix.

Respond with ONLY valid JSON in this exact format:
{{
  "fix": "Brief description of the fix (one sentence)",
  "file": "relative/path/to/file.ext",
  "change": "The exact new content for the entire file, OR a shell command starting with 'mvn ', 'npm ', 'npx ', or 'rm '",
  "confidence": 0.0-1.0
}}

Rules:
1. If providing file content, output the COMPLETE new file content (not a diff)
2. If providing a command, it must be a single command array like ["mvn", "dependency:resolve"]
3. Confidence should reflect how certain you are (0.8+ for clear fixes, 0.3-0.5 for speculative)
4. Only suggest fixes for the specific error - don't refactor unrelated code
5. For Java: prefer adding imports, fixing annotations, correcting types
6. For React/TypeScript: prefer adding imports, fixing types, correcting JSX
7. For Maven: prefer dependency fixes, version alignment, plugin config
8. For npm: prefer dependency installs, peer dep resolution, config fixes

No other text - only the JSON."""

            response = self.llm_provider.generate(prompt, json_mode=True)
            import json
            result = json.loads(response.content)

            fix_desc = result.get("fix", "")
            file_path = result.get("file", "")
            change = result.get("change", "")
            confidence = result.get("confidence", 0.3)

            if fix_desc and (file_path or change.startswith(("mvn ", "npm ", "npx ", "rm "))):
                plan = RepairPlan(
                    error=error,
                    strategy=RepairStrategy.LLM_ASSISTED,
                    description=fix_desc,
                    confidence=confidence,
                )

                if file_path:
                    plan.file_changes[file_path] = change
                else:
                    # Parse command
                    plan.commands = [change.split()]

                return plan

        except json.JSONDecodeError:
            # Try one retry with correction
            try:
                retry_prompt = f"""The previous response was invalid JSON. Please respond with ONLY valid JSON matching this schema:
{{
  "fix": "string",
  "file": "string or null",
  "change": "string",
  "confidence": number
}}

Error to fix: {error.message} ({error.category.value})
File: {error.file or 'unknown'}
Output: {error.raw_output[:2000]}"""
                response = self.llm_provider.generate(retry_prompt, json_mode=True)
                result = json.loads(response.content)
                fix_desc = result.get("fix", "")
                file_path = result.get("file", "")
                change = result.get("change", "")
                confidence = result.get("confidence", 0.2)

                if fix_desc and (file_path or change.startswith(("mvn ", "npm ", "npx ", "rm "))):
                    plan = RepairPlan(
                        error=error,
                        strategy=RepairStrategy.LLM_ASSISTED,
                        description=fix_desc,
                        confidence=confidence,
                    )
                    if file_path:
                        plan.file_changes[file_path] = change
                    else:
                        plan.commands = [change.split()]
                    return plan
            except Exception:
                pass

        except Exception:
            pass

        return None

    def _apply_repair_plan(self, plan: RepairPlan, component: str) -> RepairAttempt:
        """Apply a repair plan and return the result."""
        files_changed = []

        try:
            # Apply file changes
            for rel_path, new_content in plan.file_changes.items():
                file_path = self.project_dir / rel_path
                file_path.parent.mkdir(parents=True, exist_ok=True)
                file_path.write_text(new_content, encoding="utf-8")
                files_changed.append(rel_path)

            # Run commands
            for cmd in plan.commands:
                cwd = self.project_dir
                if cmd[0] in ("mvn", "npm", "npx"):
                    if component == "backend" or cmd[0] == "mvn":
                        cwd = self.backend_dir
                    elif component == "frontend" or cmd[0] in ("npm", "npx"):
                        cwd = self.frontend_dir

                # Resolve through PATH so Windows .CMD shims work.
                resolved = resolve_executable(cmd)
                if resolved is None:
                    return RepairAttempt(
                        error_category=plan.error.category,
                        fix_applied=plan.description,
                        strategy=plan.strategy,
                        success=False,
                        output=f"Command not found: {cmd[0]}",
                        files_changed=files_changed,
                        confidence=plan.confidence,
                    )

                result = subprocess.run(
                    resolved,
                    cwd=cwd,
                    capture_output=True,
                    text=True,
                    timeout=120,
                )

                if result.returncode != 0:
                    return RepairAttempt(
                        error_category=plan.error.category,
                        fix_applied=plan.description,
                        strategy=plan.strategy,
                        success=False,
                        output=result.stderr,
                        files_changed=files_changed,
                        confidence=plan.confidence,
                    )

            return RepairAttempt(
                error_category=plan.error.category,
                fix_applied=plan.description,
                strategy=plan.strategy,
                success=True,
                output="Fix applied successfully",
                files_changed=files_changed,
                confidence=plan.confidence,
            )

        except Exception as e:
            return RepairAttempt(
                error_category=plan.error.category,
                fix_applied=plan.description,
                strategy=plan.strategy,
                success=False,
                output=str(e),
                files_changed=files_changed,
                confidence=plan.confidence,
            )

    def _run_tool(
        self,
        cmd: List[str],
        cwd: Path,
        timeout: int = 120,
    ) -> Optional[subprocess.CompletedProcess]:
        """Run a build tool, resolving the executable through PATH.

        Returns ``None`` when the tool is not installed, so callers can
        record a clean "not found" instead of surfacing a FileNotFoundError.
        """
        resolved = resolve_executable(cmd)
        if resolved is None:
            raise FileNotFoundError(f"{cmd[0]} not found")
        return subprocess.run(
            resolved,
            cwd=cwd,
            capture_output=True,
            text=True,
            timeout=timeout,
        )

    def _generate_build_report(self, session: RepairSession) -> None:
        """Generate the migration build report (spec §55, §66).

        Outputs: migration-report/build.json with complete audit trail.
        """
        report_dir = self.project_dir / "migration-report"
        report_dir.mkdir(parents=True, exist_ok=True)

        report_path = report_dir / "build.json"

        # Build comprehensive report structure
        report = {
            "schema_version": "1.0",
            "generated_at": datetime.utcnow().isoformat(),
            "project_dir": str(self.project_dir),
            "session": session.to_dict(),
            "summary": {
                "total_attempts": session.total_attempts,
                "deterministic_attempts": session.deterministic_attempts,
                "llm_attempts": session.llm_attempts,
                "rollbacks": session.rollbacks,
                "final_status": session.final_status,
                "initial_error_counts": session.initial_errors,
                "final_error_counts": session.final_errors,
            },
            "components": session.components,
        }

        report_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
        logger.info(f"Build report written to {report_path}")

    def _generate_dependency_graph(self) -> None:
        """Generate the dependency graph report (spec §58).

        Runs mvn dependency:tree and npm ls --json to capture the
        full resolved dependency graph for the generated project.

        Outputs: generated-dependency-graph.json
        """
        graph = {
            "generated_at": datetime.utcnow().isoformat(),
            "project_dir": str(self.project_dir),
            "backend": {"dependencies": [], "conflicts": []},
            "frontend": {"dependencies": [], "conflicts": []},
        }

        # ---- Backend: Maven dependency tree ----
        if self.backend_dir.exists():
            try:
                # Run mvn dependency:tree for text output
                result = self._run_tool(
                    ["mvn", "dependency:tree", "-DoutputType=text"],
                    cwd=self.backend_dir,
                )
                if result.returncode == 0:
                    graph["backend"]["tree_text"] = result.stdout

                # Also get JSON for structured parsing
                result_json = self._run_tool(
                    ["mvn", "dependency:tree", "-DoutputType=json"],
                    cwd=self.backend_dir,
                )
                if result_json.returncode == 0:
                    try:
                        import json as _json
                        dep_data = _json.loads(result_json.stdout)
                        graph["backend"]["dependencies"] = self._parse_maven_deps(dep_data)
                    except _json.JSONDecodeError:
                        pass

                # Run dependency:analyze for convergence conflicts
                result_analyze = self._run_tool(
                    ["mvn", "dependency:analyze"],
                    cwd=self.backend_dir,
                )
                if "conflicts" in result_analyze.stdout.lower() or result_analyze.returncode != 0:
                    # Parse conflicts from output
                    conflicts = self._parse_maven_conflicts(result_analyze.stdout + result_analyze.stderr)
                    graph["backend"]["conflicts"] = conflicts

            except subprocess.TimeoutExpired:
                graph["backend"]["error"] = "Maven dependency analysis timed out"
            except FileNotFoundError:
                graph["backend"]["error"] = "Maven not found"
            except Exception as e:
                graph["backend"]["error"] = str(e)

        # ---- Frontend: npm dependency tree ----
        if self.frontend_dir.exists():
            try:
                # Get full dependency tree as JSON
                result = self._run_tool(
                    ["npm", "ls", "--json", "--all", "--depth=999"],
                    cwd=self.frontend_dir,
                )
                # npm ls exits non-zero on peer dep issues but still outputs JSON
                if result.stdout:
                    try:
                        dep_data = json.loads(result.stdout)
                        graph["frontend"]["dependencies"] = self._parse_npm_deps(dep_data)
                    except json.JSONDecodeError:
                        graph["frontend"]["raw_output"] = result.stdout[:5000]

                # Also capture peer dependency conflicts
                if result.returncode != 0:
                    conflicts = self._parse_npm_conflicts(result.stderr + result.stdout)
                    graph["frontend"]["conflicts"] = conflicts

            except subprocess.TimeoutExpired:
                graph["frontend"]["error"] = "npm dependency analysis timed out"
            except FileNotFoundError:
                graph["frontend"]["error"] = "npm not found"
            except Exception as e:
                graph["frontend"]["error"] = str(e)

        # Write the graph
        graph_path = self.project_dir / "generated-dependency-graph.json"
        graph_path.write_text(json.dumps(graph, indent=2), encoding="utf-8")
        logger.info(f"Dependency graph written to {graph_path}")

    def _parse_maven_deps(self, dep_data: dict) -> list[dict]:
        """Parse Maven dependency tree JSON into structured format."""
        deps = []
        if not isinstance(dep_data, dict):
            return deps

        def walk(node: dict, depth: int = 0):
            if not isinstance(node, dict):
                return
            dep = {
                "groupId": node.get("groupId", ""),
                "artifactId": node.get("artifactId", ""),
                "version": node.get("version", ""),
                "scope": node.get("scope", "compile"),
                "depth": depth,
            }
            deps.append(dep)
            children = node.get("children", [])
            for child in children:
                walk(child, depth + 1)

        walk(dep_data)
        return deps

    def _parse_maven_conflicts(self, output: str) -> list[dict]:
        """Parse Maven dependency convergence conflicts from output."""
        conflicts = []
        import re
        # Look for convergence warnings
        # Pattern: "Dependency convergence error for groupId:artifactId:version"
        pattern = re.compile(
            r'(?:conflict|convergence)[^\n]*?([a-zA-Z0-9_.-]+):([a-zA-Z0-9_.-]+):([a-zA-Z0-9_.-]+)',
            re.IGNORECASE,
        )
        for match in pattern.finditer(output):
            conflicts.append({
                "groupId": match.group(1),
                "artifactId": match.group(2),
                "version": match.group(3),
            })
        return conflicts

    def _parse_npm_deps(self, dep_data: dict) -> list[dict]:
        """Parse npm ls JSON into structured format."""
        deps = []
        if not isinstance(dep_data, dict):
            return deps

        dependencies = dep_data.get("dependencies", {})
        for name, info in dependencies.items():
            if not isinstance(info, dict):
                continue
            dep = {
                "name": name,
                "version": info.get("version", ""),
                "resolved": info.get("resolved", ""),
                "dev": info.get("dev", False),
                "optional": info.get("optional", False),
                "dependencies": list(info.get("dependencies", {}).keys()) if info.get("dependencies") else [],
            }
            deps.append(dep)
            # Recurse into sub-dependencies
            if info.get("dependencies"):
                deps.extend(self._parse_npm_deps({"dependencies": info["dependencies"]}))
        return deps

    def _parse_npm_conflicts(self, output: str) -> list[dict]:
        """Parse npm peer dependency conflicts from output."""
        conflicts = []
        import re
        # Pattern: npm ERR! ERESOLVE unable to resolve dependency tree
        # or: npm ERR! peer dep missing: package@version
        peer_pattern = re.compile(r'peer dep (?:missing|conflict):\s*([^\s@]+)@([^\s]+)', re.IGNORECASE)
        for match in peer_pattern.finditer(output):
            conflicts.append({
                "package": match.group(1),
                "required": match.group(2),
                "type": "peer_conflict",
            })

        # Also look for ERESOLVE
        if "ERESOLVE" in output:
            # Try to extract packages from ERESOLVE message
            eresolve_pattern = re.compile(r'([a-zA-Z0-9_.-]+)@([a-zA-Z0-9_.-]+)')
            for match in eresolve_pattern.finditer(output):
                conflicts.append({
                    "package": match.group(1),
                    "version": match.group(2),
                    "type": "eresolve",
                })
        return conflicts


def repair_project(project_dir: str | Path, llm_provider=None) -> dict:
    """Entry point to repair a project (legacy dict interface)."""
    repair = BuildRepair(Path(project_dir), llm_provider)
    return repair.repair_all()


def repair_loop(project_dir: str | Path, llm_provider=None) -> RepairSession:
    """Entry point using the full repair loop (spec §35).

    Returns a ``RepairSession`` with the complete audit trail,
    build report, and dependency graph.
    """
    repair = BuildRepair(Path(project_dir), llm_provider)
    return repair.repair_loop()