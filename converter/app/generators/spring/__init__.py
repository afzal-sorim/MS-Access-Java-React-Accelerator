"""Spring Boot backend generator - JPA entities, repositories, services, controllers.

Spec section 15, 17: Generate from IR with deterministic naming conventions.
"""
from .generator import SpringBootGenerator, generate_spring_boot

__all__ = ["SpringBootGenerator", "generate_spring_boot"]
