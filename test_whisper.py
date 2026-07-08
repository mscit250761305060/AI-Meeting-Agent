import whisper

model = whisper.load_model("medium")

result = model.transcribe(
    "audio/test.m4a"
)

print(result["text"])