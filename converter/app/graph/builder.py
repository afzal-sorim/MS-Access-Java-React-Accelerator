"""Dependency Graph Builder - analyzes relationships between Access objects.

Spec section 11: Every Access object becomes a graph node. This is critical for:
- LLM context selection (only send relevant context)
- Correct generation ordering (tables before forms that use them)
- Identifying orphan objects and circular references
"""
from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional


class NodeType(str, Enum):
    TABLE = "TABLE"
    QUERY = "QUERY"
    FORM = "FORM"
    REPORT = "REPORT"
    MACRO = "MACRO"
    VBA_MODULE = "VBA_MODULE"
    VBA_PROCEDURE = "VBA_PROCEDURE"


@dataclass
class GraphNode:
    """A node in the dependency graph."""
    id: str  # Fully qualified name like "Employees" or "modBusiness.CalculateTotal"
    name: str  # Short name
    node_type: NodeType
    dependencies: list[str] = field(default_factory=list)  # What this node depends on
    dependents: list[str] = field(default_factory=list)  # What depends on this node
    depth: int = 0  # Distance from root (tables have depth 0)

    def __hash__(self):
        return hash(self.id)


class DependencyGraph:
    """Dependency graph for Access application objects."""

    def __init__(self):
        self.nodes: dict[str, GraphNode] = {}
        self._adjacency: dict[str, list[str]] = defaultdict(list)
        self._reverse_adjacency: dict[str, list[str]] = defaultdict(list)

    def add_node(self, node: GraphNode) -> None:
        """Add a node to the graph."""
        self.nodes[node.id] = node

    def add_edge(self, from_id: str, to_id: str) -> None:
        """Add a dependency edge: from_id depends on to_id."""
        if from_id not in self.nodes or to_id not in self.nodes:
            return  # Skip if nodes don't exist

        if to_id not in self._adjacency[from_id]:
            self._adjacency[from_id].append(to_id)

        if from_id not in self._reverse_adjacency[to_id]:
            self._reverse_adjacency[to_id].append(from_id)

        # Update node's dependency list
        if to_id not in self.nodes[from_id].dependencies:
            self.nodes[from_id].dependencies.append(to_id)
        if from_id not in self.nodes[to_id].dependents:
            self.nodes[to_id].dependents.append(from_id)

    def get_dependencies(self, node_id: str, recursive: bool = False) -> list[str]:
        """Get all dependencies of a node."""
        if not recursive:
            return self._adjacency.get(node_id, []).copy()

        # BFS to get all transitive dependencies
        visited = set()
        result = []
        queue = list(self._adjacency.get(node_id, []))

        while queue:
            dep = queue.pop(0)
            if dep not in visited:
                visited.add(dep)
                result.append(dep)
                queue.extend(self._adjacency.get(dep, []))

        return result

    def get_dependents(self, node_id: str, recursive: bool = False) -> list[str]:
        """Get all nodes that depend on this node."""
        if not recursive:
            return self._reverse_adjacency.get(node_id, []).copy()

        # BFS to get all transitive dependents
        visited = set()
        result = []
        queue = list(self._reverse_adjacency.get(node_id, []))

        while queue:
            dep = queue.pop(0)
            if dep not in visited:
                visited.add(dep)
                result.append(dep)
                queue.extend(self._reverse_adjacency.get(dep, []))

        return result

    def find_cycles(self) -> list[list[str]]:
        """Find all cycles in the dependency graph."""
        cycles = []
        visited = set()
        rec_stack = set()
        path = []

        def dfs(node_id: str) -> None:
            visited.add(node_id)
            rec_stack.add(node_id)
            path.append(node_id)

            for neighbor in self._adjacency.get(node_id, []):
                if neighbor not in visited:
                    dfs(neighbor)
                elif neighbor in rec_stack:
                    # Found a cycle
                    cycle_start = path.index(neighbor)
                    cycle = path[cycle_start:] + [neighbor]
                    cycles.append(cycle)

            path.pop()
            rec_stack.remove(node_id)

        for node_id in self.nodes:
            if node_id not in visited:
                dfs(node_id)

        return cycles

    def find_orphans(self) -> list[str]:
        """Find nodes with no dependencies and no dependents."""
        orphans = []
        for node_id, node in self.nodes.items():
            if not node.dependencies and not node.dependents:
                orphans.append(node_id)
        return orphans

    def find_unused(self) -> list[str]:
        """Find nodes that no other node depends on (dead code candidates)."""
        unused = []
        for node_id in self.nodes:
            if not self._reverse_adjacency.get(node_id):
                # Only mark as unused if it's not a top-level object (form/report)
                node = self.nodes[node_id]
                if node.node_type not in (NodeType.FORM, NodeType.REPORT, NodeType.MACRO):
                    unused.append(node_id)
        return unused

    def topological_sort(self) -> list[str]:
        """Return nodes in dependency order (dependencies first)."""
        import heapq

        in_degree = {node_id: 0 for node_id in self.nodes}
        for node_id in self.nodes:
            for dep in self._adjacency.get(node_id, []):
                in_degree[node_id] += 1

        # Start with nodes that have no dependencies.
        # Use a min-heap for O(log N) maintenance of deterministic order.
        queue = [node_id for node_id, degree in in_degree.items() if degree == 0]
        heapq.heapify(queue)
        result = []

        while queue:
            node_id = heapq.heappop(queue)
            result.append(node_id)

            # Reduce in-degree for dependents
            for dependent in self._reverse_adjacency.get(node_id, []):
                in_degree[dependent] -= 1
                if in_degree[dependent] == 0:
                    heapq.heappush(queue, dependent)

        # Check for cycles (nodes not in result)
        if len(result) != len(self.nodes):
            remaining = [n for n in self.nodes if n not in result]
            # Add remaining nodes anyway (they're part of cycles)
            result.extend(sorted(remaining))

        return result

    def calculate_depths(self) -> None:
        """Calculate depth for each node (distance from root tables)."""
        # Reset depths
        for node in self.nodes.values():
            node.depth = 0

        # Tables have depth 0
        for node in self.nodes.values():
            if node.node_type == NodeType.TABLE:
                node.depth = 0

        # Calculate depth for others using topological order
        sorted_nodes = self.topological_sort()
        for node_id in sorted_nodes:
            node = self.nodes[node_id]
            if node.dependencies:
                max_dep_depth = max(
                    self.nodes[dep].depth for dep in node.dependencies
                    if dep in self.nodes
                )
                node.depth = max_dep_depth + 1

    def get_context_for(self, node_id: str, max_depth: int = 3) -> list[str]:
        """Get relevant context nodes for LLM (dependencies up to max_depth)."""
        if node_id not in self.nodes:
            return []

        visited = set()
        result = []
        queue = [(node_id, 0)]

        while queue:
            current_id, depth = queue.pop(0)
            if current_id in visited:
                continue
            visited.add(current_id)

            if depth > 0:  # Don't include the target node itself
                result.append(current_id)

            if depth < max_depth:
                for dep in self._adjacency.get(current_id, []):
                    if dep not in visited:
                        queue.append((dep, depth + 1))

        return result

    def to_dict(self) -> dict:
        """Export graph to dictionary for JSON serialization."""
        return {
            "nodes": [
                {
                    "id": node.id,
                    "name": node.name,
                    "type": node.node_type.value,
                    "dependencies": node.dependencies,
                    "dependents": node.dependents,
                    "depth": node.depth,
                }
                for node in self.nodes.values()
            ],
            "edges": [
                {"from": from_id, "to": to_id}
                for from_id, deps in self._adjacency.items()
                for to_id in deps
            ],
        }


class GraphBuilder:
    """Builds dependency graph from ApplicationIR."""

    def __init__(self, app_ir):
        self.app = app_ir
        self.graph = DependencyGraph()
        self._table_names: set[str] = set()
        self._query_names: set[str] = set()
        self._form_names: set[str] = set()
        self._module_names: set[str] = set()

    def build(self) -> DependencyGraph:
        """Build the complete dependency graph."""
        # Collect all object names
        self._table_names = {t.name for t in self.app.tables}
        self._query_names = {q.name for q in self.app.queries}
        self._form_names = {f.name for f in self.app.forms}
        self._module_names = {m.name for m in self.app.vba_modules}

        # Add nodes for tables
        for table in self.app.tables:
            self.graph.add_node(GraphNode(
                id=table.name,
                name=table.name,
                node_type=NodeType.TABLE,
            ))

        # Add nodes for queries and their dependencies
        for query in self.app.queries:
            self.graph.add_node(GraphNode(
                id=query.name,
                name=query.name,
                node_type=NodeType.QUERY,
            ))
            # Add dependencies on tables
            for table_ref in query.references_tables:
                if table_ref in self._table_names:
                    self.graph.add_edge(query.name, table_ref)
            # Add dependencies on other queries
            for query_ref in query.references_queries:
                if query_ref in self._query_names:
                    self.graph.add_edge(query.name, query_ref)

        # Add nodes for forms and their dependencies
        for form in self.app.forms:
            self.graph.add_node(GraphNode(
                id=form.name,
                name=form.name,
                node_type=NodeType.FORM,
            ))

            # Dependency on record source (table or query)
            if form.record_source:
                source = form.record_source
                if source in self._table_names:
                    self.graph.add_edge(form.name, source)
                elif source in self._query_names:
                    self.graph.add_edge(form.name, source)

            # Dependencies on row sources (combos)
            for control in form.controls:
                if control.row_source:
                    rs = control.row_source
                    # Check if it's a table or query name
                    if rs in self._table_names:
                        self.graph.add_edge(form.name, rs)
                    elif rs in self._query_names:
                        self.graph.add_edge(form.name, rs)

            # Dependency on VBA module
            if form.module_name:
                self.graph.add_edge(form.name, form.module_name)

        # Add nodes for reports and their dependencies
        for report in self.app.reports:
            self.graph.add_node(GraphNode(
                id=report.name,
                name=report.name,
                node_type=NodeType.REPORT,
            ))

            # Dependency on record source
            if report.record_source:
                source = report.record_source
                if source in self._table_names:
                    self.graph.add_edge(report.name, source)
                elif source in self._query_names:
                    self.graph.add_edge(report.name, source)

            # Dependency on VBA module
            if report.module_name:
                self.graph.add_edge(report.name, report.module_name)

        # Add nodes for macros
        for macro in self.app.macros:
            self.graph.add_node(GraphNode(
                id=macro.name,
                name=macro.name,
                node_type=NodeType.MACRO,
            ))

        # Add nodes for VBA modules
        for module in self.app.vba_modules:
            self.graph.add_node(GraphNode(
                id=module.name,
                name=module.name,
                node_type=NodeType.VBA_MODULE,
            ))

            # Add procedure nodes
            for proc in module.procedures:
                proc_id = f"{module.name}.{proc.name}"
                self.graph.add_node(GraphNode(
                    id=proc_id,
                    name=proc.name,
                    node_type=NodeType.VBA_PROCEDURE,
                ))
                # Procedure depends on its module
                self.graph.add_edge(proc_id, module.name)

                # Procedure calls dependencies
                for call in proc.calls:
                    # Could be another procedure, table, query, etc.
                    if call in self._table_names:
                        self.graph.add_edge(proc_id, call)
                    elif call in self._query_names:
                        self.graph.add_edge(proc_id, call)
                    elif "." in call:  # Qualified procedure call
                        self.graph.add_edge(proc_id, call)

        # Calculate depths
        self.graph.calculate_depths()

        return self.graph


def build_dependency_graph(app_ir) -> DependencyGraph:
    """Entry point to build dependency graph from ApplicationIR."""
    return GraphBuilder(app_ir).build()
