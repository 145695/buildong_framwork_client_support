import os
from contextlib import asynccontextmanager
from dotenv import load_dotenv
import torch
from fastapi import FastAPI
from fastapi.responses import HTMLResponse, JSONResponse
from kokoro import KPipeline
from transformers import pipeline
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
import asyncio

load_dotenv()

DEVICE = "cuda" if torch.cuda.is_available() else "cpu"
WHISPER_MODEL = os.getenv("WHISPER_MODEL", "openai/whisper-tiny")
LOAD_VOICE_MODELS = os.getenv("LOAD_VOICE_MODELS", "true").lower() == "true"

ml_models: dict[str, object] = {}


@asynccontextmanager
async def lifespan(_: FastAPI):
    print(f"Using device: {DEVICE}")
    print("Preparing runtime...")

    # Load intent model at startup
    try:
        from app.layer2.shared.model_loader import load_model_at_startup
        load_model_at_startup()
    except Exception as exc:
        print(f"Intent model loading failed: {exc}")

    # Load Nemotron translation model at startup
    try:
        from app.layer2.shared.model_loader import load_nemotron_at_startup
        load_nemotron_at_startup()
    except Exception as exc:
        print(f"Nemotron model loading failed: {exc}")

    print(f"LOAD_VOICE_MODELS = {LOAD_VOICE_MODELS}")

    if LOAD_VOICE_MODELS:
        print("Loading voice models...")

        # Layer 1: STT (NVIDIA Riva gRPC - whisper-large-v3)
        ml_models["stt_whisper"] = "nvidia_riva_grpc"
        print("STT configured: NVIDIA Riva gRPC (whisper-large-v3)")

        try:
            print("Loading Kokoro EN...")
            ml_models["tts_kokoro_en"] = KPipeline(lang_code="a")
            print("Kokoro EN loaded successfully")
        except Exception as exc:
            print(f"Kokoro EN loading failed: {exc}")
            ml_models["tts_kokoro_en"] = None

        try:
            print("Loading Kokoro FR...")
            ml_models["tts_kokoro_fr"] = KPipeline(lang_code="f")
            print("Kokoro FR loaded successfully")
        except Exception as exc:
            print(f"Kokoro FR loading failed: {exc}")
            ml_models["tts_kokoro_fr"] = None

        if ml_models.get("tts_kokoro_en") or ml_models.get("tts_kokoro_fr"):
            print("Layer 3: Kokoro loaded (EN + FR)")

        # FIX 2: Removed runtime pip install — f5-tts must be pre-installed via requirements.txt
        try:
            from f5_tts.api import F5TTS
            print("Loading Habibi-TTS...")
            ml_models["tts_habibi"] = F5TTS()
            print("Layer 3: Habibi-TTS loaded (ALG)")
        except Exception as exc:
            ml_models["tts_habibi"] = None
            print(f"Layer 3: Habibi-TTS not available: {exc}")
            print("Arabic TTS will use gTTS as fallback")

    else:
        ml_models["stt_whisper"] = None
        ml_models["tts_kokoro_en"] = None
        ml_models["tts_kokoro_fr"] = None
        ml_models["tts_habibi"] = None
        print("Voice models skipped (set LOAD_VOICE_MODELS=true to enable).")

    # Pre-load Knowledge Base at startup
    print("Pre-loading Knowledge Base...")
    try:
        from app.layer2.knowledgebase.intelligent_rag_system import IntelligentRAGSystem
        kb = IntelligentRAGSystem()
        if asyncio.iscoroutinefunction(kb.load_documents):
            await kb.load_documents()
        else:
            kb.load_documents()
        ml_models["kb_system"] = kb
        print(f"KB ready: {len(kb.documents)} docs cached")
    except Exception as exc:
        print(f"KB pre-load failed: {exc}")
        ml_models["kb_system"] = None

    print(f"Final ml_models keys: {list(ml_models.keys())}")
    yield
    print("Shutting down...")
    ml_models.clear()


app = FastAPI(title="AI Client Support System", lifespan=lifespan)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

from app.routers.chat import router as chat_router
from app.routers.voice import router as voice_router
from app.routers.session import router as session_router
from app.routers.ws_audio import router as ws_audio_router

app.include_router(chat_router)
app.include_router(voice_router)
app.include_router(session_router)
app.include_router(ws_audio_router)

# Serve static files from the app/static directory
app.mount("/static", StaticFiles(directory="app/static"), name="static")

# Serve voice‑lab landing page
@app.get("/", response_class=HTMLResponse)
async def voice_lab_page():
    """Serve landing page with Start Call button that redirects to full pipeline mic interface."""
    html_path = os.path.join(os.path.dirname(__file__), "templates", "index.html")
    with open(html_path, "r", encoding="utf-8") as f:
        html_content = f.read()
    return HTMLResponse(content=html_content)

@app.get("/call", summary="Complete Voice Pipeline Laboratory")
async def voice_lab_complete():
    """Complete voice pipeline testing interface with final voice output"""
    html_path = os.path.join(os.path.dirname(__file__), "templates", "voice_lab_complete.html")
    if not os.path.exists(html_path):
        return JSONResponse(
            status_code=404,
            content={"error": "voice_lab_complete.html not found. Please ensure the file exists in the project root."}
        )
    with open(html_path, "r", encoding="utf-8") as f:
        html_content = f.read()
    return HTMLResponse(content=html_content)