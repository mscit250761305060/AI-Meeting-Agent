from agents.system_audio_agent import get_microphone_device
import logging
import os
import tempfile
import time
import wave

import pyaudiowpatch as pyaudio

import server.meeting_state as meeting_state
from agents.system_audio_agent import get_loopback_device
from meeting_engine.audio_queue import audio_queue

logger = logging.getLogger(__name__)


def start_audio_capture():

    print("ENTERED AUDIO CAPTURE")
    print("meeting_running =", meeting_state.meeting_running)

    p = None
    stream = None

    logger.info("Audio Capture Started")

    try:
        p = pyaudio.PyAudio()
        from agents.system_audio_agent import (
            get_loopback_device,
            get_microphone_device,
        )

        # Temporary Testing Mode
        device = get_loopback_device()

        if not device:
            logger.warning("No loopback device detected; audio capture cannot start")
            return

        rate = int(device["defaultSampleRate"])
        chunk = 1024

        stream = p.open(
            format=pyaudio.paInt16,
            channels=2,
            rate=rate,
            input=True,
            input_device_index=device["index"],
            frames_per_buffer=chunk,
        )

        print("DEVICE NAME:", device["name"])
        print("RATE:", rate)

        print("STREAM OPENED")

        print("INSIDE CAPTURE LOOP")
        while meeting_state.meeting_running and not meeting_state.stop_event.is_set():
            print("START RECORDING 5 SECONDS")
            frames = []
            start = time.time()

            while (
                meeting_state.meeting_running
                and not meeting_state.stop_event.is_set()
                and time.time() - start < 5
            ):

                try:
                    data = stream.read(chunk, exception_on_overflow=False)

                    print("READ:", len(data))

                    if data:
                        frames.append(data)

                except Exception as exc:
                    logger.warning(exc)
                    break

            print("TOTAL FRAMES =", len(frames))

            if len(frames) == 0:
                print("NO AUDIO CAPTURED")
                continue

            print("CREATING WAV FILE")
            with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as temp:
                filename = temp.name

            try:
                wf = wave.open(filename, "wb")
                wf.setnchannels(2)
                wf.setsampwidth(p.get_sample_size(pyaudio.paInt16))
                wf.setframerate(rate)
                wf.writeframes(b"".join(frames))
                wf.close()

                logger.info("WAV Created: %s", filename)
                audio_queue.put(filename)
                print("QUEUE SENT")
                print("QUEUE PUSHED:", filename)
                logger.info("Added to Queue")
            except (OSError, ValueError, wave.Error) as exc:
                logger.exception("Failed to write audio chunk: %s", exc)
                try:
                    os.remove(filename)
                except FileNotFoundError:
                    pass

            if not meeting_state.meeting_running or meeting_state.stop_event.is_set():
                break

            time.sleep(0.1)

        print("RECORDING FINISHED")
        print("FRAME COUNT:", len(frames))

    except Exception as exc:
        logger.exception("Audio capture failed: %s", exc)
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