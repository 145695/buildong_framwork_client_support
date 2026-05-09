# BNA Multi-Agent Voice Pipeline - Project Structure

## 📁 Root Directory
```
buildong_framwork_client_support/
├── .env                          # Environment variables (API keys, settings)
├── .env.example                   # Template for environment variables
├── .git/                          # Git repository
├── .gitignore                      # Git ignore patterns
├── .idea/                          # IDE configuration
├── README.md                        # Project documentation
├── main.py                         # Application entry point
├── requirements.txt                  # Python dependencies
├──
├── 📁 app/                         # Main application code
│   ├── main.py                     # FastAPI application & routes
│   ├── __init__.py
│   ├──
│   ├── 📁 layer1/                   # Input processing layer
│   │   └── ingestion.py             # Audio ingestion & STT
│   ├──
│   ├── 📁 layer2/                   # Agent orchestration layer
│   │   ├── graph.py                 # LangGraph orchestration flow
│   │   ├── 📁 agents/              # Individual agents
│   │   │   ├── knowledge_base.py    # Knowledge base RAG agent
│   │   │   ├── loan.py             # Loan evaluation agent
│   │   │   ├── client_support.py   # Client support agent
│   │   │   └── model_loader.py     # Model loading utilities
│   │   ├── 📁 orchestrator/         # Intent routing
│   │   │   ├── orchestrator.py       # Main orchestrator logic
│   │   │   ├── capability_registry.py # Agent capability mapping
│   │   │   └── intent_classifier.py  # Intent classification
│   │   └── 📁 knowledgebase/       # Knowledge base infrastructure
│   │       ├── rag_agent.py          # RAG implementation
│   │       ├── llm.py               # LLM interface
│   │       ├── embeddings.py         # Embedding generation
│   │       ├── pdf_parser.py         # PDF processing
│   │       └── vector_store.py       # Vector storage
│   ├──
│   ├── 📁 layer3/                   # Output processing layer
│   │   └── tts.py                 # Text-to-speech synthesis
│   ├──
│   ├── 📁 routers/                  # API route handlers
│   │   └── voice.py               # Voice pipeline endpoints
│   ├──
│   ├── 📁 schemas/                   # Data models
│   │   └── conversation.py        # Conversation state model
│   ├──
│   ├── 📁 security_layer1/           # Security layer 1
│   └── 📁 security_layer2/           # Security layer 2
│
├── 📁 assets/                       # Static assets
├── 📁 policies/                     # Policy documents (PDF)
├── 📁 policies_text/                # Policy documents (text)
├── 📁 outputs/                      # Generated outputs
├── 📁 python-clients/               # Python client examples
├── 📁 chroma_db/                   # Vector database storage
├── 📁 __pycache__/                  # Python cache
│
├── 📄 policy_registry.json            # Policy metadata
├── 📄 AI_MODULES.md                  # AI modules documentation
├── 📄 ARCHITECTURE.md               # System architecture
├── 📄 CLOUD_RAG_IMPLEMENTATION_GUIDE.md # RAG implementation guide
├── 📄 VOICE_INTEGRATION_REPORT.md     # Voice integration report
│
└── 🧪 Test Files                    # Various test scripts
    ├── test_full_pipeline.py
    ├── test_full_pipeline_questions.py
    ├── test_layer3_tts.py
    ├── test_pipeline_final.py
    ├── test_simple.py
    ├── test_translation.py
    ├── test_translation_new.py
    └── test_tts_web.html
```

## 🏗️ Architecture Overview

### **Layer 1 - Input Processing**
- **Audio Ingestion**: STT using Whisper models
- **Speech Processing**: Noise reduction, format conversion

### **Layer 2 - Agent Orchestration**
- **Orchestrator**: Intent analysis & agent selection
- **Knowledge Base**: RAG with vector search
- **Loan Agent**: Loan evaluation logic
- **Client Support**: Final response synthesis
- **LangGraph**: Agent flow orchestration

### **Layer 3 - Output Processing**
- **TTS**: Text-to-speech synthesis
- **Audio Output**: Voice response generation

## 🔧 Key Components

### **Voice Pipeline Flow**
1. **STT** → Audio → Text transcription
2. **Translation** → Non-English → English
3. **Orchestrator** → Intent analysis & routing
4. **Knowledge Base** → Policy information retrieval
5. **Client Support** → Final response synthesis
6. **TTS** → Text → Audio response

### **API Endpoints**
- **`/voice-lab`** - Modern voice pipeline UI
- **`/test/voice-full-pipeline`** - Pipeline API endpoint
- **`/voice-full-pipeline-ui`** - Removed (replaced by voice-lab)

### **Configuration**
- **Environment**: .env file with API keys
- **Dependencies**: requirements.txt
- **Database**: ChromaDB for vector storage
- **Policies**: PDF documents + text extraction

## 🚀 Deployment Ready

The project is structured for:
- **Development**: Modular layers for easy debugging
- **Testing**: Comprehensive test suite
- **Production**: Environment-based configuration
- **Scalability**: Agent-based architecture
