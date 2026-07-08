import pyaudiowpatch as pyaudio

p = pyaudio.PyAudio()

print("\nINPUT DEVICES\n")

for i in range(p.get_device_count()):

    info = p.get_device_info_by_index(i)

    if info["maxInputChannels"] > 0:

        print(i, "-", info["name"])