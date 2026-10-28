"""
config.py — Central AI Configuration

Supports Ollama local AI provider as primary, with configurable URL and model names.
"""

import os
from dotenv import load_dotenv

# Set override=True so that the .env file always takes precedence
load_dotenv(override=True)

# ============================================================
# Primary AI Provider: Ollama (Local)
# ============================================================
OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://127.0.0.1:11434")
DEFAULT_OLLAMA_MODEL = os.getenv("DEFAULT_OLLAMA_MODEL", "qwen2.5-coder:7b")

# Timeout in seconds for Ollama requests (CPU inference can take longer for large prompts)
OLLAMA_TIMEOUT = int(os.getenv("OLLAMA_TIMEOUT", "180"))

# ============================================================
# Model Assignments for Different Tasks
# ============================================================
# Code generation & repair tasks default to qwen2.5-coder:7b
# Natural language extraction defaults to llama3.1:8b or qwen2.5-coder:7b
MODELS = {
    "requirement":      os.getenv("MODEL_REQUIREMENT", "qwen2.5-coder:7b"),
    "backend":          os.getenv("MODEL_BACKEND", "qwen2.5-coder:7b"),
    "page_generator":   os.getenv("MODEL_PAGE_GENERATOR", "qwen2.5-coder:7b"),
    "seed_data":        os.getenv("MODEL_SEED_DATA", "qwen2.5-coder:7b"),
    "screen_vision":    os.getenv("MODEL_SCREEN_VISION", "llava:7b"),
    "error_fix":        os.getenv("MODEL_ERROR_FIX", "qwen2.5-coder:7b"),
    "documentation":    os.getenv("MODEL_DOCUMENTATION", "qwen2.5-coder:7b"),
    "architect":        os.getenv("MODEL_ARCHITECT", "qwen2.5-coder:7b"),
    "business_analyst": os.getenv("MODEL_BUSINESS_ANALYST", "qwen2.5-coder:7b"),
}


def get_model(agent_name: str) -> str:
    """Get the model name for a specific agent.
    
    Usage:
        from config import get_model
        model = get_model("requirement")
    """
    return MODELS.get(agent_name, DEFAULT_OLLAMA_MODEL)
