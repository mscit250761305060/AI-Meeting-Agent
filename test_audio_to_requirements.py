from faster_whisper import WhisperModel
from agents.requirement_agent import (
    extract_requirements
)

print("Loading Whisper Model...")

model = WhisperModel("base", device="cpu", compute_type="int8")

print("Transcribing Audio...")

segments, info = model.transcribe(
    "audio/test.m4a",
    beam_size=1
)

transcript = " ".join(s.text for s in segments)

print("\nTRANSCRIPT:\n")
print(transcript)

print("\nEXTRACTING REQUIREMENTS...\n")

requirements = extract_requirements(
    transcript
)

print(requirements)