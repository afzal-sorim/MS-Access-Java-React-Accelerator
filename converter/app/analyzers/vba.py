"""VBA Parser/Analyzer - parses VBA code, extracts procedures, detects patterns.

Spec section 12, 31, 33: Parse VBA from SaveAsText source dumps.
Extract procedures, references, API calls, and business logic patterns.
Identify supportability issues and business rules.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Optional

from ..ir.models import VbaModuleIR, VbaProcedureIR


# VBA procedure declarations; captures visibility, kind, name, the full
# parameter list, and the return type (Functions/Property Get only).
PROCEDURE_PATTERN = re.compile(
    r'^\s*(?:(Public|Private|Friend)\s+)?((?:Sub|Function)|Property\s+(?:Get|Let|Set))\s+(\w+)\s*\(([^)]*)\)(?:\s+As\s+([\w.]+))?',
    re.MULTILINE
)
PROCEDURE_END_PATTERN = re.compile(r'^\s*End\s+(Sub|Function|Property)\b', re.MULTILINE)

# Common VBA patterns and their conversions
VBA_PATTERNS = {
    # Control flow (simple patterns)
    "If_Then": r'\bIf\s+.*?\s+Then\b',
    "Select_Case": r'\bSelect\s+Case\b',
    "For_Next": r'\bFor\s+.*?\s+To\b',
    "For_Each": r'\bFor\s+Each\b',
    "Do_Loop": r'\bDo\s+(?:While|Until)\b',
    "While_Wend": r'\bWhile\s+.*?\s+Wend\b',
    "Exit_Sub": r'\bExit\s+Sub\b',
    "Exit_Function": r'\bExit\s+Function\b',

    # Object/recordset operations
    "Open_Recordset": r'\.OpenRecordset\s*\(',
    "Edit_Recordset": r'\.Edit\b',
    "AddNew_Recordset": r'\.AddNew\b',
    "Update_Recordset": r'\.Update\b',
    "Delete_Recordset": r'\.Delete\b',
    "Close_Recordset": r'\.Close\b',
    "MoveFirst": r'\.MoveFirst\b',
    "MoveNext": r'\.MoveNext\b',
    "MoveLast": r'\.MoveLast\b',
    "EOF_Check": r'\.EOF\b',
    "FindFirst": r'\.FindFirst\b',
    "Seek": r'\.Seek\b',

    # DoCmd operations
    "DoCmd_OpenForm": r'DoCmd\.OpenForm\b',
    "DoCmd_OpenReport": r'DoCmd\.OpenReport\b',
    "DoCmd_OpenQuery": r'DoCmd\.OpenQuery\b',
    "DoCmd_RunSQL": r'DoCmd\.RunSQL\b',
    "DoCmd_GoToRecord": r'DoCmd\.GoToRecord\b',
    "DoCmd_Maximize": r'DoCmd\.Maximize\b',
    "DoCmd_Close": r'DoCmd\.Close\b',
    "DoCmd_SetValue": r'DoCmd\.SetValue\b',

    # Form/Control references
    "Forms_Bang": r'Forms\s*!\s*\w+\s*!\s*\w+',
    "Forms_Paren": r'Forms\s*\(\s*"[^"]+"\s*\)',
    "Me_Reference": r'\bMe\s*(?:\.|!)\s*\w+',
    "Controls_Collection": r'\.Controls\s*\(',

    # CurrentDb and DBEngine
    "CurrentDb": r'\bCurrentDb\b',
    "DBEngine": r'\bDBEngine\b',
    "Workspaces": r'\bWorkspaces\b',

    # Error handling
    "On_Error": r'\bOn\s+Error\b',
    "Resume": r'\bResume\b',
    "Err_Object": r'\bErr\.(?:Number|Description|Source)\b',

    # External references (unsupported in V1).
    # These require a real usage shape, not a bare product name — see
    # EXTERNAL_APP_PATTERNS and strip_noncode().
    "Outlook": r'\bOutlook\s*\.\s*\w+|CreateObject\s*\(\s*"Outlook',
    "Excel": r'\bExcel\s*\.\s*\w+|CreateObject\s*\(\s*"Excel',
    "Word": r'\bWord\s*\.\s*(?:Application|Document|Documents|Selection)\b|CreateObject\s*\(\s*"Word',
    "PowerPoint": r'\bPowerPoint\s*\.\s*\w+|CreateObject\s*\(\s*"PowerPoint',
    "FileSystemObject": r'\bFileSystemObject\b|CreateObject\s*\(\s*"Scripting',
    "Shell": r'\bShell\s*\(',
    "WScript": r'\bWScript\s*\.\s*\w+',
    "API_Declare": r'\bDeclare\s+(?:PtrSafe\s+)?Function\b',

    # COM references
    "CreateObject": r'\bCreateObject\s*\(',
    "GetObject": r'\bGetObject\s*\(',

    # VBA built-ins
    "MsgBox": r'\bMsgBox\s*\(',
    "InputBox": r'\bInputBox\s*\(',
    "DoEvents": r'\bDoEvents\b',
    "DoCmd": r'\bDoCmd\b',
    "Nz": r'\bNz\s*\(',
    "IIf": r'\bIIf\s*\(',
    "DLookup": r'\bDLookup\s*\(',
    "DCount": r'\bDCount\s*\(',
    "DSum": r'\bDSum\s*\(',

    # SQL operations
    "Execute_SQL": r'\.Execute\s*\(',
    "QueryDef": r'\bQueryDef\b',
    "Parameters": r'\.Parameters\s*\(',

    # Date/Time
    "Date_Function": r'\bDate\b|Now\(\)|Time\b',
    "DateSerial": r'\bDateSerial\s*\(',
    "DateDiff": r'\bDateDiff\s*\(',
    "DateAdd": r'\bDateAdd\s*\(',
    "Format_Function": r'\bFormat\s*\(',

    # Math
    "Abs": r'\bAbs\s*\(',
    "Round": r'\bRound\s*\(',
    "Int": r'\bInt\s*\(',

    # String
    "Left": r'\bLeft\s*\(',
    "Right": r'\bRight\s*\(',
    "Mid": r'\bMid\s*\(',
    "Len": r'\bLen\s*\(',
    "InStr": r'\bInStr\s*\(',
    "Replace": r'\bReplace\s*\(',
    "Trim": r'\bTrim\s*\(',
    "UCase": r'\bUCase\s*\(',
    "LCase": r'\bLCase\s*\(',
    "StrConv": r'\bStrConv\s*\(',
}


# Unsupported patterns flag modules as SUPPORTED_WITH_REVIEW
UNSUPPORTED_PATTERNS = {
    "Outlook", "Excel", "Word", "PowerPoint",
    "FileSystemObject", "Shell", "WScript",
    "API_Declare", "CreateObject", "GetObject",
}


@dataclass
class VBAModuleAnalysis:
    """Result of VBA module analysis."""
    module_name: str
    module_type: str
    procedures: list[VbaProcedureIR] = field(default_factory=list)
    patterns_found: list[str] = field(default_factory=list)
    unsupported_patterns: list[str] = field(default_factory=list)
    references_com: list[str] = field(default_factory=list)
    uses_external: list[str] = field(default_factory=list)
    declares_api: list[str] = field(default_factory=list)
    line_count: int = 0
    has_error_handling: bool = False
    supports_conversion: bool = True
    conversion_difficulty: str = "MEDIUM"  # LOW, MEDIUM, HIGH
    warnings: list[str] = field(default_factory=list)
    business_rules: list[dict] = field(default_factory=list)


def strip_noncode(source: str) -> str:
    """Return VBA source with comments and string literals blanked out.

    External-dependency detection must not fire on prose or data.  In the
    reference corpus, ``Dim Word As String``, the comment "first letter of
    each word", and the literal ``"Excel Files"`` in a file-dialog filter
    all matched the old bare ``\\bWord\\b`` / ``\\bExcel\\b`` patterns and
    produced phantom Word/Excel dependencies.

    Comments and literals are replaced with spaces rather than deleted so
    line and column offsets stay usable for diagnostics.
    """
    out = []
    for line in source.splitlines():
        buf = []
        in_string = False
        i = 0
        while i < len(line):
            ch = line[i]
            if in_string:
                if ch == '"':
                    # "" is an escaped quote inside a VBA string.
                    if i + 1 < len(line) and line[i + 1] == '"':
                        buf.append("  ")
                        i += 2
                        continue
                    in_string = False
                    buf.append(" ")
                else:
                    buf.append(" ")
                i += 1
                continue

            if ch == '"':
                in_string = True
                buf.append(" ")
                i += 1
                continue

            # Comment to end of line.
            if ch == "'":
                buf.append(" " * (len(line) - i))
                break

            # REM comment (only as a statement, not inside an identifier).
            if (ch in "rR") and line[i:i + 3].upper() == "REM" and (
                i == 0 or not (line[i - 1].isalnum() or line[i - 1] == "_")
            ) and (i + 3 >= len(line) or not (line[i + 3].isalnum() or line[i + 3] == "_")):
                buf.append(" " * (len(line) - i))
                break

            buf.append(ch)
            i += 1
        out.append("".join(buf))
    return "\n".join(out)


# External application detection, applied to code-only source.
# Each pattern requires a genuine COM usage shape — a member access
# (``Outlook.Application``), a typed declaration (``As New Excel.…``), or a
# CreateObject/GetObject call — never a bare product name.
EXTERNAL_APP_PATTERNS: dict[str, str] = {
    "Outlook": r'\bOutlook\s*\.\s*\w+|(?:CreateObject|GetObject)\s*\(\s*"Outlook',
    "Excel": r'\bExcel\s*\.\s*\w+|(?:CreateObject|GetObject)\s*\(\s*"Excel',
    "Word": r'\bWord\s*\.\s*(?:Application|Document|Documents|Selection)\b'
            r'|(?:CreateObject|GetObject)\s*\(\s*"Word',
    "PowerPoint": r'\bPowerPoint\s*\.\s*\w+|(?:CreateObject|GetObject)\s*\(\s*"PowerPoint',
    "FileSystemObject": r'\bFileSystemObject\b|(?:CreateObject|GetObject)\s*\(\s*"Scripting',
    "Shell": r'\bShell\s*\(|\bWScript\s*\.\s*Shell\b',
    "WScript": r'\bWScript\s*\.\s*\w+',
    "InternetExplorer": r'\bInternetExplorer(?:\.Application)?\b',
    "MSXML": r'\bMSXML\d*\s*\.\s*\w+|\bXMLHTTP\b',
}

# COM library -> external dependency kind used in the IR (spec §8, §53).
EXTERNAL_KIND_MAP: dict[str, str] = {
    "Outlook": "OUTLOOK",
    "Excel": "EXCEL",
    "Word": "COM",
    "PowerPoint": "COM",
    "FileSystemObject": "FILE",
    "Shell": "COM",
    "WScript": "COM",
    "InternetExplorer": "COM",
    "MSXML": "API",
}


class VBAParser:
    """Parses and analyzes VBA code from module source dumps."""

    def __init__(self, module_ir: VbaModuleIR):
        self.module = module_ir
        self.source = module_ir.source or ""
        self.name = module_ir.name
        # Comment/literal-free view used for dependency detection.
        self._code = strip_noncode(self.source)

    def parse(self) -> VBAModuleAnalysis:
        """Parse the VBA module and extract analysis."""
        result = VBAModuleAnalysis(
            module_name=self.name,
            module_type=self.module.module_type,
            line_count=len(self.source.split("\n")) if self.source else 0,
        )

        if not self.source:
            result.warnings.append("No source available for module")
            return result

        # Extract procedures
        result.procedures = self._extract_procedures()

        # Detect patterns
        result.patterns_found = self._detect_patterns()

        # Identify unsupported patterns
        result.unsupported_patterns = [
            p for p in result.patterns_found if p in UNSUPPORTED_PATTERNS
        ]

        # Extract COM references
        result.references_com = self._extract_com_references()

        # Extract external dependencies
        result.uses_external = self._extract_external_uses()

        # Extract API declarations
        result.declares_api = self._extract_api_declarations()

        # Check for error handling
        result.has_error_handling = bool(re.search(
            VBA_PATTERNS["On_Error"], self.source, re.IGNORECASE
        ))

        # Determine conversion difficulty
        result.conversion_difficulty = self._determine_difficulty(result)

        # Update supportability flag
        if result.unsupported_patterns:
            result.supports_conversion = False

        # Extract business rules from procedures
        result.business_rules = self._extract_business_rules(result.procedures)

        # Sync findings onto the module IR itself: downstream consumers
        # (supportability engine, dependency graph, external-dependency
        # discovery) read the IR, not the transient analysis object.
        self.module.references_com = result.references_com
        self.module.uses_external = result.uses_external
        self.module.declares_api = result.declares_api

        return result

    def _extract_procedures(self) -> list[VbaProcedureIR]:
        """Extract all procedures (Sub, Function, Property) from the source."""
        procedures = []

        for match in PROCEDURE_PATTERN.finditer(self.source):
            visibility = (match.group(1) or "Public").upper()
            proc_type = re.sub(r"\s+", "", match.group(2))  # e.g. PropertyGet
            proc_name = match.group(3)
            param_text = (match.group(4) or "").strip()
            return_type = match.group(5)

            # Find the end of the procedure
            start_pos = match.start()
            end_match = PROCEDURE_END_PATTERN.search(self.source, start_pos)

            if end_match:
                body = self.source[start_pos:end_match.end()]
            else:
                body = self.source[start_pos:]

            signature = match.group(0).strip()

            # Extract features
            calls = self._extract_calls(body)
            has_error_handling = bool(re.search(
                VBA_PATTERNS["On_Error"], body, re.IGNORECASE
            ))
            has_recordset_ops = any(p in body for p in [
                "OpenRecordset", ".Edit", ".AddNew", ".Update", ".Delete"
            ])

            proc = VbaProcedureIR(
                name=proc_name,
                kind=proc_type.upper(),
                visibility=visibility,
                signature=signature,
                parameters=self._parse_parameters(param_text),
                return_type=return_type,
                body=body,
                calls=calls,
                references_tables=self._extract_table_refs(body),
                uses_recordset=has_recordset_ops,
                has_error_handling=has_error_handling,
            )

            procedures.append(proc)

            # Update the module IR's procedures list
            if proc not in self.module.procedures:
                self.module.procedures.append(proc)

        return procedures

    @staticmethod
    def _parse_parameters(param_text: str) -> list[dict[str, str]]:
        """Parse a VBA parameter list into {"name", "type"} dicts.

        Handles Optional/ByVal/ByRef/ParamArray modifiers and default values;
        complex cases degrade to a name with an empty type rather than
        dropping the parameter.
        """
        params: list[dict[str, str]] = []
        if not param_text:
            return params

        # Split on commas that are not inside parentheses (array bounds).
        parts, depth, current = [], 0, []
        for ch in param_text:
            if ch == "(":
                depth += 1
            elif ch == ")":
                depth -= 1
            if ch == "," and depth == 0:
                parts.append("".join(current))
                current = []
            else:
                current.append(ch)
        if current:
            parts.append("".join(current))

        modifiers = {"optional", "byval", "byref", "paramarray"}
        for part in parts:
            tokens = part.strip().split()
            tokens = [t for t in tokens if t.lower() not in modifiers]
            if not tokens:
                continue
            # Strip default values: name As String = "x"
            first = tokens[0].split("=")[0].strip()
            ptype = None
            if len(tokens) >= 3 and tokens[1].lower() == "as":
                ptype = " ".join(t.split("=")[0].strip() for t in tokens[2:])
            params.append({"name": first, "type": ptype or ""})
        return params

    def _extract_calls(self, body: str) -> list[str]:
        """Extract function/sub calls from a procedure body."""
        calls = []
        # Match calls like "Call Foo()" or just "Foo x, y" or "Foo(x, y)"
        call_pattern = re.compile(r'\b(?:Call\s+)?(\w+)\s*(?:\(|\s)', re.MULTILINE)

        # VBA keywords to ignore
        keywords = {
            "if", "then", "else", "elseif", "end", "for", "next", "to",
            "step", "do", "loop", "while", "until", "wend", "select", "case",
            "with", "dim", "set", "let", "const", "public", "private", "sub",
            "function", "property", "get", "let", "set", "exit", "on", "error",
            "goto", "resume", "and", "or", "not", "is", "in", "mod", "new",
            "nothing", "true", "false", "null", "empty", "me", "byval", "byref",
            "optional", "paramarray", "as", "type", "enum", "redim", "preserve",
            "erase", "open", "close", "input", "output", "append", "binary",
            "random", "print", "write", "line", "get", "put", "lock", "unlock",
            "reset", "width", "tab", "spc", "true", "false", "called", "doevents",
            "stop", "end", "exit", "sub", "function", "property",
        }

        for match in call_pattern.finditer(body):
            name = match.group(1)
            if name.lower() not in keywords and name not in calls:
                calls.append(name)

        return calls

    def _extract_table_refs(self, body: str) -> list[str]:
        """Extract table name references from VBA body."""
        refs = []

        # Look for "FROM tablename" in SQL strings
        from_matches = re.findall(r'FROM\s+(\w+)', body, re.IGNORECASE)
        refs.extend(from_matches)

        # Look for CurrentDb.OpenRecordset("tablename")
        open_matches = re.findall(r'OpenRecordset\s*\(\s*"(\w+)"', body, re.IGNORECASE)
        refs.extend(open_matches)

        # Look for tabledefs("tablename")
        td_matches = re.findall(r'TableDefs\s*\(\s*"(\w+)"\s*\)', body, re.IGNORECASE)
        refs.extend(td_matches)

        return list(set(refs))

    def _detect_patterns(self) -> list[str]:
        """Detect all VBA patterns in the source.

        Uses the comment/literal-stripped view so commented-out code and
        string data do not register as live language features.
        """
        found = []

        for pattern_name, pattern_re in VBA_PATTERNS.items():
            if re.search(pattern_re, self._code, re.IGNORECASE):
                found.append(pattern_name)

        return found

    def _extract_com_references(self) -> list[str]:
        """Extract COM object references.

        Covers both late binding (``CreateObject("Outlook.Application")``)
        and early binding (``Dim o As New Outlook.Application``).  The
        reference corpus uses early binding exclusively, which the old
        CreateObject-only scan missed entirely.
        """
        refs = []
        code = self._code

        com_pattern = re.compile(
            r'(?:CreateObject|GetObject)\s*\(\s*"([^"]+)"', re.IGNORECASE
        )
        for match in com_pattern.finditer(self.source):
            refs.append(match.group(1))

        # Early-bound declarations: Dim/Private/Public/Static x As [New] Lib.Class
        early_pattern = re.compile(
            r'\b(?:Dim|Private|Public|Static|Global)\s+\w+\s+As\s+(?:New\s+)?'
            r'([A-Za-z_]\w*\s*\.\s*[A-Za-z_]\w*)',
            re.IGNORECASE,
        )
        for match in early_pattern.finditer(code):
            refs.append(re.sub(r'\s+', '', match.group(1)))

        # Set x = New Lib.Class
        set_new_pattern = re.compile(
            r'\bSet\s+\w+\s*=\s*New\s+([A-Za-z_]\w*\s*\.\s*[A-Za-z_]\w*)',
            re.IGNORECASE,
        )
        for match in set_new_pattern.finditer(code):
            refs.append(re.sub(r'\s+', '', match.group(1)))

        # Also check for referenced libraries
        lib_pattern = re.compile(
            r'Reference\s+::\s*\\GUID\s*\{([^}]+)\}', re.IGNORECASE
        )
        for match in lib_pattern.finditer(self.source):
            refs.append(f"GUID:{match.group(1)}")

        return sorted(set(refs))

    def _extract_external_uses(self) -> list[str]:
        """Detect usage of external applications.

        Matched against comment- and literal-stripped source so prose and
        data (e.g. a ``"Excel Files"`` dialog filter) cannot register as a
        real dependency.
        """
        external_apps = []
        for app, pattern in EXTERNAL_APP_PATTERNS.items():
            if re.search(pattern, self._code, re.IGNORECASE):
                external_apps.append(app)
        return external_apps

    def _extract_api_declarations(self) -> list[str]:
        """Extract Declare statements (Windows API calls)."""
        apis = []
        declare_pattern = re.compile(
            r'(?:Public\s+|Private\s+)?Declare\s+(?:PtrSafe\s+)?Function\s+(\w+)',
            re.IGNORECASE
        )
        for match in declare_pattern.finditer(self.source):
            apis.append(match.group(1))

        return apis

    def _determine_difficulty(self, analysis: VBAModuleAnalysis) -> str:
        """Determine conversion difficulty based on analysis."""
        score = 0

        # External dependencies are deal-breakers for automatic conversion
        if analysis.uses_external:
            score += 3
        if analysis.declares_api:
            score += 2
        if analysis.references_com:
            score += 2

        # Recordset operations are common and easy
        if any(p in analysis.patterns_found for p in [
            "Open_Recordset", "Edit_Recordset", "AddNew_Recordset"
        ]):
            score += 1

        # DoCmd operations are easily mapped
        if any(p.startswith("DoCmd_") for p in analysis.patterns_found):
            score += 1

        # Complex patterns add difficulty
        if "For_Each" in analysis.patterns_found:
            score += 1
        if "Select_Case" in analysis.patterns_found:
            score += 1

        if score >= 5:
            return "HIGH"
        elif score >= 2:
            return "MEDIUM"
        else:
            return "LOW"

    def _extract_business_rules(self, procedures: list[VbaProcedureIR]) -> list[dict]:
        """Extract business rules from procedure bodies.

        Looks for validation patterns, conditional logic, and data manipulation.
        """
        rules = []

        for proc in procedures:
            body = proc.body

            # Look for validation patterns
            # Pattern: If Me.field <operator> value Then MsgBox "..."
            validation_pattern = re.compile(
                r'If\s+(.+?)\s+(<|>|<=|>=|=|<>|Like)\s+(.+?)\s+Then\s+.*?MsgBox\s+"([^"]+)"',
                re.IGNORECASE | re.DOTALL
            )
            for match in validation_pattern.finditer(body):
                rules.append({
                    "type": "validation",
                    "procedure": proc.name,
                    "condition": match.group(1).strip(),
                    "operator": match.group(2),
                    "value": match.group(3).strip(),
                    "message": match.group(4),
                    "origin": "VBA",
                    "source": self.name,
                })

            # Look for field-level validation (BeforeUpdate events)
            if "BeforeUpdate" in body or "BeforeInsert" in body:
                # Extract the field name from the event
                field_match = re.search(r'(?:Private\s+)?Sub\s+\w+_BeforeUpdate', body)
                if field_match:
                    rules.append({
                        "type": "field_validation",
                        "procedure": proc.name,
                        "origin": "VBA",
                        "source": self.name,
                        "description": "BeforeUpdate validation logic",
                    })

            # Look for calculated fields
            # Pattern: Me.field = expression
            calc_pattern = re.compile(
                r'Me\s*[!\.]\s*(\w+)\s*=\s*(.+?)(?:\n|$)',
                re.IGNORECASE
            )
            for match in calc_pattern.finditer(body):
                field = match.group(1)
                expression = match.group(2).strip()
                # Only if it looks like a calculation (not a simple assignment)
                if any(op in expression for op in ["+", "-", "*", "/", "(", ")"]):
                    rules.append({
                        "type": "calculated_field",
                        "procedure": proc.name,
                        "field": field,
                        "expression": expression,
                        "origin": "VBA",
                        "source": self.name,
                    })

            # Look for workflow/conditional business logic
            if "If" in body and ("Save" in body or "Delete" in body or "Cancel" in body):
                if_match = re.search(r'If\s+(.+?)\s+Then\s*\n\s*(?:DoCmd|Me|Cancel)', body, re.DOTALL)
                if if_match:
                    rules.append({
                        "type": "business_workflow",
                        "procedure": proc.name,
                        "condition": if_match.group(1).strip(),
                        "origin": "VBA",
                        "source": self.name,
                        "description": "Conditional workflow logic",
                    })

        return rules

    def generate_conversion_notes(self) -> str:
        """Generate notes about conversion approach for this module."""
        analysis = self.parse()
        lines = [
            f"Conversion notes for module: {self.name}",
            f"  Type: {analysis.module_type}",
            f"  Procedures: {len(analysis.procedures)}",
            f"  Lines: {analysis.line_count}",
            f"  Difficulty: {analysis.conversion_difficulty}",
            f"  Has error handling: {analysis.has_error_handling}",
            "",
        ]

        if analysis.unsupported_patterns:
            lines.append("  UNSUPPORTED patterns:")
            for p in analysis.unsupported_patterns:
                lines.append(f"    - {p}")
            lines.append("")

        if analysis.references_com:
            lines.append("  COM references:")
            for ref in analysis.references_com:
                lines.append(f"    - {ref}")
            lines.append("")

        if analysis.uses_external:
            lines.append("  External application usage:")
            for ext in analysis.uses_external:
                lines.append(f"    - {ext}")
            lines.append("")

        if analysis.declares_api:
            lines.append("  API declarations:")
            for api in analysis.declares_api:
                lines.append(f"    - {api}")
            lines.append("")

        if analysis.business_rules:
            lines.append(f"  Business rules extracted: {len(analysis.business_rules)}")

        return "\n".join(lines)


def parse_vba_module(module_ir: VbaModuleIR) -> VBAModuleAnalysis:
    """Entry point to parse a VBA module."""
    return VBAParser(module_ir).parse()


def parse_all_vba(app_ir) -> list[VBAModuleAnalysis]:
    """Parse all VBA modules in an application."""
    return [parse_vba_module(m) for m in app_ir.vba_modules]
