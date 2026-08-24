"""Query Analyzer - classifies queries and detects Access-specific functions.

Spec section 16: Queries must be classified and Access-specific functions detected.
Simple queries converted deterministically; complex queries may invoke LLM.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from enum import Enum
from typing import Optional


class QueryClassification(str, Enum):
    READ = "READ"  # SELECT queries
    WRITE = "WRITE"  # INSERT, UPDATE, DELETE
    AGGREGATE = "AGGREGATE"  # GROUP BY, totals
    PARAMETERIZED = "PARAMETERIZED"
    NESTED = "NESTED"  # Contains subqueries
    COMPLEX = "COMPLEX"  # Needs LLM analysis


@dataclass
class QueryAnalysis:
    """Result of query analysis."""
    name: str
    classification: QueryClassification
    table_refs: list[str]
    query_refs: list[str]
    access_functions: list[str]
    parameters: list[dict]
    joins: list[str]
    has_aggregates: bool
    complexity_score: int  # 1-10
    issues: list[str]
    suggested_operation: Optional[str] = None  # e.g., "list", "get", "update"


# Access function mappings to PostgreSQL equivalents
ACCESS_FUNCTION_MAP = {
    "Nz": "COALESCE",
    "IIf": "CASE WHEN",
    "Date": "CURRENT_DATE",
    "Now": "CURRENT_TIMESTAMP",
    "Year": "EXTRACT(YEAR FROM",
    "Month": "EXTRACT(MONTH FROM",
    "Day": "EXTRACT(DAY FROM",
    "Hour": "EXTRACT(HOUR FROM",
    "Minute": "EXTRACT(MINUTE FROM",
    "Second": "EXTRACT(SECOND FROM",
    "DateDiff": None,  # Needs custom handling
    "DateAdd": None,  # Needs custom handling
    "DatePart": None,  # Needs custom handling
    "Format": "TO_CHAR",
    "Str": "CAST",
    "Val": "CAST",
    "Len": "LENGTH",
    "Left": "LEFT",
    "Right": "RIGHT",
    "Mid": "SUBSTRING",
    "InStr": "POSITION",
    "Replace": "REPLACE",
    "Trim": "TRIM",
    "LTrim": "LTRIM",
    "RTrim": "RTRIM",
    "UCase": "UPPER",
    "LCase": "LOWER",
    "Abs": "ABS",
    "Round": "ROUND",
    "Int": "FLOOR",
    "Sqr": "SQRT",
    # Domain aggregates - need transformation to subqueries
    "DLookup": None,
    "DCount": None,
    "DSum": None,
    "DAvg": None,
    "DMax": None,
    "DMin": None,
    "DFirst": None,
    "DLast": None,
    # Conditional
    "Switch": "CASE",
    "Choose": "CASE",
    "Partition": None,
}


class QueryAnalyzer:
    """Analyzes Access SQL queries for conversion."""

    ACCESS_FUNC_PATTERN = re.compile(
        r'\b(' + '|'.join(re.escape(f) for f in ACCESS_FUNCTION_MAP.keys()) + r')\s*\(',
        re.IGNORECASE
    )

    # Patterns for SQL analysis
    SELECT_PATTERN = re.compile(r'\bSELECT\b', re.IGNORECASE)
    FROM_PATTERN = re.compile(r'\bFROM\s+\[?(\w+)\]?', re.IGNORECASE)
    JOIN_PATTERN = re.compile(r'\b(?:INNER|LEFT|RIGHT|OUTER)?\s*JOIN\s+\[?(\w+)\]?', re.IGNORECASE)
    WHERE_PATTERN = re.compile(r'\bWHERE\b', re.IGNORECASE)
    GROUP_BY_PATTERN = re.compile(r'\bGROUP\s+BY\b', re.IGNORECASE)
    ORDER_BY_PATTERN = re.compile(r'\bORDER\s+BY\b', re.IGNORECASE)
    HAVING_PATTERN = re.compile(r'\bHAVING\b', re.IGNORECASE)
    PARAM_PATTERN = re.compile(r'\bPARAMETERS\s+(.+?);', re.IGNORECASE | re.DOTALL)
    PARAM_REF_PATTERN = re.compile(r'\[([^\]]+)\]', re.IGNORECASE)
    AGGREGATE_PATTERN = re.compile(
        r'\b(SUM|COUNT|AVG|MIN|MAX|FIRST|LAST|STDEV|VAR)\s*\(',
        re.IGNORECASE
    )
    SUBQUERY_PATTERN = re.compile(r'\(\s*SELECT\b', re.IGNORECASE)

    def __init__(self, query_name: str, sql: str, parameters: Optional[list] = None):
        self.name = query_name
        self.sql = sql
        self.parameters = parameters or []
        self.sql_upper = sql.upper()

    def analyze(self) -> QueryAnalysis:
        """Perform full analysis of the query."""
        classification = self._classify()
        table_refs = self._extract_table_refs()
        query_refs = self._extract_query_refs()
        access_funcs = self._extract_access_functions()
        joins = self._extract_joins()
        has_aggregates = self._has_aggregates()
        complexity = self._calculate_complexity(
            table_refs, query_refs, access_funcs, joins, has_aggregates
        )
        issues = self._find_issues(access_funcs, classification)
        operation = self._suggest_operation(classification)

        return QueryAnalysis(
            name=self.name,
            classification=classification,
            table_refs=table_refs,
            query_refs=query_refs,
            access_functions=access_funcs,
            parameters=self.parameters,
            joins=joins,
            has_aggregates=has_aggregates,
            complexity_score=complexity,
            issues=issues,
            suggested_operation=operation,
        )

    def _classify(self) -> QueryClassification:
        """Classify the query type."""
        sql = self.sql_upper.strip()

        # Check for parameters
        if self.parameters or "PARAMETERS" in sql:
            return QueryClassification.PARAMETERIZED

        # Check for subqueries
        if self.SUBQUERY_PATTERN.search(self.sql):
            return QueryClassification.NESTED

        # Check for aggregates
        if self.GROUP_BY_PATTERN.search(self.sql) or self.HAVING_PATTERN.search(self.sql):
            return QueryClassification.AGGREGATE

        # Check for write operations
        if sql.startswith("INSERT"):
            return QueryClassification.WRITE
        if sql.startswith("UPDATE"):
            return QueryClassification.WRITE
        if sql.startswith("DELETE"):
            return QueryClassification.WRITE

        # Check for complexity
        access_funcs = self._extract_access_functions()
        if any(f in ("DLookup", "DCount", "DSum", "DMax", "DMin", "DAvg") for f in access_funcs):
            return QueryClassification.COMPLEX

        return QueryClassification.READ

    def _extract_table_refs(self) -> list[str]:
        """Extract all table names referenced in the query."""
        refs = set()

        # FROM clause
        for match in self.FROM_PATTERN.finditer(self.sql):
            refs.add(match.group(1))

        # JOIN clauses
        for match in self.JOIN_PATTERN.finditer(self.sql):
            refs.add(match.group(1))

        # INTO clause for INSERT
        into_match = re.search(r'\bINTO\s+\[?(\w+)\]?', self.sql, re.IGNORECASE)
        if into_match:
            refs.add(into_match.group(1))

        return sorted(refs)

    def _extract_query_refs(self) -> list[str]:
        """Extract references to other queries (nested queries)."""
        # Find bracketed identifiers that aren't tables
        refs = set()
        bracket_matches = self.PARAM_REF_PATTERN.findall(self.sql)

        # Filter out parameter references and known tables
        param_names = {p.get("name", "").lower() for p in self.parameters}
        table_names = set(t.lower() for t in self._extract_table_refs())

        for match in bracket_matches:
            name = match.strip("[]")
            if name.lower() not in param_names and name.lower() not in table_names:
                refs.add(name)

        return sorted(refs)

    def _extract_access_functions(self) -> list[str]:
        """Extract Access-specific function calls."""
        funcs = set()
        for match in self.ACCESS_FUNC_PATTERN.finditer(self.sql):
            funcs.add(match.group(1))
        return sorted(funcs)

    def _extract_joins(self) -> list[str]:
        """Extract join information."""
        joins = []
        for match in self.JOIN_PATTERN.finditer(self.sql):
            joins.append(match.group(0).strip())
        return joins

    def _has_aggregates(self) -> bool:
        """Check if query has aggregate functions."""
        return bool(self.AGGREGATE_PATTERN.search(self.sql))

    def _calculate_complexity(
        self,
        tables: list[str],
        queries: list[str],
        funcs: list[str],
        joins: list[str],
        has_aggregates: bool,
    ) -> int:
        """Calculate complexity score (1-10)."""
        score = 1

        # Base complexity from table count
        score += min(len(tables), 3)

        # Nested queries add complexity
        if queries:
            score += 2

        # Joins add complexity
        score += min(len(joins), 2)

        # Aggregates add complexity
        if has_aggregates:
            score += 1

        # Access-specific functions
        domain_aggregates = sum(1 for f in funcs if f.startswith("D"))
        score += domain_aggregates

        # Other Access functions
        other_funcs = len(funcs) - domain_aggregates
        score += min(other_funcs, 2)

        # Parameters
        if self.parameters:
            score += 1

        return min(score, 10)

    def _find_issues(self, funcs: list[str], classification: QueryClassification) -> list[str]:
        """Find potential issues with the query."""
        issues = []

        # Check for unsupported functions
        for func in funcs:
            if func in ("DLookup", "DCount", "DSum", "DMax", "DMin", "DAvg"):
                issues.append(f"Domain aggregate {func}() needs transformation to subquery")
            elif ACCESS_FUNCTION_MAP.get(func) is None:
                issues.append(f"Function {func}() requires custom handling")

        # Check for complex patterns
        if classification == QueryClassification.COMPLEX:
            issues.append("Query classified as complex - may need LLM analysis")

        # Check for multiple table references without explicit joins
        if len(self._extract_table_refs()) > 1 and not self._extract_joins():
            issues.append("Multiple tables without explicit JOIN - may use old-style joins")

        return issues

    def _suggest_operation(self, classification: QueryClassification) -> Optional[str]:
        """Suggest the target operation type."""
        if classification == QueryClassification.READ:
            # Analyze if it's a list or single item query
            if "TOP 1" in self.sql_upper or "LIMIT 1" in self.sql_upper:
                return "get"
            return "list"
        elif classification == QueryClassification.AGGREGATE:
            return "aggregate"
        elif classification == QueryClassification.WRITE:
            if self.sql_upper.strip().startswith("INSERT"):
                return "create"
            elif self.sql_upper.strip().startswith("UPDATE"):
                return "update"
            elif self.sql_upper.strip().startswith("DELETE"):
                return "delete"
        elif classification == QueryClassification.PARAMETERIZED:
            if self.sql_upper.strip().startswith("SELECT"):
                return "list"
            elif self.sql_upper.strip().startswith("UPDATE"):
                return "update"
        return None

    def convert_to_postgresql(self) -> str:
        """Convert Access SQL to PostgreSQL (deterministic conversion only)."""
        sql = self.sql

        # Simple transformations
        # Replace [] with ""
        sql = re.sub(r'\[([^\]]+)\]', r'"\1"', sql)

        # Replace Access wildcards
        sql = sql.replace("*", "%").replace("?", "_")

        # Replace True/False
        sql = re.sub(r'\bTrue\b', 'TRUE', sql, flags=re.IGNORECASE)
        sql = re.sub(r'\bFalse\b', 'FALSE', sql, flags=re.IGNORECASE)

        # Handle basic function conversions
        for access_func, pg_func in ACCESS_FUNCTION_MAP.items():
            if pg_func and access_func in self._extract_access_functions():
                # This is simplified - real conversion would need SQL parsing
                if access_func == "Nz":
                    sql = re.sub(r'\bNz\s*\(', 'COALESCE(', sql, flags=re.IGNORECASE)
                elif access_func in ("UCase", "LCase"):
                    replacement = "UPPER" if access_func == "UCase" else "LOWER"
                    sql = re.sub(
                        rf'\b{access_func}\s*\(', f'{replacement}(',
                        sql, flags=re.IGNORECASE
                    )

        return sql


def analyze_query(query) -> QueryAnalysis:
    """Entry point to analyze a query."""
    analyzer = QueryAnalyzer(
        query.name,
        query.sql,
        query.parameters if hasattr(query, 'parameters') else None
    )
    return analyzer.analyze()
