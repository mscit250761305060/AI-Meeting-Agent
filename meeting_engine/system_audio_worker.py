from meeting_engine.audio_queue import audio_queue


def push_system_audio(audio):

    audio_queue.put(audio)