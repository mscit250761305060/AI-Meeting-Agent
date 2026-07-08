import threading

from agents.audio_capture_agent import (
    start_audio_capture
)

from agents.whisper_consumer_agent import (
    start_whisper_consumer
)

threading.Thread(

    target=start_audio_capture,

    daemon=True

).start()

threading.Thread(

    target=start_whisper_consumer,

    daemon=True

).start()

print(

    "Meeting AI Started"

)

input()