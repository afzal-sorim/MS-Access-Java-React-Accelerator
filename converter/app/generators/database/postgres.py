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
    "Replication ID": "UUID",
    "Hyperlink": "TEXT",
    # Special types handled separately
    "Attachment": None,  # Unsupported
    "OLE Object": "BYTEA",  # With warning
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
        self._pk_map: dict[str, str] = {}  # table -> pk column
        self._fk_map: dict[str, list[dict]] = {}  # table -> list of FKs

    def generate(self) -> str:
        """Generate the complete schema.sql content."""
        self.statements = []
        self.warnings = []

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

        # Generate seed data
        self.statements.append("")
        self.statements.append("-- Seed Data")
        self._generate_seed_data()

        return "\n".join(self.statements)

    def _analyze_keys(self) -> None:
        """Analyze primary keys and foreign keys from relationships."""
        # Find primary keys from indexes
        for table in self.app.tables:
            for idx in table.indexes:
                if idx.primary and idx.columns:
                    self._pk_map[table.name] = idx.columns[0]
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
        primary_key_col = self._pk_map.get(table.name)

        for col in table.columns:
            col_spec = self._column_spec(col, table.name, primary_key_col)
            columns_sql.append(self._format_column(col_spec))

        # Add primary key constraint if composite or explicit
        if primary_key_col:
            # Single column PK is handled inline
            pass

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

    def _column_spec(self, col, table_name: str, pk_col: Optional[str]) -> ColumnSpec:
        """Build column specification from IR column."""
        # Map Access type to PostgreSQL type
        sql_type = self._map_type(col.access_type, col)

        # Determine if primary key
        is_pk = pk_col == col.name and col.auto_number

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
            is_primary_key=is_pk,
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
        """Convert Access default value to PostgreSQL."""
        if not default:
            return None

        default = default.strip("'\"")

        # Common Access defaults
        if default.lower() == "true":
            return "TRUE"
        if default.lower() == "false":
            return "FALSE"
        if default.lower() in ("now()", "date()", "time()"):
            return "CURRENT_TIMESTAMP"

        # String literal
        if access_type in ("Short Text", "Long Text", "Hyperlink"):
            return f"'{default}'"

        # Number
        try:
            float(default)
            return default
        except ValueError:
            pass

        return f"'{default}'"

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

        self.statements.append(
            f"ALTER TABLE \"{table}\" "
            f"ADD CONSTRAINT \"{constraint}\" "
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
        """Convert CamelCase to snake_case."""
        import re
        s1 = re.sub(r'(.)([A-Z][a-z]+)', r'\1_\2', name)
        return re.sub(r'([a-z0-9])([A-Z])', r'\1_\2', s1).lower()

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
