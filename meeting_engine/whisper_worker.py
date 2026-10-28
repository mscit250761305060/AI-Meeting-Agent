import logging
import os
import threading
from queue import Empty

try:
    from faster_whisper import WhisperModel
except ImportError:
    WhisperModel = None

from app.services import meeting_state
from meeting_engine.audio_queue import audio_queue

logger = logging.getLogger(__name__)

_model = None
_model_lock = threading.Lock()


def get_whisper_model():
    global _model

    if _model is None:
        with _model_lock:
            if _model is not None:
                return _model
            if WhisperModel is None:
                logger.warning("faster_whisper is not installed. Returning None for WhisperModel.")
                return None
            model_name = os.getenv("WHISPER_MODEL", "base")
            try:
                # Try cached local model first for instant offline loading
                _model = WhisperModel(model_name, device="cpu", compute_type="int8", local_files_only=True)
                logger.info("Faster-Whisper model '%s' loaded from local cache.", model_name)
            except Exception:
                try:
                    logger.info("Downloading/verifying Faster-Whisper model '%s' on CPU (int8)...", model_name)
                    _model = WhisperModel(model_name, device="cpu", compute_type="int8")
                    logger.info("Faster-Whisper model '%s' loaded successfully.", model_name)
                except Exception as exc:
                    logger.exception("Failed to load Whisper model: %s", exc)
                    return None

    return _model


def transcribe_audio(file_path: str) -> str:
    if not os.path.exists(file_path):
        logger.warning("transcribe_audio: file does not exist: %s", file_path)
        return ""

    model = get_whisper_model()
    if model is None:
        msg = "Whisper speech-to-text model is unavailable. Install faster-whisper to enable live transcription."
        meeting_state.runtime_error = msg
        try:
            from app.services.ws_manager import manager
            manager.broadcast_sync({"action": "log", "message": f"⚠️ {msg}", "type": "w"})
        except Exception:
            pass
        return ""

    try:
        segments, info = model.transcribe(
            file_path,
            beam_size=1,
            initial_prompt="Meeting discussion about software architecture, requirements, features, UI, database, APIs."
        )

        text_parts = []
        for segment in segments:
            seg_text = segment.text.strip()
            if seg_text:
                text_parts.append(seg_text)

        full_text = " ".join(text_parts).strip()
        if full_text:
            logger.info("Whisper transcribed (%s, prob=%.2f): %s", info.language, info.language_probability, full_text)
        return full_text

    except Exception as exc:
        logger.exception("Whisper transcription failed for %s: %s", file_path, exc)
        return ""


def start_whisper_worker():
    logger.info("Whisper Worker Started")
    processed_files = set()

    try:
        # Pre-warm model in background
        get_whisper_model()

        while meeting_state.meeting_running or not audio_queue.empty():
            if meeting_state.stop_event.is_set():
                if not meeting_state.meeting_running or audio_queue.empty():
                    break

            try:
                filename = audio_queue.get(timeout=0.5)
            except Empty:
                continue

            if not filename or filename in processed_files:
                continue

            processed_files.add(filename)

            if not os.path.exists(filename):
                logger.warning("Audio file missing: %s", filename)
                continue

            try:
                text = transcribe_audio(filename)
                if text and text.strip():
                    clean_text = text.strip()
                    from meeting_engine.live_transcript_manager import transcript_manager
                    transcript_manager.process(filename, clean_text)
            except Exception as e:
                logger.exception("Whisper worker processing error: %s", e)
            finally:
                try:
                    os.remove(filename)
                except FileNotFoundError:
                    pass
                except OSError as exc:
                    logger.warning("Unable to remove temporary audio file %s: %s", filename, exc)

        # Drain any leftover files if meeting stopped
        while not audio_queue.empty() and meeting_state.stop_event.is_set():
            try:
                leftover = audio_queue.get_nowait()
                if leftover and os.path.exists(leftover):
                    try:
                        os.remove(leftover)
                    except Exception:
                        pass
            except Exception:
                break
    except Exception as exc:
        logger.exception("Unexpected whisper worker error: %s", exc)
    finally:
        logger.info("Whisper Worker Stopped")