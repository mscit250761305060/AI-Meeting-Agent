from agents.meeting_context_agent import (
    clear_context,
    append_context
)

from agents.transcript_merger_agent import (
    merge_transcript
)

clear_context()

append_context(
    "Create Employee Management System"
)

append_context(
    "Add Dashboard"
)

merged = merge_transcript(
    "Add Search Bar"
)

print(merged)