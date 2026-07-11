FROM python:3.13-slim

WORKDIR /app

COPY requirements.txt .

RUN apt-get update -y && apt-get upgrade -y \
    && apt-get install -y --no-install-recommends ffmpeg curl unzip ca-certificates gnupg \
    && rm -rf /var/lib/apt/lists/*

# Install Node.js (required by yt-dlp >=2026 to solve YouTube's n-signature challenge)
RUN curl -fsSL https://deb.nodesource.com/setup_20.x | bash - \
    && apt-get install -y --no-install-recommends nodejs \
    && rm -rf /var/lib/apt/lists/* \
    && node --version

RUN pip3 install --no-cache-dir -U pip && pip3 install --no-cache-dir -U -r requirements.txt

COPY . .

CMD ["bash", "start"]
