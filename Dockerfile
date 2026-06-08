# ============================================
# Stage 1: Builder - Download models and dependencies
# ============================================
FROM python:3.10-slim as builder

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    git \
    ffmpeg \
    espeak-ng \
    libsndfile1 \
    build-essential \
    python3-dev \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Clone NVIDIA Riva python-clients
RUN git clone https://github.com/nvidia-riva/python-clients.git python-clients

# Pre-download models during build
# 1. Kokoro TTS models (EN and FR)
RUN python -c "from kokoro import KPipeline; KPipeline(lang_code='a'); KPipeline(lang_code='f')"

# 2. SentenceTransformer model for embeddings
RUN python -c "from sentence_transformers import SentenceTransformer; SentenceTransformer('paraphrase-multilingual-MiniLM-L12-v2')"

# 3. Download spacy models (already in requirements, but ensure they're cached)
RUN python -m spacy download en_core_web_sm
RUN python -m spacy download en_core_web_lg

# 4. Download transformers cache for common models
RUN python -c "from transformers import AutoTokenizer; AutoTokenizer.from_pretrained('bert-base-uncased')"
RUN python -c "from transformers import AutoTokenizer; AutoTokenizer.from_pretrained('roberta-base')"

# ============================================
# Stage 2: Runtime - Minimal image with pre-downloaded models
# ============================================
FROM python:3.10-slim

WORKDIR /app

# Install only runtime system dependencies
RUN apt-get update && apt-get install -y \
    ffmpeg \
    espeak-ng \
    libsndfile1 \
    && rm -rf /var/lib/apt/lists/*

# Copy Python dependencies from builder
COPY --from=builder /usr/local/lib/python3.10/site-packages /usr/local/lib/python3.10/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin

# Copy NVIDIA Riva python-clients
COPY --from=builder /app/python-clients /app/python-clients

# Copy cached models from builder
COPY --from=builder /root/.cache/huggingface /root/.cache/huggingface
# Torch cache may not exist, skip if not present

# Copy the RoBERTa intent classifier local model
COPY app/layer2/orchestrator/bna_intent_classifier/ /app/bna_intent_classifier/

# Copy application code
COPY . .

# Create runtime write directories
RUN mkdir -p outputs knowledgebase/vector_cache chroma_db .uploads

# Expose port
EXPOSE 8000

# Copy entrypoint script
COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

# Set entrypoint
ENTRYPOINT ["/entrypoint.sh"]
