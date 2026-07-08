from agents.transcript_corrector_agent import (
    correct_transcript
)

from agents.meeting_memory_agent import (
    add_to_memory
)

from agents.requirement_updater_agent import (
    update_requirements
)

from agents.project_regenerator_agent import (
    start_project_regenerator
)

from agents.ui_event_agent import (
    send_transcript
)

from agents.pipeline_logger import log_stage

def process_live_transcript(text):

    print("\nRAW Transcript:")

    # STEP 0
    # Show raw transcript immediately in UI
    send_transcript(text)

    print(text)

    # STEP 1: correct
    corrected = correct_transcript(text)
    # send_transcript(corrected)
    
    log_stage("RAW TRANSCRIPT", text)

    print("\nCorrected Transcript:")

    print(corrected)

    # STEP 2: memory update
    log_stage("MEMORY UPDATE", corrected)
    add_to_memory(corrected)

    # STEP 3: update requirements
    requirements = update_requirements(corrected)

    log_stage("REQUIREMENTS", requirements)

    # STEP 4: trigger regeneration
    start_project_regenerator()
