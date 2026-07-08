from meeting_engine.audio_queue import audio_queue


def push_microphone_audio(audio):

    audio_queue.put(

        (

            "microphone",

            audio

        )

    )