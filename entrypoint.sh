#!/bin/bash
set -e

# Setup PulseAudio
mkdir -p ~/.config/pulse
echo "autospawn = no" > ~/.config/pulse/client.conf
echo "daemon-binary = /bin/true" >> ~/.config/pulse/client.conf

# Start PulseAudio in the background
pulseaudio -D --exit-idle-time=-1

# Load a null sink so Chromium has an audio output device
pacmd load-module module-null-sink sink_name=DummyOutput sink_properties=device.description="DummyOutput"
pacmd set-default-sink DummyOutput
pacmd set-default-source DummyOutput.monitor

# Start Xvfb (Virtual Framebuffer) in the background
export DISPLAY=:99
Xvfb :99 -screen 0 1280x720x24 -ac &

# Wait for Xvfb to be ready
sleep 2

echo "Container environment initialized. Starting backend..."
exec python run_backend.py
