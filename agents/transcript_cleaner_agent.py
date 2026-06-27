from google import genai
from dotenv import load_dotenv
import os

load_dotenv()


def clean_transcript(raw_text):

    client = genai.Client(
        api_key=os.getenv("GEMINI_API_KEY")
    )

    prompt = f"""
You are a transcript correction AI.

Fix speech-to-text mistakes.

Rules:

- Keep original meaning.
- Correct software development terminology.
- Employee pitch likely means Employee List.
- Employment management system likely means Employee Management System.
- Dashboard page, employee list page and employee form page are common software pages.
- Remove garbage text.
- Return only cleaned transcript.

Transcript:

{raw_text}
"""

    response = client.models.generate_content(
        model="gemini-2.5-flash",
        contents=prompt
    )

    return response.text.strip()