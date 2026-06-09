# ==============================================================================
# Optimized Runtime Environment - Minimal and Ultra Fast Jenkins Pipeline Build
# ==============================================================================
FROM python:3.10-slim

WORKDIR /app

# 1. Install all system dependencies required for audio, cloning, and compilation
RUN apt-get update && apt-get install -y \
    git \
    ffmpeg \
    espeak-ng \
    libsndfile1 \
    build-essential \
    python3-dev \
    && rm -rf /var/lib/apt/lists/*

# 2. Non-sensitive Application Configurations (Baked into the image)
ENV LANGCHAIN_TRACING_V2=true \
    LANGCHAIN_PROJECT="bna-multi-agent" \
    AUDIO_SAMPLE_RATE=16000 \
    AUDIO_CHUNK_SIZE=512 \
    SILENCE_DURATION_SEC=1.2 \
    VAD_AGGRESSIVENESS=2 \
    WS_BUFFER_MAX_SIZE=5242880 \
    AUDIO_PROCESSING_TIMEOUT=30 \
    RESPONSE_STREAMING_TIMEOUT=60

# 3. Copy the Python dependencies list and install them safely
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 4. Clone NVIDIA Riva python-clients locally inside the container environment
RUN git clone https://github.com/nvidia-riva/python-clients.git python-clients

# REMOVED: Duplicate spaCy download commands (already handled inside requirements.txt)

# 5. Copy the RoBERTa intent classifier local model directory explicitly
COPY app/layer2/orchestrator/bna_intent_classifier/ /app/bna_intent_classifier/

# 6. Copy the entire remaining application source code
COPY . .

# 7. Pre-create application runtime write directories to prevent permission issues
RUN mkdir -p outputs knowledgebase/vector_cache chroma_db .uploads

# 8. Expose network port for the application API layer
EXPOSE 8000

# 9. Copy and configure the shell execution permissions for the entrypoint script
COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

# 10. Execute the initialization runner script
ENTRYPOINT ["/entrypoint.sh"]