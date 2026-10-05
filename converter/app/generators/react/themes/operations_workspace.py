"""Operations Workspace theme for data-dense generated applications."""
from __future__ import annotations

from .modern_dashboard import ModernDashboardTheme


class OperationsWorkspaceTheme(ModernDashboardTheme):
    """A compact operational sidebar and record-focused workspace variant."""

    @property
    def name(self) -> str:
        return "Operations Workspace"

    @property
    def key(self) -> str:
        return "operations_workspace"

    def get_css(self, app_name, presentations) -> dict[str, str]:
        files = super().get_css(app_name, presentations)
        files["workspace.css"] = """.sidebar { background: #0b1220; width: 18rem; } .content { max-width: none; } .card-grid { grid-template-columns: repeat(auto-fill, minmax(18rem, 1fr)); } .data-table { font-size: .9rem; }\n"""
        return files
