"""Business Rule Extractor - extracts business rules from VBA, macros, and table validations.

Spec section 33: Extract rules with metadata (origin, source, confidence).
Spec section 34: BusinessRuleIR model with rule_type, natural_language, pseudo_code, etc.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Optional

from ..ir.models import (
    BusinessRuleIR, TableIR, ColumnIR, FormIR, ControlIR,
    QueryIR, VbaModuleIR, KnowledgeOrigin
)

from .vba import parse_vba_module
from .macro import parse_macro
from .query import analyze_query


@dataclass
class ExtractedRule:
    """A business rule extracted from source."""
    rule_type: str  # validation, calculation, workflow, security, ui
    natural_language: str
    pseudo_code: str
    source_object: str
    source_location: str
    severity: str = "MEDIUM"  # LOW, MEDIUM, HIGH, CRITICAL
    confidence: float = 0.9
    origin: KnowledgeOrigin = KnowledgeOrigin.INFERENCE
    metadata: dict = field(default_factory=dict)


class BusinessRuleExtractor:
    """Extracts business rules from all Access application artifacts."""

    def __init__(self, app_ir):
        self.app = app_ir
        self.rules: list[ExtractedRule] = []

    def extract_all(self) -> list[ExtractedRule]:
        """Extract business rules from all sources."""
        self.rules = []

        # 1. Table-level rules (validation rules, required fields, etc.)
        for table in self.app.tables:
            self._extract_table_rules(table)

        # 2. Query-level rules (complex logic, domain aggregates)
        for query in self.app.queries:
            self._extract_query_rules(query)

        # 3. Form/Control rules (validation rules, events, default values)
        for form in self.app.forms:
            self._extract_form_rules(form)

        # 4. VBA rules (from procedure bodies)
        for module in self.app.vba_modules:
            self._extract_vba_rules(module)

        # 5. Macro rules (actions with conditions)
        for macro in self.app.macros:
            self._extract_macro_rules(macro)

        return self.rules

    def to_ir_rules(self) -> list[BusinessRuleIR]:
        """Convert extracted rules to BusinessRuleIR models."""
        ir_rules = []

        for rule in self.rules:
            ir_rule = BusinessRuleIR(
                rule_type=rule.rule_type,
                natural_language=rule.natural_language,
                pseudo_code=rule.pseudo_code,
                source_object=rule.source_object,
                source_location=rule.source_location,
                severity=rule.severity,
                confidence=rule.confidence,
                origin=rule.origin,
                metadata=rule.metadata,
            )
            ir_rules.append(ir_rule)

        return ir_rules

    # ---------------------------------------------------------------- tables

    def _extract_table_rules(self, table: TableIR) -> None:
        """Extract rules from table structure and column properties."""
        # Primary key as identity rule
        pk_cols = [c for c in table.columns if c.primary_key]
        if pk_cols:
            for pk in pk_cols:
                self.rules.append(ExtractedRule(
                    rule_type="identity",
                    natural_language=f"{table.name}.{pk.name} is the primary key",
                    pseudo_code=f"PRIMARY KEY ({pk.name})",
                    source_object=table.name,
                    source_location=f"Table.{table.name}.Column.{pk.name}",
                    severity="CRITICAL",
                    confidence=1.0,
                    origin=KnowledgeOrigin.FACT,
                ))

        # Required field rules
        for col in table.columns:
            if col.required and not col.primary_key:
                self.rules.append(ExtractedRule(
                    rule_type="validation",
                    natural_language=f"{table.name}.{col.name} cannot be null",
                    pseudo_code=f"NOT NULL ({col.name})",
                    source_object=table.name,
                    source_location=f"Table.{table.name}.Column.{col.name}",
                    severity="HIGH",
                    confidence=1.0,
                    origin=KnowledgeOrigin.FACT,
                ))

            # Validation rule
            if col.validation_rule:
                self.rules.append(ExtractedRule(
                    rule_type="validation",
                    natural_language=f"{table.name}.{col.name}: {col.validation_rule}",
                    pseudo_code=f"CHECK ({col.validation_rule})",
                    source_object=table.name,
                    source_location=f"Table.{table.name}.Column.{col.name}.ValidationRule",
                    severity="HIGH",
                    confidence=0.9,
                    origin=KnowledgeOrigin.FACT,
                    metadata={"validation_text": col.validation_text},
                ))

            # Unique constraint
            if col.unique:
                self.rules.append(ExtractedRule(
                    rule_type="uniqueness",
                    natural_language=f"{table.name}.{col.name} must be unique",
                    pseudo_code=f"UNIQUE ({col.name})",
                    source_object=table.name,
                    source_location=f"Table.{table.name}.Column.{col.name}",
                    severity="MEDIUM",
                    confidence=1.0,
                    origin=KnowledgeOrigin.FACT,
                ))

            # Default value
            if col.default_value:
                self.rules.append(ExtractedRule(
                    rule_type="default",
                    natural_language=f"{table.name}.{col.name} defaults to {col.default_value}",
                    pseudo_code=f"DEFAULT {col.default_value}",
                    source_object=table.name,
                    source_location=f"Table.{table.name}.Column.{col.name}.DefaultValue",
                    severity="LOW",
                    confidence=1.0,
                    origin=KnowledgeOrigin.FACT,
                ))

        # Referential integrity from relationships
        for rel in self.app.relationships:
            if rel.child_table == table.name:
                for i, child_col in enumerate(rel.child_columns):
                    parent_col = rel.parent_columns[i] if i < len(rel.parent_columns) else rel.parent_columns[0]
                    self.rules.append(ExtractedRule(
                        rule_type="referential_integrity",
                        natural_language=f"{table.name}.{child_col} references {rel.parent_table}.{parent_col}",
                        pseudo_code=f"FOREIGN KEY ({child_col}) REFERENCES {rel.parent_table}({parent_col})",
                        source_object=table.name,
                        source_location=f"Relationship.{rel.name}",
                        severity="HIGH",
                        confidence=1.0,
                        origin=KnowledgeOrigin.FACT,
                        metadata={
                            "cascade_update": rel.cascade_update,
                            "cascade_delete": rel.cascade_delete,
                        },
                    ))

    # ---------------------------------------------------------------- queries

    def _extract_query_rules(self, query: QueryIR) -> None:
        """Extract rules from query SQL and parameters."""
        sql = query.sql.upper()

        # Parameterized queries indicate required inputs
        if query.parameters:
            for param in query.parameters:
                self.rules.append(ExtractedRule(
                    rule_type="parameter",
                    natural_language=f"Query {query.name} requires parameter {param.get('name', '?')}",
                    pseudo_code=f"PARAMETER {param.get('name')} {param.get('type', 'TEXT')}",
                    source_object=query.name,
                    source_location=f"Query.{query.name}.Parameters",
                    severity="MEDIUM",
                    confidence=0.95,
                    origin=KnowledgeOrigin.FACT,
                ))

        # Domain aggregate functions indicate business calculations
        domain_funcs = re.findall(r'\b(DLookup|DCount|DSum|DAvg|DMax|DMin)\s*\(', query.sql, re.IGNORECASE)
        for func in domain_funcs:
            self.rules.append(ExtractedRule(
                rule_type="calculation",
                natural_language=f"Query {query.name} uses {func} for domain aggregation",
                pseudo_code=f"-- Domain function {func} needs conversion to subquery",
                source_object=query.name,
                source_location=f"Query.{query.name}.SQL",
                severity="HIGH",
                confidence=0.85,
                origin=KnowledgeOrigin.INFERENCE,
                metadata={"function": func},
            ))

        # Complex joins indicate business relationships
        join_count = len(re.findall(r'\bJOIN\b', sql))
        if join_count >= 3:
            self.rules.append(ExtractedRule(
                rule_type="relationship",
                natural_language=f"Query {query.name} joins {join_count} tables",
                pseudo_code=f"-- Multi-table join requires relationship mapping",
                source_object=query.name,
                source_location=f"Query.{query.name}.SQL",
                severity="MEDIUM",
                confidence=0.9,
                origin=KnowledgeOrigin.INFERENCE,
                metadata={"join_count": join_count},
            ))

    # ---------------------------------------------------------------- forms

    def _extract_form_rules(self, form: FormIR) -> None:
        """Extract rules from form and control properties."""
        # Record source indicates binding
        if form.record_source:
            self.rules.append(ExtractedRule(
                rule_type="binding",
                natural_language=f"Form {form.name} is bound to {form.record_source}",
                pseudo_code=f"Form.RecordSource = {form.record_source}",
                source_object=form.name,
                source_location=f"Form.{form.name}.RecordSource",
                severity="MEDIUM",
                confidence=1.0,
                origin=KnowledgeOrigin.FACT,
            ))

        # Process each control
        for ctrl in form.controls:
            if ctrl.control_type == "TextBox":
                self._extract_textbox_rules(form.name, ctrl)
            elif ctrl.control_type == "ComboBox":
                self._extract_combobox_rules(form.name, ctrl)
            elif ctrl.control_type == "CheckBox":
                self._extract_checkbox_rules(form.name, ctrl)
            elif ctrl.control_type == "CommandButton":
                self._extract_button_rules(form.name, ctrl)

    def _extract_textbox_rules(self, form_name: str, ctrl: ControlIR) -> None:
        """Extract rules from text box controls."""
        if ctrl.control_source:
            self.rules.append(ExtractedRule(
                rule_type="binding",
                natural_language=f"Form {form_name}.{ctrl.name} is bound to {ctrl.control_source}",
                pseudo_code=f"ControlSource = {ctrl.control_source}",
                source_object=form_name,
                source_location=f"Form.{form_name}.Control.{ctrl.name}.ControlSource",
                severity="MEDIUM",
                confidence=1.0,
                origin=KnowledgeOrigin.FACT,
            ))

        if ctrl.validation_rule:
            self.rules.append(ExtractedRule(
                rule_type="validation",
                natural_language=f"Form {form_name}.{ctrl.name}: {ctrl.validation_rule}",
                pseudo_code=f"ON CHANGE VALIDATE {ctrl.validation_rule}",
                source_object=form_name,
                source_location=f"Form.{form_name}.Control.{ctrl.name}.ValidationRule",
                severity="HIGH",
                confidence=0.95,
                origin=KnowledgeOrigin.FACT,
                metadata={"validation_text": ctrl.caption},
            ))

        if ctrl.default_value:
            self.rules.append(ExtractedRule(
                rule_type="default",
                natural_language=f"Form {form_name}.{ctrl.name} defaults to {ctrl.default_value}",
                pseudo_code=f"DEFAULT VALUE = {ctrl.default_value}",
                source_object=form_name,
                source_location=f"Form.{form_name}.Control.{ctrl.name}.DefaultValue",
                severity="LOW",
                confidence=1.0,
                origin=KnowledgeOrigin.FACT,
            ))

    def _extract_combobox_rules(self, form_name: str, ctrl: ControlIR) -> None:
        """Extract rules from combo box controls."""
        if ctrl.row_source:
            self.rules.append(ExtractedRule(
                rule_type="lookup",
                natural_language=f"Form {form_name}.{ctrl.name} uses lookup from {ctrl.row_source}",
                pseudo_code=f"RowSource = {ctrl.row_source} (lookup table/query)",
                source_object=form_name,
                source_location=f"Form.{form_name}.Control.{ctrl.name}.RowSource",
                severity="MEDIUM",
                confidence=0.9,
                origin=KnowledgeOrigin.FACT,
                metadata={"row_source_kind": ctrl.row_source_kind},
            ))

    def _extract_checkbox_rules(self, form_name: str, ctrl: ControlIR) -> None:
        """Extract rules from checkbox controls."""
        if ctrl.control_source:
            self.rules.append(ExtractedRule(
                rule_type="binding",
                natural_language=f"Form {form_name}.{ctrl.name} is bound to boolean field {ctrl.control_source}",
                pseudo_code=f"ControlSource = {ctrl.control_source} (boolean)",
                source_object=form_name,
                source_location=f"Form.{form_name}.Control.{ctrl.name}.ControlSource",
                severity="MEDIUM",
                confidence=1.0,
                origin=KnowledgeOrigin.FACT,
            ))

    def _extract_button_rules(self, form_name: str, ctrl: ControlIR) -> None:
        """Extract rules from command buttons."""
        if ctrl.events.get("OnClick"):
            self.rules.append(ExtractedRule(
                rule_type="workflow",
                natural_language=f"Form {form_name}.{ctrl.name} has click handler: {ctrl.events['OnClick']}",
                pseudo_code=f"ON CLICK: {ctrl.events['OnClick']}",
                source_object=form_name,
                source_location=f"Form.{form_name}.Control.{ctrl.name}.OnClick",
                severity="HIGH",
                confidence=0.85,
                origin=KnowledgeOrigin.INFERENCE,
                metadata={"event_code": ctrl.events["OnClick"]},
            ))

    # ---------------------------------------------------------------- vba

    def _extract_vba_rules(self, module: VbaModuleIR) -> None:
        """Extract rules from VBA module analysis."""
        analysis = parse_vba_module(module)

        for rule in analysis.business_rules:
            rule_type = rule.get("type", "business_logic")
            severity = {
                "validation": "HIGH",
                "calculated_field": "MEDIUM",
                "business_workflow": "HIGH",
                "field_validation": "HIGH",
            }.get(rule_type, "MEDIUM")

            self.rules.append(ExtractedRule(
                rule_type=rule_type,
                natural_language=rule.get("description", f"VBA rule in {module.name}.{rule.get('procedure', '?')}"),
                pseudo_code=rule.get("expression", rule.get("condition", "// Business logic from VBA")),
                source_object=module.name,
                source_location=f"Module.{module.name}.Procedure.{rule.get('procedure', 'unknown')}",
                severity=severity,
                confidence=0.8,
                origin=KnowledgeOrigin.INFERENCE,
                metadata=rule,
            ))

    # ---------------------------------------------------------------- macros

    def _extract_macro_rules(self, macro) -> None:
        """Extract rules from macro analysis."""
        parsed = parse_macro(macro)

        for i, action in enumerate(parsed.actions):
            if action.condition:
                self.rules.append(ExtractedRule(
                    rule_type="conditional_action",
                    natural_language=f"Macro {macro.name} action {action.action} has condition: {action.condition}",
                    pseudo_code=f"IF {action.condition} THEN {action.action}",
                    source_object=macro.name,
                    source_location=f"Macro.{macro.name}.Action[{i}].Condition",
                    severity="MEDIUM",
                    confidence=0.85,
                    origin=KnowledgeOrigin.INFERENCE,
                    metadata={
                        "action": action.action,
                        "arguments": action.arguments,
                    },
                ))

            # Certain actions imply business rules
            if action.action == "SendObject":
                self.rules.append(ExtractedRule(
                    rule_type="communication",
                    natural_language=f"Macro {macro.name} sends email/object via {action.action}",
                    pseudo_code=f"SEND {action.arguments.get('Object Type', 'Object')}",
                    source_object=macro.name,
                    source_location=f"Macro.{macro.name}.Action[{i}]",
                    severity="MEDIUM",
                    confidence=0.8,
                    origin=KnowledgeOrigin.INFERENCE,
                    metadata=action.arguments,
                ))

            if action.action == "RunCode":
                self.rules.append(ExtractedRule(
                    rule_type="code_execution",
                    natural_language=f"Macro {macro.name} runs function {action.arguments.get('Function Name', '?')}",
                    pseudo_code=f"EXECUTE {action.arguments.get('Function Name', 'Function')}",
                    source_object=macro.name,
                    source_location=f"Macro.{macro.name}.Action[{i}]",
                    severity="HIGH",
                    confidence=0.9,
                    origin=KnowledgeOrigin.INFERENCE,
                    metadata=action.arguments,
                ))


def extract_business_rules(app_ir) -> list[BusinessRuleIR]:
    """Entry point to extract all business rules from an application."""
    extractor = BusinessRuleExtractor(app_ir)
    extractor.extract_all()
    return extractor.to_ir_rules()