import tempfile

import sounddevice as sd
import numpy as np
from scipy.io.wavfile import write

from faster_whisper import WhisperModel

from pathlib import Path

# Load model only once
model = WhisperModel(
    "medium",
    device="cpu",
    compute_type="int8"
)

TRANSCRIPT = Path(
    "data/live_transcript.txt"
)


def listen_once(duration=5):

    sample_rate = 16000

    print("Listening...")

    recording = sd.rec(

        int(duration * sample_rate),

        samplerate=sample_rate,

        channels=1,

        dtype=np.int16

    )

    sd.wait()

    with tempfile.NamedTemporaryFile(
        suffix=".wav",
        delete=False
    ) as temp_audio:

        write(
            temp_audio.name,
            sample_rate,
            recording
        )

        segments, info = model.transcribe(
            temp_audio.name
        )

    transcript = ""

    for segment in segments:

        transcript += segment.text + " "

    transcript = transcript.strip()

    print("Transcript Updated")

    print("Transcript:", transcript)

    if transcript:

        TRANSCRIPT.write_text(

            transcript,

            encoding="utf-8"

        )

    return transcript

import time


def start_live_whisper():

    print("Whisper Live Started...")

    while True:

        try:

            listen_once(duration=5)

        except KeyboardInterrupt:

            print("Stopped.")

            break

        except Exception as e:

            print("Error:", e)

        time.sleep(1)