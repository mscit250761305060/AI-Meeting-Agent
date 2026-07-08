from agents.system_audio_agent import (
    get_loopback_device
)

device = get_loopback_device()

print(device)