import logging
import os
import threading
from queue import Empty

from faster_whisper import WhisperModel

import server.meeting_state as meeting_state
from agents.live_requirement_detector import should_process
from agents.meeting_filter_agent import is_project_requirement
from agents.transcript_pipeline_agent import process_live_transcript
from meeting_engine.audio_queue import audio_queue

logger = logging.getLogger(__name__)

_model = None
_model_lock = threading.Lock()


def get_whisper_model():
    global _model

    if _model is None:
        with _model_lock:
            if _model is None:
                try:
                    _model = WhisperModel("base", device="cpu", compute_type="int8")
                except Exception as exc:
                    logger.exception("Failed to load Whisper model: %s", exc)
                    return None

    return _model


def transcribe_audio(file_path):

    print("TRANSCRIBE START")

    model = get_whisper_model()

    print("MODEL =", model)

    if model is None:
        print("MODEL NONE")
        return ""

    try:

        print("CALLING WHISPER")

        segments, info = model.transcribe(
            file_path,
            beam_size=1
        )

        print("WHISPER FINISHED")

        text = ""

        for segment in segments:

            print(segment.text)

            text += segment.text + " "

        print("FINAL TEXT =", text)

        return text

    except Exception as exc:

        print("WHISPER ERROR")

        print(exc)

        logger.exception(exc)

        return ""

def start_whisper_worker():

    print("ENTERED WHISPER")

    print("meeting_running =", meeting_state.meeting_running)

    logger.info("Whisper Worker Started")

    processed_files = set()


    print("ABOUT TO ENTER LOOP")
    while meeting_state.meeting_running or not audio_queue.empty():
        print("WAITING FOR AUDIO")
        if meeting_state.stop_event.is_set() and audio_queue.empty():
            break

        logger.info("Queue Waiting")
        try:
            filename = audio_queue.get(timeout=0.5)
            print("QUEUE RECEIVED:", filename)
        except Empty:
            continue

        if not filename or filename in processed_files:
            logger.info("Skipping duplicate or empty queue item: %s", filename)
            continue

        processed_files.add(filename)

        if not os.path.exists(filename):
            logger.warning("Audio file missing: %s", filename)
            continue

        logger.info("Whisper Processing: %s", filename)

        try:

            print("BEFORE TRANSCRIBE")

            text = transcribe_audio(filename)

            print("AFTER TRANSCRIBE")

            print("TEXT =", text)

            from meeting_engine.live_transcript_manager import transcript_manager

            transcript_manager.process(filename, text)

        except Exception as e:

            print("WHISPER WORKER EXCEPTION")

            print(type(e))

            print(e)

            import traceback
            traceback.print_exc()
        finally:
            try:
                os.remove(filename)
            except FileNotFoundError:
                pass
            except OSError as exc:
                logger.warning("Unable to remove temporary audio file %s: %s", filename, exc)

    logger.info("Whisper Worker Stopped")