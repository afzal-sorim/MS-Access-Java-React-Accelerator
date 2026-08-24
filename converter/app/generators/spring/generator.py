"""Spring Boot backend generator - JPA entities, repositories, services, controllers.

Spec section 43: Use standard Spring layered architecture.
Controller → Service → Repository → Entity/DTO
"""
from __future__ import annotations

from pathlib import Path
from typing import Optional


class SpringBootGenerator:
    """Generates Spring Boot backend from ApplicationIR."""

    def __init__(
        self,
        app_ir,
        *,
        base_package: str = "com.generated.app",
        app_name: Optional[str] = None,
        report_strategy: str = "pdf",
    ):
        self.app = app_ir
        self.base_package = base_package
        self.app_name = app_name or app_ir.application_name
        self.package_path = base_package.replace(".", "/")
        self.report_strategy = report_strategy
        self.warnings: list[str] = []
        self._pk_map: dict[str, str] = {}
        self._fk_map: dict[str, list[dict]] = {}
        # Populated by _generate_reports(); drives the optional PDF dependency.
        self.report_definitions: list = []
        self._needs_pdf_dependency = False

        # Analyze keys
        self._analyze_keys()

    def generate(self, output_dir: str | Path) -> dict[str, str]:
        """Generate all Spring Boot files and return a map of path -> content."""
        output_dir = Path(output_dir)
        files: dict[str, str] = {}

        # Generate directory structure
        src_main = output_dir / "src" / "main" / "java" / self.package_path
        src_test = output_dir / "src" / "test" / "java" / self.package_path
        resources = output_dir / "src" / "main" / "resources"

        # Generate entities
        for table in self.app.tables:
            if table.role in ("SYSTEM", "INTERNAL"):
                continue
            entity_name = self._to_pascal(table.name)
            entity_content = self._generate_entity(table)
            files[str(src_main / "entity" / f"{entity_name}.java")] = entity_content

        # Generate repositories
        for table in self.app.tables:
            if table.role in ("SYSTEM", "INTERNAL"):
                continue
            entity_name = self._to_pascal(table.name)
            repo_content = self._generate_repository(table)
            files[str(src_main / "repository" / f"{entity_name}Repository.java")] = repo_content

        # Generate services
        for table in self.app.tables:
            if table.role in ("SYSTEM", "INTERNAL"):
                continue
            entity_name = self._to_pascal(table.name)
            service_content = self._generate_service(table)
            files[str(src_main / "service" / f"{entity_name}Service.java")] = service_content

        # Generate controllers
        for table in self.app.tables:
            if table.role in ("SYSTEM", "INTERNAL", "LOOKUP"):
                # Lookups might still get read-only endpoints
                if table.role == "LOOKUP":
                    ctrl_content = self._generate_lookup_controller(table)
                    entity_name = self._to_pascal(table.name)
                    files[str(src_main / "controller" / f"{entity_name}Controller.java")] = ctrl_content
                continue
            entity_name = self._to_pascal(table.name)
            ctrl_content = self._generate_controller(table)
            files[str(src_main / "controller" / f"{entity_name}Controller.java")] = ctrl_content

        # Generate DTOs
        for table in self.app.tables:
            if table.role in ("SYSTEM",):
                continue
            entity_name = self._to_pascal(table.name)
            dto_content = self._generate_dto(table)
            files[str(src_main / "dto" / f"{entity_name}DTO.java")] = dto_content

        # Generate reports (spec section 20) before the pom, which may need
        # the PDF dependency.
        for name, content in self._generate_reports().items():
            files[str(src_main / "report" / name)] = content

        # Generate configuration
        files[str(resources / "application.yml")] = self._generate_application_yml()

        # Generate pom.xml
        files[str(output_dir / "pom.xml")] = self._generate_pom()

        return files

    def _generate_reports(self) -> dict[str, str]:
        """Generate the report package from the IR's reports."""
        from ...reporting.model import build_report_definitions
        from ...reporting.spring_reports import SpringReportGenerator

        self.report_definitions = build_report_definitions(self.app)
        if not self.report_definitions:
            return {}

        generator = SpringReportGenerator(
            self.report_definitions,
            base_package=self.base_package,
            report_strategy=self.report_strategy,
        )
        self._needs_pdf_dependency = generator.needs_pdf_dependency

        for definition in generator.skipped:
            reason = "; ".join(definition.blockers) or "no report SQL could be produced"
            self.warnings.append(f"report {definition.name} not generated: {reason}")

        return generator.generate()

    def write(self, output_dir: str | Path) -> None:
        """Generate and write all files to disk."""
        output_dir = Path(output_dir)
        files = self.generate(output_dir)

        for path, content in files.items():
            file_path = Path(path)
            file_path.parent.mkdir(parents=True, exist_ok=True)
            file_path.write_text(content, encoding="utf-8")

    # ---------------------------------------------------------------- helpers

    def _analyze_keys(self) -> None:
        """Analyze primary and foreign keys."""
        # Find primary keys
        for table in self.app.tables:
            for idx in table.indexes:
                if idx.primary and idx.columns:
                    self._pk_map[table.name] = idx.columns[0]
                    break

        # Build FK map
        for rel in self.app.relationships:
            child = rel.child_table
            if child not in self._fk_map:
                self._fk_map[child] = []
            for i, col in enumerate(rel.child_columns):
                self._fk_map[child].append({
                    "column": col,
                    "parent_table": rel.parent_table,
                    "parent_column": rel.parent_columns[i] if i < len(rel.parent_columns) else rel.parent_columns[0],
                })

    def _generate_entity(self, table) -> str:
        """Generate JPA entity class."""
        entity_name = self._to_pascal(table.name)
        table_name = self._to_snake(table.name)
        pk_col = self._pk_map.get(table.name)

        lines = [
            f"package {self.base_package}.entity;",
            "",
            "import jakarta.persistence.*;",
            "import java.math.BigDecimal;",
            "import java.time.LocalDateTime;",
            "",
            f"/** JPA entity for {table.name}. */",
            f"@Entity",
            f'@Table(name = "{table_name}")',
            f"public class {entity_name} {{",
        ]

        # Fields
        for col in table.columns:
            field_name = self._to_camel(col.name)
            java_type = self._map_java_type(col.access_type)

            # Annotations
            anns = []

            if col.name == pk_col:
                anns.append("@Id")
                if col.auto_number:
                    anns.append(f'@GeneratedValue(strategy = GenerationType.IDENTITY)')

            col_name = self._to_snake(col.name)
            if col_name != field_name:
                anns.append(f'@Column(name = "{col_name}")')
            else:
                anns.append("@Column")

            if not col.allow_null:
                anns[-1] = anns[-1].replace(")", ", nullable = false)")

            if col.unique:
                anns[-1] = anns[-1].replace(")", ", unique = true)")

            # Check for FK relationship
            fks = self._fk_map.get(table.name, [])
            for fk in fks:
                if fk["column"] == col.name:
                    parent_entity = self._to_pascal(fk["parent_table"])
                    anns = [f"@ManyToOne", f"@JoinColumn(name = \"{col_name}\")"]
                    java_type = parent_entity
                    field_name = self._to_camel(fk["parent_table"])
                    break

            for ann in anns:
                lines.append(f"    {ann}")
            lines.append(f"    private {java_type} {field_name};")
            lines.append("")

        # Constructors
        lines.append(f"    public {entity_name}() {{}}")
        lines.append("")

        # Getters and Setters
        for col in table.columns:
            field_name = self._to_camel(col.name)
            java_type = self._map_java_type(col.access_type)

            # Check for FK
            fks = self._fk_map.get(table.name, [])
            actual_field = field_name
            actual_type = java_type
            for fk in fks:
                if fk["column"] == col.name:
                    actual_field = self._to_camel(fk["parent_table"])
                    actual_type = self._to_pascal(fk["parent_table"])
                    break

            lines.append(f"    public {actual_type} get{self._to_pascal(actual_field)}() {{ return {actual_field}; }}")
            lines.append(f"    public void set{self._to_pascal(actual_field)}({actual_type} {actual_field}) {{ this.{actual_field} = {actual_field}; }}")
            lines.append("")

        lines.append("}")
        return "\n".join(lines)

    def _generate_repository(self, table) -> str:
        """Generate Spring Data JPA repository."""
        entity_name = self._to_pascal(table.name)

        return f"""package {self.base_package}.repository;

import {self.base_package}.entity.{entity_name};
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.stereotype.Repository;

/**
 * Repository for {entity_name} entities.
 */
@Repository
public interface {entity_name}Repository extends JpaRepository<{entity_name}, Long> {{
    // Custom query methods can be added here
}}
"""

    def _generate_service(self, table) -> str:
        """Generate service layer class."""
        entity_name = self._to_pascal(table.name)
        var_name = self._to_camel(table.name)

        return f"""package {self.base_package}.service;

import {self.base_package}.entity.{entity_name};
import {self.base_package}.repository.{entity_name}Repository;
import {self.base_package}.dto.{entity_name}DTO;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.util.List;
import java.util.Optional;

/**
 * Service layer for {entity_name} operations.
 */
@Service
@Transactional
public class {entity_name}Service {{

    @Autowired
    private {entity_name}Repository {var_name}Repository;

    public List<{entity_name}> findAll() {{
        return {var_name}Repository.findAll();
    }}

    public Optional<{entity_name}> findById(Long id) {{
        return {var_name}Repository.findById(id);
    }}

    public {entity_name} create({entity_name}DTO dto) {{
        {entity_name} entity = new {entity_name}();
        // Map DTO to entity
        return {var_name}Repository.save(entity);
    }}

    public {entity_name} update(Long id, {entity_name}DTO dto) {{
        Optional<{entity_name}> existing = {var_name}Repository.findById(id);
        if (existing.isEmpty()) {{
            throw new RuntimeException("{entity_name} not found: " + id);
        }}
        {entity_name} entity = existing.get();
        // Map DTO to entity
        return {var_name}Repository.save(entity);
    }}

    public void delete(Long id) {{
        {var_name}Repository.deleteById(id);
    }}
}}
"""

    def _generate_controller(self, table) -> str:
        """Generate REST controller."""
        entity_name = self._to_pascal(table.name)
        var_name = self._to_camel(table.name)
        endpoint = self._to_kebab(table.name)

        return f"""package {self.base_package}.controller;

import {self.base_package}.entity.{entity_name};
import {self.base_package}.service.{entity_name}Service;
import {self.base_package}.dto.{entity_name}DTO;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.*;

import java.util.List;

/**
 * REST controller for {entity_name} operations.
 */
@RestController
@RequestMapping("/api/{endpoint}")
@CrossOrigin(origins = "*")
public class {entity_name}Controller {{

    @Autowired
    private {entity_name}Service {var_name}Service;

    @GetMapping
    public List<{entity_name}> getAll() {{
        return {var_name}Service.findAll();
    }}

    @GetMapping("/{{id}}")
    public ResponseEntity<{entity_name}> getById(@PathVariable Long id) {{
        return {var_name}Service.findById(id)
            .map(ResponseEntity::ok)
            .orElse(ResponseEntity.notFound().build());
    }}

    @PostMapping
    public {entity_name} create(@RequestBody {entity_name}DTO dto) {{
        return {var_name}Service.create(dto);
    }}

    @PutMapping("/{{id}}")
    public {entity_name} update(@PathVariable Long id, @RequestBody {entity_name}DTO dto) {{
        return {var_name}Service.update(id, dto);
    }}

    @DeleteMapping("/{{id}}")
    public ResponseEntity<Void> delete(@PathVariable Long id) {{
        {var_name}Service.delete(id);
        return ResponseEntity.ok().build();
    }}
}}
"""

    def _generate_lookup_controller(self, table) -> str:
        """Generate read-only controller for lookup tables."""
        entity_name = self._to_pascal(table.name)
        var_name = self._to_camel(table.name)
        endpoint = self._to_kebab(table.name)

        return f"""package {self.base_package}.controller;

import {self.base_package}.entity.{entity_name};
import {self.base_package}.repository.{entity_name}Repository;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.web.bind.annotation.*;

import java.util.List;

/**
 * Read-only controller for {entity_name} lookup data.
 */
@RestController
@RequestMapping("/api/{endpoint}")
@CrossOrigin(origins = "*")
public class {entity_name}Controller {{

    @Autowired
    private {entity_name}Repository {var_name}Repository;

    @GetMapping
    public List<{entity_name}> getAll() {{
        return {var_name}Repository.findAll();
    }}
}}
"""

    def _generate_dto(self, table) -> str:
        """Generate DTO class."""
        entity_name = self._to_pascal(table.name)

        lines = [
            f"package {self.base_package}.dto;",
            "",
            "import java.math.BigDecimal;",
            "import java.time.LocalDateTime;",
            "",
            f"/** DTO for {entity_name}. */",
            f"public class {entity_name}DTO {{",
        ]

        # Fields (same as entity but without JPA annotations)
        for col in table.columns:
            field_name = self._to_camel(col.name)
            java_type = self._map_java_type(col.access_type)
            lines.append(f"    private {java_type} {field_name};")

        lines.append("")

        # Getters and Setters
        for col in table.columns:
            field_name = self._to_camel(col.name)
            java_type = self._map_java_type(col.access_type)
            lines.append(f"    public {java_type} get{self._to_pascal(field_name)}() {{ return {field_name}; }}")
            lines.append(f"    public void set{self._to_pascal(field_name)}({java_type} {field_name}) {{ this.{field_name} = {field_name}; }}")
            lines.append("")

        lines.append("}")
        return "\n".join(lines)

    def _generate_application_yml(self) -> str:
        """Generate application.yml configuration."""
        return f"""spring:
  application:
    name: {self.app_name}
  datasource:
    url: jdbc:postgresql://localhost:5432/{self._to_snake(self.app_name)}
    username: postgres
    password: postgres
    driver-class-name: org.postgresql.Driver
  jpa:
    hibernate:
      ddl-auto: validate
    show-sql: false
    properties:
      hibernate:
        dialect: org.hibernate.dialect.PostgreSQLDialect
        format_sql: true

server:
  port: 8080

logging:
  level:
    {self.base_package}: DEBUG
    org.hibernate.SQL: DEBUG
"""

    def _generate_pom(self) -> str:
        """Generate Maven pom.xml.

        Dependencies are added only when something generated actually needs
        them (spec section 29), and versions are pinned exactly rather than
        ranged (spec section 26).
        """
        extra_dependencies = ""
        if self._needs_pdf_dependency:
            from ...reporting.spring_reports import PDF_DEPENDENCY

            extra_dependencies = f"""
        <!-- Required by generated report PDF output (Access reports). -->
        <dependency>
            <groupId>{PDF_DEPENDENCY['groupId']}</groupId>
            <artifactId>{PDF_DEPENDENCY['artifactId']}</artifactId>
            <version>{PDF_DEPENDENCY['version']}</version>
        </dependency>"""

        return f"""<?xml version="1.0" encoding="UTF-8"?>
<project xmlns="http://maven.apache.org/POM/4.0.0"
         xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"
         xsi:schemaLocation="http://maven.apache.org/POM/4.0.0 http://maven.apache.org/xsd/maven-4.0.0.xsd">
    <modelVersion>4.0.0</modelVersion>

    <parent>
        <groupId>org.springframework.boot</groupId>
        <artifactId>spring-boot-starter-parent</artifactId>
        <version>4.1.0</version>
        <relativePath/>
    </parent>

    <groupId>{self.base_package}</groupId>
    <artifactId>{self._to_kebab(self.app_name)}</artifactId>
    <version>1.0.0</version>
    <name>{self.app_name}</name>
    <description>Generated from MS Access application</description>

    <properties>
        <java.version>25</java.version>
    </properties>

    <dependencies>
        <dependency>
            <groupId>org.springframework.boot</groupId>
            <artifactId>spring-boot-starter-web</artifactId>
        </dependency>
        <dependency>
            <groupId>org.springframework.boot</groupId>
            <artifactId>spring-boot-starter-data-jpa</artifactId>
        </dependency>
        <dependency>
            <groupId>org.springframework.boot</groupId>
            <artifactId>spring-boot-starter-validation</artifactId>
        </dependency>
        <dependency>
            <groupId>org.postgresql</groupId>
            <artifactId>postgresql</artifactId>
            <scope>runtime</scope>
        </dependency>{extra_dependencies}
        <dependency>
            <groupId>org.springframework.boot</groupId>
            <artifactId>spring-boot-starter-test</artifactId>
            <scope>test</scope>
        </dependency>
    </dependencies>

    <build>
        <plugins>
            <plugin>
                <groupId>org.springframework.boot</groupId>
                <artifactId>spring-boot-maven-plugin</artifactId>
            </plugin>
        </plugins>
    </build>
</project>
"""

    def _map_java_type(self, access_type: str) -> str:
        """Map Access type to Java type."""
        type_map = {
            "Short Text": "String",
            "Long Text": "String",
            "Byte": "Integer",
            "Integer (Short)": "Integer",
            "Integer": "Integer",
            "Long Integer": "Long",
            "BigInt": "Long",
            "Single": "Float",
            "Double": "Double",
            "Currency": "BigDecimal",
            "Decimal": "BigDecimal",
            "Numeric": "BigDecimal",
            "Date/Time": "LocalDateTime",
            "Yes/No": "Boolean",
            "Binary": "byte[]",
            "Replication ID": "String",
            "Hyperlink": "String",
            "OLE Object": "byte[]",
        }
        return type_map.get(access_type, "String")

    @staticmethod
    def _to_pascal(name: str) -> str:
        """Convert to PascalCase."""
        parts = name.replace("_", " ").replace("-", " ").split()
        return "".join(p.capitalize() for p in parts)

    @staticmethod
    def _to_camel(name: str) -> str:
        """Convert to camelCase."""
        pascal = SpringBootGenerator._to_pascal(name)
        return pascal[0].lower() + pascal[1:] if pascal else pascal

    @staticmethod
    def _to_snake(name: str) -> str:
        """Convert to snake_case."""
        import re
        s1 = re.sub(r'(.)([A-Z][a-z]+)', r'\1_\2', name)
        return re.sub(r'([a-z0-9])([A-Z])', r'\1_\2', s1).lower()

    @staticmethod
    def _to_kebab(name: str) -> str:
        """Convert to kebab-case."""
        return SpringBootGenerator._to_snake(name).replace("_", "-")


def generate_spring_boot(app_ir, output_dir: str | Path, **kwargs) -> dict[str, str]:
    """Entry point to generate Spring Boot backend."""
    generator = SpringBootGenerator(app_ir, **kwargs)
    return generator.generate(output_dir)
