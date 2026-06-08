#!/bin/bash
set -e

echo "Starting BNA Client Support System..."

# Check for required API keys
REQUIRED_KEYS=(
    "NVIDIA_API_KEY"
    "NVIDIA_NEMOTRON_API_KEY"
    "NVIDIA_API_KEY_LLAMA"
    "NVIDIA_API_KEY_MISTRAL"
    "MISTRAL_API_KEY"
    "GROQ_API_KEY"
    "HUGGINGFACE_API_TOKEN"
)

MISSING_KEYS=()
for key in "${REQUIRED_KEYS[@]}"; do
    if [ -z "${!key}" ]; then
        MISSING_KEYS+=("$key")
    fi
done

if [ ${#MISSING_KEYS[@]} -ne 0 ]; then
    echo "ERROR: Missing required environment variables:"
    for key in "${MISSING_KEYS[@]}"; do
        echo "  - $key"
    done
    echo ""
    echo "Please set these environment variables in your .env file or docker-compose.yml"
    exit 1
fi

# Set INTENT_CLASSIFIER_PATH to point to the copied bna_intent_classifier folder
export INTENT_CLASSIFIER_PATH="/app/bna_intent_classifier"

echo "All required environment variables are set."
echo "Starting FastAPI server on port 8000..."

# Start the app
exec uvicorn app.main:app --host 0.0.0.0 --port 8000 --timeout-keep-alive 300
