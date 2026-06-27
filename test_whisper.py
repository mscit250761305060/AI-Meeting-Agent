import whisper

model = whisper.load_model("base")

result = model.transcribe(
    "audio/test.m4a"
)

print(result["text"])