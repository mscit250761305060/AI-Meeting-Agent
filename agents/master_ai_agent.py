import threading

from agents.transcript_watcher_agent import (
    start_transcript_watcher
)

from agents.project_regenerator_agent import (
    start_project_regenerator
)


def start_master_ai():

    print("=" * 60)
    print("MASTER AI STARTED")
    print("=" * 60)

    threading.Thread(

        target=start_transcript_watcher,

        daemon=True

    ).start()

    threading.Thread(

        target=start_project_regenerator,

        daemon=True

    ).start()

    print("Transcript Watcher Started")

    print("Project Regenerator Started")

    print("\nMaster AI Running...\n")

    import time

    while True:

        time.sleep(1)