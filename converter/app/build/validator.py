"""Build Validation Pipeline - spec section 33.

Validates generated projects by:
- Building backend with Maven
- Building frontend with npm
- Running database migrations
- Executing tests
"""
from __future__ import annotations

import json
import re
import subprocess
import shutil
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Optional


class BuildStatus(str, Enum):
    PENDING = "PENDING"
    RUNNING = "RUNNING"
    SUCCESS = "SUCCESS"
    FAILED = "FAILED"
    SKIPPED = "SKIPPED"


class ErrorCategory(str, Enum):
    """Build error categories - spec section 34."""
    MISSING_DEPENDENCY = "MISSING_DEPENDENCY"
    DEPENDENCY_VERSION_MISMATCH = "DEPENDENCY_VERSION_MISMATCH"
    DEPENDENCY_CONVERGENCE = "DEPENDENCY_CONVERGENCE"
    PEER_DEPENDENCY_CONFLICT = "PEER_DEPENDENCY_CONFLICT"
    JAVA_VERSION_MISMATCH = "JAVA_VERSION_MISMATCH"
    NODE_VERSION_MISMATCH = "NODE_VERSION_MISMATCH"
    API_INCOMPATIBILITY = "API_INCOMPATIBILITY"
    IMPORT_FAILURE = "IMPORT_FAILURE"
    TYPE_MISMATCH = "TYPE_MISMATCH"
    ANNOTATION_MISMATCH = "ANNOTATION_MISMATCH"
    SPRING_CONFIG_ERROR = "SPRING_CONFIG_ERROR"
    SCHEMA_ERROR = "SCHEMA_ERROR"
    SQL_SYNTAX_ERROR = "SQL_SYNTAX_ERROR"
    JPA_MAPPING_ERROR = "JPA_MAPPING_ERROR"
    REACT_COMPILE_ERROR = "REACT_COMPILE_ERROR"
    ENVIRONMENT_ERROR = "ENVIRONMENT_ERROR"
    GENERATED_CODE_ERROR = "GENERATED_CODE_ERROR"
    UNKNOWN = "UNKNOWN"


def normalize_reported_path(raw: Optional[str]) -> Optional[str]:
    """Normalize a file path as reported by a build tool.

    Maven on Windows prints compiler diagnostics with a URI-style leading
    slash (``/C:/Users/...``).  ``Path("/C:/...").exists()`` is False and
    ``is_absolute()`` is False, so every file-based repair plan silently
    bailed out and no fix was ever applied.  Strip the spurious prefix so
    the path resolves.
    """
    if not raw:
        return raw
    candidate = raw.strip()
    # /C:/Users/... or \C:\Users\...  ->  C:/Users/...
    if re.match(r'^[/\\][A-Za-z]:[/\\]', candidate):
        candidate = candidate[1:]
    return candidate


def resolve_executable(command: list[str]) -> Optional[list[str]]:
    """Resolve ``command[0]`` to an absolute path via PATH lookup.

    On Windows the Maven and npm entry points are ``mvn.CMD`` / ``npm.CMD``
    batch shims.  ``subprocess.run(["mvn", ...])`` does not consult PATHEXT,
    so it raises ``FileNotFoundError`` even when Maven is installed and on
    PATH.  Resolving the name to its full path first makes the same call
    work identically on Windows and POSIX.

    Returns the command with an absolute executable, or ``None`` if the
    executable is genuinely not installed.
    """
    if not command:
        return None
    resolved = shutil.which(command[0])
    if resolved is None:
        return None
    return [resolved, *command[1:]]


@dataclass
class BuildError:
    """A build error with classification."""
    category: ErrorCategory
    message: str
    file: Optional[str] = None
    line: Optional[int] = None
    raw_output: str = ""
    suggested_fix: Optional[str] = None


@dataclass
class BuildResult:
    """Result of a build operation."""
    status: BuildStatus
    output: str = ""
    errors: list[BuildError] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    duration_seconds: float = 0.0


class BuildValidator:
    """Validates generated projects."""

    def __init__(self, project_dir: Path):
        self.project_dir = Path(project_dir)
        self.backend_dir = self.project_dir / "backend"
        self.frontend_dir = self.project_dir / "frontend"
        self.database_dir = self.project_dir / "database"

    def validate_all(self) -> dict[str, BuildResult]:
        """Run all validations.

        A missing toolchain no longer aborts the whole run.  Previously an
        environment failure returned immediately, so ``backend`` /
        ``frontend`` / ``database`` were never validated — which left the
        repair loop with no errors to fix and made a broken project look
        clean.  Now each component is skipped only if *its own* toolchain
        is unavailable; everything else still validates and stays
        repairable (spec §30, §31, §33).
        """
        results = {}

        # Check environment (reported, but not fatal on its own)
        env_check = self.check_environment()
        results["environment"] = env_check

        has_maven = resolve_executable(["mvn"]) is not None
        has_npm = resolve_executable(["npm"]) is not None

        # Build backend
        if self.backend_dir.exists():
            if has_maven:
                results["backend"] = self.build_backend()
            else:
                results["backend"] = BuildResult(
                    status=BuildStatus.SKIPPED,
                    output="Maven not available - backend build skipped",
                )

        # Build frontend
        if self.frontend_dir.exists():
            if has_npm:
                results["frontend"] = self.build_frontend()
            else:
                results["frontend"] = BuildResult(
                    status=BuildStatus.SKIPPED,
                    output="npm not available - frontend build skipped",
                )

        # Validate database schema (pure file inspection, no toolchain)
        if self.database_dir.exists():
            results["database"] = self.validate_database()

        return results

    def check_environment(self) -> BuildResult:
        """Check that required tools are available."""
        errors = []
        output_lines = []

        # Check Java
        java_result = self._run_command(["java", "-version"], check=False)
        output_lines.append(f"Java: {java_result.output.split()[0] if java_result.output else 'NOT FOUND'}")
        if java_result.status == BuildStatus.FAILED:
            errors.append(BuildError(
                category=ErrorCategory.ENVIRONMENT_ERROR,
                message="Java not found. Install Java 17+ to build the backend.",
            ))

        # Check Maven
        mvn_result = self._run_command(["mvn", "-version"], check=False)
        output_lines.append(f"Maven: {'OK' if mvn_result.status == BuildStatus.SUCCESS else 'NOT FOUND'}")
        if mvn_result.status == BuildStatus.FAILED:
            errors.append(BuildError(
                category=ErrorCategory.ENVIRONMENT_ERROR,
                message="Maven not found. Install Maven 3.6+ to build the backend.",
            ))

        # Check Node
        node_result = self._run_command(["node", "--version"], check=False)
        output_lines.append(f"Node: {node_result.output.strip() if node_result.output else 'NOT FOUND'}")
        if node_result.status == BuildStatus.FAILED:
            errors.append(BuildError(
                category=ErrorCategory.ENVIRONMENT_ERROR,
                message="Node.js not found. Install Node 20+ to build the frontend.",
            ))

        # Check npm
        npm_result = self._run_command(["npm", "--version"], check=False)
        output_lines.append(f"npm: {npm_result.output.strip() if npm_result.output else 'NOT FOUND'}")

        return BuildResult(
            status=BuildStatus.FAILED if errors else BuildStatus.SUCCESS,
            output="\n".join(output_lines),
            errors=errors,
        )

    def build_backend(self) -> BuildResult:
        """Build the backend with Maven."""
        if not self.backend_dir.exists():
            return BuildResult(status=BuildStatus.SKIPPED, output="Backend directory not found")

        # Run Maven compile
        result = self._run_command(
            ["mvn", "clean", "compile", "-DskipTests"],
            cwd=self.backend_dir,
        )

        if result.status == BuildStatus.FAILED:
            result.errors = self._classify_maven_errors(result.output)

        return result

    def build_frontend(self) -> BuildResult:
        """Build the frontend with npm."""
        if not self.frontend_dir.exists():
            return BuildResult(status=BuildStatus.SKIPPED, output="Frontend directory not found")

        # Install dependencies
        install_result = self._run_command(
            ["npm", "ci"],
            cwd=self.frontend_dir,
        )

        if install_result.status == BuildStatus.FAILED:
            install_result.errors = self._classify_npm_errors(install_result.output)
            return install_result

        # Build
        build_result = self._run_command(
            ["npm", "run", "build"],
            cwd=self.frontend_dir,
        )

        if build_result.status == BuildStatus.FAILED:
            build_result.errors = self._classify_npm_errors(build_result.output)

        return build_result

    def validate_database(self) -> BuildResult:
        """Validate database schema."""
        schema_file = self.database_dir / "schema.sql"

        if not schema_file.exists():
            return BuildResult(status=BuildStatus.SKIPPED, output="Schema file not found")

        content = schema_file.read_text()
        errors = []

        # Basic SQL validation
        # Check for unbalanced parentheses
        if content.count("(") != content.count(")"):
            errors.append(BuildError(
                category=ErrorCategory.SQL_SYNTAX_ERROR,
                message="Unbalanced parentheses in schema",
            ))

        # Check for common issues
        if "undefined" in content.lower():
            errors.append(BuildError(
                category=ErrorCategory.SQL_SYNTAX_ERROR,
                message="Schema contains 'undefined' values",
            ))

        return BuildResult(
            status=BuildStatus.FAILED if errors else BuildStatus.SUCCESS,
            output=f"Schema validated: {len(content.splitlines())} lines",
            errors=errors,
        )

    def run_backend_tests(self) -> BuildResult:
        """Run backend tests."""
        if not self.backend_dir.exists():
            return BuildResult(status=BuildStatus.SKIPPED)

        result = self._run_command(
            ["mvn", "test"],
            cwd=self.backend_dir,
        )

        if result.status == BuildStatus.FAILED:
            result.errors = self._classify_maven_errors(result.output)

        return result

    def _run_command(
        self,
        command: list[str],
        cwd: Optional[Path] = None,
        timeout: int = 300,
        check: bool = True,
    ) -> BuildResult:
        """Run a shell command."""
        import time
        start = time.time()

        # Resolve the executable through PATH so Windows .CMD shims
        # (mvn.CMD, npm.CMD) are found the same way they are on POSIX.
        resolved = resolve_executable(command)
        if resolved is None:
            return BuildResult(
                status=BuildStatus.FAILED,
                output=f"Command not found: {command[0]}",
                errors=[BuildError(
                    category=ErrorCategory.ENVIRONMENT_ERROR,
                    message=f"Command not found: {command[0]}",
                )],
            )

        try:
            result = subprocess.run(
                resolved,
                cwd=cwd or self.project_dir,
                capture_output=True,
                text=True,
                timeout=timeout,
            )

            output = result.stdout + "\n" + result.stderr
            duration = time.time() - start

            if result.returncode == 0:
                return BuildResult(
                    status=BuildStatus.SUCCESS,
                    output=output,
                    duration_seconds=duration,
                )
            else:
                return BuildResult(
                    status=BuildStatus.FAILED,
                    output=output,
                    duration_seconds=duration,
                )

        except subprocess.TimeoutExpired:
            return BuildResult(
                status=BuildStatus.FAILED,
                output="Command timed out",
                errors=[BuildError(
                    category=ErrorCategory.ENVIRONMENT_ERROR,
                    message=f"Command timed out after {timeout} seconds",
                )],
            )
        except FileNotFoundError:
            return BuildResult(
                status=BuildStatus.FAILED,
                output=f"Command not found: {command[0]}",
                errors=[BuildError(
                    category=ErrorCategory.ENVIRONMENT_ERROR,
                    message=f"Command not found: {command[0]}",
                )],
            )

    def _classify_maven_errors(self, output: str) -> list[BuildError]:
        """Classify Maven build errors."""
        errors = []

        # Dependency errors
        if "Could not resolve dependencies" in output:
            errors.append(BuildError(
                category=ErrorCategory.MISSING_DEPENDENCY,
                message="Maven could not resolve dependencies",
                raw_output=output,
            ))

        # Could not find artifact
        artifact_pattern = re.compile(r'Could not find artifact\s+([^:]+):([^:]+):([^:]+)')
        for match in artifact_pattern.finditer(output):
            errors.append(BuildError(
                category=ErrorCategory.MISSING_DEPENDENCY,
                message=f"Missing artifact: {match.group(1)}:{match.group(2)}:{match.group(3)}",
                raw_output=output,
                suggested_fix=f"Add dependency to pom.xml or check repository configuration",
            ))

        # Version mismatch
        if "version mismatch" in output.lower():
            errors.append(BuildError(
                category=ErrorCategory.DEPENDENCY_VERSION_MISMATCH,
                message="Dependency version mismatch detected",
                raw_output=output,
            ))

        # Dependency convergence
        if "dependency convergence" in output.lower() or "conflicts with" in output.lower():
            errors.append(BuildError(
                category=ErrorCategory.DEPENDENCY_CONVERGENCE,
                message="Dependency convergence conflict",
                raw_output=output,
                suggested_fix="Run 'mvn dependency:tree' to analyze and add dependencyManagement",
            ))

        # Java version.
        # Match the strings Maven/javac actually emit.  The previous check
        # looked for "unsupported class version", which is not a real
        # message, and was case-sensitive — so genuine Java version
        # failures were misclassified as UNKNOWN and never repaired.
        lowered = output.lower()
        java_version_markers = (
            "invalid target release",
            "invalid source release",
            "unsupported class file major version",
            "unsupportedclassversionerror",
            "has been compiled by a more recent version",
            "release version",
            "class file has wrong version",
        )
        if any(marker in lowered for marker in java_version_markers):
            errors.append(BuildError(
                category=ErrorCategory.JAVA_VERSION_MISMATCH,
                message="Java version mismatch",
                raw_output=output,
            ))

        # Spring configuration errors
        if "application.yml" in output or "application.properties" in output:
            if "cannot resolve" in output.lower() or "invalid" in output.lower() or "yaml" in output.lower():
                errors.append(BuildError(
                    category=ErrorCategory.SPRING_CONFIG_ERROR,
                    message="Spring configuration error in application.yml/properties",
                    raw_output=output,
                ))

        # Plugin errors
        if "plugin" in output.lower() and ("execution" in output.lower() or "goal" in output.lower()):
            if "failed" in output.lower() or "error" in output.lower():
                errors.append(BuildError(
                    category=ErrorCategory.GENERATED_CODE_ERROR,
                    message="Maven plugin execution failed",
                    raw_output=output,
                    suggested_fix="Check plugin configuration in pom.xml",
                ))

        # Test failures
        test_failure_pattern = re.compile(r'\[ERROR\] (.*?Test.*?\.java):\[(\d+),(\d+)\] (.+)')
        for match in test_failure_pattern.finditer(output):
            errors.append(BuildError(
                category=ErrorCategory.GENERATED_CODE_ERROR,
                message=f"Test failure: {match.group(4)}",
                file=normalize_reported_path(match.group(1)),
                line=int(match.group(2)),
                raw_output=output,
            ))

        # Surefire/Failsafe test failures
        if "Tests run:" in output and ("Failures:" in output or "Errors:" in output):
            if "FAILURE" in output or "BUILD FAILURE" in output:
                errors.append(BuildError(
                    category=ErrorCategory.GENERATED_CODE_ERROR,
                    message="Test failures detected in Maven surefire/failsafe",
                    raw_output=output,
                    suggested_fix="Run 'mvn test' to see detailed test output",
                ))

        # Compilation errors (general).
        # "cannot find symbol" is classified as IMPORT_FAILURE so the
        # import-repair path can handle it.  Previously this generic branch
        # tagged everything GENERATED_CODE_ERROR and won the race against
        # the dedicated symbol pattern below, so missing imports — the most
        # common generated-code defect — were never repaired.
        compile_pattern = re.compile(r'\[ERROR\] (.*?\.java):\[(\d+),(\d+)\] (.+)')
        for match in compile_pattern.finditer(output):
            file_path = normalize_reported_path(match.group(1))
            line_no = int(match.group(2))
            detail = match.group(4).strip()

            # Avoid duplicate test errors
            if any(e.file == file_path and e.line == line_no for e in errors):
                continue

            if "cannot find symbol" in detail.lower():
                category = ErrorCategory.IMPORT_FAILURE
                # Recover the symbol name from the following
                # "symbol: class List" / "symbol: variable foo" line.
                symbol_match = re.search(
                    r'symbol:\s*(?:class|interface|variable|method|enum)?\s*(\w+)',
                    output,
                )
                if symbol_match:
                    detail = f"cannot find symbol: {symbol_match.group(1)}"
            else:
                category = ErrorCategory.GENERATED_CODE_ERROR

            errors.append(BuildError(
                category=category,
                message=detail,
                file=file_path,
                line=line_no,
                raw_output=output,
            ))

        # Cannot find symbol
        symbol_pattern = re.compile(r'cannot find symbol\s*\n\s*symbol:\s*(\w+)\s*\n\s*location:\s*(.+)')
        for match in symbol_pattern.finditer(output):
            errors.append(BuildError(
                category=ErrorCategory.IMPORT_FAILURE,
                message=f"Cannot find symbol: {match.group(1)} in {match.group(2)}",
                raw_output=output,
            ))

        # Missing annotations / JPA issues
        if "identifier expected" in output or "Annotation" in output and "error" in output.lower():
            errors.append(BuildError(
                category=ErrorCategory.ANNOTATION_MISMATCH,
                message="Annotation or JPA mapping error",
                raw_output=output,
            ))

        # JPA/Entity mapping errors
        if "entity" in output.lower() and ("mapping" in output.lower() or "not a managed type" in output.lower()):
            errors.append(BuildError(
                category=ErrorCategory.JPA_MAPPING_ERROR,
                message="JPA entity mapping error",
                raw_output=output,
            ))

        # SQL syntax errors from schema validation
        if "sql" in output.lower() and ("syntax" in output.lower() or "error" in output.lower()):
            errors.append(BuildError(
                category=ErrorCategory.SQL_SYNTAX_ERROR,
                message="SQL syntax error in schema or migration",
                raw_output=output,
            ))

        # API incompatibility - spec section 34 category 7
        if any(pattern in output for pattern in [
            "NoSuchMethodError", "AbstractMethodError", "NoClassDefFoundError",
            "IncompatibleClassChangeError", "MethodNotFoundException",
        ]):
            method_match = re.search(
                r'(NoSuchMethodError|AbstractMethodError|NoClassDefFoundError):\s*(.+)',
                output,
            )
            msg = method_match.group(2).strip() if method_match else "API incompatibility detected"
            errors.append(BuildError(
                category=ErrorCategory.API_INCOMPATIBILITY,
                message=f"API incompatibility: {msg[:200]}",
                raw_output=output,
                suggested_fix="Check dependency version compatibility with the compatibility matrix",
            ))

        # Missing main class
        if "main class" in output.lower() and "not found" in output.lower():
            errors.append(BuildError(
                category=ErrorCategory.GENERATED_CODE_ERROR,
                message="Main class not found",
                raw_output=output,
                suggested_fix="Check Spring Boot main class annotation and package structure",
            ))

        if not errors:
            errors.append(BuildError(
                category=ErrorCategory.UNKNOWN,
                message="Build failed with unknown error",
                raw_output=output[:500],
            ))

        return errors

    def _classify_npm_errors(self, output: str) -> list[BuildError]:
        """Classify npm build errors."""
        errors = []

        # Peer dependency conflicts
        if "ERESOLVE" in output or "peer dep" in output.lower():
            errors.append(BuildError(
                category=ErrorCategory.PEER_DEPENDENCY_CONFLICT,
                message="npm peer dependency conflict",
                raw_output=output,
                suggested_fix="Try: npm ci --legacy-peer-deps",
            ))

        # Module not found
        module_not_found_pattern = re.compile(r"Module not found: Error: Can't resolve '([^']+)'")
        for match in module_not_found_pattern.finditer(output):
            errors.append(BuildError(
                category=ErrorCategory.MISSING_DEPENDENCY,
                message=f"Module not found: {match.group(1)}",
                raw_output=output,
                suggested_fix=f"Run: npm install {match.group(1)}",
            ))

        if "Module not found" in output and not any(e.category == ErrorCategory.MISSING_DEPENDENCY for e in errors):
            errors.append(BuildError(
                category=ErrorCategory.MISSING_DEPENDENCY,
                message="Module not found",
                raw_output=output,
            ))

        # Node version
        if "engine" in output.lower() and "node" in output.lower():
            errors.append(BuildError(
                category=ErrorCategory.NODE_VERSION_MISMATCH,
                message="Node version does not match requirements",
                raw_output=output,
            ))

        # TypeScript compilation errors
        ts_error_pattern = re.compile(r'ERROR in ([^:]+):(\d+):(\d+)\s+TS(\d+):\s+(.+)')
        for match in ts_error_pattern.finditer(output):
            errors.append(BuildError(
                category=ErrorCategory.REACT_COMPILE_ERROR,
                message=f"TypeScript error TS{match.group(4)}: {match.group(5)}",
                file=match.group(1),
                line=int(match.group(2)),
                raw_output=output,
            ))

        # General TypeScript errors
        if "TS2" in output or "TS1" in output or "TypeScript" in output:
            if "error TS" in output:
                if not any(e.category == ErrorCategory.REACT_COMPILE_ERROR for e in errors):
                    errors.append(BuildError(
                        category=ErrorCategory.REACT_COMPILE_ERROR,
                        message="TypeScript compilation error",
                        raw_output=output,
                        suggested_fix="Run 'npm run build' or 'tsc --noEmit' to see full TypeScript errors",
                    ))

        # ESLint errors
        if "eslint" in output.lower() and ("error" in output.lower() or "warn" in output.lower()):
            if "error" in output.lower():
                errors.append(BuildError(
                    category=ErrorCategory.REACT_COMPILE_ERROR,
                    message="ESLint error detected",
                    raw_output=output,
                    suggested_fix="Run 'npm run lint' to see ESLint errors, or 'npm run lint -- --fix' to auto-fix",
                ))

        # Vite build errors
        if "vite" in output.lower() and ("error" in output.lower() or "failed" in output.lower()):
            if not any(e.category == ErrorCategory.REACT_COMPILE_ERROR for e in errors):
                errors.append(BuildError(
                    category=ErrorCategory.REACT_COMPILE_ERROR,
                    message="Vite build error",
                    raw_output=output,
                ))

        # React specific errors
        if "react" in output.lower() and ("is not defined" in output or "not found" in output):
            errors.append(BuildError(
                category=ErrorCategory.REACT_COMPILE_ERROR,
                message="React component/reference error",
                raw_output=output,
                suggested_fix="Check imports and component names",
            ))

        # Missing script
        if "missing script" in output.lower():
            errors.append(BuildError(
                category=ErrorCategory.GENERATED_CODE_ERROR,
                message="npm script not found in package.json",
                raw_output=output,
                suggested_fix="Check package.json scripts section",
            ))

        # Package.json parse errors
        if "package.json" in output and ("json" in output.lower() and ("parse" in output.lower() or "syntax" in output.lower() or "unexpected" in output.lower())):
            errors.append(BuildError(
                category=ErrorCategory.GENERATED_CODE_ERROR,
                message="package.json syntax error",
                raw_output=output,
            ))

        # Out of memory
        if "javascript heap out of memory" in output.lower() or "out of memory" in output.lower():
            errors.append(BuildError(
                category=ErrorCategory.ENVIRONMENT_ERROR,
                message="Node.js out of memory during build",
                raw_output=output,
                suggested_fix="Increase Node memory: NODE_OPTIONS='--max-old-space-size=4096' npm run build",
            ))

        if not errors:
            errors.append(BuildError(
                category=ErrorCategory.UNKNOWN,
                message="npm build failed",
                raw_output=output[:500],
            ))

        return errors

    # ============================================================
    # Dependency analysis utilities (spec §27, §28)
    # ============================================================

    def run_dependency_tree(self) -> BuildResult:
        """Run mvn dependency:tree and return parsed output.

        Used by the repair engine for convergence analysis and
        generating the dependency graph report (spec §58).
        """
        if not self.backend_dir.exists():
            return BuildResult(status=BuildStatus.SKIPPED, output="Backend directory not found")

        return self._run_command(
            ["mvn", "dependency:tree", "-DoutputType=text"],
            cwd=self.backend_dir,
        )

    def run_frontend_audit(self) -> BuildResult:
        """Run npm ls --json to get the full frontend dependency tree.

        Used for peer-dependency analysis and generating the
        dependency graph report (spec §58).
        """
        if not self.frontend_dir.exists():
            return BuildResult(status=BuildStatus.SKIPPED, output="Frontend directory not found")

        return self._run_command(
            ["npm", "ls", "--json", "--all"],
            cwd=self.frontend_dir,
            check=False,  # npm ls exits non-zero on peer dep issues
        )

    @staticmethod
    def count_errors(result: BuildResult) -> int:
        """Return the total error count from a BuildResult.

        Used by the repair loop for regression detection: if a patch
        increases the error count, the patch is reverted (spec §59).
        """
        return len(result.errors)


def validate_project(project_dir: str | Path) -> dict[str, Any]:
    """Validate a generated project."""
    validator = BuildValidator(Path(project_dir))
    results = validator.validate_all()

    return {
        "status": "success" if all(r.status == BuildStatus.SUCCESS for r in results.values()) else "failed",
        "results": {
            name: {
                "status": result.status.value,
                "errors": [{"category": e.category.value, "message": e.message} for e in result.errors],
                "warnings": result.warnings,
                "duration": result.duration_seconds,
            }
            for name, result in results.items()
        },
    }
