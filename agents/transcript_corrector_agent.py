from agents.gemini_agent import ask_gemini

from agents.transcript_merger_agent import (
    merge_transcript
)


def correct_transcript(new_text):

    

    prompt = f"""
You are an AI Meeting Assistant.

Below is the complete meeting context.

Your job is:

1. Correct speech recognition mistakes.
2. Remove duplicated sentences.
3. Merge incomplete sentences.
4. Keep only meaningful project requirements.
5. Preserve the project context.

Meeting:

{new_text}

Return ONLY the corrected meeting transcript.
"""

    response = ask_gemini(prompt)

    if response is None:
        return new_text

    return response.strip()