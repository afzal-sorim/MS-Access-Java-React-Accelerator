"""Macro Parser - parses Access macros and extracts actions with arguments.

Spec section 22: Parse macro XML from SaveAsText source dumps.
Extract actions, conditions, and arguments for service method generation.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Optional

from ..ir.models import MacroIR, MacroActionIR


# Known Access macro action names
MACRO_ACTIONS = {
    "OpenForm": ["Form Name", "View", "Filter Name", "Where Condition", "Data Mode", "Window Mode"],
    "OpenReport": ["Report Name", "View", "Filter Name", "Where Condition"],
    "OpenQuery": ["Query Name", "View", "Data Mode"],
    "OpenTable": ["Table Name", "View", "Data Mode"],
    "RunQuery": ["Query Name"],
    "RunCode": ["Function Name"],
    "RunMacro": ["Macro Name", "Repeat Count", "Repeat Expression"],
    "RunSQL": ["SQL Statement", "Use Transaction"],
    "SetValue": ["Item", "Expression"],
    "GoToRecord": ["Object Type", "Object Name", "Record", "Offset"],
    "GoToControl": ["Control Name"],
    "ApplyFilter": ["Filter Name", "Where Condition"],
    "ShowAllRecords": [],
    "FindRecord": ["Find What", "Match", "Whole Word", "Search"],
    "FindNext": [],
    "MsgBox": ["Message", "Beep", "Type", "Title"],
    "Beep": [],
    "Echo": ["Echo On", "Status Bar Text"],
    "SetWarnings": ["Warnings On"],
    "SetMenuItem": ["Menu Index", "Command Index", "Subcommand Index", "Flag"],
    "OutputTo": ["Object Type", "Object Name", "Output Format", "Output File", "Auto Start"],
    "SendObject": ["Object Type", "Object Name", "Output Format", "To", "Cc", "Bcc", "Subject", "Message Text", "Edit Message"],
    "TransferSpreadsheet": ["Transfer Type", "Spreadsheet Type", "Table Name", "File Name", "Has Field Names", "Range"],
    "TransferText": ["Transfer Type", "Specification Name", "Table Name", "File Name", "Has Field Names"],
    "TransferDatabase": ["Transfer Type", "Database Type", "Database Name", "Object Type", "Source", "Destination"],
    "Quit": ["Options"],
    "Save": ["Object Type", "Object Name"],
    "DeleteObject": ["Object Type", "Object Name"],
    "CopyObject": ["Destination Database", "New Name", "Source Object Type", "Source Object Name"],
    "Rename": ["New Name", "Object Type", "Old Name"],
    "RepaintObject": ["Object Type", "Object Name"],
    "RefreshRecord": [],
    "Requery": ["Control Name"],
    "SelectObject": ["Object Type", "Object Name", "In Database Window"],
    "Close": ["Object Type", "Object Name", "Save"],
    "CloseDatabase": [],
    "Maximize": [],
    "Minimize": [],
    "Restore": [],
    "MoveSize": ["Right", "Down", "Width", "Height"],
    "PrintOut": ["Print Range", "Page From", "Page To", "Print Quality", "Copies", "Collate Copies"],
    "ShowToolbar": ["Toolbar Name", "Show"],
    "SetTempVar": ["Variable Name", "Expression"],
    "RemoveTempVar": ["Therefore"],
    "CreateRecord": ["Object", "Alias"],
    "CreateLinkedRecord": ["Object Table", "Linked Table", "Alias", "Foreign Key"],
    "EditRecord": ["Alias"],
    "ForEachRecord": ["Object", "Where Condition", "Alias"],
    "LookUpRecord": ["Object", "Where Condition", "Alias"],

    # Modern Access 2010+ data macros
    "BeginTemplate": [],
    "EndTemplate": [],
}


@dataclass
class ParsedMacro:
    """Result of macro parsing."""
    name: str
    is_autoexec: bool
    actions: list[MacroActionIR] = field(default_factory=list)
    has_conditions: bool = False
    has_error_handling: bool = False
    submacros: dict[str, list[MacroActionIR]] = field(default_factory=dict)
    warnings: list[str] = field(default_factory=list)


class MacroParser:
    """Parses Access macro source dumps and extracts actions."""

    # Patterns for the legacy macro source format (binary/text dump)
    # Modern macros (.laccdb) use XML; legacy uses action tokens
    ACTION_PATTERN = re.compile(r'^\s*(\w+)\s+(.*?)(?:\s*)$', re.MULTILINE)
    CONDITION_PATTERN = re.compile(r'^\s*Condition\s*:\s*(.+)$', re.MULTILINE)

    # XML patterns for modern macros (Access 2007+)
    XML_ACTION_PATTERN = re.compile(r'<Action\s+Name="(\w+)"(.*?)/>', re.DOTALL)
    XML_ARGUMENT_PATTERN = re.compile(r'<Argument\s+Name="(\w+)">(.*?)</Argument>', re.DOTALL)
    XML_CONDITION_PATTERN = re.compile(r'<Condition>(.*?)</Condition>', re.DOTALL)
    XML_SUBMACRO_PATTERN = re.compile(r'<Sub\s+Name="(\w+)">(.*?)</Sub>', re.DOTALL)

    def __init__(self, macro_ir: MacroIR):
        self.macro = macro_ir
        self.name = macro_ir.name
        self.source = macro_ir.source or ""
        self.warnings: list[str] = []

    def parse(self) -> ParsedMacro:
        """Parse the macro source and extract actions."""
        result = ParsedMacro(
            name=self.name,
            is_autoexec=self.macro.is_autoexec,
        )

        if not self.source:
            result.warnings.append("No source available for macro")
            return result

        # Detect format: XML (modern) vs legacy text
        if "<?xml" in self.source or "<mac:" in self.source or "<Action " in self.source:
            self._parse_xml(result)
        else:
            self._parse_legacy(result)

        # Check for conditions
        if any(a.condition for a in result.actions):
            result.has_conditions = True

        # Check for error handling submacros
        if "OnError" in self.source or "errorHandler" in self.source.lower():
            result.has_error_handling = True

        # Filter supported actions
        for action in result.actions:
            if action.action not in MACRO_ACTIONS:
                result.warnings.append(f"Action '{action.action}' may not be supported")

        return result

    def _parse_xml(self, result: ParsedMacro) -> None:
        """Parse XML format macro (Access 2007+)."""
        # Extract submacros first
        for sub_match in self.XML_SUBMACRO_PATTERN.finditer(self.source):
            sub_name = sub_match.group(1)
            sub_source = sub_match.group(2)
            sub_actions = self._extract_xml_actions(sub_source)
            result.submacros[sub_name] = sub_actions

            # If this is the main macro block, use it for top-level actions
            if sub_name.lower() in ("main", self.name.lower()):
                result.actions = sub_actions

        # If no submacros found, extract actions directly
        if not result.actions and not result.submacros:
            result.actions = self._extract_xml_actions(self.source)

    def _extract_xml_actions(self, source: str) -> list[MacroActionIR]:
        """Extract actions from XML source."""
        actions = []

        for action_match in self.XML_ACTION_PATTERN.finditer(source):
            action_name = action_match.group(1)
            action_body = action_match.group(2)

            # Extract condition if present
            condition_match = self.XML_CONDITION_PATTERN.search(action_body)
            condition = condition_match.group(1).strip() if condition_match else None

            # Extract arguments
            arguments = {}
            for arg_match in self.XML_ARGUMENT_PATTERN.finditer(action_body):
                arg_name = arg_match.group(1)
                arg_value = arg_match.group(2).strip()
                arguments[arg_name] = arg_value

            actions.append(MacroActionIR(
                action=action_name,
                arguments=arguments,
                condition=condition,
            ))

        return actions

    def _parse_legacy(self, result: ParsedMacro) -> None:
        """Parse legacy macro text format."""
        lines = self.source.split("\n")
        current_action: Optional[MacroActionIR] = None

        for line in lines:
            line = line.strip()
            if not line or line.startswith("'"):
                continue

            # Try to match action
            parts = line.split(None, 1)
            if not parts:
                continue

            action_name = parts[0]
            rest = parts[1] if len(parts) > 1 else ""

            if action_name in MACRO_ACTIONS:
                # Parse arguments from the rest
                arguments = self._parse_legacy_arguments(action_name, rest)

                current_action = MacroActionIR(
                    action=action_name,
                    arguments=arguments,
                )
                result.actions.append(current_action)
            elif action_name == "Condition" and current_action:
                current_action.condition = rest
            elif ":" in line and current_action:
                # Argument line: "ArgumentName: value"
                arg_parts = line.split(":", 1)
                if len(arg_parts) == 2:
                    current_action.arguments[arg_parts[0].strip()] = arg_parts[1].strip()

    def _parse_legacy_arguments(self, action_name: str, rest: str) -> dict:
        """Parse arguments from legacy macro format."""
        arguments = {}

        if action_name not in MACRO_ACTIONS:
            return arguments

        expected = MACRO_ACTIONS[action_name]
        if not expected:
            return arguments

        # Arguments are typically comma-separated
        values = [v.strip() for v in rest.split(",")]

        for i, arg_name in enumerate(expected):
            if i < len(values) and values[i]:
                arguments[arg_name] = values[i]

        return arguments

    def to_service_method(self) -> str:
        """Generate a Java service method from this macro."""
        result = self.parse()
        lines = ["// Generated from macro: {self.name}"]

        if result.is_autoexec:
            lines.append("// This macro runs on application startup")

        lines.append(f"public void execute{self.name}() {{")
        lines.append("    // Macro actions:")

        for i, action in enumerate(result.actions):
            if action.condition:
                lines.append(f"    if ({doesnt_make_sense_in_java(action.condition)}) {{")
                lines.append(f"        // {action.action}")
                lines.append("    }")
            else:
                lines.append(f"    // Action {i+1}: {action.action}")
                if action.arguments:
                    for k, v in action.arguments.items():
                        lines.append(f"    //   {k} = {v}")

        lines.append("}")
        return "\n".join(lines)


def doesnt_make_sense_in_java(condition: str) -> str:
    """Placeholder - VBA conditions would need their own conversion."""
    return f"/* {condition} */ true"


def parse_macro(macro_ir: MacroIR) -> ParsedMacro:
    """Entry point to parse a macro."""
    return MacroParser(macro_ir).parse()


def parse_all_macros(app_ir) -> list[ParsedMacro]:
    """Parse all macros in an application."""
    return [parse_macro(m) for m in app_ir.macros]
