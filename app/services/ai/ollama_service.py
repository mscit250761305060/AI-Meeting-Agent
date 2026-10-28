"""
Ollama Client Service

Provides robust, typed, centralized communication with local Ollama runtime.
Handles timeouts, connection retries, JSON mode, and error reporting gracefully.
"""

import json
import logging
import time
import requests
from typing import Optional, Dict, Any, Union

from config import OLLAMA_BASE_URL, DEFAULT_OLLAMA_MODEL, OLLAMA_TIMEOUT, get_model

logger = logging.getLogger(__name__)


class OllamaServiceException(Exception):
    """Custom exception raised when Ollama call fails permanently."""
    pass


class OllamaClient:
    def __init__(self, base_url: Optional[str] = None, timeout: Optional[int] = None):
        self.base_url = (base_url or OLLAMA_BASE_URL).rstrip("/")
        self.timeout = timeout or OLLAMA_TIMEOUT

    def is_available(self) -> bool:
        """Checks if local Ollama daemon is reachable."""
        try:
            res = requests.get(f"{self.base_url}/api/tags", timeout=2)
            return res.status_code == 200
        except Exception:
            return False

    def list_models(self) -> list:
        """Returns list of models installed locally in Ollama."""
        try:
            res = requests.get(f"{self.base_url}/api/tags", timeout=3)
            if res.status_code == 200:
                data = res.json()
                return [m.get("name") for m in data.get("models", [])]
        except Exception as e:
            logger.warning(f"Failed to query Ollama models: {e}")
        return []

    def generate(
        self,
        prompt: str,
        model: Optional[str] = None,
        system: Optional[str] = None,
        json_mode: bool = False,
        temperature: float = 0.2,
        max_retries: int = 3,
        retry_delay: float = 2.0
    ) -> str:
        """
        Generates completion using local Ollama model.
        Returns the output text.
        """
        model_name = model or DEFAULT_OLLAMA_MODEL
        url = f"{self.base_url}/api/generate"

        payload: Dict[str, Any] = {
            "model": model_name,
            "prompt": prompt,
            "stream": False,
            "options": {
                "temperature": temperature,
            }
        }

        if system:
            payload["system"] = system

        if json_mode:
            payload["format"] = "json"

        last_error = None
        for attempt in range(1, max_retries + 1):
            try:
                logger.info(f"Calling Ollama model '{model_name}' (attempt {attempt}/{max_retries})...")
                res = requests.post(url, json=payload, timeout=self.timeout)

                if res.status_code == 404:
                    err_msg = (
                        f"Ollama model '{model_name}' not found. "
                        f"Run 'ollama pull {model_name}' or check available models with 'ollama list'."
                    )
                    logger.error(err_msg)
                    raise OllamaServiceException(err_msg)

                res.raise_for_status()
                data = res.json()
                response_text = data.get("response", "")
                return response_text.strip()

            except requests.exceptions.ConnectionError as e:
                last_error = (
                    f"Cannot connect to Ollama at {self.base_url}. "
                    f"Ensure the Ollama application or service is started. ({e})"
                )
                logger.warning(f"Ollama connection error (attempt {attempt}): {last_error}")
                if attempt < max_retries:
                    time.sleep(retry_delay)

            except requests.exceptions.Timeout as e:
                last_error = f"Ollama request timed out after {self.timeout}s ({e})"
                logger.warning(f"Ollama timeout (attempt {attempt}): {last_error}")
                if attempt < max_retries:
                    time.sleep(retry_delay)

            except OllamaServiceException:
                raise

            except Exception as e:
                last_error = f"Unexpected error during Ollama call: {e}"
                logger.warning(f"Ollama error (attempt {attempt}): {last_error}")
                if attempt < max_retries:
                    time.sleep(retry_delay)

        raise OllamaServiceException(f"Failed to generate after {max_retries} attempts: {last_error}")

    def chat(
        self,
        messages: list,
        model: Optional[str] = None,
        json_mode: bool = False,
        temperature: float = 0.2
    ) -> str:
        """
        Chat completion interface for structured multi-turn conversations.
        """
        model_name = model or DEFAULT_OLLAMA_MODEL
        url = f"{self.base_url}/api/chat"

        payload = {
            "model": model_name,
            "messages": messages,
            "stream": False,
            "options": {
                "temperature": temperature
            }
        }
        if json_mode:
            payload["format"] = "json"

        try:
            res = requests.post(url, json=payload, timeout=self.timeout)
            res.raise_for_status()
            data = res.json()
            return data.get("message", {}).get("content", "").strip()
        except Exception as e:
            raise OllamaServiceException(f"Ollama chat call failed: {e}")


# Singleton instance
ollama_service = OllamaClient()


def ask_ollama(prompt: str, model_role: Optional[str] = None) -> str:
    """
    Standard drop-in function to query local Ollama.
    Role can be 'requirement', 'backend', 'error_fix', etc.
    """
    model = get_model(model_role) if model_role else DEFAULT_OLLAMA_MODEL
    return ollama_service.generate(prompt=prompt, model=model)
