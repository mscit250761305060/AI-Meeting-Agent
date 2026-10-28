import logging
from app.services.ai.ollama_service import ollama_service
from config import get_model

logger = logging.getLogger(__name__)


def clean_transcript(raw_text: str) -> str:
    prompt = f"""You are a transcript correction AI.

Fix speech-to-text mistakes.

Rules:
- Keep original meaning.
- Correct software development terminology.
- Remove garbage text and stuttering.
- Return only cleaned transcript.

Transcript:
{raw_text}
"""
    model_name = get_model("requirement")
    try:
        return ollama_service.generate(prompt=prompt, model=model_name).strip()
    except Exception as e:
        logger.warning(f"Transcript cleaning failed: {e}. Returning raw text.")
        return raw_text.strip()