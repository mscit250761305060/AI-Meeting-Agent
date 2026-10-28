import logging
import os
import tempfile
import time
import wave
import numpy as np

try:
    import pyaudiowpatch as pyaudio
except ImportError:
    try:
        import pyaudio
    except ImportError:
        pyaudio = None

try:
    from app.services import meeting_state
except ImportError:
    import server.meeting_state as meeting_state

from agents.system_audio_agent import get_loopback_device, get_microphone_device
from meeting_engine.audio_queue import audio_queue

logger = logging.getLogger(__name__)


def start_audio_capture():
    logger.info("Audio Capture Started")

    if not meeting_state.meeting_running:
        logger.warning("Meeting is not running; audio capture will not record.")
        return

    if pyaudio is None:
        msg = "Audio capture driver (pyaudio/pyaudiowpatch) is not installed. Audio capture cannot start."
        logger.warning(msg)
        meeting_state.runtime_error = msg
        try:
            from app.services.ws_manager import manager
            manager.broadcast_sync({"action": "log", "message": f"⚠️ {msg}", "type": "w"})
        except Exception:
            pass
        return

    p = None
    stream = None

    try:
        p = pyaudio.PyAudio()

        device = get_loopback_device()
        if not device:
            device = get_microphone_device()

        if not device:
            msg = "No audio loopback or microphone device detected; meeting audio capture cannot start."
            logger.warning(msg)
            meeting_state.runtime_error = msg
            try:
                from app.services.ws_manager import manager
                manager.broadcast_sync({"action": "log", "message": f"⚠️ {msg}", "type": "w"})
            except Exception:
                pass
            return

        rate = int(device["defaultSampleRate"])
        channels = int(device.get("maxInputChannels", 2))
        chunk = 1024

        stream = p.open(
            format=pyaudio.paInt16,
            channels=channels,
            rate=rate,
            input=True,
            input_device_index=device["index"],
            frames_per_buffer=chunk,
        )

        logger.info("Audio capture opened on '%s' (%d Hz, %d ch)", device["name"], rate, channels)

        while meeting_state.meeting_running and not meeting_state.stop_event.is_set():
            frames = []
            chunk_start = time.time()

            while (
                meeting_state.meeting_running
                and not meeting_state.stop_event.is_set()
                and (time.time() - chunk_start < 5.0)
            ):
                try:
                    # In Windows WASAPI loopback, stream.read blocks if no audio is playing.
                    # get_read_available() allows non-blocking reads and quick response to stop events.
                    available = stream.get_read_available() if hasattr(stream, "get_read_available") else chunk
                    if available <= 0:
                        time.sleep(0.04)
                        continue

                    read_count = min(chunk, available)
                    data = stream.read(read_count, exception_on_overflow=False)
                    if data:
                        frames.append(data)
                except Exception as exc:
                    logger.warning("Stream read interrupted: %s", exc)
                    time.sleep(0.05)
                    break

            if not meeting_state.meeting_running or meeting_state.stop_event.is_set():
                break

            if not frames:
                continue

            raw_bytes = b"".join(frames)

            # Silence detection: do not feed empty or digital-silence blocks into Whisper
            samples = np.frombuffer(raw_bytes, dtype=np.int16)
            if len(samples) == 0 or np.max(np.abs(samples)) < 150:
                continue

            with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as temp:
                filename = temp.name

            try:
                wf = wave.open(filename, "wb")
                wf.setnchannels(channels)
                wf.setsampwidth(p.get_sample_size(pyaudio.paInt16))
                wf.setframerate(rate)
                wf.writeframes(raw_bytes)
                wf.close()

                logger.info("Audio chunk saved: %s", filename)
                audio_queue.put(filename)
            except (OSError, ValueError, wave.Error) as exc:
                logger.exception("Failed to write audio chunk: %s", exc)
                try:
                    os.remove(filename)
                except FileNotFoundError:
                    pass

    except Exception as exc:
        logger.exception("Audio capture failed: %s", exc)
        meeting_state.runtime_error = f"Audio capture error: {exc}"
    finally:
        if stream is not None:
            try:
                stream.stop_stream()
            except Exception:
                pass
            try:
                stream.close()
            except Exception:
                pass
        if p is not None:
            try:
                p.terminate()
            except Exception:
                pass

        logger.info("Audio Capture Stopped")