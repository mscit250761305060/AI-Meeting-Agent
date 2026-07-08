from agents.live_system_whisper_agent import (
    transcribe_audio
)

from agents.transcript_corrector_agent import (
    correct_transcript
)

from agents.meeting_memory_agent import (
    update_memory
)

from agents.requirement_updater_agent import (
    update_requirements
)

from agents.project_regenerator_agent import (
    start_project_regenerator
)

def process_transcript(transcript):

    corrected = correct_transcript(
        transcript
    )

    print(
        "\nCorrected:"
    )

    print(
        corrected
    )

    update_memory(
        corrected
    )

    update_requirements(
        corrected
    )

    print(
        "\nRequirements Updated"
    )