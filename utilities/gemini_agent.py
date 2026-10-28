import logging
from app.services.ai.ollama_service import ask_ollama

logger = logging.getLogger(__name__)

def ask_gemini(prompt: str) -> str:
    """
    Backwards-compatible wrapper now routed 100% to local Ollama.
    """
    return ask_ollama(prompt)