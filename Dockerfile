# Docker image for the Firmix demo (deployed on Render free tier). Rules + compiler only; no LLM runs in the container.
FROM python:3.11-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
        gcc-arm-none-eabi libnewlib-arm-none-eabi cppcheck git ca-certificates \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt flask gunicorn

COPY include ./include
COPY src ./src
COPY tools/setup_deps.py ./tools/setup_deps.py
RUN python tools/setup_deps.py

COPY benchmark ./benchmark
COPY app ./app

ENV PORT=7860
EXPOSE 7860
# Render injects $PORT; 7860 is the local default. 1 worker + threads to fit the 512 MB free instance.
CMD gunicorn -b 0.0.0.0:${PORT:-7860} -w 1 --threads 4 --timeout 120 app.server:app
