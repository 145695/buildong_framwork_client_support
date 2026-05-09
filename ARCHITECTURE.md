# Voice Pipeline Architecture

## Overview
Complete end-to-end voice processing system that converts audio input through 5 distinct stages, providing detailed results and error handling at each step.

## Architecture Diagram

```
┌─────────────────┐
│   Audio Input   │  (WAV, MP3, etc.)
└─────────┬───────┘
          │
          ▼
┌─────────────────┐
│  Stage 1: STT │  NVIDIA Riva gRPC (Whisper Large V3)
│  Transcription   │  ┌─────────────────────────────────┐
│                 │  │ • Language Detection         │
│ • Speech→Text  │  │ • Multi-language Support     │
│ • Confidence    │  │ • NVIDIA Cloud API          │
└─────────┬───────┘  └─────────────────────────────────┘
          │
          ▼
┌─────────────────┐
│  Stage 2: NLP  │  Translation Gate (Conditional)
│  Processing     │  ┌─────────────────────────────────┐
│                 │  │ • Nemotron Translation       │
│ • Translation   │  │ • Only if non-English       │
│ • Sanitization  │  │ • Language Detection         │
└─────────┬───────┘  └─────────────────────────────────┘
          │
          ▼
┌─────────────────┐
│  Stage 3: Layer 1│  Ingestion & Preprocessing
│  Ingestion       │  ┌─────────────────────────────────┐
│                 │  │ • PII Masking             │
│ • PII Masking  │  │ • Text Normalization        │
│ • Normalization │  │ • State Management         │
└─────────┬───────┘  └─────────────────────────────────┘
          │
          ▼
┌─────────────────┐
│  Stage 4: Layer 2│  Orchestrator & Intent Detection
│  Orchestrator    │  ┌─────────────────────────────────┐
│                 │  │ • Intent Classification      │
│ • Intent Detect │  │ • Agent Routing             │
│ • Agent Routing │  │ • Mission Brief Generation   │
└─────────┬───────┘  └─────────────────────────────────┘
          │
          ▼
┌─────────────────┐
│  Stage 5: Knowledge │  Intelligent RAG System
│  Base Query        │  ┌─────────────────────────────────┐
│                    │  │ • Document Retrieval        │
│ • Vector Search     │  │ • LLM-based Filtering      │
│ • Answer Generation │  │ • Source Attribution        │
│ • Confidence Scoring│  │ • Fallback Handling        │
└─────────┬──────────┘  └─────────────────────────────────┘
          │
          ▼
┌─────────────────┐
│  Final Results   │  Comprehensive JSON Response
│                 │  ┌─────────────────────────────────┐
│ • All Stages     │  │ • Success/Failure Status    │
│ • Error Details  │  │ • Intermediate Results      │
│ • Metadata       │  │ • Debug Information        │
└─────────────────┘  └─────────────────────────────────┘
```

## Component Details

### Stage 1: Speech-to-Text (STT)
- **Technology**: NVIDIA Riva gRPC with Whisper Large V3
- **Features**: 
  - Multi-language support (auto-detection)
  - High accuracy transcription
  - Cloud-based processing
- **Input**: Audio files (WAV, MP3, etc.)
- **Output**: Text transcription + detected language

### Stage 2: Natural Language Processing (NLP)
- **Technology**: Nemotron Translation Model
- **Features**:
  - Conditional translation (only if non-English)
  - Text sanitization
  - Language preservation
- **Input**: Transcribed text
- **Output**: English text (original preserved if English)

### Stage 3: Layer 1 Ingestion
- **Technology**: Custom ingestion pipeline
- **Features**:
  - PII (Personally Identifiable Information) masking
  - Text normalization
  - Conversation state management
- **Input**: Processed text
- **Output**: Normalized text with metadata

### Stage 4: Layer 2 Orchestrator
- **Technology**: Llama-based intent detection
- **Features**:
  - Intent classification
  - Agent routing logic
  - Mission brief generation
  - Confidence scoring
- **Input**: Normalized text
- **Output**: Intent + required agents + response

### Stage 5: Knowledge Base (RAG)
- **Technology**: ChromaDB + FAISS + Mistral LLM
- **Features**:
  - Vector-based document retrieval
  - LLM-powered answer generation
  - Source attribution
  - Confidence scoring
  - Fallback handling
- **Input**: Original question
- **Output**: Answer + sources + metadata

## Data Flow

```
Audio File → STT → Translation Gate → Ingestion → Orchestrator → Knowledge Base → Results
     ↓           ↓              ↓           ↓            ↓              ↓
  Transcription  English Text  Clean Text  Intent + Agents  Answer + Sources
```

## Error Handling & Resilience

### Multi-Level Fallbacks
1. **STT Fallback**: Local Whisper if NVIDIA API fails
2. **Translation Fallback**: Original text if Nemotron fails
3. **Ingestion Fallback**: Basic processing if PII fails
4. **Orchestrator Fallback**: Default routing if intent fails
5. **Knowledge Base Fallback**: Simple response if LLM fails

### Comprehensive Logging
- Stage-by-stage success/failure tracking
- Detailed error messages
- Processing time metrics
- Debug information
- Performance monitoring

## API Endpoints

### `/test/voice-full-pipeline` (POST)
- **Purpose**: Complete pipeline processing
- **Input**: Audio file upload
- **Output**: JSON with all stage results
- **Features**: Real-time processing, error handling

### `/voice-full-pipeline-ui` (GET)
- **Purpose**: Web interface for testing
- **Features**: 
  - Drag-and-drop audio upload
  - Real-time progress tracking
  - Detailed results display
  - Error visualization

## Technology Stack

### Core Technologies
- **Backend**: FastAPI (Python)
- **Frontend**: HTML5 + JavaScript
- **Speech Processing**: NVIDIA Riva gRPC
- **Translation**: NVIDIA Nemotron
- **Vector Database**: ChromaDB + FAISS
- **LLM**: Mistral (with fallbacks)
- **Embeddings**: Sentence Transformers

### Dependencies
- **NumPy**: 1.26.4 (downgraded for compatibility)
- **ChromaDB**: Vector storage
- **FAISS**: Vector similarity search
- **Requests**: HTTP client
- **Uvicorn**: ASGI server

## Key Features

### Real-time Processing
- Streaming audio processing
- Progressive result updates
- WebSocket support (future)

### Multi-language Support
- Automatic language detection
- Translation pipeline
- Language-specific handling

### Scalability
- Modular architecture
- Component isolation
- Easy extensibility

### Monitoring & Debugging
- Comprehensive logging
- Stage-by-stage metrics
- Error tracking
- Performance monitoring

## Future Enhancements

1. **Streaming Support**: Real-time audio processing
2. **Multiple LLMs**: Configurable LLM backends
3. **Caching**: Response caching for common queries
4. **Analytics**: Usage statistics and patterns
5. **API Rate Limiting**: Prevent abuse
6. **Authentication**: Secure endpoint access
