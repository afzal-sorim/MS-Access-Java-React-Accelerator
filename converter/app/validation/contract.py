"""Cross-layer contract validator (PHASE 20).

Validates that the React frontend, api.js, Spring controllers/entities,
and PostgreSQL schema all agree on identifiers and endpoints.

For every table-bound form:

    React page imports get{Pascal} from api.js
       ↕
    api.js exports get{Pascal} / get{Pascal}ById / etc.
       ↕
    Spring @GetMapping("/api/{kebab}")
       ↕
    PostgreSQL table "{snake}"

A missing link is a CONVERSION_VALIDATION_ERROR.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any


@dataclass
class ContractViolation:
    severity: str          # ERROR | WARNING
    layer: str              # REACT | API_CLIENT | SPRING | POSTGRES
    object: str             # form / table / query name
    detail: str


@dataclass
class ContractReport:
    violations: list[ContractViolation] = field(default_factory=list)

    @property
    def has_errors(self) -> bool:
        return any(v.severity == "ERROR" for v in self.violations)

    def to_dict(self) -> dict[str, Any]:
        return {
            "valid": not self.has_errors,
            "errorCount": sum(1 for v in self.violations if v.severity == "ERROR"),
            "warningCount": sum(1 for v in self.violations if v.severity == "WARNING"),
            "violations": [
                {"severity": v.severity, "layer": v.layer,
                 "object": v.object, "detail": v.detail}
                for v in self.violations
            ],
        }


def _norm(path: str) -> str:
    """Normalize a generated-file path so checks work on any OS."""
    return path.replace("\\", "/")


def _strip_api_prefix(endpoint: str) -> str:
    """Spring mounts controllers under /api while api.js builds URLs from
    API_BASE (which already ends in /api); normalize both to the same form."""
    prefix = "/api"
    while endpoint.startswith(prefix):
        endpoint = endpoint[len(prefix):]
    return endpoint or "/"


class ContractValidator:
    """Validates cross-layer naming/endpoint consistency."""

    def __init__(self, app_ir):
        self.app = app_ir
        self.report = ContractReport()

    def validate(self, generated_files: dict[str, str]) -> ContractReport:
        """Run all validations against the generated file set."""
        self._validate_api_imports(generated_files)
        self._validate_spring_endpoints(generated_files)
        self._validate_postgres_tables(generated_files)
        return self.report

    # ------------------------------------------------------------------

    def _validate_api_imports(self, files: dict[str, str]) -> None:
        """Check React pages import functions that exist in api.js."""
        api_content = ""
        for path, content in files.items():
            if "api.js" in _norm(path) and "services/" in _norm(path):
                api_content = content
                break

        if not api_content:
            return

        # Collect exported function names from api.js
        exported: set[str] = set()
        for m in re.finditer(r'export\s+(?:async\s+)?function\s+(\w+)', api_content):
            exported.add(m.group(1))

        # Check each React page imports
        for path, content in files.items():
            norm = _norm(path)
            if "pages/" not in norm or not norm.endswith(".jsx"):
                continue
            for m in re.finditer(r'import\s+\{[^}]*\}\s+from\s+["\'].*api["\']', content):
                # Extract individual named imports
                names = re.findall(r'\b(\w+)\b', m.group(0).split('from')[0])
                names = [n for n in names if n not in ('import', 'from', 'async')]
                for name in names:
                    if name.startswith('get') or name.startswith('create') or name.startswith('update') or name.startswith('delete'):
                        if name not in exported:
                            self.report.violations.append(ContractViolation(
                                severity="ERROR",
                                layer="REACT",
                                object=_norm(path).split("/")[-1],
                                detail=f"imports {name}() but api.js does not export it",
                            ))

    def _validate_spring_endpoints(self, files: dict[str, str]) -> None:
        """Check Spring controllers expose @RequestMapping paths React needs."""
        endpoints: set[str] = set()
        for path, content in files.items():
            if _norm(path).endswith("Controller.java"):
                for m in re.finditer(r'@RequestMapping\("(/[^"]+)"\)', content):
                    endpoints.add(_strip_api_prefix(m.group(1)))

        if not endpoints:
            return

        # Collect API_BASE + endpoint references from api.js
        api_content = ""
        for path, content in files.items():
            if "api.js" in _norm(path) and "services/" in _norm(path):
                api_content = content
                break
        if not api_content:
            return

        api_endpoints: set[str] = set()
        # Match fetch(`${API_BASE}/path`) patterns
        for m in re.finditer(r'\$\{API_BASE\}(/[\w\-]+)', api_content):
            api_endpoints.add(_strip_api_prefix(m.group(1)))

        for ep in api_endpoints:
            if ep not in endpoints:
                self.report.violations.append(ContractViolation(
                    severity="ERROR",
                    layer="API_CLIENT",
                    object=ep,
                    detail=f"api.js calls {ep} but no Spring controller exposes it",
                ))

    def _validate_postgres_tables(self, files: dict[str, str]) -> None:
        """Check schema.sql defines tables for every JPA entity."""
        schema_content = ""
        for path, content in files.items():
            if path.endswith("schema.sql"):
                schema_content = content
                break
        if not schema_content:
            return

        db_tables: set[str] = set()
        for m in re.finditer(r'CREATE\s+TABLE\s+IF\s+NOT\s+EXISTS\s+"([^"]+)"', schema_content, re.IGNORECASE):
            db_tables.add(m.group(1).lower())

        for table in self.app.tables:
            from ..naming import to_snake
            expected = to_snake(table.name)
            if expected.lower() not in db_tables:
                self.report.violations.append(ContractViolation(
                    severity="ERROR",
                    layer="POSTGRES",
                    object=table.name,
                    detail=f"table '{expected}' not found in schema.sql",
                ))
