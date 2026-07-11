FROM python:3.13-slim

WORKDIR /app

COPY requirements.txt .

RUN apt-get update -y && apt-get upgrade -y \
    && apt-get install -y --no-install-recommends ffmpeg curl unzip ca-certificates gnupg \
    && rm -rf /var/lib/apt/lists/*

# Install Node.js >=23.5 (required by yt-dlp 2026.x to solve YouTube's n-signature challenge; Node <23.5 is rejected as "unsupported")
RUN curl -fsSL https://deb.nodesource.com/setup_24.x | bash - \
    && apt-get install -y --no-install-recommends nodejs \
    && rm -rf /var/lib/apt/lists/* \
    && node --version

RUN pip3 install --no-cache-dir -U pip && pip3 install --no-cache-dir -U -r requirements.txt

COPY . .

CMD ["bash", "start"]
