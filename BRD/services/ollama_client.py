"""Ollama Client for BRD Generation.
Interfaces directly with the local Ollama instance (defaulting to deepseek-r1:1.5b).
Handles extraction of clean JSON, stripping <think>...</think> reasoning tags,
and comprehensive error handling.
"""
from __future__ import annotations

import json
import logging
import os
import re
from typing import Any, Dict, Optional
import httpx

logger = logging.getLogger("converter.brd.ollama_client")


class OllamaUnavailableError(Exception):
    """Raised when the local Ollama server cannot be reached."""
    pass


class OllamaModelError(Exception):
    """Raised when the specified model is missing or unsupported."""
    pass


class OllamaClient:
    """Client for querying local Ollama instance."""

    def __init__(
        self,
        base_url: Optional[str] = None,
        model: Optional[str] = None,
        timeout: int = 180,
    ):
        self.base_url = (
            base_url
            or os.environ.get("LLM_BASE_URL")
            or os.environ.get("OLLAMA_BASE_URL")
            or os.environ.get("OLLAMA_HOST")
            or "http://localhost:11434"
        ).rstrip("/")
        self.model = (
            model
            or os.environ.get("LLM_MODEL")
            or os.environ.get("OLLAMA_MODEL")
            or "deepseek-r1:1.5b"
        )
        self.timeout = timeout

    def check_health(self) -> bool:
        """Check if Ollama service is reachable."""
        try:
            with httpx.Client(timeout=5) as client:
                res = client.get(f"{self.base_url}/api/tags")
                return res.status_code == 200
        except Exception as e:
            logger.warning("Ollama health check failed: %s", e)
            return False

    def generate_narratives(self, prompt: str, system_prompt: Optional[str] = None) -> Dict[str, Any]:
        """Send prompt to Ollama and return parsed JSON structure."""
        url = f"{self.base_url}/api/generate"
        payload = {
            "model": self.model,
            "prompt": prompt,
            "stream": False,
            "format": "json",
            "options": {
                "temperature": 0.2,
                "num_predict": 1500,
            },
        }
        if system_prompt:
            payload["system"] = system_prompt

        logger.info("Calling Ollama at %s with model '%s'", self.base_url, self.model)

        try:
            client_timeout = httpx.Timeout(5.0, connect=2.0)
            with httpx.Client(timeout=client_timeout) as client:
                res = client.post(url, json=payload)
        except httpx.ConnectError as e:
            logger.error("Failed to connect to Ollama: %s", e)
            raise OllamaUnavailableError(
                "BRD generation is unavailable because the local Ollama service could not be reached."
            ) from e
        except httpx.TimeoutException as e:
            logger.error("Ollama request timed out after %ds", self.timeout)
            raise OllamaUnavailableError(
                f"Ollama request timed out after {self.timeout}s. Please verify your local Ollama instance."
            ) from e
        except Exception as e:
            logger.error("Ollama communication error: %s", e)
            raise OllamaUnavailableError(f"Ollama communication error: {e}") from e

        if res.status_code == 404:
            raise OllamaModelError(
                f"Model '{self.model}' was not found in your local Ollama instance. Please run 'ollama pull {self.model}'."
            )
        elif res.status_code != 200:
            raise OllamaUnavailableError(
                f"Ollama returned HTTP error {res.status_code}: {res.text}"
            )

        data = res.json()
        raw_response = data.get("response", "").strip()

        # Clean reasoning tokens e.g. <think>...</think> from deepseek-r1
        cleaned = re.sub(r"<think>.*?</think>", "", raw_response, flags=re.DOTALL).strip()

        # Strip markdown codeblocks if wrapped
        if cleaned.startswith("```"):
            cleaned = re.sub(r"^```(?:json)?\n?", "", cleaned, flags=re.IGNORECASE)
            cleaned = re.sub(r"\n?```$", "", cleaned)
            cleaned = cleaned.strip()

        try:
            return json.loads(cleaned)
        except json.JSONDecodeError as e:
            logger.warning("Direct JSON decode failed: %s. Attempting heuristic regex match...", e)
            match = re.search(r"(\{.*\})", cleaned, flags=re.DOTALL)
            if match:
                try:
                    return json.loads(match.group(1))
                except Exception:
                    pass
            logger.error("Could not parse LLM output as JSON: %s", cleaned[:500])
            raise ValueError(f"LLM produced invalid JSON format: {e}")
