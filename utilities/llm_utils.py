"""
utilities/llm_utils.py — Unified LLM Utility routed to local Ollama
"""

import json
import logging
from typing import Optional, Any
from app.services.ai.ollama_service import ollama_service, OllamaServiceException
from config import get_model

logger = logging.getLogger(__name__)


class MockOllamaResponse:
    """Mock response object providing .text attribute for backwards compatibility."""
    def __init__(self, text: str):
        self.text = text


def generate_content_with_retry(
    model_name: str,
    contents: Any,
    config: Optional[Any] = None,
    max_retries: int = 3,
    base_delay: float = 2.0
) -> MockOllamaResponse:
    """
    Unified caller routed to local Ollama engine.
    Compatible with callers expecting a response object with .text.
    """
    # Convert list/dict contents to text prompt if needed
    if isinstance(contents, str):
        prompt = contents
    elif isinstance(contents, list):
        prompt = "\n".join(str(c) for c in contents)
    else:
        prompt = str(contents)

    # Determine temperature if specified
    temperature = 0.2
    if config and hasattr(config, "temperature") and config.temperature is not None:
        temperature = config.temperature

    json_mode = False
    if config and hasattr(config, "response_mime_type") and "json" in str(config.response_mime_type).lower():
        json_mode = True

    try:
        response_text = ollama_service.generate(
            prompt=prompt,
            model=model_name,
            json_mode=json_mode,
            temperature=temperature,
            max_retries=max_retries,
            retry_delay=base_delay
        )
        return MockOllamaResponse(response_text)
    except OllamaServiceException as e:
        logger.error(f"Ollama generation failure: {e}")
        raise
