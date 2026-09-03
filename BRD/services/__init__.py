"""BRD Services package."""
from .source_analyzer import extract_project_facts
from .static_analyzer import compute_static_metrics
from .ollama_client import OllamaClient, OllamaUnavailableError
from .template_renderer import render_brd_template
from .brd_generator import generate_brd_for_job

__all__ = [
    "extract_project_facts",
    "compute_static_metrics",
    "OllamaClient",
    "OllamaUnavailableError",
    "render_brd_template",
    "generate_brd_for_job",
]
