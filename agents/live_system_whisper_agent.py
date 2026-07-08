import tempfile
import wave

import pyaudiowpatch as pyaudio

import time

from faster_whisper import WhisperModel

from agents.system_audio_agent import (
    get_loopback_device
)

model = WhisperModel(

    "base",

    device="cpu",

    compute_type="int8"

)

def transcribe_audio(file):

    segments, _ = model.transcribe(

        file

    )

    return " ".join(

        s.text

        for s in segments

    )

def start_live_system_whisper():

    import tempfile
    import wave
    import time

    p = pyaudio.PyAudio()

    device = get_loopback_device()

    rate = int(device["defaultSampleRate"])

    chunk = 1024

    stream = p.open(

        format=pyaudio.paInt16,

        channels=2,

        rate=rate,

        input=True,

        input_device_index=device["index"],

        frames_per_buffer=chunk

    )

    print("Live Meeting Listening...")

    try:

        while True:

            print("Recording 5 sec...")

            frames = []

            start = time.time()

            while time.time() - start < 5:

                data = stream.read(

                    chunk,

                    exception_on_overflow=False

                )

                frames.append(data)

            print("Recording Finished")

            with tempfile.NamedTemporaryFile(

                suffix=".wav",

                delete=False

            ) as temp:

                filename = temp.name

            wf = wave.open(filename, "wb")

            wf.setnchannels(2)

            wf.setsampwidth(

                p.get_sample_size(

                    pyaudio.paInt16

                )

            )

            wf.setframerate(rate)

            wf.writeframes(

                b"".join(frames)

            )

            wf.close()

            print("Running Whisper...")

            text = transcribe_audio(filename)

            print("Whisper Finished")

            if text.strip():

                from agents.meeting_pipeline_agent import (
                    process_transcript
                )

                process_transcript(text)

    except KeyboardInterrupt:

        print("\nStopped")

    finally:

        stream.stop_stream()

        stream.close()

        p.terminate()