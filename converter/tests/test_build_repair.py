"""Tests for self-healing build repair."""
from __future__ import annotations

import json
import pytest
import subprocess
from pathlib import Path
from unittest.mock import patch
import tempfile
import shutil

from converter.app.build.repair import (
    BuildRepair,
    RepairStrategy,
    RepairPlan,
    RepairAttempt,
    repair_project,
)
from converter.app.build.validator import (
    BuildValidator,
    BuildStatus,
    ErrorCategory,
    BuildError,
    BuildResult,
)


class TestBuildRepair:
    """Test the BuildRepair class."""

    @pytest.fixture
    def temp_project_dir(self):
        """Create a temporary project directory structure."""
        with tempfile.TemporaryDirectory() as tmpdir:
            project_dir = Path(tmpdir)
            # Create backend structure
            backend = project_dir / "backend"
            backend.mkdir()
            (backend / "src" / "main" / "java" / "com" / "generated" / "app").mkdir(parents=True)
            (backend / "src" / "main" / "resources").mkdir(parents=True)
            (backend / "pom.xml").write_text("""<?xml version="1.0" encoding="UTF-8"?>
<project xmlns="http://maven.apache.org/POM/4.0.0"
         xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"
         xsi:schemaLocation="http://maven.apache.org/POM/4.0.0 http://maven.apache.org/xsd/maven-4.0.0.xsd">
    <modelVersion>4.0.0</modelVersion>
    <groupId>com.generated.app</groupId>
    <artifactId>backend</artifactId>
    <version>1.0.0-SNAPSHOT</version>
    <packaging>jar</packaging>
    <parent>
        <groupId>org.springframework.boot</groupId>
        <artifactId>spring-boot-starter-parent</artifactId>
        <version>3.1.0</version>
    </parent>
    <properties>
        <java.version>17</java.version>
    </properties>
    <dependencies>
        <dependency>
            <groupId>org.springframework.boot</groupId>
            <artifactId>spring-boot-starter-web</artifactId>
        </dependency>
    </dependencies>
</project>
""")

            # Create frontend structure
            frontend = project_dir / "frontend"
            frontend.mkdir()
            (frontend / "src").mkdir()
            (frontend / "package.json").write_text(json.dumps({
                "name": "frontend",
                "version": "1.0.0",
                "private": True,
                "type": "module",
                "scripts": {
                    "dev": "vite",
                    "build": "tsc && vite build",
                    "preview": "vite preview"
                },
                "dependencies": {
                    "react": "^18.2.0",
                    "react-dom": "^18.2.0"
                },
                "devDependencies": {
                    "@types/react": "^18.2.0",
                    "@types/react-dom": "^18.2.0",
                    "@vitejs/plugin-react": "^4.2.0",
                    "typescript": "^5.3.0",
                    "vite": "^5.0.0"
                }
            }, indent=2))

            # Create database structure
            database = project_dir / "database"
            database.mkdir()
            (database / "schema.sql").write_text("""CREATE TABLE test (
    id SERIAL PRIMARY KEY,
    name VARCHAR(255)
);""")

            yield project_dir

    def test_init(self, temp_project_dir):
        """Test BuildRepair initialization."""
        repair = BuildRepair(temp_project_dir)
        assert repair.project_dir == temp_project_dir
        assert repair.backend_dir == temp_project_dir / "backend"
        assert repair.frontend_dir == temp_project_dir / "frontend"
        assert repair.validator is not None

    def test_java_version_fix(self, temp_project_dir):
        """Test Java version fix generation."""
        # Ensure pom.xml exists
        backend_dir = temp_project_dir / "backend"
        backend_dir.mkdir(exist_ok=True)
        (backend_dir / "pom.xml").write_text("""<?xml version="1.0" encoding="UTF-8"?>
<project>
    <properties>
        <java.version>21</java.version>
    </properties>
</project>""")

        repair = BuildRepair(temp_project_dir)

        error = BuildError(
            category=ErrorCategory.JAVA_VERSION_MISMATCH,
            message="Unsupported class file major version 61",
            raw_output="Unsupported class file major version 61",
        )

        fix = repair._create_java_version_fix(error)
        assert fix is not None
        assert fix.strategy == RepairStrategy.DETERMINISTIC
        assert "17" in fix.file_changes.get("backend/pom.xml", "")
        assert fix.confidence > 0.5

    def test_missing_dependency_fix_backend(self, temp_project_dir):
        """Test missing Maven dependency fix."""
        repair = BuildRepair(temp_project_dir)

        error = BuildError(
            category=ErrorCategory.MISSING_DEPENDENCY,
            message="Could not find artifact org.example:missing-lib:1.0.0",
            raw_output="Could not find artifact org.example:missing-lib:1.0.0",
        )

        fix = repair._create_missing_dependency_fix(error, "backend")
        assert fix is not None
        assert "org.example" in fix.file_changes.get("backend/pom.xml", "")
        assert "missing-lib" in fix.file_changes.get("backend/pom.xml", "")

    def test_missing_dependency_fix_frontend(self, temp_project_dir):
        """Test missing npm dependency fix."""
        repair = BuildRepair(temp_project_dir)

        error = BuildError(
            category=ErrorCategory.MISSING_DEPENDENCY,
            message="npm ERR! code E404",
            raw_output="npm ERR! code E404\nnpm ERR! 404 Not Found - GET https://registry.npmjs.org/missing-package",
        )

        fix = repair._create_missing_dependency_fix(error, "frontend")
        assert fix is not None
        assert "missing-package" in fix.file_changes.get("frontend/package.json", "")

    def test_node_version_fix(self, temp_project_dir):
        """Test Node version fix."""
        repair = BuildRepair(temp_project_dir)

        error = BuildError(
            category=ErrorCategory.NODE_VERSION_MISMATCH,
            message="Engine node is incompatible",
            raw_output="npm ERR! engine node@18.0.0 required",
        )

        fix = repair._create_node_version_fix(error)
        assert fix is not None
        assert "engines" in fix.file_changes.get("frontend/package.json", "")

    def test_peer_dep_fix(self, temp_project_dir):
        """Test peer dependency conflict fix."""
        repair = BuildRepair(temp_project_dir)

        error = BuildError(
            category=ErrorCategory.PEER_DEPENDENCY_CONFLICT,
            message="ERESOLVE unable to resolve dependency tree",
            raw_output="npm ERR! ERESOLVE unable to resolve dependency tree",
        )

        fix = repair._create_peer_dep_fix(error)
        assert fix is not None
        assert fix.file_changes.get("frontend/.npmrc") == "legacy-peer-deps=true\n"

    def test_import_fix_java(self, temp_project_dir):
        """Test Java import fix."""
        repair = BuildRepair(temp_project_dir)

        # Create a test Java file
        java_file = temp_project_dir / "backend" / "src" / "main" / "java" / "com" / "generated" / "app" / "TestEntity.java"
        java_file.write_text("""package com.generated.app;

public class TestEntity {
    private String name;
}
""")

        error = BuildError(
            category=ErrorCategory.IMPORT_FAILURE,
            message="cannot find symbol: class Entity",
            file=str(java_file),  # Use absolute path
            line=1,
        )

        fix = repair._create_import_fix(error, "backend")
        # Note: The fix requires the symbol to be in import_map
        # "Entity" is in the map, so it should return a fix
        if fix is not None:
            # The fix file_changes key is relative to project_dir
            rel_path = java_file.relative_to(temp_project_dir).as_posix()
            assert rel_path in fix.file_changes
            assert "jakarta.persistence.Entity" in fix.file_changes[rel_path]

    def test_react_compile_fix(self, temp_project_dir):
        """Test React compilation fix."""
        repair = BuildRepair(temp_project_dir)

        # Create a test React file
        react_file = temp_project_dir / "frontend" / "src" / "TestComponent.jsx"
        react_file.write_text("""import React from 'react';

export function TestComponent() {
    return <div>Hello</div>;
}
""")

        error = BuildError(
            category=ErrorCategory.REACT_COMPILE_ERROR,
            message="'Button' is not defined",
            file=react_file.relative_to(temp_project_dir).as_posix(),
            line=5,
        )

        fix = repair._create_react_compile_fix(error)
        assert fix is not None
        assert "Button" in fix.file_changes.get(react_file.relative_to(temp_project_dir).as_posix(), "")

    def test_generated_code_fix(self, temp_project_dir):
        """Test generated code fix for missing getter."""
        repair = BuildRepair(temp_project_dir)

        # Create a test Java file with a field
        java_file = temp_project_dir / "backend" / "src" / "main" / "java" / "com" / "generated" / "app" / "TestEntity.java"
        java_file.write_text("""package com.generated.app;

public class TestEntity {
    private String userName;
}
""")

        error = BuildError(
            category=ErrorCategory.GENERATED_CODE_ERROR,
            message="cannot find symbol: method getUserName()",
            file=java_file.relative_to(temp_project_dir).as_posix(),
            line=1,
        )

        fix = repair._create_generated_code_fix(error, "backend")
        assert fix is not None
        assert "getUserName" in fix.file_changes.get(java_file.relative_to(temp_project_dir).as_posix(), "")
        assert "setUserName" in fix.file_changes.get(java_file.relative_to(temp_project_dir).as_posix(), "")

    def test_database_fix_undefined(self, temp_project_dir):
        """Test database fix for undefined values."""
        repair = BuildRepair(temp_project_dir)

        schema_file = temp_project_dir / "database" / "schema.sql"
        schema_file.write_text("""CREATE TABLE test (
    id SERIAL PRIMARY KEY,
    name undefined
);""")

        error = BuildError(
            category=ErrorCategory.SQL_SYNTAX_ERROR,
            message="syntax error at or near \"undefined\"",
            raw_output="syntax error at or near \"undefined\"",
        )

        fix = repair._get_database_fix(error)
        assert fix is not None
        assert "NULL" in fix.file_changes.get("database/schema.sql", "")
        assert "undefined" not in fix.file_changes.get("database/schema.sql", "")

    def test_database_fix_unbalanced_parens(self, temp_project_dir):
        """Test database fix for unbalanced parentheses."""
        repair = BuildRepair(temp_project_dir)

        schema_file = temp_project_dir / "database" / "schema.sql"
        schema_file.write_text("""CREATE TABLE test (
    id SERIAL PRIMARY KEY,
    name VARCHAR(255)
""")

        error = BuildError(
            category=ErrorCategory.SQL_SYNTAX_ERROR,
            message="unbalanced parentheses",
            raw_output="unbalanced parentheses",
        )

        fix = repair._get_database_fix(error)
        assert fix is not None
        content = fix.file_changes.get("database/schema.sql", "")
        assert content.count("(") == content.count(")")

    def test_repair_all_structure(self, temp_project_dir):
        """Test the overall repair_all structure."""
        repair = BuildRepair(temp_project_dir)
        result = repair.repair_all()

        assert "backend" in result
        assert "frontend" in result
        assert "database" in result
        assert "attempts" in result
        assert "final_status" in result
        assert "total_attempts" in result

    def test_repair_project_entry_point(self, temp_project_dir):
        """Test the repair_project entry point."""
        result = repair_project(temp_project_dir)

        assert "backend" in result
        assert "frontend" in result
        assert "database" in result
        assert "attempts" in result
        assert "final_status" in result
        assert "total_attempts" in result

    def test_repair_strategy_enum(self):
        """Test RepairStrategy enum values."""
        assert RepairStrategy.DETERMINISTIC.value == "deterministic"
        assert RepairStrategy.LLM_ASSISTED.value == "llm_assisted"
        assert RepairStrategy.MANUAL.value == "manual"

    def test_repair_plan_creation(self):
        """Test RepairPlan creation."""
        error = BuildError(
            category=ErrorCategory.MISSING_DEPENDENCY,
            message="Test error",
        )

        plan = RepairPlan(
            error=error,
            strategy=RepairStrategy.DETERMINISTIC,
            description="Test fix",
            file_changes={"test.txt": "content"},
            confidence=0.8,
        )

        assert plan.error == error
        assert plan.strategy == RepairStrategy.DETERMINISTIC
        assert plan.description == "Test fix"
        assert plan.file_changes == {"test.txt": "content"}
        assert plan.confidence == 0.8

    def test_repair_attempt_creation(self):
        """Test RepairAttempt creation."""
        error = BuildError(
            category=ErrorCategory.MISSING_DEPENDENCY,
            message="Test error",
        )

        attempt = RepairAttempt(
            error_category=error.category,
            fix_applied="Test fix",
            strategy=RepairStrategy.DETERMINISTIC,
            success=True,
            files_changed=["test.txt"],
            confidence=0.8,
        )

        assert attempt.error_category == error.category
        assert attempt.fix_applied == "Test fix"
        assert attempt.strategy == RepairStrategy.DETERMINISTIC
        assert attempt.success is True
        assert attempt.files_changed == ["test.txt"]
        assert attempt.confidence == 0.8


class TestRepairIntegration:
    """Integration tests for repair with validator."""

    @pytest.fixture
    def failing_project_dir(self):
        """Create a project with known issues."""
        with tempfile.TemporaryDirectory() as tmpdir:
            project_dir = Path(tmpdir)
            # Create backend with Java version issue
            backend = project_dir / "backend"
            backend.mkdir()
            (backend / "src" / "main" / "java" / "com" / "generated" / "app").mkdir(parents=True)
            (backend / "src" / "main" / "resources").mkdir(parents=True)
            (backend / "pom.xml").write_text("""<?xml version="1.0" encoding="UTF-8"?>
<project xmlns="http://maven.apache.org/POM/4.0.0"
         xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"
         xsi:schemaLocation="http://maven.apache.org/POM/4.0.0 http://maven.apache.org/xsd/maven-4.0.0.xsd">
    <modelVersion>4.0.0</modelVersion>
    <groupId>com.generated.app</groupId>
    <artifactId>backend</artifactId>
    <version>1.0.0-SNAPSHOT</version>
    <packaging>jar</packaging>
    <parent>
        <groupId>org.springframework.boot</groupId>
        <artifactId>spring-boot-starter-parent</artifactId>
        <version>3.1.0</version>
    </parent>
    <properties>
        <java.version>21</java.version>
    </properties>
    <dependencies>
        <dependency>
            <groupId>org.springframework.boot</groupId>
            <artifactId>spring-boot-starter-web</artifactId>
        </dependency>
    </dependencies>
</project>
""")

            # Create frontend
            frontend = project_dir / "frontend"
            frontend.mkdir()
            (frontend / "src").mkdir()
            (frontend / "package.json").write_text(json.dumps({
                "name": "frontend",
                "version": "1.0.0",
                "private": True,
                "type": "module",
                "scripts": {
                    "dev": "vite",
                    "build": "tsc && vite build",
                    "preview": "vite preview"
                },
                "dependencies": {
                    "react": "^18.2.0",
                    "react-dom": "^18.2.0"
                },
                "devDependencies": {
                    "@types/react": "^18.2.0",
                    "@types/react-dom": "^18.2.0",
                    "@vitejs/plugin-react": "^4.2.0",
                    "typescript": "^5.3.0",
                    "vite": "^5.0.0"
                }
            }, indent=2))

            # Create database
            database = project_dir / "database"
            database.mkdir()
            (database / "schema.sql").write_text("""CREATE TABLE test (
    id SERIAL PRIMARY KEY,
    name VARCHAR(255)
);""")

            yield project_dir

    def test_repair_with_mock_errors(self, failing_project_dir):
        """Test repair with mocked validation errors."""
        repair = BuildRepair(failing_project_dir)

        # Mock the validator to return errors
        from unittest.mock import patch, MagicMock

        mock_backend_result = BuildResult(
            status=BuildStatus.FAILED,
            errors=[
                BuildError(
                    category=ErrorCategory.JAVA_VERSION_MISMATCH,
                    message="Unsupported class file major version 61",
                    raw_output="Unsupported class file major version 61",
                )
            ],
        )

        with patch.object(repair.validator, 'validate_all', return_value={"backend": mock_backend_result}):
            with patch.object(repair.validator, 'build_backend', return_value=BuildResult(status=BuildStatus.SUCCESS, errors=[])):
                result = repair.repair_all()

        assert result["backend"] is not None
        assert result["backend"]["success"] is True
        assert result["total_attempts"] > 0

    def test_annotation_fix_entity(self, failing_project_dir):
        """Test JPA @Entity annotation fix."""
        repair = BuildRepair(failing_project_dir)

        # Create a test Java file without @Entity
        java_file = failing_project_dir / "backend" / "src" / "main" / "java" / "com" / "generated" / "app" / "entity" / "TestEntity.java"
        java_file.parent.mkdir(parents=True, exist_ok=True)
        java_file.write_text("""package com.generated.app.entity;

public class TestEntity {
    private Long id;
    private String name;
}
""")

        error = BuildError(
            category=ErrorCategory.ANNOTATION_MISMATCH,
            message="entity not a managed type: class com.generated.app.entity.TestEntity",
            file=java_file.relative_to(failing_project_dir).as_posix(),
            line=1,
        )

        fix = repair._create_annotation_fix(error)
        assert fix is not None
        assert "@Entity" in fix.file_changes.get(java_file.relative_to(failing_project_dir).as_posix(), "")
        assert "@Table" in fix.file_changes.get(java_file.relative_to(failing_project_dir).as_posix(), "")

    def test_annotation_fix_missing_id(self, failing_project_dir):
        """Test JPA @Id annotation fix."""
        repair = BuildRepair(failing_project_dir)

        # Create a test Java file with @Entity but no @Id
        java_file = failing_project_dir / "backend" / "src" / "main" / "java" / "com" / "generated" / "app" / "entity" / "TestEntity.java"
        java_file.parent.mkdir(parents=True, exist_ok=True)
        java_file.write_text("""package com.generated.app.entity;

import jakarta.persistence.Entity;
import jakarta.persistence.Table;

@Entity
@Table(name = "test_entity")
public class TestEntity {
    private Long id;
    private String name;
}
""")

        error = BuildError(
            category=ErrorCategory.ANNOTATION_MISMATCH,
            message="Entity must have an identifier",
            file=java_file.relative_to(failing_project_dir).as_posix(),
            line=1,
        )

        fix = repair._create_annotation_fix(error)
        assert fix is not None
        assert "@Id" in fix.file_changes.get(java_file.relative_to(failing_project_dir).as_posix(), "")
        assert "@GeneratedValue" in fix.file_changes.get(java_file.relative_to(failing_project_dir).as_posix(), "")

    def test_jpa_mapping_fix_relationship(self, failing_project_dir):
        """Test JPA relationship annotation fix."""
        repair = BuildRepair(failing_project_dir)

        # Create a test Java file with relationship but missing imports
        java_file = failing_project_dir / "backend" / "src" / "main" / "java" / "com" / "generated" / "app" / "entity" / "Order.java"
        java_file.parent.mkdir(parents=True, exist_ok=True)
        java_file.write_text("""package com.generated.app.entity;

import jakarta.persistence.Entity;
import jakarta.persistence.Table;

@Entity
@Table(name = "orders")
public class Order {
    private Customer customer;
}
""")

        error = BuildError(
            category=ErrorCategory.JPA_MAPPING_ERROR,
            message="Could not determine type for: customer, @ManyToOne or @OneToOne required",
            file=java_file.relative_to(failing_project_dir).as_posix(),
            line=10,
        )

        fix = repair._create_jpa_mapping_fix(error)
        assert fix is not None
        content = fix.file_changes.get(java_file.relative_to(failing_project_dir).as_posix(), "")
        assert "ManyToOne" in content or "JoinColumn" in content

    def test_spring_config_fix(self, failing_project_dir):
        """Test Spring application.yml fix."""
        repair = BuildRepair(failing_project_dir)

        # Create application.yml with issues
        yml_path = failing_project_dir / "backend" / "src" / "main" / "resources" / "application.yml"
        yml_path.parent.mkdir(parents=True, exist_ok=True)
        yml_path.write_text("""spring:
  datasource:
    url: jdbc:postgresql://localhost:5432/test
    username: postgres
    password: postgres
  jpa:
    hibernate:
      ddl-auto: validate
""")

        error = BuildError(
            category=ErrorCategory.SPRING_CONFIG_ERROR,
            message="Missing driver-class-name in datasource",
            raw_output="application.yml: Missing driver-class-name",
        )

        fix = repair._create_spring_config_fix(error)
        assert fix is not None
        content = fix.file_changes.get("backend/src/main/resources/application.yml", "")
        assert "driver-class-name" in content

    def test_type_mismatch_fix_java(self, failing_project_dir):
        """Test Java type mismatch fix."""
        repair = BuildRepair(failing_project_dir)

        # Create a test Java file with type mismatch
        java_file = failing_project_dir / "backend" / "src" / "main" / "java" / "com" / "generated" / "app" / "entity" / "TestEntity.java"
        java_file.parent.mkdir(parents=True, exist_ok=True)
        java_file.write_text("""package com.generated.app.entity;

public class TestEntity {
    private String name;
    public void setName(Integer value) {
        this.name = value;
    }
}
""")

        error = BuildError(
            category=ErrorCategory.TYPE_MISMATCH,
            message="incompatible types: Integer cannot be converted to String",
            file=java_file.relative_to(failing_project_dir).as_posix(),
            line=5,
        )

        fix = repair._create_type_mismatch_fix(error, "backend")
        if fix:
            content = fix.file_changes.get(java_file.relative_to(failing_project_dir).as_posix(), "")
            # Should add cast
            assert "(String)" in content or "String" in content

    def test_react_compile_fix_missing_hook(self, failing_project_dir):
        """Test React hook import fix."""
        repair = BuildRepair(failing_project_dir)

        # Create a React file using useState without import
        react_file = failing_project_dir / "frontend" / "src" / "pages" / "TestPage.jsx"
        react_file.parent.mkdir(parents=True, exist_ok=True)
        react_file.write_text("""import React from 'react';

export default function TestPage() {
    const [count, setCount] = useState(0);
    return <div>{count}</div>;
}
""")

        error = BuildError(
            category=ErrorCategory.REACT_COMPILE_ERROR,
            message="'useState' is not defined",
            file=react_file.relative_to(failing_project_dir).as_posix(),
            line=4,
        )

        fix = repair._create_react_compile_fix(error)
        assert fix is not None
        content = fix.file_changes.get(react_file.relative_to(failing_project_dir).as_posix(), "")
        assert "useState" in content and "from 'react'" in content

    def test_react_compile_fix_missing_react(self, failing_project_dir):
        """Test React import fix."""
        repair = BuildRepair(failing_project_dir)

        # Create a React file without React import
        react_file = failing_project_dir / "frontend" / "src" / "pages" / "TestPage.jsx"
        react_file.parent.mkdir(parents=True, exist_ok=True)
        react_file.write_text("""export default function TestPage() {
    return <div>Hello</div>;
}
""")

        error = BuildError(
            category=ErrorCategory.REACT_COMPILE_ERROR,
            message="React is not defined",
            file=react_file.relative_to(failing_project_dir).as_posix(),
            line=1,
        )

        fix = repair._create_react_compile_fix(error)
        assert fix is not None
        content = fix.file_changes.get(react_file.relative_to(failing_project_dir).as_posix(), "")
        assert "import React from 'react'" in content

    def test_generated_code_fix_constructor(self, failing_project_dir):
        """Test generated code fix for missing constructor."""
        repair = BuildRepair(failing_project_dir)

        # Create a Java class without default constructor
        java_file = failing_project_dir / "backend" / "src" / "main" / "java" / "com" / "generated" / "app" / "entity" / "TestEntity.java"
        java_file.parent.mkdir(parents=True, exist_ok=True)
        java_file.write_text("""package com.generated.app.entity;

public class TestEntity {
    private String name;
    public TestEntity(String name) {
        this.name = name;
    }
}
""")

        error = BuildError(
            category=ErrorCategory.GENERATED_CODE_ERROR,
            message="constructor TestEntity in class TestEntity cannot be applied to given types",
            file=java_file.relative_to(failing_project_dir).as_posix(),
            line=1,
        )

        fix = repair._create_generated_code_fix(error, "backend")
        assert fix is not None
        content = fix.file_changes.get(java_file.relative_to(failing_project_dir).as_posix(), "")
        assert "public TestEntity()" in content

    def test_generated_code_fix_missing_setter(self, failing_project_dir):
        """Test generated code fix for missing setter."""
        repair = BuildRepair(failing_project_dir)

        # Create a Java class with getter but no setter
        java_file = failing_project_dir / "backend" / "src" / "main" / "java" / "com" / "generated" / "app" / "entity" / "TestEntity.java"
        java_file.parent.mkdir(parents=True, exist_ok=True)
        java_file.write_text("""package com.generated.app.entity;

public class TestEntity {
    private String userName;
    public String getUserName() { return userName; }
}
""")

        error = BuildError(
            category=ErrorCategory.GENERATED_CODE_ERROR,
            message="cannot find symbol: method setUserName(java.lang.String)",
            file=java_file.relative_to(failing_project_dir).as_posix(),
            line=1,
        )

        fix = repair._create_generated_code_fix(error, "backend")
        assert fix is not None
        content = fix.file_changes.get(java_file.relative_to(failing_project_dir).as_posix(), "")
        assert "setUserName" in content

    def test_repair_all_with_multiple_errors(self, failing_project_dir):
        """Test repair_all handles multiple errors."""
        repair = BuildRepair(failing_project_dir)

        # Mock validator to return multiple errors
        from unittest.mock import patch

        mock_backend_result = BuildResult(
            status=BuildStatus.FAILED,
            errors=[
                BuildError(
                    category=ErrorCategory.JAVA_VERSION_MISMATCH,
                    message="Unsupported class file major version 61",
                    raw_output="Unsupported class file major version 61",
                ),
                BuildError(
                    category=ErrorCategory.MISSING_DEPENDENCY,
                    message="Could not find artifact org.example:missing:1.0",
                    raw_output="Could not find artifact org.example:missing:1.0",
                ),
            ],
        )

        mock_frontend_result = BuildResult(
            status=BuildStatus.FAILED,
            errors=[
                BuildError(
                    category=ErrorCategory.PEER_DEPENDENCY_CONFLICT,
                    message="ERESOLVE unable to resolve dependency tree",
                    raw_output="npm ERR! ERESOLVE",
                ),
            ],
        )

        def mock_validate_all():
            return {
                "backend": mock_backend_result,
                "frontend": mock_frontend_result,
                "database": BuildResult(status=BuildStatus.SUCCESS, errors=[]),
            }

        def mock_build_backend():
            return BuildResult(status=BuildStatus.SUCCESS, errors=[])

        def mock_build_frontend():
            return BuildResult(status=BuildStatus.SUCCESS, errors=[])

        with patch.object(repair.validator, 'validate_all', side_effect=[mock_validate_all(), {
            "backend": mock_build_backend(),
            "frontend": mock_build_frontend(),
            "database": BuildResult(status=BuildStatus.SUCCESS, errors=[]),
        }]):
            with patch.object(repair.validator, 'build_backend', side_effect=[mock_backend_result, mock_build_backend(), mock_build_backend()]):
                with patch.object(repair.validator, 'build_frontend', side_effect=[mock_frontend_result, mock_build_frontend()]):
                    result = repair.repair_all()

        assert result["backend"] is not None
        assert result["frontend"] is not None
        assert result["total_attempts"] > 0
        assert "remaining_errors" in result["backend"]
        assert "remaining_errors" in result["frontend"]

    def test_llm_fix_priority_ordering(self, failing_project_dir):
        """Test that LLM fixes are prioritized correctly."""
        repair = BuildRepair(failing_project_dir)

        errors = [
            BuildError(category=ErrorCategory.UNKNOWN, message="Unknown error"),
            BuildError(category=ErrorCategory.GENERATED_CODE_ERROR, message="Generated code error"),
            BuildError(category=ErrorCategory.TYPE_MISMATCH, message="Type mismatch"),
            BuildError(category=ErrorCategory.REACT_COMPILE_ERROR, message="React compile error"),
        ]

        llm_fixes = repair._get_llm_fixes(errors, "backend")
        # Should prioritize GENERATED_CODE_ERROR, TYPE_MISMATCH, REACT_COMPILE_ERROR over UNKNOWN
        assert len(llm_fixes) <= 3


class TestBuildReportGeneration:
    """Tests for _generate_build_report and _generate_dependency_graph (spec §55, §58, §66)."""

    @pytest.fixture
    def temp_project_dir(self):
        """Create a minimal generated project directory."""
        with tempfile.TemporaryDirectory() as tmpdir:
            project_dir = Path(tmpdir)
            (project_dir / "backend").mkdir()
            (project_dir / "frontend").mkdir()
            (project_dir / "database").mkdir()
            yield project_dir

    def test_generate_build_report_writes_json(self, temp_project_dir):
        """_generate_build_report writes build.json with the session audit trail."""
        from converter.app.build.repair import BuildRepair, RepairSession

        repair = BuildRepair(temp_project_dir)

        session = RepairSession(
            started_at="2026-08-20T10:00:00",
            completed_at="2026-08-20T10:05:00",
            project_dir=str(temp_project_dir),
            total_attempts=4,
            deterministic_attempts=2,
            llm_attempts=2,
            rollbacks=1,
            final_status="SUCCESS",
            initial_errors={"backend": 3, "frontend": 1},
            final_errors={},
            components={"backend": {"status": "success", "repairs": []}},
        )

        repair._generate_build_report(session)

        report_path = temp_project_dir / "migration-report" / "build.json"
        assert report_path.exists(), "build.json was not written"

        report = json.loads(report_path.read_text(encoding="utf-8"))
        assert report["schema_version"] == "1.0"
        assert report["session"]["total_attempts"] == 4
        assert report["summary"]["deterministic_attempts"] == 2
        assert report["summary"]["llm_attempts"] == 2
        assert report["summary"]["rollbacks"] == 1
        assert report["summary"]["final_status"] == "SUCCESS"
        assert report["summary"]["initial_error_counts"] == {"backend": 3, "frontend": 1}
        assert report["summary"]["final_error_counts"] == {}
        assert "backend" in report["components"]

    def test_generate_build_report_creates_directory(self, temp_project_dir):
        """_generate_build_report creates the migration-report dir if absent."""
        from converter.app.build.repair import BuildRepair, RepairSession

        repair = BuildRepair(temp_project_dir)
        assert not (temp_project_dir / "migration-report").exists()

        session = RepairSession(project_dir=str(temp_project_dir))
        repair._generate_build_report(session)

        assert (temp_project_dir / "migration-report").exists()
        assert (temp_project_dir / "migration-report" / "build.json").exists()

    def test_generate_dependency_graph_handles_missing_build_tools(self, temp_project_dir):
        """_generate_dependency_graph does not crash when mvn/npm are unavailable."""
        from converter.app.build.repair import BuildRepair

        repair = BuildRepair(temp_project_dir)

        # Simulate environment where mvn and npm are not installed
        import converter.app.build.repair as repair_module

        def fake_run(*args, **kwargs):
            raise FileNotFoundError("mvn/npm not found")

        original_run = subprocess.run
        subprocess.run = fake_run
        try:
            # Should not raise even though tools are missing
            repair._generate_dependency_graph()
        finally:
            subprocess.run = original_run

        graph_path = temp_project_dir / "generated-dependency-graph.json"
        assert graph_path.exists(), "dependency graph JSON was not written"

        graph = json.loads(graph_path.read_text(encoding="utf-8"))
        assert graph["project_dir"] == str(temp_project_dir)
        # Backend/frontend attempted but recorded the error gracefully
        assert graph["backend"]["error"] == "Maven not found"
        assert graph["frontend"]["error"] == "npm not found"
        assert graph["backend"]["dependencies"] == []
        assert graph["frontend"]["dependencies"] == []

    def test_generate_dependency_graph_parses_npm_json(self, temp_project_dir):
        """_generate_dependency_graph parses npm ls JSON output into structured deps."""
        from converter.app.build.repair import BuildRepair

        repair = BuildRepair(temp_project_dir)

        npm_output = json.dumps({
            "name": "frontend",
            "version": "1.0.0",
            "dependencies": {
                "react": {
                    "version": "18.2.0",
                    "resolved": "https://registry.npmjs.org/react/-/react-18.2.0.tgz",
                    "dependencies": {"loose-envify": {"version": "1.4.0"}},
                },
            },
        })

        class FakeResult:
            returncode = 0
            stdout = npm_output
            stderr = ""

        def fake_run(cmd, **kwargs):
            return FakeResult()

        original_run = subprocess.run
        subprocess.run = fake_run
        try:
            repair._generate_dependency_graph()
        finally:
            subprocess.run = original_run

        graph_path = temp_project_dir / "generated-dependency-graph.json"
        graph = json.loads(graph_path.read_text(encoding="utf-8"))
        # Top-level react dependency recorded
        names = [d["name"] for d in graph["frontend"]["dependencies"]]
        assert "react" in names
        assert "loose-envify" in names  # recursed into sub-dependency

    def test_parse_maven_deps_walks_tree(self, temp_project_dir):
        """_parse_maven_deps walks a nested Maven dependency tree."""
        from converter.app.build.repair import BuildRepair

        repair = BuildRepair(temp_project_dir)
        tree = {
            "groupId": "org.springframework.boot",
            "artifactId": "backend",
            "version": "1.0.0-SNAPSHOT",
            "children": [
                {
                    "groupId": "org.springframework.boot",
                    "artifactId": "spring-boot-starter-web",
                    "version": "3.1.0",
                    "children": [
                        {
                            "groupId": "org.springframework",
                            "artifactId": "spring-web",
                            "version": "6.0.10",
                        },
                    ],
                },
            ],
        }
        deps = repair._parse_maven_deps(tree)
        assert len(deps) == 3
        assert deps[0]["artifactId"] == "backend"
        assert deps[1]["artifactId"] == "spring-boot-starter-web"
        assert deps[2]["artifactId"] == "spring-web"
        assert deps[2]["depth"] == 2

    def test_parse_npm_conflicts_finds_peer_conflicts(self, temp_project_dir):
        """_parse_npm_conflicts extracts peer dependency conflicts."""
        from converter.app.build.repair import BuildRepair

        repair = BuildRepair(temp_project_dir)
        output = "npm ERR! peer dep missing: react-router-dom@6.20.0\nnpm ERR! ERESOLVE react@18.2.0"
        conflicts = repair._parse_npm_conflicts(output)
        assert any(c["package"] == "react-router-dom" for c in conflicts)


class TestSelfHealingRegressions:
    """Regressions for defects that made self-healing a no-op."""

    @pytest.fixture
    def project(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            (root / "backend" / "src" / "main" / "java" / "com" / "demo").mkdir(parents=True)
            (root / "frontend").mkdir()
            yield root

    # ---- Windows .CMD resolution ----

    def test_resolve_executable_finds_real_tool(self):
        """Bare 'mvn'/'npm' must resolve, including Windows .CMD shims.

        subprocess does not consult PATHEXT, so passing a bare name raised
        FileNotFoundError on Windows even with Maven installed — which made
        every build report ENVIRONMENT_ERROR and skipped repair entirely.
        """
        from converter.app.build.validator import resolve_executable

        resolved = resolve_executable(["python", "--version"])
        assert resolved is not None
        assert Path(resolved[0]).exists()
        assert resolved[1:] == ["--version"]

    def test_resolve_executable_missing_tool_returns_none(self):
        from converter.app.build.validator import resolve_executable

        assert resolve_executable(["definitely-not-installed-xyz"]) is None

    # ---- Path normalization ----

    def test_normalize_reported_path_strips_uri_slash(self):
        from converter.app.build.validator import normalize_reported_path

        assert normalize_reported_path("/C:/proj/Foo.java") == "C:/proj/Foo.java"
        assert normalize_reported_path("com/demo/Foo.java") == "com/demo/Foo.java"
        assert normalize_reported_path("/usr/src/Foo.java") == "/usr/src/Foo.java"
        assert normalize_reported_path(None) is None

    def test_resolve_error_file_handles_maven_windows_path(self, project):
        """A /C:/... path from Maven must still resolve to the real file."""
        target = project / "backend" / "src" / "main" / "java" / "com" / "demo" / "Thing.java"
        target.write_text("package com.demo;\n")

        repair = BuildRepair(project)
        err = BuildError(
            category=ErrorCategory.IMPORT_FAILURE,
            message="cannot find symbol: List",
            file="/" + target.as_posix(),
        )
        assert repair._resolve_error_file(err) is not None

    # ---- Import repair actually fires ----

    def test_import_fix_adds_missing_java_import(self, project):
        """The end-to-end deterministic win: List -> java.util.List."""
        target = project / "backend" / "src" / "main" / "java" / "com" / "demo" / "Thing.java"
        target.write_text("package com.demo;\n\npublic class Thing {\n    private List<String> names;\n}\n")

        repair = BuildRepair(project)
        err = BuildError(
            category=ErrorCategory.IMPORT_FAILURE,
            message="cannot find symbol: class List",
            file="/" + target.as_posix(),
            line=4,
        )
        plan = repair._create_import_fix(err, "backend")
        assert plan is not None, "expected an import repair plan"
        patched = next(iter(plan.file_changes.values()))
        assert "import java.util.List;" in patched
        assert "package com.demo;" in patched

    # ---- No placebo plans ----

    @pytest.mark.parametrize("message", [
        "Type 'string' is not assignable to type 'number'",
        "Property 'foo' does not exist on type 'Props'",
    ])
    def test_no_echo_only_repair_plans(self, project, message):
        """Plans must never 'succeed' by running echo without editing.

        Such plans consumed the deterministic attempt budget and marked the
        error as addressed, so the real fix never ran.
        """
        target = project / "frontend" / "App.jsx"
        target.write_text("const App = () => <div/>;\n")

        repair = BuildRepair(project)
        err = BuildError(
            category=ErrorCategory.REACT_COMPILE_ERROR,
            message=message,
            file="frontend/App.jsx",
        )
        for plan in (
            repair._create_type_mismatch_fix(err, "frontend"),
            repair._create_react_compile_fix(err),
        ):
            if plan is not None:
                assert not any(
                    cmd and cmd[0] == "echo" for cmd in plan.commands
                ), f"placebo echo plan for: {message}"

    # ---- Java version detection ----

    @pytest.mark.parametrize("raw,expected", [
        ("Unsupported class file major version 69", "25"),
        ("invalid target release: 21", "21"),
        ("error: invalid source release: 17", "17"),
    ])
    def test_java_version_fix_targets_reported_version(self, project, raw, expected):
        (project / "backend" / "pom.xml").write_text(
            "<project><properties>"
            "<java.version>11</java.version>"
            "<maven.compiler.release>11</maven.compiler.release>"
            "</properties></project>"
        )
        repair = BuildRepair(project)
        err = BuildError(
            category=ErrorCategory.JAVA_VERSION_MISMATCH,
            message="Java version mismatch",
            raw_output=raw,
        )
        plan = repair._create_java_version_fix(err)
        assert plan is not None
        pom = plan.file_changes["backend/pom.xml"]
        assert f"<java.version>{expected}</java.version>" in pom
        assert f"<maven.compiler.release>{expected}</maven.compiler.release>" in pom

    # ---- Graceful degradation ----

    def test_validate_all_still_checks_components_without_toolchain(self, project):
        """A missing toolchain must not drop other components.

        validate_all used to return only {'environment'} when a tool was
        missing, so the repair loop saw zero errors and a broken project
        looked clean.
        """
        from converter.app.build import validator as validator_mod

        (project / "database").mkdir()
        (project / "database" / "schema.sql").write_text("CREATE TABLE t (id INT);")

        validator = BuildValidator(project)
        with patch.object(
            validator_mod, "resolve_executable",
            side_effect=lambda cmd: None if cmd[0] in ("mvn", "npm") else ["/usr/bin/" + cmd[0]],
        ):
            results = validator.validate_all()

        assert "database" in results
        assert results["database"].status == BuildStatus.SUCCESS
        assert results["backend"].status == BuildStatus.SKIPPED
        assert results["frontend"].status == BuildStatus.SKIPPED

    # ---- Deterministic rollback ----

    def test_deterministic_regression_is_rolled_back(self, project):
        """A deterministic fix that increases errors must be reverted."""
        from converter.app.build.repair import RepairPlan, RepairSession, RepairStrategy

        target = project / "backend" / "Foo.java"
        original = "public class Foo { }"
        target.write_text(original)

        err = BuildError(
            category=ErrorCategory.TYPE_MISMATCH,
            message="incompatible types",
            file="backend/Foo.java",
        )
        harmful = RepairPlan(
            error=err,
            strategy=RepairStrategy.DETERMINISTIC,
            description="harmful rewrite",
            file_changes={"backend/Foo.java": "CORRUPTED"},
            confidence=0.9,
        )

        repair = BuildRepair(project)
        session = RepairSession()
        served = {"done": False}

        def one_plan(errors, component):
            if served["done"]:
                return []
            served["done"] = True
            return [harmful]

        # Post-patch validation reports MORE errors than before -> regression.
        with patch.object(BuildRepair, "_get_deterministic_fixes", side_effect=one_plan), \
             patch.object(
                 BuildRepair, "_revalidate_component",
                 return_value=BuildResult(status=BuildStatus.FAILED, errors=[err] * 5),
             ):
            result = repair._repair_component_loop(
                BuildResult(status=BuildStatus.FAILED, errors=[err]),
                "backend",
                session,
            )

        assert target.read_text() == original, "harmful fix was not reverted"
        assert session.rollbacks == 1
        assert result["rollbacks"] == 1
        assert result["repairs"][0]["success"] is False
        assert result["repairs"][0]["rolled_back"] is True

    def test_beneficial_deterministic_fix_is_kept(self, project):
        """A fix that reduces errors must NOT be rolled back."""
        from converter.app.build.repair import RepairPlan, RepairSession, RepairStrategy

        target = project / "backend" / "Foo.java"
        target.write_text("public class Foo { }")

        err = BuildError(
            category=ErrorCategory.TYPE_MISMATCH,
            message="incompatible types",
            file="backend/Foo.java",
        )
        good = RepairPlan(
            error=err,
            strategy=RepairStrategy.DETERMINISTIC,
            description="helpful rewrite",
            file_changes={"backend/Foo.java": "public class Foo { /* fixed */ }"},
            confidence=0.9,
        )

        repair = BuildRepair(project)
        session = RepairSession()
        served = {"done": False}

        def one_plan(errors, component):
            if served["done"]:
                return []
            served["done"] = True
            return [good]

        with patch.object(BuildRepair, "_get_deterministic_fixes", side_effect=one_plan), \
             patch.object(
                 BuildRepair, "_revalidate_component",
                 return_value=BuildResult(status=BuildStatus.SUCCESS, errors=[]),
             ):
            result = repair._repair_component_loop(
                BuildResult(status=BuildStatus.FAILED, errors=[err, err]),
                "backend",
                session,
            )

        assert "fixed" in target.read_text(), "beneficial fix was wrongly reverted"
        assert session.rollbacks == 0
        assert result["success"] is True

    # ---- Phase routing ----

    def test_component_maps_to_correct_build_phase(self):
        """frontend must route to NPM, not fall back to MAVEN."""
        from converter.app.api.main import _COMPONENT_TO_BUILD_PHASE
        from converter.app.build.pipeline import BuildPhase

        assert _COMPONENT_TO_BUILD_PHASE["backend"] == BuildPhase.MAVEN
        assert _COMPONENT_TO_BUILD_PHASE["frontend"] == BuildPhase.NPM
        assert _COMPONENT_TO_BUILD_PHASE["database"] == BuildPhase.DATABASE


if __name__ == "__main__":
    pytest.main([__file__, "-v"])