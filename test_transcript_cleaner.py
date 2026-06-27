from agents.transcript_cleaner_agent import (
    clean_transcript
)

raw_text = """
I want employment management system
need dashboard page
need employee pitch
need employee form
"""

result = clean_transcript(
    raw_text
)

print("\nCLEANED:\n")
print(result)