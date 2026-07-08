import threading

from meeting_engine.system_audio_worker import (
    push_system_audio
)

from meeting_engine.microphone_worker import (
    push_microphone_audio
)

from meeting_engine.whisper_worker import (
    start_whisper_worker
)

threading.Thread(

    target=start_whisper_worker,

    daemon=True

).start()

push_system_audio(

    "System Audio"

)

push_microphone_audio(

    "Mic Audio"

)

input()