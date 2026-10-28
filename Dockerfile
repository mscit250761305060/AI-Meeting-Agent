FROM python:3.11-slim

# Install system dependencies for audio capture, headless chromium, and Xvfb
RUN apt-get update && apt-get install -y \
    xvfb \
    pulseaudio \
    ffmpeg \
    wget \
    gnupg \
    procps \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install Playwright dependencies
RUN npx -y playwright@1.44.0 install-deps

# Create app directory
WORKDIR /app

# Copy requirements and install
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Install Playwright browsers
RUN playwright install chromium

# Copy application source
COPY . .

# Set up entrypoint
RUN chmod +x /app/entrypoint.sh
ENTRYPOINT ["/app/entrypoint.sh"]
