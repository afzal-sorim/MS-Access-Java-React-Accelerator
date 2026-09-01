"""LLM Provider abstraction - supports Ollama and OpenRouter.

Spec section 36: Create an abstraction LLMProvider with OllamaProvider and OpenRouterProvider.
The converter must not depend on one specific model. Primary local mode preferred for sensitive code.
"""
from __future__ import annotations

import hashlib
import json
import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import Enum
from typing import Any, Optional

logger = logging.getLogger("converter.llm")


class LLMProviderType(str, Enum):
    OLLAMA = "ollama"
    OPENROUTER = "openrouter"
    ANTHROPIC = "anthropic"


@dataclass
class LLMResponse:
    """Structured response from LLM."""
    content: str
    model: str
    tokens_used: int
    cached: bool = False
    confidence: float = 1.0
    raw_response: Optional[dict] = None


@dataclass
class LLMConfig:
    """Configuration for LLM provider."""
    provider_type: Optional[LLMProviderType] = None
    model: Optional[str] = None
    base_url: Optional[str] = None
    api_key: Optional[str] = None
    max_tokens: int = 4096
    temperature: float = 0.1
    timeout: int = 120
    max_retries: int = 3

    def __post_init__(self):
        import os
        if self.provider_type is None:
            p_type = os.environ.get("LLM_PROVIDER", "ollama").lower()
            if p_type == "openrouter":
                self.provider_type = LLMProviderType.OPENROUTER
            elif p_type == "anthropic":
                self.provider_type = LLMProviderType.ANTHROPIC
            else:
                self.provider_type = LLMProviderType.OLLAMA

        if self.model is None:
            if self.provider_type == LLMProviderType.OLLAMA:
                self.model = os.environ.get("OLLAMA_MODEL") or os.environ.get("LLM_MODEL") or "deepseek-r1:1.5b"
            elif self.provider_type == LLMProviderType.OPENROUTER:
                self.model = os.environ.get("OPENROUTER_MODEL") or os.environ.get("LLM_MODEL") or "google/gemini-2.5-flash"
            else:
                self.model = os.environ.get("LLM_MODEL") or "deepseek-r1:1.5b"

        if self.base_url is None:
            if self.provider_type == LLMProviderType.OLLAMA:
                self.base_url = os.environ.get("OLLAMA_BASE_URL") or os.environ.get("OLLAMA_HOST") or "http://localhost:11434"
            elif self.provider_type == LLMProviderType.OPENROUTER:
                self.base_url = os.environ.get("OPENROUTER_BASE_URL") or "https://openrouter.ai/api/v1"

        if self.api_key is None:
            if self.provider_type == LLMProviderType.OPENROUTER:
                self.api_key = os.environ.get("OPENROUTER_API_KEY") or os.environ.get("LLM_API_KEY")


class LLMProvider(ABC):
    """Abstract base class for LLM providers."""

    def __init__(self, config: LLMConfig):
        self.config = config
        self._cache: dict[str, LLMResponse] = {}

    @abstractmethod
    def generate(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        json_mode: bool = False,
    ) -> LLMResponse:
        """Generate a response from the LLM."""
        pass

    @abstractmethod
    def generate_structured(
        self,
        prompt: str,
        schema: dict,
        system_prompt: Optional[str] = None,
    ) -> dict:
        """Generate a structured JSON response conforming to schema."""
        pass

    def _cache_key(self, prompt: str, system_prompt: Optional[str] = None) -> str:
        """Generate cache key from prompts."""
        combined = f"{system_prompt or ''}|{prompt}"
        return hashlib.sha256(combined.encode()).hexdigest()

    def _check_cache(self, cache_key: str) -> Optional[LLMResponse]:
        """Check if response is cached."""
        return self._cache.get(cache_key)

    def _store_cache(self, cache_key: str, response: LLMResponse) -> None:
        """Store response in cache."""
        response.cached = True
        self._cache[cache_key] = response


class OllamaProvider(LLMProvider):
    """Ollama local LLM provider."""

    def __init__(self, config: LLMConfig):
        super().__init__(config)
        self.base_url = config.base_url or "http://localhost:11434"
        self._client = None
        logger.info(
            "✓ LLM Connection Initialized: [Provider: OLLAMA] | [Connected Model: %s] | [Base URL: %s] | [Timeout: %ss] | [Temp: %.2f]",
            self.config.model,
            self.base_url,
            self.config.timeout,
            self.config.temperature,
        )

    def _get_client(self):
        """Lazy import and create HTTP client."""
        if self._client is None:
            import httpx
            self._client = httpx.Client(timeout=self.config.timeout)
        return self._client

    def generate(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        json_mode: bool = False,
    ) -> LLMResponse:
        """Generate response using Ollama API."""
        cache_key = self._cache_key(prompt, system_prompt)
        cached = self._check_cache(cache_key)
        if cached:
            logger.info("LLM cache hit for model %s (prompt length: %d)", self.config.model, len(prompt))
            return cached

        logger.info(
            "Sending request to Ollama LLM: Model='%s' | BaseURL='%s' | PromptLength=%d | JSONMode=%s",
            self.config.model,
            self.base_url,
            len(prompt),
            json_mode,
        )

        client = self._get_client()

        payload = {
            "model": self.config.model,
            "prompt": prompt,
            "stream": False,
            "options": {
                "temperature": self.config.temperature,
                "num_predict": self.config.max_tokens,
            },
        }

        if system_prompt:
            payload["system"] = system_prompt

        if json_mode:
            payload["format"] = "json"

        response = client.post(
            f"{self.base_url}/api/generate",
            json=payload,
        )
        response.raise_for_status()

        data = response.json()
        tokens = data.get("eval_count", 0) + data.get("prompt_eval_count", 0)
        result = LLMResponse(
            content=data.get("response", ""),
            model=self.config.model,
            tokens_used=tokens,
            raw_response=data,
        )

        logger.info("Received response from Ollama LLM: Model='%s' | TokensUsed=%d", self.config.model, tokens)
        self._store_cache(cache_key, result)
        return result

    def generate_structured(
        self,
        prompt: str,
        schema: dict,
        system_prompt: Optional[str] = None,
    ) -> dict:
        """Generate structured JSON response."""
        enhanced_prompt = f"""{prompt}

You must respond with valid JSON conforming to this schema:
{json.dumps(schema, indent=2)}

Respond ONLY with the JSON, no other text."""

        response = self.generate(
            enhanced_prompt,
            system_prompt=system_prompt,
            json_mode=True,
        )

        try:
            return json.loads(response.content)
        except json.JSONDecodeError as e:
            logger.warning("JSON decode failed from LLM (%s), retrying with correction prompt...", e)
            # Retry with correction instruction
            retry_prompt = f"""The previous response was invalid JSON. Error: {e}

Original prompt: {prompt}

Please respond with valid JSON conforming to this schema:
{json.dumps(schema, indent=2)}"""

            retry_response = self.generate(
                retry_prompt,
                system_prompt=system_prompt,
                json_mode=True,
            )
            return json.loads(retry_response.content)


class OpenRouterProvider(LLMProvider):
    """OpenRouter API provider for cloud LLMs."""

    def __init__(self, config: LLMConfig):
        super().__init__(config)
        self.base_url = config.base_url or "https://openrouter.ai/api/v1"
        self._client = None
        logger.info(
            "✓ LLM Connection Initialized: [Provider: OPENROUTER] | [Connected Model: %s] | [Base URL: %s] | [Timeout: %ss]",
            self.config.model,
            self.base_url,
            self.config.timeout,
        )

    def _get_client(self):
        """Lazy import and create HTTP client."""
        if self._client is None:
            import httpx
            self._client = httpx.Client(
                timeout=self.config.timeout,
                headers={
                    "Authorization": f"Bearer {self.config.api_key}",
                    "HTTP-Referer": "https://github.com/access-converter",
                    "X-Title": "MS Access Converter",
                },
            )
        return self._client

    def generate(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        json_mode: bool = False,
    ) -> LLMResponse:
        """Generate response using OpenRouter API."""
        cache_key = self._cache_key(prompt, system_prompt)
        cached = self._check_cache(cache_key)
        if cached:
            logger.info("LLM cache hit for model %s (prompt length: %d)", self.config.model, len(prompt))
            return cached

        logger.info(
            "Sending request to OpenRouter LLM: Model='%s' | BaseURL='%s' | PromptLength=%d",
            self.config.model,
            self.base_url,
            len(prompt),
        )

        client = self._get_client()

        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        payload = {
            "model": self.config.model,
            "messages": messages,
            "max_tokens": self.config.max_tokens,
            "temperature": self.config.temperature,
        }

        if json_mode:
            payload["response_format"] = {"type": "json_object"}

        response = client.post(
            f"{self.base_url}/chat/completions",
            json=payload,
        )
        response.raise_for_status()

        data = response.json()
        usage = data.get("usage", {})
        tokens = usage.get("total_tokens", 0)
        result = LLMResponse(
            content=data["choices"][0]["message"]["content"],
            model=self.config.model,
            tokens_used=tokens,
            raw_response=data,
        )

        logger.info("Received response from OpenRouter LLM: Model='%s' | TokensUsed=%d", self.config.model, tokens)
        self._store_cache(cache_key, result)
        return result

    def generate_structured(
        self,
        prompt: str,
        schema: dict,
        system_prompt: Optional[str] = None,
    ) -> dict:
        """Generate structured JSON response."""
        enhanced_prompt = f"""{prompt}

You must respond with valid JSON conforming to this schema:
{json.dumps(schema, indent=2)}

Respond ONLY with the JSON, no other text."""

        response = self.generate(
            enhanced_prompt,
            system_prompt=system_prompt,
            json_mode=True,
        )

        return json.loads(response.content)


class LLMProviderFactory:
    """Factory for creating LLM providers."""

    @staticmethod
    def create(config: LLMConfig) -> LLMProvider:
        """Create an LLM provider based on configuration."""
        p_type = config.provider_type.value if config.provider_type else "unknown"
        logger.info("Initializing LLM connection provider: [Type: %s] | [Target Model: %s]", p_type, config.model)
        if config.provider_type == LLMProviderType.OLLAMA:
            return OllamaProvider(config)
        elif config.provider_type == LLMProviderType.OPENROUTER:
            if not config.api_key:
                raise ValueError("OpenRouter requires an API key")
            return OpenRouterProvider(config)
        else:
            raise ValueError(f"Unknown provider type: {config.provider_type}")


# Default provider instance
_default_provider: Optional[LLMProvider] = None


def get_default_provider() -> LLMProvider:
    """Get or create the default LLM provider."""
    global _default_provider
    if _default_provider is None:
        logger.info("Loading default LLM provider from environment configuration...")
        config = LLMConfig()
        _default_provider = LLMProviderFactory.create(config)
    return _default_provider


def set_default_provider(provider: LLMProvider) -> None:
    """Set the default LLM provider."""
    global _default_provider
    _default_provider = provider
    logger.info("Default LLM provider updated: Model=%s", getattr(provider.config, 'model', 'unknown'))

