import whisper

from agents.requirement_agent import (
    extract_requirements
)

print("Loading Whisper Model...")

model = whisper.load_model("base")

print("Transcribing Audio...")

result = model.transcribe(
    "audio/test.m4a"
)

transcript = result["text"]

print("\nTRANSCRIPT:\n")
print(transcript)

print("\nEXTRACTING REQUIREMENTS...\n")

requirements = extract_requirements(
    transcript
)

print(requirements)