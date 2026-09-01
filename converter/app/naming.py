"""Centralised identifier mapping for the conversion pipeline.

All generators (React, Spring Boot, PostgreSQL) consume these functions so
that a single Access object always produces the same target identifiers
across every layer.

Hump-preserving rules (PHASE 18 fix)
----------------------------------------
`str.capitalize()` lowercases every character after the first, turning
`"tagGrpNme"` into `"Taggrpnme"` and producing `getTaggrpnme()` instead
of `getTagGrpNme()`.  The functions below split on `_` and `-` only and
capitalise the first letter of each segment, preserving internal humps.

The React generator further requires that identifiers never start with a
digit (Leszynski-named objects like ``001_About_frm``); `to_pascal`
handles this by prefixing `N`.
"""
from __future__ import annotations

import re
from typing import Optional


# ------------------------------------------------------------------ segment split

_SEGMENT_RE = re.compile(r'[\s_\-]+|(?<=[a-z])(?=[A-Z])|(?<=[A-Z])(?=[A-Z][a-z])')


def _segments(name: str) -> list[str]:
    """Split *name* into case-preserving segments.

    >>> _segments('tagGrpNme')
    ['tag', 'Grp', 'Nme']
    >>> _segments('301_Roulette_frm')
    ['301', 'Roulette', 'frm']
    >>> _segments('TypeID')
    ['Type', 'ID']
    """
    parts = _SEGMENT_RE.split(name)
    return [p for p in parts if p]


# ------------------------------------------------------------------ public API

def to_pascal(name: str) -> str:
    """Convert *name* to PascalCase, preserving internal humps.

    JavaScript identifiers cannot start with a digit, so names like
    ``001_About_frm`` become ``N001AboutFrm``.
    """
    parts = _segments(name)
    result = ''.join(p[0].upper() + p[1:] for p in parts if p)
    if result and result[0].isdigit():
        # Prefix only the leading digit run with 'N'.
        m = re.match(r'^\d+', result)
        if m:
            result = 'N' + result
    return result


def to_camel(name: str) -> str:
    """Convert *name* to camelCase (first letter lower)."""
    pascal = to_pascal(name)
    return pascal[0].lower() + pascal[1:] if pascal else pascal


def to_snake(name: str) -> str:
    """Convert *name* to snake_case.

    >>> to_snake('tagGrpNme')
    'tag_grp_nme'
    >>> to_snake('301_Roulette_frm')
    '301_roulette_frm'
    """
    parts = _segments(name)
    return '_'.join(p.lower() for p in parts if p)


def to_kebab(name: str) -> str:
    """Convert *name* to kebab-case."""
    return to_snake(name).replace('_', '-')


# ------------------------------------------------------------------ registry

class NameMappingRegistry:
    """Produces consistent target identifiers for every Access object.

    Example::

        reg = NameMappingRegistry(app_ir)
        m = reg.mapping_for('301_Roulette_frm', 'FORM')
        m['reactComponent']  # 'N301RouletteFrmPage'
        m['route']           # '/roulette-tb'
        m['apiResource']     # 'roulette-tb'
        m['javaClass']       # 'RouletteTbService'
        m['databaseObject']  # 'roulette_tb'
    """

    def __init__(self, app_ir):
        self.app = app_ir
        self._pk_map: dict[str, str] = {}
        self._analyze_keys()

    def _analyze_keys(self) -> None:
        for table in self.app.tables:
            for idx in table.indexes:
                if idx.primary and idx.columns:
                    self._pk_map[table.name] = idx.columns[0]
                    break

    def pk_for(self, table_name: str) -> Optional[str]:
        return self._pk_map.get(table_name)

    def mapping_for(self, name: str, category: str) -> dict[str, str]:
        """Return a dict of target-layer identifiers for an Access object."""
        if category == 'TABLE':
            return self._table_mapping(name)
        if category == 'FORM':
            return self._form_mapping(name)
        if category == 'REPORT':
            return self._report_mapping(name)
        return {}

    def _table_mapping(self, name: str) -> dict[str, str]:
        pascal = to_pascal(name)
        return {
            'reactComponent': f'{pascal}Page',
            'javaEntity': pascal,
            'javaRepository': f'{pascal}Repository',
            'javaService': f'{pascal}Service',
            'javaController': f'{pascal}Controller',
            'javaDTO': f'{pascal}DTO',
            'route': f'/{to_kebab(name)}',
            'apiResource': to_kebab(name),
            'databaseTable': to_snake(name),
        }

    def _form_mapping(self, name: str) -> dict[str, str]:
        # Use the form's record source for the API endpoint when it's a
        # table, falling back to the form name for unbound forms.
        form_ir = self.app.form(name)
        rs = form_ir.record_source if form_ir else None
        rs_kind = form_ir.record_source_kind if form_ir else None

        page_name = to_pascal(name)
        if rs and rs_kind in ('TABLE', 'QUERY'):
            endpoint = to_kebab(rs)
            api_pascal = to_pascal(rs)
        else:
            endpoint = to_kebab(name)
            api_pascal = page_name

        return {
            'reactComponent': f'{page_name}Page',
            'route': f'/{endpoint}',
            'apiResource': endpoint,
            'apiPascal': api_pascal,
            'recordSource': rs or '',
            'recordSourceKind': rs_kind or 'NONE',
        }

    def _report_mapping(self, name: str) -> dict[str, str]:
        return {
            'reactComponent': f'{to_pascal(name)}ReportPage',
            'route': f'/reports/{to_kebab(name)}',
        }
