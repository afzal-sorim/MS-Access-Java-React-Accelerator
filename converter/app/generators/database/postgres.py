"""PostgreSQL Schema Generator - generates schema.sql from IR tables.

Spec section 15: Deterministic type mapping from Access to PostgreSQL.
Spec section 44: Use snake_case, explicit PKs, FKs, indexes, constraints.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Optional


# Access type to PostgreSQL type mapping (spec section 15)
TYPE_MAP = {
    "Short Text": "VARCHAR",
    "Long Text": "TEXT",
    "Byte": "SMALLINT",
    "Integer (Short)": "SMALLINT",
    "Integer": "INTEGER",
    "Long Integer": "BIGINT",
    "BigInt": "BIGINT",
    "Single": "REAL",
    "Double": "DOUBLE PRECISION",
    "Currency": "NUMERIC(19,4)",
    "Decimal": "DECIMAL",
    "Numeric": "NUMERIC",
    "Date/Time": "TIMESTAMP",
    "Yes/No": "BOOLEAN",
    "Binary": "BYTEA",
    "VarBinary": "BYTEA",
    "Char": "CHAR",
    "Float": "DOUBLE PRECISION",
    "Time": "TIME",
    "TimeStamp": "TIMESTAMP",
    "Replication ID": "UUID",
    "Hyperlink": "TEXT",
    # Special types handled separately
    "Attachment": None,  # Unsupported
    "OLE Object": "BYTEA",  # With warning
    # Complex (multi-value) types — stored as JSONB arrays
    "Complex Byte": None,
    "Complex Integer": None,
    "Complex Long": None,
    "Complex Single": None,
    "Complex Double": None,
    "Complex Decimal": None,
    "Complex Text": None,
}


@dataclass
class ColumnSpec:
    """Specification for a database column."""
    name: str
    sql_type: str
    nullable: bool = True
    default: Optional[str] = None
    check_constraint: Optional[str] = None
    is_primary_key: bool = False
    is_unique: bool = False
    is_foreign_key: bool = False
    fk_table: Optional[str] = None
    fk_column: Optional[str] = None
    comment: Optional[str] = None


class PostgresSchemaGenerator:
    """Generates PostgreSQL schema from ApplicationIR tables."""

    def __init__(self, app_ir, *, schema_name: str = "public"):
        self.app = app_ir
        self.schema_name = schema_name
        self.statements: list[str] = []
        self.warnings: list[str] = []
        self._pk_map: dict[str, list[str]] = {}  # table -> list of pk columns
        self._fk_map: dict[str, list[dict]] = {}  # table -> list of FKs
        self._emitted_fk_cols: set[tuple[str, str]] = set()  # (table, column) -> avoid duplicate FK constraints

    def generate(self) -> str:
        """Generate the complete schema.sql content."""
        self.statements = []
        self.warnings = []
        self._emitted_fk_cols = set()

        # Header comment
        self.statements.append("-- Generated PostgreSQL Schema")
        self.statements.append(f"-- Source: {self.app.source_file}")
        self.statements.append(f"-- Application: {self.app.application_name}")
        self.statements.append("")
        self.statements.append(f"SET search_path TO {self.schema_name};")
        self.statements.append("")

        # Analyze primary keys and foreign keys
        self._analyze_keys()

        # Generate table statements
        for table in self.app.tables:
            if table.role == "SYSTEM":  # Skip system tables
                continue
            self._generate_table(table)

        # Generate indexes
        for table in self.app.tables:
            if table.role == "SYSTEM":
                continue
            for index in table.indexes:
                if not index.primary:  # Primary indexes already created
                    self._generate_index(table.name, index)

        # Generate foreign key constraints (after all tables)
        for table in self.app.tables:
            if table.role == "SYSTEM":
                continue
            for fk in self._fk_map.get(table.name, []):
                self._generate_fk_constraint(table.name, fk)

        # Generate views from Access SELECT queries
        self._generate_views()

        # Generate seed data
        self.statements.append("")
        self.statements.append("-- Seed Data")
        self._generate_seed_data()

        return "\n".join(self.statements)

    def _analyze_keys(self) -> None:
        """Analyze primary keys and foreign keys from relationships."""
        # Find primary keys from indexes — store all columns for composite PK support
        for table in self.app.tables:
            for idx in table.indexes:
                if idx.primary and idx.columns:
                    self._pk_map[table.name] = list(idx.columns)
                    break

        # Build foreign key map from relationships
        for rel in self.app.relationships:
            child_table = rel.child_table
            if child_table not in self._fk_map:
                self._fk_map[child_table] = []

            for i, col in enumerate(rel.child_columns):
                self._fk_map[child_table].append({
                    "column": col,
                    "parent_table": rel.parent_table,
                    "parent_column": rel.parent_columns[i] if i < len(rel.parent_columns) else rel.parent_columns[0],
                    "constraint_name": rel.name,
                    "cascade_update": rel.cascade_update,
                    "cascade_delete": rel.cascade_delete,
                })

    def _generate_table(self, table) -> None:
        """Generate CREATE TABLE statement."""
        self.statements.append(f"-- Table: {table.name}")

        if table.description:
            self.statements.append(f"-- {table.description}")

        self.statements.append(f"CREATE TABLE IF NOT EXISTS \"{self._to_snake(table.name)}\" (")

        columns_sql = []
        pk_columns = self._pk_map.get(table.name)  # list of PK column names, or None
        is_composite_pk = pk_columns is not None and len(pk_columns) > 1

        # If no primary key defined, add a synthetic surrogate PK
        if pk_columns is None:
            columns_sql.append('"generated_id" BIGSERIAL PRIMARY KEY')
            self.warnings.append(
                f"Table {table.name} has no primary key — synthetic 'generated_id' added"
            )

        for col in table.columns:
            col_spec = self._column_spec(col, table.name, pk_columns, is_composite_pk)
            columns_sql.append(self._format_column(col_spec))

        # Add composite primary key constraint as a table constraint
        if is_composite_pk:
            pk_col_list = ", ".join(f'"{self._to_snake(c)}"' for c in pk_columns)
            columns_sql.append(f"PRIMARY KEY ({pk_col_list})")

        self.statements.append(",\n".join(f"    {c}" for c in columns_sql))
        self.statements.append(");")
        self.statements.append("")

        # Add comment on table
        if table.description:
            self.statements.append(
                f"COMMENT ON TABLE \"{self._to_snake(table.name)}\" IS '{table.description}';"
            )

        # Add column comments
        for col in table.columns:
            if col.description:
                self.statements.append(
                    f"COMMENT ON COLUMN \"{self._to_snake(table.name)}\"."
                    f"\"{self._to_snake(col.name)}\" IS '{col.description}';"
                )

        self.statements.append("")

    def _column_spec(self, col, table_name: str, pk_columns: Optional[list[str]], is_composite_pk: bool = False) -> ColumnSpec:
        """Build column specification from IR column."""
        # Map Access type to PostgreSQL type
        sql_type = self._map_type(col.access_type, col)

        # Determine if primary key — any column in the PK index is a PK,
        # regardless of whether it is auto-number
        is_pk = pk_columns is not None and col.name in pk_columns

        # For composite PKs, PRIMARY KEY is emitted as a table constraint,
        # so individual columns should NOT be marked inline
        is_pk_inline = is_pk and not is_composite_pk

        # Handle auto-number (serial/identity)
        if col.auto_number and is_pk:
            sql_type = "BIGSERIAL" if "BIGINT" in sql_type else "SERIAL"

        # Default value
        default = None
        if col.default_value:
            default = self._convert_default(col.default_value, col.access_type)

        # Check constraint from validation rule
        check = None
        if col.validation_rule:
            check = self._convert_validation(col.validation_rule)

        # Check if foreign key
        is_fk = False
        fk_table = None
        fk_column = None
        fks = self._fk_map.get(table_name, [])
        for fk in fks:
            if fk["column"] == col.name:
                is_fk = True
                fk_table = fk["parent_table"]
                fk_column = fk["parent_column"]
                break

        return ColumnSpec(
            name=self._to_snake(col.name),
            sql_type=sql_type,
            nullable=col.allow_null and not is_pk,
            default=default,
            check_constraint=check,
            is_primary_key=is_pk_inline,
            is_unique=col.unique,
            is_foreign_key=is_fk,
            fk_table=fk_table,
            fk_column=fk_column,
            comment=col.description,
        )

    def _map_type(self, access_type: str, col) -> str:
        """Map Access type to PostgreSQL type."""
        base_type = TYPE_MAP.get(access_type)

        if base_type is None:
            # Handle special/unsupported types
            if access_type == "Attachment":
                self.warnings.append(
                    f"Column {col.name}: Attachment type not supported, using JSONB"
                )
                return "JSONB"
            if access_type == "OLE Object":
                self.warnings.append(
                    f"Column {col.name}: OLE Object stored as BYTEA"
                )
                return "BYTEA"
            if access_type.startswith("Complex"):
                self.warnings.append(
                    f"Column {col.name}: multi-value {access_type} stored as JSONB array"
                )
                return "JSONB"

            # Default fallback
            self.warnings.append(f"Unknown type '{access_type}' for column {col.name}, using TEXT")
            return "TEXT"

        # Add size for VARCHAR
        if base_type == "VARCHAR" and col.size:
            if col.size > 0:
                return f"VARCHAR({col.size})"

        # Add precision/scale for NUMERIC
        if base_type.startswith("NUMERIC") or base_type.startswith("DECIMAL"):
            if col.precision and col.scale:
                return f"NUMERIC({col.precision}, {col.scale})"
            elif col.precision:
                return f"NUMERIC({col.precision})"

        return base_type

    def _convert_default(self, default: str, access_type: str) -> Optional[str]:
        """Convert Access default value to PostgreSQL.

        Delegates to the shared expression engine.
        """
        from ...expressions import translate_postgres_default

        if not default:
            return None

        result = translate_postgres_default(default, access_type)
        if result is None and default.strip().startswith("="):
            self.warnings.append(
                f"Access default expression '{default}' could not be converted to PostgreSQL; omitted"
            )
        return result

    def _convert_validation(self, rule: str) -> Optional[str]:
        """Convert Access validation rule to PostgreSQL CHECK constraint."""
        if not rule:
            return None

        # Remove null characters
        rule = rule.replace("\x00", "").strip()

        # Common patterns
        # "Is Null Or Like '*@*'" -> CHECK (column IS NULL OR column LIKE '%@%')
        if "Like" in rule:
            rule = rule.replace("*", "%").replace("?", "_")

        return rule

    def _format_column(self, spec: ColumnSpec) -> str:
        """Format column specification for CREATE TABLE."""
        parts = [f'"{spec.name}"', spec.sql_type]

        if not spec.nullable:
            parts.append("NOT NULL")

        if spec.is_primary_key:
            parts.append("PRIMARY KEY")

        if spec.default:
            parts.append(f"DEFAULT {spec.default}")

        if spec.check_constraint:
            parts.append(f"CHECK ({spec.check_constraint})")

        if spec.is_unique and not spec.is_primary_key:
            parts.append("UNIQUE")

        return " ".join(parts)

    def _generate_index(self, table_name: str, index) -> None:
        """Generate CREATE INDEX statement."""
        if not index.columns:
            return

        idx_name = self._to_snake(index.name)
        table = self._to_snake(table_name)
        cols = ", ".join(f'"{self._to_snake(c)}"' for c in index.columns)

        unique = "UNIQUE " if index.unique else ""

        self.statements.append(
            f'CREATE {unique}INDEX IF NOT EXISTS "{idx_name}" ON "{table}" ({cols});'
        )

    def _generate_fk_constraint(self, table_name: str, fk: dict) -> None:
        """Generate ALTER TABLE for foreign key constraint."""
        table = self._to_snake(table_name)
        constraint = self._to_snake(fk["constraint_name"])
        col = self._to_snake(fk["column"])
        parent = self._to_snake(fk["parent_table"])
        parent_col = self._to_snake(fk["parent_column"])

        # Prevent duplicate FK constraints on the same (table, column) pair.
        # A single Access relationship with multiple child columns produces
        # multiple entries in _fk_map with the same constraint_name, and
        # keying on (table, constraint_name) wrongly deduplicates them.
        fk_key = (table, col)
        if fk_key in self._emitted_fk_cols:
            return
        self._emitted_fk_cols.add(fk_key)

        self.statements.append(
            f"ALTER TABLE \"{table}\" "
            f"ADD CONSTRAINT \"{constraint}_{col}\" "
            f"FOREIGN KEY (\"{col}\") "
            f"REFERENCES \"{parent}\" (\"{parent_col}\")"
        )

        actions = []
        if fk.get("cascade_update"):
            actions.append("ON UPDATE CASCADE")
        if fk.get("cascade_delete"):
            actions.append("ON DELETE CASCADE")

        if actions:
            self.statements[-1] += " " + " ".join(actions)

        self.statements[-1] += ";"

    def _generate_views(self) -> None:
        """Generate CREATE VIEW statements from Access SELECT queries."""
        if not hasattr(self.app, 'queries') or not self.app.queries:
            return

        from ...reporting.sql_translate import translate_access_sql

        # Collect table and query names for the translator
        known_tables = {t.name for t in self.app.tables if t.role != "SYSTEM"}
        known_queries = {q.name for q in self.app.queries}
        select_kinds = {"SELECT", "UNION", "PARAMETER"}

        views_emitted = False
        for query in self.app.queries:
            if query.kind.value not in select_kinds:
                continue
            if not query.sql or not query.sql.strip():
                continue

            view_name = self._to_snake(query.name)
            result = translate_access_sql(
                query.sql,
                known_tables=known_tables,
                known_queries=known_queries,
                declared_parameters=query.parameters,
            )

            if not views_emitted:
                self.statements.append("")
                self.statements.append("-- Views (from Access saved queries)")
                views_emitted = True

            if result.ok:
                self.statements.append(f'CREATE OR REPLACE VIEW "{view_name}" AS')
                self.statements.append(f"    {result.sql};")
                if result.notes:
                    for note in result.notes:
                        self.statements.append(f"-- NOTE: {note}")
            else:
                # Emit as a TODO comment so nothing is silently lost
                self.statements.append(f"-- TODO: View \"{view_name}\" could not be auto-translated:")
                for blocker in result.blockers:
                    self.statements.append(f"--   BLOCKER: {blocker}")
                self.statements.append(f"-- Original Access SQL:")
                for line in query.sql.strip().splitlines():
                    self.statements.append(f"--   {line}")

            self.statements.append("")

    def _generate_seed_data(self) -> None:
        """Generate INSERT statements for seed data from extracted table data."""
        if not hasattr(self.app, "_raw_data"):
            return

        table_data = self.app._raw_data.get("table_data", {})
        if not table_data:
            return

        for table_name, rows in table_data.items():
            if not rows:
                continue

            table = self._to_snake(table_name)
            self.statements.append(f"-- Seed data for {table_name}")

            for row in rows:
                columns = []
                values = []
                for col_name, value in row.items():
                    columns.append(f'"{self._to_snake(col_name)}"')
                    values.append(self._format_value(value))

                if columns:
                    self.statements.append(
                        f'INSERT INTO "{table}" ({", ".join(columns)}) '
                        f'VALUES ({", ".join(values)});'
                    )

            self.statements.append("")

    def _format_value(self, value) -> str:
        """Format a value for SQL INSERT."""
        if value is None:
            return "NULL"
        if isinstance(value, bool):
            return "TRUE" if value else "FALSE"
        if isinstance(value, (int, float)):
            return str(value)
        if isinstance(value, str):
            # Escape single quotes
            escaped = value.replace("'", "''")
            return f"'{escaped}'"
        # Default: stringify
        return f"'{str(value).replace(chr(39), chr(39)+chr(39))}'"

    @staticmethod
    def _to_snake(name: str) -> str:
        from ...naming import to_snake
        return to_snake(name)

    def write(self, output_path: str | Path) -> None:
        """Write the generated schema to a file."""
        path = Path(output_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(self.generate(), encoding="utf-8")


def generate_schema(app_ir, output_path: Optional[str | Path] = None) -> str:
    """Entry point to generate PostgreSQL schema."""
    generator = PostgresSchemaGenerator(app_ir)
    schema = generator.generate()

    if output_path:
        generator.write(output_path)

    return schema
