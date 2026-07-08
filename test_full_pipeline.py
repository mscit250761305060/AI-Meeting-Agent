import threading

from agents.transcript_watcher_agent import (
    start_transcript_watcher
)

threading.Thread(
    target=start_transcript_watcher,
    daemon=True
).start()

print("Full Pipeline Started")

input()