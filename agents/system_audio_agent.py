import logging
import wave

try:
    import pyaudiowpatch as pyaudio
except ImportError:
    try:
        import pyaudio
    except ImportError:
        pyaudio = None

from meeting_engine.system_audio_worker import push_system_audio

logger = logging.getLogger(__name__)


def record_system_audio(seconds=5):
    if pyaudio is None:
        logger.warning("pyaudio/pyaudiowpatch is not installed; system audio capture unavailable.")
        return

    p = None
    stream = None
    frames = []

    try:
        p = pyaudio.PyAudio()
        device = get_loopback_device()

        if not device:
            logger.warning("No loopback device detected")
            return

        stream = p.open(
            format=pyaudio.paInt16,
            channels=2,
            rate=int(device["defaultSampleRate"]),
            input=True,
            input_device_index=device["index"],
            frames_per_buffer=1024,
        )

        logger.info("Recording...")

        for _ in range(int(device["defaultSampleRate"] / 1024 * seconds)):
            try:
                data = stream.read(1024)
                if data:
                    frames.append(data)
                    push_system_audio(data)
            except (AttributeError, IOError, OSError, ValueError) as exc:
                logger.warning("System audio capture interrupted: %s", exc)
                break
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

        if frames:
            wf = wave.open("meeting_audio.wav", "wb")
            wf.setnchannels(2)
            wf.setsampwidth(p.get_sample_size(pyaudio.paInt16) if p is not None else 2)
            wf.setframerate(int(device["defaultSampleRate"]) if device else 16000)
            wf.writeframes(b"".join(frames))
            wf.close()
            logger.info("Saved meeting_audio.wav")


def get_loopback_device():
    if pyaudio is None:
        return None
    p = pyaudio.PyAudio()

    try:
        # First priority: direct WASAPI loopback device from pyaudiowpatch
        if hasattr(p, "get_default_wasapi_loopback"):
            try:
                loopback = p.get_default_wasapi_loopback()
                if loopback:
                    return loopback
            except Exception:
                pass

        # Second priority: match default output device name
        try:
            default = p.get_default_output_device_info()
            if hasattr(p, "get_loopback_device_info_generator"):
                for device in p.get_loopback_device_info_generator():
                    if default["name"] in device["name"]:
                        return device
        except Exception:
            pass

        # Third priority: first available loopback device
        if hasattr(p, "get_loopback_device_info_generator"):
            for device in p.get_loopback_device_info_generator():
                return device
    except Exception as exc:
        logger.warning("Unable to detect loopback device: %s", exc)
    finally:
        try:
            p.terminate()
        except Exception:
            pass

    return None

def get_microphone_device():
    if pyaudio is None:
        return None
    p = pyaudio.PyAudio()

    try:
        device = p.get_default_input_device_info()
        return device
    except Exception as exc:
        logger.warning("No microphone detected: %s", exc)
        return None
    finally:
        try:
            p.terminate()
        except Exception:
            pass