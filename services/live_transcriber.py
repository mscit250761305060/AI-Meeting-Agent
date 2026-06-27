import speech_recognition as sr
from pathlib import Path
import whisper
import os
import io

def start_live_transcription():
    print("System: Loading Whisper AI Model (base)... Please wait...")
    model = whisper.load_model("small")
    print("System: Whisper Model loaded successfully!")

    recognizer = sr.Recognizer()
    transcript_file = Path("data/live_transcript.txt")
    transcript_file.parent.mkdir(exist_ok=True)
    with open(transcript_file, "w", encoding="utf-8") as f:
        f.write("")
    
    mic_index = None
    
    try:
        with sr.Microphone(device_index=mic_index) as source:
            print("System: Adjusting for ambient noise. Please be quiet for 1 second...")
            recognizer.adjust_for_ambient_noise(source, duration=1)
            print("Live transcription started using Whisper AI (English Only)...")
            print("Press CTRL + C to stop")
            
            while True:
                try:
                    audio = recognizer.listen(source, timeout=10, phrase_time_limit=10)
                    wav_data = io.BytesIO(audio.get_wav_data())
                    
                    temp_filename = "data/temp_live_audio.wav"
                    with open(temp_filename, "wb") as f:
                        f.write(wav_data.read())
                    
                    # Fixed language to English to avoid foreign language hallucinations
                    result = model.transcribe(temp_filename, fp16=False, language="en")
                    text = result["text"].strip()
                    
                    if os.path.exists(temp_filename):
                        os.remove(temp_filename)
                        
                    if text:
                        print("Whisper Transcript:", text)
                        with open(transcript_file, "a", encoding="utf-8") as f:
                            f.write(text + "\n")
                        
                except sr.WaitTimeoutError:
                    continue
                except Exception as inner_error:
                    print(f"[Loop Error]: {inner_error}")
                    
    except KeyboardInterrupt:
        print("\nLive transcription stopped by user.")
    except Exception as outer_error:
        print(f"\n[Microphone Error]: {outer_error}")

if __name__ == "__main__":
    start_live_transcription()