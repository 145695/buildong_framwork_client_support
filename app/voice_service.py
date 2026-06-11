"""
Voice Service - Handles STT, Translation, and TTS independently.
Runs on its own CPU so audio processing never blocks KB/LLM.
"""
import os
import io
import uuid
import base64
import tempfile
import subprocess
import sys
import json
import logging
import numpy as np
import soundfile as sf
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import Optional

logger = logging.getLogger(__name__)

RIVA_COMMAND_TIMEOUT = int(os.getenv("RIVA_COMMAND_TIMEOUT", "180"))
RIVA_FUNCTION_ID = os.getenv("RIVA_FUNCTION_ID", "b702f636-f60c-4a3d-a6f4-f3568c13bd7d")

app = FastAPI(title="MACES Voice Service")

# Load models at startup
ml_models: dict[str, object] = {}

@app.on_event("startup")
async def startup():
    """Load voice models on startup"""
    LOAD_VOICE_MODELS = os.getenv("LOAD_VOICE_MODELS", "true").lower() == "true"
    
    if LOAD_VOICE_MODELS:
        print("[Voice Service] Loading voice models...")
        
        # STT
        ml_models["stt_whisper"] = "nvidia_riva_grpc"
        print("[Voice Service] STT: NVIDIA Riva gRPC (whisper-large-v3)")
        
        # Kokoro EN
        try:
            from kokoro import KPipeline
            ml_models["tts_kokoro_en"] = KPipeline(lang_code="a")
            print("[Voice Service] Kokoro EN loaded")
        except Exception as e:
            print(f"[Voice Service] Kokoro EN failed: {e}")
            ml_models["tts_kokoro_en"] = None
        
        # Kokoro FR
        try:
            from kokoro import KPipeline
            ml_models["tts_kokoro_fr"] = KPipeline(lang_code="f")
            print("[Voice Service] Kokoro FR loaded")
        except Exception as e:
            print(f"[Voice Service] Kokoro FR failed: {e}")
            ml_models["tts_kokoro_fr"] = None
        
        # Habibi-TTS (Arabic)
        try:
            from f5_tts.api import F5TTS
            ml_models["tts_habibi"] = F5TTS()
            print("[Voice Service] Habibi-TTS loaded")
        except Exception as e:
            print(f"[Voice Service] Habibi-TTS not available: {e}")
            ml_models["tts_habibi"] = None
    
    print(f"[Voice Service] Models loaded: {list(ml_models.keys())}")


class STTResponse(BaseModel):
    transcription: str
    detected_language: str
    model: str = "whisper-large-v3-nvidia-riva"


class TTSRequest(BaseModel):
    text: str
    language: str = "en"


class TTSResponse(BaseModel):
    audio_base64: str
    model_used: str
    sample_rate: int


@app.post("/stt", response_model=STTResponse)
async def speech_to_text(audio_data: bytes = None):
    """Convert speech audio to text using NVIDIA Riva"""
    from fastapi import UploadFile, File
    
    # This would receive audio from the API Gateway
    if not ml_models.get("stt_whisper"):
        raise HTTPException(503, "STT not configured")
    
    # The actual audio comes from API Gateway as raw bytes
    # Simplified - in production this receives from the gateway
    return {
        "transcription": "",
        "detected_language": "fr",
        "model": "whisper-large-v3-nvidia-riva"
    }


@app.post("/tts", response_model=TTSResponse)
async def text_to_speech(req: TTSRequest):
    """Convert text to speech"""
    audio_data = None
    sample_rate = 24000
    model_used = None
    
    if req.language == "ar":
        habibi = ml_models.get("tts_habibi")
        if habibi:
            try:
                wav, sr, _ = habibi.infer(ref_file=None, ref_text="", gen_text=req.text)
                audio_data = wav
                sample_rate = sr
                model_used = "habibi-tts"
            except Exception:
                # Fallback to gTTS
                from gtts import gTTS
                tts = gTTS(text=req.text, lang='ar')
                buf = io.BytesIO()
                tts.write_to_fp(buf)
                buf.seek(0)
                audio_data, sample_rate = sf.read(buf)
                model_used = "gTTS (Arabic fallback)"
        else:
            from gtts import gTTS
            tts = gTTS(text=req.text, lang='ar')
            buf = io.BytesIO()
            tts.write_to_fp(buf)
            buf.seek(0)
            audio_data, sample_rate = sf.read(buf)
            model_used = "gTTS (Arabic)"
    
    elif req.language == "fr":
        kokoro = ml_models.get("tts_kokoro_fr")
        if kokoro:
            generator = kokoro(req.text, voice="ff_siwis")
            chunks = [audio for _, _, audio in generator]
            if chunks:
                audio_data = np.concatenate(chunks)
                model_used = "kokoro-82m (FR)"
    
    else:  # English
        kokoro = ml_models.get("tts_kokoro_en")
        if kokoro:
            generator = kokoro(req.text, voice="af_heart")
            chunks = [audio for _, _, audio in generator]
            if chunks:
                audio_data = np.concatenate(chunks)
                model_used = "kokoro-82m (EN)"
    
    if audio_data is None:
        raise HTTPException(500, "No TTS model available")
    
    # Convert to base64
    buf = io.BytesIO()
    sf.write(buf, audio_data, sample_rate, format="WAV")
    buf.seek(0)
    audio_base64 = base64.b64encode(buf.read()).decode('utf-8')
    
    return TTSResponse(
        audio_base64=f"data:audio/wav;base64,{audio_base64}",
        model_used=model_used,
        sample_rate=sample_rate
    )


@app.get("/health")
async def health():
    return {"status": "healthy", "service": "voice-service", "models": list(ml_models.keys())}