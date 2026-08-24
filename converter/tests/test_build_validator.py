"""Tests for build validation pipeline."""
from __future__ import annotations

import pytest
import pytest_asyncio
from pathlib import Path
import tempfile
import shutil
from unittest.mock import AsyncMock, MagicMock, patch

from converter.app.build.validator import (
    BuildValidator,
    BuildStatus,
    ErrorCategory,
    BuildError,
    BuildResult,
    validate_project,
)
from converter.app.build.pipeline import (
    BuildValidator as PipelineBuildValidator,
    BuildPhase,
    BuildStatus as PipelineBuildStatus,
    BuildStepResult,
    validate_generated_project,
    attempt_build_repair,
)


class TestBuildValidator:
    """Test the BuildValidator class."""

    @pytest.fixture
    def temp_project_dir(self):
        """Create a temporary project directory structure."""
        with tempfile.TemporaryDirectory() as tmpdir:
            project_dir = Path(tmpdir)
            # Create backend, frontend, database directories
            (project_dir / "backend").mkdir()
            (project_dir / "frontend").mkdir()
            (project_dir / "database").mkdir()
            yield project_dir

    def test_init(self, temp_project_dir):
        """Test BuildValidator initialization."""
        validator = BuildValidator(temp_project_dir)
        assert validator.project_dir == temp_project_dir
        assert validator.backend_dir == temp_project_dir / "backend"
        assert validator.frontend_dir == temp_project_dir / "frontend"
        assert validator.database_dir == temp_project_dir / "database"

    def test_check_environment_java_not_found(self, temp_project_dir):
        """Test environment check when Java is not found."""
        validator = BuildValidator(temp_project_dir)

        with patch.object(validator, '_run_command') as mock_run:
            # Java not found
            mock_run.side_effect = [
                BuildResult(status=BuildStatus.FAILED, output=""),
                BuildResult(status=BuildStatus.SUCCESS, output="Apache Maven 3.9.0"),
                BuildResult(status=BuildStatus.SUCCESS, output="v20.0.0"),
                BuildResult(status=BuildStatus.SUCCESS, output="10.0.0"),
            ]

            result = validator.check_environment()
            assert result.status == BuildStatus.FAILED
            assert any(e.category == ErrorCategory.ENVIRONMENT_ERROR for e in result.errors)

    def test_check_environment_all_ok(self, temp_project_dir):
        """Test environment check when all tools are available."""
        validator = BuildValidator(temp_project_dir)

        with patch.object(validator, '_run_command') as mock_run:
            mock_run.side_effect = [
                BuildResult(status=BuildStatus.SUCCESS, output="openjdk version 17"),
                BuildResult(status=BuildStatus.SUCCESS, output="Apache Maven 3.9.0"),
                BuildResult(status=BuildStatus.SUCCESS, output="v20.0.0"),
                BuildResult(status=BuildStatus.SUCCESS, output="10.0.0"),
            ]

            result = validator.check_environment()
            assert result.status == BuildStatus.SUCCESS
            assert len(result.errors) == 0

    def test_build_backend_skipped_when_missing(self, temp_project_dir):
        """Test backend build is skipped when directory missing."""
        validator = BuildValidator(temp_project_dir)
        shutil.rmtree(validator.backend_dir)

        result = validator.build_backend()
        assert result.status == BuildStatus.SKIPPED

    def test_build_frontend_skipped_when_missing(self, temp_project_dir):
        """Test frontend build is skipped when directory missing."""
        validator = BuildValidator(temp_project_dir)
        shutil.rmtree(validator.frontend_dir)

        result = validator.build_frontend()
        assert result.status == BuildStatus.SKIPPED

    def test_validate_database_skipped_when_missing(self, temp_project_dir):
        """Test database validation is skipped when directory missing."""
        validator = BuildValidator(temp_project_dir)
        shutil.rmtree(validator.database_dir)

        result = validator.validate_database()
        assert result.status == BuildStatus.SKIPPED

    def test_validate_database_balanced_parentheses(self, temp_project_dir):
        """Test database validation catches unbalanced parentheses."""
        validator = BuildValidator(temp_project_dir)
        schema_file = validator.database_dir / "schema.sql"
        schema_file.write_text("CREATE TABLE test (id INT;")

        result = validator.validate_database()
        assert result.status == BuildStatus.FAILED
        assert any(e.category == ErrorCategory.SQL_SYNTAX_ERROR for e in result.errors)

    def test_validate_database_undefined_values(self, temp_project_dir):
        """Test database validation catches undefined values."""
        validator = BuildValidator(temp_project_dir)
        schema_file = validator.database_dir / "schema.sql"
        schema_file.write_text("CREATE TABLE test (id INT PRIMARY KEY);")

        result = validator.validate_database()
        assert result.status == BuildStatus.SUCCESS

    def test_validate_database_undefined_fails(self, temp_project_dir):
        """Test database validation fails on undefined."""
        validator = BuildValidator(temp_project_dir)
        schema_file = validator.database_dir / "schema.sql"
        schema_file.write_text("CREATE TABLE test (id UNDEFINED);")

        result = validator.validate_database()
        assert result.status == BuildStatus.FAILED
        assert any(e.category == ErrorCategory.SQL_SYNTAX_ERROR for e in result.errors)

    def test_classify_maven_errors_missing_dependency(self, temp_project_dir):
        """Test Maven error classification for missing dependency."""
        validator = BuildValidator(temp_project_dir)
        output = "Could not resolve dependencies for project"
        errors = validator._classify_maven_errors(output)
        assert any(e.category == ErrorCategory.MISSING_DEPENDENCY for e in errors)

    def test_classify_maven_errors_version_mismatch(self, temp_project_dir):
        """Test Maven error classification for version mismatch."""
        validator = BuildValidator(temp_project_dir)
        output = "dependency version mismatch detected"
        errors = validator._classify_maven_errors(output)
        assert any(e.category == ErrorCategory.DEPENDENCY_VERSION_MISMATCH for e in errors)

    def test_classify_maven_errors_java_version(self, temp_project_dir):
        """Test Maven error classification for Java version mismatch."""
        validator = BuildValidator(temp_project_dir)
        output = "invalid source release 21"
        errors = validator._classify_maven_errors(output)
        assert any(e.category == ErrorCategory.JAVA_VERSION_MISMATCH for e in errors)

    def test_classify_maven_errors_compilation(self, temp_project_dir):
        """A 'cannot find symbol' error is an IMPORT_FAILURE.

        It used to be classified as GENERATED_CODE_ERROR, which meant the
        import-repair path never ran for the single most common generated
        code defect (a missing import).
        """
        validator = BuildValidator(temp_project_dir)
        output = "[ERROR] com/example/MyClass.java:[10,5] cannot find symbol"
        errors = validator._classify_maven_errors(output)
        assert any(e.category == ErrorCategory.IMPORT_FAILURE for e in errors)
        assert any(e.file == "com/example/MyClass.java" for e in errors)
        assert any(e.line == 10 for e in errors)

    def test_classify_maven_errors_generic_compile(self, temp_project_dir):
        """A non-symbol compile error is still GENERATED_CODE_ERROR."""
        validator = BuildValidator(temp_project_dir)
        output = "[ERROR] com/example/MyClass.java:[12,9] ';' expected"
        errors = validator._classify_maven_errors(output)
        assert any(e.category == ErrorCategory.GENERATED_CODE_ERROR for e in errors)

    def test_classify_maven_errors_normalizes_windows_path(self, temp_project_dir):
        """Maven's URI-style /C:/... paths are normalized.

        Without this, Path('/C:/...').exists() is False and every
        file-based repair plan silently returns None.
        """
        validator = BuildValidator(temp_project_dir)
        output = "[ERROR] /C:/proj/backend/src/main/java/com/demo/Thing.java:[4,13] cannot find symbol"
        errors = validator._classify_maven_errors(output)
        files = [e.file for e in errors if e.file]
        assert files, "expected a file-attributed error"
        assert all(not f.startswith("/C:") for f in files)
        assert any(f.startswith("C:/") for f in files)

    def test_classify_npm_errors_peer_dependency(self, temp_project_dir):
        """Test npm error classification for peer dependency conflict."""
        validator = BuildValidator(temp_project_dir)
        output = "ERESOLVE unable to resolve dependency tree"
        errors = validator._classify_npm_errors(output)
        assert any(e.category == ErrorCategory.PEER_DEPENDENCY_CONFLICT for e in errors)

    def test_classify_npm_errors_module_not_found(self, temp_project_dir):
        """Test npm error classification for module not found."""
        validator = BuildValidator(temp_project_dir)
        output = "Module not found: Error: Can't resolve 'some-module'"
        errors = validator._classify_npm_errors(output)
        assert any(e.category == ErrorCategory.MISSING_DEPENDENCY for e in errors)

    def test_classify_npm_errors_node_version(self, temp_project_dir):
        """Test npm error classification for Node version mismatch."""
        validator = BuildValidator(temp_project_dir)
        output = "engine node version mismatch"
        errors = validator._classify_npm_errors(output)
        assert any(e.category == ErrorCategory.NODE_VERSION_MISMATCH for e in errors)

    def test_validate_project_integration(self, temp_project_dir):
        """Test full project validation integration."""
        # Create minimal valid schema
        schema_file = temp_project_dir / "database" / "schema.sql"
        schema_file.write_text("CREATE TABLE test (id INT PRIMARY KEY);")

        with patch('converter.app.build.validator.BuildValidator.check_environment') as mock_env, \
             patch('converter.app.build.validator.BuildValidator.build_backend') as mock_backend, \
             patch('converter.app.build.validator.BuildValidator.build_frontend') as mock_frontend, \
             patch('converter.app.build.validator.BuildValidator.validate_database') as mock_db:

            mock_env.return_value = BuildResult(status=BuildStatus.SUCCESS, output="OK")
            mock_backend.return_value = BuildResult(status=BuildStatus.SUCCESS, output="Built")
            mock_frontend.return_value = BuildResult(status=BuildStatus.SUCCESS, output="Built")
            mock_db.return_value = BuildResult(status=BuildStatus.SUCCESS, output="Valid")

            result = validate_project(str(temp_project_dir))
            assert result["status"] == "success"
            assert "environment" in result["results"]
            assert "backend" in result["results"]
            assert "frontend" in result["results"]
            assert "database" in result["results"]


class TestPipelineBuildValidator:
    """Test the async pipeline build validator."""

    @pytest.fixture
    def temp_project_dir(self):
        """Create a temporary project directory structure."""
        with tempfile.TemporaryDirectory() as tmpdir:
            project_dir = Path(tmpdir)
            (project_dir / "backend").mkdir()
            (project_dir / "frontend").mkdir()
            (project_dir / "database").mkdir()
            # Create a minimal schema.sql
            (project_dir / "database" / "schema.sql").write_text("CREATE TABLE test (id INT PRIMARY KEY);")
            yield project_dir

    @pytest.fixture
    def mock_db_session(self):
        """Create a mock database session."""
        session = AsyncMock()
        session.commit = AsyncMock()
        return session

    @pytest.fixture
    def mock_build_log_repo(self):
        """Create a mock build log repository."""
        repo = AsyncMock()
        repo.create = AsyncMock(return_value=MagicMock(id="test-id"))
        repo.update = AsyncMock()
        return repo

    @pytest.mark.asyncio
    async def test_run_maven_build_skipped_missing_dir(self, temp_project_dir, mock_build_log_repo, mock_db_session):
        """Test Maven build skipped when backend dir missing."""
        shutil.rmtree(temp_project_dir / "backend")

        validator = PipelineBuildValidator(temp_project_dir, "job123", mock_build_log_repo, mock_db_session)
        result = await validator.run_maven_build()

        assert result.status == PipelineBuildStatus.FAILED
        assert "not found" in result.error.lower()

    @pytest.mark.asyncio
    async def test_run_maven_build_command_not_found(self, temp_project_dir, mock_build_log_repo, mock_db_session):
        """Test Maven build fails when mvn not found."""
        with patch('shutil.which', return_value=None):
            validator = PipelineBuildValidator(temp_project_dir, "job123", mock_build_log_repo, mock_db_session)
            result = await validator.run_maven_build()

            assert result.status == PipelineBuildStatus.FAILED
            assert "command not found" in result.error.lower()

    @pytest.mark.asyncio
    async def test_run_npm_install_skipped_missing_dir(self, temp_project_dir, mock_build_log_repo, mock_db_session):
        """Test npm install skipped when frontend dir missing."""
        shutil.rmtree(temp_project_dir / "frontend")

        validator = PipelineBuildValidator(temp_project_dir, "job123", mock_build_log_repo, mock_db_session)
        result = await validator.run_npm_install()

        assert result.status == PipelineBuildStatus.FAILED
        assert "not found" in result.error.lower()

    @pytest.mark.asyncio
    async def test_run_database_migration_valid(self, temp_project_dir, mock_build_log_repo, mock_db_session):
        """Test database migration validation passes for valid schema."""
        validator = PipelineBuildValidator(temp_project_dir, "job123", mock_build_log_repo, mock_db_session)
        result = await validator.run_database_migration()

        assert result.status == PipelineBuildStatus.COMPLETED
        assert "validated" in result.output.lower()

    @pytest.mark.asyncio
    async def test_run_database_migration_empty(self, temp_project_dir, mock_build_log_repo, mock_db_session):
        """Test database migration fails for empty schema."""
        (temp_project_dir / "database" / "schema.sql").write_text("")

        validator = PipelineBuildValidator(temp_project_dir, "job123", mock_build_log_repo, mock_db_session)
        result = await validator.run_database_migration()

        assert result.status == PipelineBuildStatus.FAILED
        assert "empty" in result.error.lower()

    @pytest.mark.asyncio
    async def test_run_full_build_mocked(self, temp_project_dir, mock_build_log_repo, mock_db_session):
        """Test full build pipeline with mocked subprocess."""
        validator = PipelineBuildValidator(temp_project_dir, "job123", mock_build_log_repo, mock_db_session)

        # Mock all the run methods to return success
        with patch.object(validator, 'run_maven_build', new_callable=AsyncMock) as mock_maven_build, \
             patch.object(validator, 'run_maven_test', new_callable=AsyncMock) as mock_maven_test, \
             patch.object(validator, 'run_npm_install', new_callable=AsyncMock) as mock_npm_install, \
             patch.object(validator, 'run_npm_build', new_callable=AsyncMock) as mock_npm_build, \
             patch.object(validator, 'run_npm_test', new_callable=AsyncMock) as mock_npm_test, \
             patch.object(validator, 'run_database_migration', new_callable=AsyncMock) as mock_db_migration:

            for m in [mock_maven_build, mock_maven_test, mock_npm_install, mock_npm_build, mock_npm_test, mock_db_migration]:
                m.return_value = BuildStepResult(
                    phase=BuildPhase.MAVEN,
                    step="test",
                    status=PipelineBuildStatus.COMPLETED,
                    output="OK",
                )

            result = await validator.run_full_build()
            assert result["success"] is True
            assert len(result["steps"]) == 6


class TestBuildRepair:
    """Test the self-healing build repair (pipeline wrapper)."""

    @pytest.fixture
    def temp_project_dir(self):
        """Create a temporary project directory structure."""
        with tempfile.TemporaryDirectory() as tmpdir:
            project_dir = Path(tmpdir)
            (project_dir / "backend").mkdir()
            (project_dir / "frontend").mkdir()
            yield project_dir

    @pytest.fixture
    def mock_db_session(self):
        """Create a mock database session."""
        session = AsyncMock()
        session.commit = AsyncMock()
        return session

    @pytest.fixture
    def mock_build_log_repo(self):
        """Create a mock build log repository."""
        repo = AsyncMock()
        repo.create = AsyncMock(return_value=MagicMock(id="test-id"))
        repo.update = AsyncMock()
        return repo

    @pytest.mark.asyncio
    async def test_repair_maven_dependency(self, temp_project_dir, mock_build_log_repo, mock_db_session):
        """Test Maven dependency repair via wrapper."""
        from converter.app.build.pipeline import BuildRepair

        repair = BuildRepair(temp_project_dir, "job123", mock_build_log_repo, mock_db_session)

        # The wrapper calls the standalone repair, so we test the integration
        # by checking that attempt_repair returns a list
        results = await repair.attempt_repair(BuildPhase.MAVEN, "maven_clean_package", "dependency error", "output")
        assert isinstance(results, list)

    @pytest.mark.asyncio
    async def test_repair_npm_peer_deps(self, temp_project_dir, mock_build_log_repo, mock_db_session):
        """Test npm peer dependency repair via wrapper."""
        from converter.app.build.pipeline import BuildRepair

        repair = BuildRepair(temp_project_dir, "job123", mock_build_log_repo, mock_db_session)

        results = await repair.attempt_repair(BuildPhase.NPM, "npm_ci", "ERESOLVE error", "output")
        assert isinstance(results, list)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])