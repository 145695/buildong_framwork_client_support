# AI Client Support System

A multi-layered voice-enabled AI system for BNA (Banque Nationale d'Algérie) customer support, featuring real-time speech recognition, multi-language translation, knowledge base retrieval, and text-to-speech capabilities.

## Architecture Overview

The system is organized into three main layers:

- **Layer 1**: Audio processing and speech-to-text (STT)
- **Layer 2**: Core intelligence (translation, routing, knowledge base, security)
- **Layer 3**: Text-to-speech (TTS) and response delivery

## Project Structure

```
buildong_framwork_client_support/
├── app/
│   ├── layer1/                 # Audio processing and STT
│   │   ├── audio_processor.py  # Audio buffering and VAD
│   │   ├── ingestion.py        # Audio ingestion
│   │   └── vad_engine.py       # Voice Activity Detection
│   ├── layer2/                 # Core intelligence
│   │   ├── agents/             # Specialized AI agents
│   │   ├── client_support/     # Client support agent
│   │   ├── graph.py             # LangGraph orchestration
│   │   ├── knowledgebase/       # RAG system for KB queries
│   │   ├── legacy/             # Legacy components
│   │   ├── loan/               # Loan-related agents
│   │   ├── orchestrator/        # Intent routing and agent selection
│   │   └── shared/             # Shared utilities and model loading
│   ├── layer3/                 # TTS and delivery
│   │   ├── delivery.py          # Response formatting
│   │   ├── translation/        # Translation services
│   │   └── tts/                # Text-to-speech engines
│   ├── routers/                # FastAPI route handlers
│   │   ├── chat.py             # Chat endpoint
│   │   ├── session.py          # Session management
│   │   ├── voice.py            # Voice pipeline endpoint
│   │   └── ws_audio.py          # WebSocket audio streaming
│   ├── schemas/                # Data schemas
│   ├── security_layer1/        # Input validation and security
│   ├── security_layer2/        # Output validation and PII redaction
│   ├── static/                 # Static files (HTML, CSS, icons)
│   ├── templates/              # HTML templates
│   └── main.py                 # FastAPI application entry point
├── policies_text/              # Knowledge base documents
├── python-clients/             # NVIDIA Riva clients for STT
├── script.js                   # Frontend JavaScript for voice interface
└── requirements.txt            # Python dependencies
```

## Layer 1: Audio Processing and STT

### Components

- **audio_processor.py**: Handles audio buffering with Voice Activity Detection (VAD) to detect speech segments
- **vad_engine.py**: WebRTC-based Voice Activity Detection for speech/silence classification
- **ingestion.py**: Audio ingestion and preprocessing

### STT Configuration

Uses NVIDIA Riva gRPC with Whisper Large v3 model for speech recognition. Supports multi-language detection (English, French, Arabic).

## Layer 2: Core Intelligence

### Components

#### Translation (layer2/shared/model_loader.py)
- **NemotronTranslationModel**: NVIDIA API-based translation with Google Translate fallback
- Supports French, Arabic, and English
- Automatic language detection and fallback handling

#### Orchestrator (layer2/orchestrator/)
- **router_node.py**: Intent classification and agent routing
- **registry.py**: Agent registry and selection logic
- Routes queries to appropriate agents based on intent (client_support, loan_agent, kb_agent)

#### Knowledge Base (layer2/knowledgebase/)
- **intelligent_rag_system.py**: RAG (Retrieval Augmented Generation) system
- Uses FAISS for vector search and sentence-transformers for embeddings
- Queries policy documents in `policies_text/` directory
- Supports incremental document loading and caching

#### Agents (layer2/agents/)
- Specialized agents for different query types:
  - Client support agent
  - Loan agent
  - Knowledge base agent

#### Security Layers
- **security_layer1/security_screening.py**: Input validation, prompt injection detection, off-topic filtering
- **security_layer2/output_validator.py**: PII redaction (emails, phone numbers, credit cards), NeMo Guardrails integration

#### Session Management (layer2/shared/session_manager.py)
- Session creation and management
- Conversation history tracking
- Follow-up mode support

## Layer 3: TTS and Delivery

### Components

#### TTS Engines (layer3/tts/)
- **Kokoro**: High-quality TTS for English and French
- **Habibi-TTS**: Arabic TTS (with gTTS fallback)
- **gTTS**: Google Translate TTS as fallback

#### Translation (layer3/translation/)
- **translator.py**: Translation service with Nemotron and Google Translate fallback

#### Delivery (layer3/delivery.py)
- Response formatting and localization
- Audio generation and delivery

## API Endpoints

### FastAPI Routes

- `GET /` - Landing page with Start Call button
- `GET /call` - Complete voice pipeline interface
- `POST /voice/full-pipeline` - Voice pipeline endpoint (audio input)
- `POST /chat` - Chat endpoint (text input)
- `POST /session/create` - Create new session
- `DELETE /session/{session_id}` - Delete session
- `WS /ws/audio/{session_id}` - WebSocket for real-time audio streaming

### WebSocket Audio Streaming

The WebSocket endpoint (`/ws/audio/{session_id}`) handles:
- Real-time audio streaming from client
- Audio buffering and VAD processing
- Pipeline execution (STT → Translation → Security → Routing → KB → TTS)
- Status updates and audio response delivery

## Eligibility Redirect Feature

When users say "yes" to an eligibility test question:
1. The system detects the response and triggers a redirect
2. The assistant delivers the eligibility message
3. After audio finishes, the frontend redirects to `/static/eligibility_redirect.html`

## Configuration

### Environment Variables

- `NVIDIA_API_KEY`: NVIDIA API key for Riva STT
- `NVIDIA_NEMOTRON_API_KEY`: Nemotron translation API key
- `LOAD_VOICE_MODELS`: Enable/disable voice model loading (default: true)
- `WHISPER_MODEL`: Whisper model selection

### Model Loading

Models are loaded at startup in `app/main.py`:
- STT: NVIDIA Riva gRPC (whisper-large-v3)
- TTS: Kokoro (EN/FR), Habibi-TTS (Arabic)
- Translation: Nemotron with Google Translate fallback

## Frontend

### Voice Interface

The voice interface is served at `/call` and includes:
- Real-time audio recording with VAD
- Visual feedback (orb animation, waveforms)
- WebSocket communication for audio streaming
- Audio playback for assistant responses
- Eligibility redirect support

### Static Files

Static files are served from `app/static/`:
- `eligibility_redirect.html` - Eligibility test redirect page
- `icons/` - UI icons and logos

## Knowledge Base

The knowledge base is stored in `policies_text/` directory containing:
- Banking policies and regulations
- Loan information
- Fee structures
- Account management procedures

Documents are indexed using FAISS for fast similarity search.

## Security

### Input Security (Layer 1)
- Prompt injection detection
- Off-topic filtering
- Banking context validation

### Output Security (Layer 2)
- PII redaction (emails, phone numbers, credit cards)
- NeMo Guardrails integration for content safety
- Context-aware PIN mention handling

## Dependencies

See `requirements.txt` for full list of dependencies including:
- FastAPI
- NVIDIA Riva clients
- Kokoro TTS
- F5-TTS (Habibi)
- sentence-transformers
- FAISS
- LangChain
- WebRTC VAD

## Running the Application

1. Install dependencies:
```bash
pip install -r requirements.txt
```

2. Configure environment variables in `.env`:
```
NVIDIA_API_KEY=your_api_key
NVIDIA_NEMOTRON_API_KEY=your_nemotron_key
LOAD_VOICE_MODELS=true
```

3. Run the server:
```bash
python -m app.main
```

4. Access the voice interface:
- Landing page: `http://localhost:8000/`
- Voice interface: `http://localhost:8000/call`

## Multi-Language Support

The system supports:
- **English**: Full STT, translation, and TTS
- **French**: Full STT, translation, and TTS
- **Arabic**: Full STT, translation, and TTS (with fallbacks)

Language detection is automatic using the STT system.
