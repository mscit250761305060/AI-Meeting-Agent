from faster_whisper import WhisperModel

from meeting_engine.audio_queue import audio_queue

from agents.transcript_pipeline_agent import (
    process_live_transcript
)

from agents.pipeline_logger import log_stage


model = WhisperModel(

    "base",

    device="cpu",

    compute_type="int8"

)


def start_whisper_consumer():

    print(
        "Whisper Consumer Started"
    )

    while True:

        audio_file = audio_queue.get()

        segments, _ = model.transcribe(

            audio_file

        )

        transcript = " ".join(

            s.text

            for s in segments

        )

        if transcript.strip():
            
            log_stage("WHISPER OUTPUT", transcript)

            process_live_transcript(transcript)