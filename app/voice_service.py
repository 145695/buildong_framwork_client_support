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
from fastapi import FastAPI, HTTPException, UploadFile, File
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


def validate_language(detected_language: str) -> str:
    """Validate and normalize detected language"""
    SUPPORTED = ["ar", "fr", "en"]
    if detected_language in SUPPORTED:
        return detected_language
    return "ar"  # Default to Arabic


class STTResponse(BaseModel):
    transcription: str
    detected_language: str
    model: str = "whisper-large-v3-nvidia-riva"


class TranslateRequest(BaseModel):
    text: str
    source_language: str
    target_language: str = "en"


class TranslateResponse(BaseModel):
    translated_text: str
    safety_label: str = "safe"


class TTSRequest(BaseModel):
    text: str
    language: str = "en"


class TTSResponse(BaseModel):
    audio_base64: str
    model_used: str
    sample_rate: int
    success: bool = True


@app.post("/stt")
async def speech_to_text(audio: UploadFile = File(...)):
    """Convert speech to text using NVIDIA Riva"""
    if not ml_models.get("stt_whisper"):
        raise HTTPException(503, "STT not configured")
    
    api_key = os.getenv("NVIDIA_API_KEY")
    if not api_key:
        raise HTTPException(500, "NVIDIA_API_KEY missing")
    
    audio_bytes = await audio.read()
    temp_filename = os.path.join(tempfile.gettempdir(), f"stt_{uuid.uuid4().hex}.wav")
    
    try:
        # Write audio to temp file
        buffer = io.BytesIO(audio_bytes)
        audio_array, sample_rate = sf.read(buffer)
        if sample_rate != 16000:
            import librosa
            audio_array = librosa.resample(audio_array, orig_sr=sample_rate, target_sr=16000)
        sf.write(temp_filename, audio_array, 16000, format="WAV")
        
        # Clone Riva clients if needed
        project_root = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
        riva_clients_dir = os.path.join(project_root, "python-clients")
        if not os.path.exists(riva_clients_dir):
            subprocess.run(
                ["git", "clone", "https://github.com/nvidia-riva/python-clients.git", riva_clients_dir],
                check=True, capture_output=True
            )
        
        transcribe_script = os.path.join(riva_clients_dir, "scripts", "asr", "transcribe_file_offline.py")
        
        cmd = [
            sys.executable, transcribe_script,
            "--server", "grpc.nvcf.nvidia.com:443",
            "--use-ssl",
            "--metadata", "function-id", RIVA_FUNCTION_ID,
            "--metadata", "authorization", f"Bearer {api_key}",
            "--language-code", "multi",
            "--input-file", temp_filename
        ]
        
        env = os.environ.copy()
        env['PYTHONHASHSEED'] = 'random'
        env['PYTHONIOENCODING'] = 'utf-8'
        
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=RIVA_COMMAND_TIMEOUT, env=env, encoding='utf-8', errors='replace')
        
        output = result.stdout.strip()
        transcription = output
        detected_language = "unknown"
        
        # Try to parse JSON
        json_start = output.find('{')
        json_end = output.rfind('}') + 1
        if json_start != -1 and json_end > json_start:
            try:
                json_output = json.loads(output[json_start:json_end])
                if json_output and 'results' in json_output:
                    result_data = json_output['results'][0]
                    alternatives = result_data['alternatives'][0]
                    transcription = alternatives.get('transcript', output)
                    language_codes = alternatives.get('languageCode', [])
                    detected_language = language_codes[0] if language_codes else 'unknown'
            except json.JSONDecodeError:
                pass
        elif "Final transcript:" in output:
            transcription = output.split("Final transcript:")[-1].strip()
        
        detected_language = validate_language(detected_language)
        print(f"[Voice] STT: '{transcription[:50]}...' [{detected_language}]")
        
        return STTResponse(
            transcription=transcription,
            detected_language=detected_language
        )
    
    except subprocess.TimeoutExpired:
        raise HTTPException(504, "STT timed out")
    except Exception as e:
        raise HTTPException(500, f"STT failed: {str(e)}")
    finally:
        try:
            if os.path.exists(temp_filename):
                os.unlink(temp_filename)
        except:
            pass


@app.post("/translate")
async def translate_text(req: TranslateRequest):
    """Translate text using Nemotron"""
    try:
        from app.layer2.shared.model_loader import get_nemotron_model
        nemotron = get_nemotron_model()
        translated, safety = nemotron.translate_and_sanitize(
            req.text, req.source_language, req.target_language
        )
        print(f"[Voice] Translate: {req.source_language}→{req.target_language}: '{translated[:50]}...'")
        return TranslateResponse(translated_text=translated, safety_label=safety)
    except Exception as e:
        # Fallback: return original text
        print(f"[Voice] Translation failed, returning original: {e}")
        return TranslateResponse(translated_text=req.text, safety_label="safe")


@app.post("/tts")
async def text_to_speech(req: TTSRequest):
    """Convert text to speech"""
    audio_data = None
    sample_rate = 24000
    model_used = "unknown"
    
    try:
        if req.language == "ar":
            # Try Habibi-TTS first, fallback to gTTS
            habibi = ml_models.get("tts_habibi")
            if habibi:
                try:
                    wav, sr, _ = habibi.infer(ref_file=None, ref_text="", gen_text=req.text)
                    audio_data = wav
                    sample_rate = sr
                    model_used = "habibi-tts"
                except Exception as e:
                    print(f"[Voice] Habibi failed: {e}, trying gTTS")
                    habibi = None
            
            if audio_data is None:
                from gtts import gTTS
                tts = gTTS(text=req.text, lang='ar')
                buf = io.BytesIO()
                tts.write_to_fp(buf)
                buf.seek(0)
                audio_data, sample_rate = sf.read(buf)
                if len(audio_data.shape) > 1:
                    audio_data = audio_data[:, 0]
                model_used = "gTTS (Arabic)"
        
        elif req.language == "fr":
            kokoro = ml_models.get("tts_kokoro_fr")
            if kokoro:
                generator = kokoro(req.text, voice="ff_siwis")
                chunks = [audio for _, _, audio in generator]
                if chunks:
                    audio_data = np.concatenate(chunks)
                    model_used = "kokoro-82m (FR)"
            
            if audio_data is None:
                from gtts import gTTS
                tts = gTTS(text=req.text, lang='fr')
                buf = io.BytesIO()
                tts.write_to_fp(buf)
                buf.seek(0)
                audio_data, sample_rate = sf.read(buf)
                if len(audio_data.shape) > 1:
                    audio_data = audio_data[:, 0]
                model_used = "gTTS (French fallback)"
        
        else:  # English
            kokoro = ml_models.get("tts_kokoro_en")
            if kokoro:
                generator = kokoro(req.text, voice="af_heart")
                chunks = [audio for _, _, audio in generator]
                if chunks:
                    audio_data = np.concatenate(chunks)
                    model_used = "kokoro-82m (EN)"
            
            if audio_data is None:
                from gtts import gTTS
                tts = gTTS(text=req.text, lang='en')
                buf = io.BytesIO()
                tts.write_to_fp(buf)
                buf.seek(0)
                audio_data, sample_rate = sf.read(buf)
                if len(audio_data.shape) > 1:
                    audio_data = audio_data[:, 0]
                model_used = "gTTS (English fallback)"
        
        if audio_data is None:
            raise HTTPException(500, "No TTS model available")
        
        # Convert to base64
        buf = io.BytesIO()
        sf.write(buf, audio_data, sample_rate, format="WAV")
        buf.seek(0)
        audio_base64 = base64.b64encode(buf.read()).decode('utf-8')
        
        print(f"[Voice] TTS: {req.language} using {model_used}")
        
        return TTSResponse(
            audio_base64=f"data:audio/wav;base64,{audio_base64}",
            model_used=model_used,
            sample_rate=sample_rate,
            success=True
        )
    
    except HTTPException:
        raise
    except Exception as e:
        print(f"[Voice] TTS error: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(500, f"TTS failed: {str(e)}")


@app.get("/health")
async def health():
    return {"status": "healthy", "service": "voice-service", "models": list(ml_models.keys())}