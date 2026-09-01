"""React frontend generator - pages, components, forms from Access forms.

Spec section 19: Forms → React pages/components with proper control mappings.
"""
from .generator import ReactGenerator, generate_react

__all__ = ["ReactGenerator", "generate_react"]
