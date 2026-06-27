from services.transcript_watcher import (
    watch_transcript
)

from agents.requirement_updater_agent import (
    update_requirements
)


watch_transcript(
    "data/live_transcript.txt",
    update_requirements
)