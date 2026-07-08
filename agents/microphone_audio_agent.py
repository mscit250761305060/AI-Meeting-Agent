import pyaudiowpatch as pyaudio


def get_microphone_device():

    p = pyaudio.PyAudio()

    host_api = p.get_default_host_api_info()

    default_input = host_api["defaultInputDevice"]

    info = p.get_device_info_by_index(default_input)

    return info