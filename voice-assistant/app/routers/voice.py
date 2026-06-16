import io
import os
import uuid
import base64
import tempfile
import subprocess
import sys
import json
import logging

import numpy as np

RIVA_COMMAND_TIMEOUT = int(os.getenv("RIVA_COMMAND_TIMEOUT", "180"))
RIVA_FUNCTION_ID = os.getenv("RIVA_FUNCTION_ID", "b702f636-f60c-4a3d-a6f4-f3568c13bd7d")
RIVA_FALLBACK_FUNCTION_ID = os.getenv("RIVA_FALLBACK_FUNCTION_ID")


logger = logging.getLogger(__name__)
try:
    from faster_whisper import WhisperModel
    WHISPER_AVAILABLE = True
except ImportError:
    WHISPER_AVAILABLE = False
    logger.warning("faster-whisper not installed. Local fallback unavailable.")
import soundfile as sf
from fastapi import APIRouter, File, HTTPException, UploadFile, Form
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from typing import Optional

router = APIRouter(prefix="/test", tags=["Layer Tests"])
LOAN_AGENT_URL = os.getenv("LOAN_AGENT_URL", "http://localhost:5000")

def validate_language(detected_language: str) -> str:
    """Validate and normalize detected language to supported languages"""
    SUPPORTED_LANGUAGES = ["ar", "fr", "en"]
    if detected_language == "unknown":
        return "unknown"
    if detected_language in SUPPORTED_LANGUAGES:
        return detected_language
    # Default to Arabic for unsupported languages
    # since BNA customers are primarily Algerian
    logger.warning(
        f"[Language] Unsupported language detected: '{detected_language}'. "
        f"Defaulting to Arabic."
    )
    return "ar"

def transcribe_with_local_whisper(audio_path: str) -> dict:
    """Fallback: Use local faster-whisper when Riva is down"""
    if not WHISPER_AVAILABLE:
        raise RuntimeError("Whisper not installed")
    
    model = WhisperModel("base", device="cpu", compute_type="int8")
    segments, info = model.transcribe(audio_path)
    transcription = " ".join([seg.text for seg in segments])
    
    return {
        "transcription": transcription.strip(),
        "detected_language": info.language if info else "unknown",
        "model": "whisper-local-fallback"
    }
@router.post("/stt", summary="Test Layer 1: Whisper STT (NVIDIA Riva gRPC)")
async def test_stt(audio: UploadFile = File(...)):
    from app.main import ml_models

    if not ml_models.get("stt_whisper"):
        raise HTTPException(503, "Whisper not configured")

    audio_bytes = await audio.read()

    api_key = os.getenv("NVIDIA_API_KEY")
    if not api_key:
        raise HTTPException(500, "NVIDIA_API_KEY environment variable is missing.")

    temp_filename = os.path.join(tempfile.gettempdir(), f"stt_temp_{hash(audio_bytes)}.wav")

    try:
        # Write audio bytes to temporary file
        buffer = io.BytesIO(audio_bytes)
        audio_array, sample_rate = sf.read(buffer)
        sf.write(temp_filename, audio_array, sample_rate, format="WAV")

        project_root = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
        riva_clients_dir = os.path.join(project_root, "python-clients")
        if not os.path.exists(riva_clients_dir):
            subprocess.run(["git", "clone", "https://github.com/nvidia-riva/python-clients.git", riva_clients_dir], check=True, capture_output=True)

        transcribe_script = os.path.join(riva_clients_dir, "scripts", "asr", "transcribe_file_offline.py")
        if not os.path.exists(transcribe_script):
            raise HTTPException(500, f"Riva client script not found at {transcribe_script}")

        cmd = [
            sys.executable,
            transcribe_script,
            "--server", "grpc.nvcf.nvidia.com:443",
            "--use-ssl",
            "--metadata", "function-id", "b702f636-f60c-4a3d-a6f4-f3568c13bd7d",
            "--metadata", "authorization", f"Bearer {api_key}",
            "--language-code", "multi",
            "--input-file", temp_filename
        ]

        env = os.environ.copy()
        env['PYTHONHASHSEED'] = 'random'
        env['PYTHONIOENCODING'] = 'utf-8'

        try:
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=RIVA_COMMAND_TIMEOUT, env=env, encoding='utf-8', errors='replace')
        except subprocess.TimeoutExpired as timeout_exc:
            # Log any partial output
            stdout = getattr(timeout_exc, 'stdout', '') or ''
            stderr = getattr(timeout_exc, 'stderr', '') or ''
            logger.error("Riva STT timeout after %ss. stdout: %s stderr: %s", RIVA_COMMAND_TIMEOUT, stdout[:200], stderr[:400])
            raise HTTPException(504, f"NVIDIA Riva STT command timed out after {RIVA_COMMAND_TIMEOUT} seconds") from timeout_exc

        if result.returncode != 0:
            logger.error("Riva client error: %s", result.stderr)
            raise HTTPException(500, f"Riva client failed: {result.stderr}")

        output = result.stdout.strip()
        # Extract JSON then transcript
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
                else:
                    transcription = output
                    detected_language = 'unknown'
            except json.JSONDecodeError:
                transcription = output
                detected_language = 'unknown'
        else:
            if 'Final transcript:' in output:
                transcription = output.split('Final transcript:')[-1].strip()
                detected_language = 'unknown'
            else:
                transcription = output
                detected_language = 'unknown'

        return {
            'layer': 1,
            'model': 'whisper-large-v3-nvidia-riva',
            'detected_language': detected_language,
            'transcription': transcription,
        }
    finally:
        try:
            if os.path.exists(temp_filename):
                os.unlink(temp_filename)
        except Exception:
            pass


@router.post("/voice-to-orchestrator", summary="Voice Input -> Layer 1 STT -> Translation Gate -> Layer 2 Orchestrator -> Output")
async def voice_to_orchestrator(audio: UploadFile = File(...)):
    """
    Simplified voice pipeline: reuse `test_stt` for transcription,
    then apply translation gate, ingestion, and orchestrator routing.
    """
    from app.main import ml_models
    from app.layer1.ingestion import ingest_chat_request
    from app.layer2.orchestrator import smart_pm_routing
    from app.schemas.conversation import ChatRequest, SourceChannel

    if not ml_models.get("stt_whisper"):
        raise HTTPException(503, "Whisper not configured")

    # Delegate transcription to test_stt to keep logic centralized
    stt_result = await test_stt(audio)
    transcription = stt_result.get("transcription")
    detected_language = stt_result.get("detected_language", "unknown")

    # Translation gate
    if detected_language != "en" and detected_language != "unknown":
        try:
            from app.layer2.shared.model_loader import get_nemotron_model
            nemotron = get_nemotron_model()
            translated_text, safety_label = nemotron.translate_and_sanitize(transcription, detected_language)
            if safety_label == "unsafe":
                raise HTTPException(400, "Query blocked by safety filter")
            text_for_ingestion = translated_text
            translation_applied = True
        except Exception:
            text_for_ingestion = transcription
            translation_applied = False
    else:
        text_for_ingestion = transcription
        translation_applied = False

    # Step 3: Pass transcription to Layer 1 ingestion
    try:
        chat_request = ChatRequest(
            message=text_for_ingestion,
            source_language=detected_language,
            source_channel=SourceChannel.VOICE,
            conversation_id=None
        )
        state = ingest_chat_request(chat_request)
    except Exception as e:
        raise HTTPException(500, f"Layer 1 ingestion failed: {str(e)}")

    # Step 4: Pass to Layer 2 Orchestrator
    try:
        result_state = smart_pm_routing(state)
    except Exception as e:
        raise HTTPException(500, f"Orchestrator processing failed: {str(e)}")

    return result_state

class TTSRequest(BaseModel):
    text: str
    language: str = "en"


@router.post("/tts", summary="Test Layer 3: TTS")
async def test_tts(req: TTSRequest):
    from app.main import ml_models

    audio_data = None
    sample_rate = 24000
    model_used = None

    # Fix encoding issue by ensuring proper UTF-8 handling
    try:
        # Debug the original text and encoding
        print(f"[TTS] Original text: {repr(req.text)}")
        print(f"[TTS] Text type: {type(req.text)}")
        
        # Ensure text is properly encoded for display
        display_text = req.text
        if isinstance(req.text, str):
            # Handle potential encoding issues
            try:
                display_text = req.text.encode('utf-8', errors='replace').decode('utf-8')
            except UnicodeEncodeError as e:
                print(f"[TTS] Encoding error: {e}")
                display_text = req.text  # Fallback to original
        
        print(f"[TTS] Request: text='{display_text}', language='{req.language}'")
        print(f"[TTS] Available models: {list(ml_models.keys())}")
    except Exception as e:
        print(f"[TTS] Text processing error: {e}")
        print(f"[TTS] Request: text='{req.text}', language='{req.language}'")
        print(f"[TTS] Available models: {list(ml_models.keys())}")

    if req.language == "ar":
        # Use Habibi-TTS as primary method for Arabic text
        habibi = ml_models.get("tts_habibi")
        if habibi is not None:
            try:
                print("[TTS] Using Habibi-TTS for Arabic TTS...")
                wav, sr, _ = habibi.infer(
                    ref_file=None,  # Don't require reference file
                    ref_text="",
                    gen_text=req.text,
                )
                audio_data = wav
                sample_rate = sr
                model_used = "habibi-tts (ALG)"
                print(f"[TTS] Arabic TTS generated with Habibi: shape={audio_data.shape if hasattr(audio_data, 'shape') else 'unknown'}")
            except Exception as e:
                print(f"[TTS] Habibi-TTS error: {e}")
                # Fall back to gTTS if Habibi fails
                print("[TTS] Falling back to gTTS for Arabic TTS...")
                try:
                    from gtts import gTTS
                    
                    # Generate Arabic TTS using gTTS
                    tts = gTTS(text=req.text, lang='ar', slow=False)
                    
                    # Save to temporary file
                    temp_dir = tempfile.gettempdir()
                    temp_filename = os.path.join(temp_dir, f"tts_arabic_{hash(req.text)}.mp3")
                    
                    try:
                        # Save to temporary file
                        tts.save(temp_filename)
                        
                        # Convert MP3 to WAV for consistency
                        from pydub import AudioSegment
                        audio = AudioSegment.from_mp3(temp_filename)
                        
                        # Convert to numpy array
                        samples = np.array(audio.get_array_of_samples())
                        if audio.channels == 2:
                            samples = samples.reshape((-1, 2))
                        
                        audio_data = samples.astype(np.float32) / 32768.0  # Convert to float
                        sample_rate = audio.frame_rate
                        
                        model_used = "gTTS (Arabic fallback)"
                        print(f"[TTS] Arabic TTS generated with gTTS fallback: shape={audio_data.shape}, sample_rate={sample_rate}")
                        
                    finally:
                        # Clean up temp file with proper error handling
                        try:
                            if os.path.exists(temp_filename):
                                os.unlink(temp_filename)
                                print(f"[TTS] Cleaned up temp file: {temp_filename}")
                        except Exception as cleanup_error:
                            print(f"[TTS] WARNING: Could not clean up temp file {temp_filename}: {cleanup_error}")
                            
                except ImportError:
                    print("[TTS] gTTS not available, falling back to Kokoro with transliteration")
                    # Final fallback to Kokoro English for Arabic text
                    kokoro = ml_models.get("tts_kokoro_en")
                    if kokoro is None:
                        raise HTTPException(503, "No TTS models available for Arabic")
                    
                    try:
                        print("[TTS] Generating Arabic TTS with Kokoro English fallback...")
                        generator = kokoro(req.text, voice="af_heart")
                        chunks = []
                        for i, (phonemes, duration, audio) in enumerate(generator):
                            print(f"[TTS] Chunk {i}: audio shape={audio.shape if hasattr(audio, 'shape') else 'unknown'}")
                            chunks.append(audio)
                        
                        if not chunks:
                            raise HTTPException(500, "No audio chunks generated for Arabic fallback")
                        
                        audio_data = np.concatenate(chunks)
                        model_used = "kokoro-82m (EN fallback for Arabic)"
                        print(f"[TTS] Arabic fallback TTS generated: shape={audio_data.shape}, chunks={len(chunks)}")
                    except Exception as e:
                        print(f"[TTS] Arabic fallback TTS error: {e}")
                        raise HTTPException(500, f"Arabic TTS fallback failed: {str(e)}")
        else:
            # Habibi-TTS not available, use gTTS as primary
            print("[TTS] Habibi-TTS not available, using gTTS for Arabic TTS...")
            try:
                from gtts import gTTS
                
                # Generate Arabic TTS using gTTS
                tts = gTTS(text=req.text, lang='ar', slow=False)
                
                # Save to temporary file
                temp_dir = tempfile.gettempdir()
                temp_filename = os.path.join(temp_dir, f"tts_arabic_{hash(req.text)}.mp3")
                
                try:
                    # Save to temporary file
                    tts.save(temp_filename)
                    
                    # Convert MP3 to WAV for consistency
                    from pydub import AudioSegment
                    audio = AudioSegment.from_mp3(temp_filename)
                    
                    # Convert to numpy array
                    samples = np.array(audio.get_array_of_samples())
                    if audio.channels == 2:
                        samples = samples.reshape((-1, 2))
                    
                    audio_data = samples.astype(np.float32) / 32768.0  # Convert to float
                    sample_rate = audio.frame_rate
                    
                    model_used = "gTTS (Arabic)"
                    print(f"[TTS] Arabic TTS generated with gTTS: shape={audio_data.shape}, sample_rate={sample_rate}")
                    
                finally:
                    # Clean up temp file with proper error handling
                    try:
                        if os.path.exists(temp_filename):
                            os.unlink(temp_filename)
                            print(f"[TTS] Cleaned up temp file: {temp_filename}")
                    except Exception as cleanup_error:
                        print(f"[TTS] WARNING: Could not clean up temp file {temp_filename}: {cleanup_error}")
                        
            except ImportError:
                print("[TTS] gTTS not available, falling back to Kokoro with transliteration")
                # Final fallback to Kokoro English for Arabic text
                kokoro = ml_models.get("tts_kokoro_en")
                if kokoro is None:
                    raise HTTPException(503, "No TTS models available for Arabic")
                
                try:
                    print("[TTS] Generating Arabic TTS with Kokoro English fallback...")
                    generator = kokoro(req.text, voice="af_heart")
                    chunks = []
                    for i, (phonemes, duration, audio) in enumerate(generator):
                        print(f"[TTS] Chunk {i}: audio shape={audio.shape if hasattr(audio, 'shape') else 'unknown'}")
                        chunks.append(audio)
                    
                    if not chunks:
                        raise HTTPException(500, "No audio chunks generated for Arabic fallback")
                    
                    audio_data = np.concatenate(chunks)
                    model_used = "kokoro-82m (EN fallback for Arabic)"
                    print(f"[TTS] Arabic fallback TTS generated: shape={audio_data.shape}, chunks={len(chunks)}")
                except Exception as e:
                    print(f"[TTS] Arabic fallback TTS error: {e}")
                    raise HTTPException(500, f"Arabic TTS fallback failed: {str(e)}")

    elif req.language == "fr":
        kokoro = ml_models.get("tts_kokoro_fr")
        if kokoro is None:
            raise HTTPException(503, "Kokoro FR not loaded")
        try:
            print("[TTS] Generating French TTS...")
            generator = kokoro(req.text, voice="ff_siwis")
            chunks = []
            for i, (phonemes, duration, audio) in enumerate(generator):
                print(f"[TTS] Chunk {i}: audio shape={audio.shape if hasattr(audio, 'shape') else 'unknown'}")
                chunks.append(audio)
            
            if not chunks:
                raise HTTPException(500, "No audio chunks generated")
            
            audio_data = np.concatenate(chunks)
            model_used = "kokoro-82m (FR)"
            print(f"[TTS] French TTS generated: shape={audio_data.shape}, chunks={len(chunks)}")
        except Exception as e:
            print(f"[TTS] French TTS error: {e}")
            raise HTTPException(500, f"French TTS failed: {str(e)}")

    else:
        kokoro = ml_models.get("tts_kokoro_en")
        if kokoro is None:
            raise HTTPException(503, "Kokoro EN not loaded")
        try:
            print("[TTS] Generating English TTS...")
            generator = kokoro(req.text, voice="af_heart")
            chunks = []
            for i, (phonemes, duration, audio) in enumerate(generator):
                print(f"[TTS] Chunk {i}: audio shape={audio.shape if hasattr(audio, 'shape') else 'unknown'}")
                chunks.append(audio)
            
            if not chunks:
                raise HTTPException(500, "No audio chunks generated")
            
            audio_data = np.concatenate(chunks)
            model_used = "kokoro-82m (EN)"
            print(f"[TTS] English TTS generated: shape={audio_data.shape}, chunks={len(chunks)}")
        except Exception as e:
            print(f"[TTS] English TTS error: {e}")
            raise HTTPException(500, f"English TTS failed: {str(e)}")

    # Validate audio data
    if audio_data is None:
        raise HTTPException(500, "No audio data generated")
    
    if hasattr(audio_data, 'shape') and audio_data.size == 0:
        raise HTTPException(500, "Empty audio data generated")

    # Create output directory if it doesn't exist
    os.makedirs("outputs", exist_ok=True)
    
    # Generate unique filename
    filename = f"output_{req.language}_{uuid.uuid4().hex[:8]}.wav"
    filepath = os.path.join("outputs", filename)
    
    print(f"Saving audio to: {filepath}")
    
    # Save audio file
    sf.write(filepath, audio_data, sample_rate, format="WAV")
    
    # Verify file was created and has content
    if not os.path.exists(filepath):
        raise HTTPException(500, "Failed to save audio file")
    
    file_size = os.path.getsize(filepath)
    print(f"Audio file saved: {file_size} bytes")
    
    if file_size == 0:
        raise HTTPException(500, "Audio file is empty")
    
    # Read audio file and convert to base64 for fallback
    with open(filepath, "rb") as f:
        audio_bytes = f.read()
    
    audio_base64 = base64.b64encode(audio_bytes).decode('utf-8')
    
    # Return download link with base64 fallback
    return {
        "success": True,
        "filename": filename,
        "download_url": f"/download/{filename}",
        "audio_base64": f"data:audio/wav;base64,{audio_base64}",
        "model_used": model_used,
        "sample_rate": sample_rate,
        "text": req.text,
        "language": req.language,
        "file_size": file_size
    }


@router.post("/voice-full-pipeline", summary="Complete Voice Pipeline: STT -> Translator -> Orchestrator -> Knowledge Base")
async def voice_full_pipeline(audio: UploadFile = File(...), session_id: Optional[str] = Form(None)):
    """
    Complete voice pipeline showing all stages:
    Voice input -> Layer 1 STT -> Translation Gate -> Layer 1 Ingestion -> Layer 2 Orchestrator -> Knowledge Base -> Output
    """
    return await _voice_full_pipeline_internal(audio, session_id, status_callback=None)


async def _voice_full_pipeline_internal(audio: UploadFile, session_id: Optional[str], status_callback: Optional[callable] = None, is_followup: bool = False):
    """
    Internal voice pipeline with optional status callback.
    This is the actual implementation that can be called with a callback from WebSocket.
    """
    session_short = session_id[:8] if session_id else "unknown"
    print(f"══════════════════════════════════════════════════")
    print(f"  PIPELINE START  │  Session: {session_short}")
    print(f"══════════════════════════════════════════════════")
    from app.main import ml_models
    from app.layer1.ingestion import ingest_chat_request
    from app.layer2.orchestrator import smart_pm_routing
    from app.layer2.knowledgebase.intelligent_rag_system import IntelligentRAGSystem
    from app.layer2.shared.session_manager import create_session, get_session, add_to_history, get_conversation_context, is_waiting_for_eligibility_answer, get_eligibility_language, clear_eligibility_flag
    from app.schemas.conversation import ChatRequest, SourceChannel
    from app.utils.status_messages import get_status_message

    # Step 1: Session Management
    if session_id:
        # Get existing session
        session = get_session(session_id)
        if not session:
            # Session expired, create new one
            session_id = create_session()
    else:
        # No session_id provided, create new session
        session_id = create_session()

    # Initialize results dictionary
    results = {
        "success": True,
        "stages": {},
        "debug_info": {
            "timestamp": str(uuid.uuid4()),
            "audio_file_size": "unknown",
            "processing_steps": []
        }
    }

    # Helper function to send status updates
    async def send_status(stage: str, language: str = "en"):
        if status_callback:
            message = get_status_message(stage, language)
            await status_callback(stage, message, language)

    # Helper function to generate TTS for status messages
    async def generate_status_tts(message: str, language: str) -> Optional[bytes]:
        """Generate TTS audio for status message"""
        try:
            from app.main import ml_models
            import soundfile as sf
            import io

            # Select TTS model based on language
            if language == "fr":
                tts_model = ml_models.get("tts_vosk_fr")
                if tts_model is None:
                    return None
                # Use Vosk for French
                # Note: Vosk is STT, not TTS - we need a different approach
                # For now, skip French TTS for status messages
                return None
            else:
                # Use Kokoro for English/Arabic (fallback to English)
                kokoro = ml_models.get("tts_kokoro_en")
                if kokoro is None:
                    return None
                generator = kokoro(message, voice="af_heart")
                chunks = []
                for i, (phonemes, duration, audio) in enumerate(generator):
                    chunks.append(audio)
                if not chunks:
                    return None
                audio_data = np.concatenate(chunks)

                # Convert to WAV bytes
                wav_buffer = io.BytesIO()
                sf.write(wav_buffer, audio_data, 24000, format="WAV")
                wav_buffer.seek(0)
                return wav_buffer.read()
        except Exception as e:
            print(f"[TTS] Error generating status TTS: {e}")
            return None

    # Step 1: Load and transcribe audio using Layer 1 STT
    if not ml_models.get("stt_whisper"):
        raise HTTPException(503, "Whisper not configured")

    transcription = None
    detected_language = "unknown"
    used_fallback = False
    
    try:
        audio_bytes = await audio.read()
        
        # Use NVIDIA Riva gRPC client for whisper-large-v3
        api_key = os.getenv("NVIDIA_API_KEY")
        if not api_key:
            raise HTTPException(500, "NVIDIA_API_KEY environment variable is missing.")
        
        # Create a temporary file for the audio
        temp_filename = os.path.join(tempfile.gettempdir(), f"stt_temp_{hash(audio_bytes)}.wav")
        
        try:
            # Write audio bytes to temporary file
            buffer = io.BytesIO(audio_bytes)
            audio_array, sample_rate = sf.read(buffer)
            # Resample to 16000 Hz if needed (standard for Riva)
            if sample_rate != 16000:
                import librosa
                audio_array = librosa.resample(audio_array, orig_sr=sample_rate, target_sr=16000)
                sample_rate = 16000
            sf.write(temp_filename, audio_array, sample_rate, format="WAV")
            
            # Clone Riva Python clients if not already present
            project_root = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
            riva_clients_dir = os.path.join(project_root, "python-clients")
            if not os.path.exists(riva_clients_dir):
                subprocess.run(
                    ["git", "clone", "https://github.com/nvidia-riva/python-clients.git", riva_clients_dir],
                    check=True, capture_output=True
                )
            
            # Path to transcribe script
            transcribe_script = os.path.join(riva_clients_dir, "scripts", "asr", "transcribe_file_offline.py")
            
            # Build command for NVIDIA Riva client
            cmd = [
                sys.executable,
                transcribe_script,
                "--server", "grpc.nvcf.nvidia.com:443",
                "--use-ssl",
                "--metadata", "function-id", RIVA_FUNCTION_ID,
                "--metadata", "authorization", f"Bearer {api_key}",
                "--language-code", "multi",
                "--input-file", temp_filename
            ]
            
            # Set environment variables for subprocess
            env = os.environ.copy()
            env['PYTHONHASHSEED'] = 'random'
            env['PYTHONIOENCODING'] = 'utf-8'
            
            # Run the command with UTF-8 encoding
            try:
                result = subprocess.run(
                    cmd,
                    capture_output=True,
                    text=True,
                    timeout=RIVA_COMMAND_TIMEOUT,
                    env=env,
                    encoding='utf-8',
                    errors='replace'
                )
            except subprocess.TimeoutExpired as timeout_exc:
                raise HTTPException(504, f"NVIDIA Riva STT command timed out after {RIVA_COMMAND_TIMEOUT} seconds") from timeout_exc
            
            stderr_lower = (result.stderr or "").lower()
            stdout_lower = (result.stdout or "").lower()
            
            error_keywords = [
                "failed", "error", "unknown", "timeout", "handshaker", "connect",
                "grpc", "exception", "degraded", "invalidargument", "stateful"
            ]
            
            riva_failed = result.returncode != 0 or any(keyword in stderr_lower for keyword in error_keywords) or any(keyword in stdout_lower for keyword in error_keywords)

            if riva_failed:
                print(f"[STT] Riva failed, trying local Whisper fallback...")
                try:
                    fallback = transcribe_with_local_whisper(temp_filename)
                    transcription = fallback["transcription"]
                    detected_language = fallback["detected_language"]
                    used_fallback = True
                    print(f"  [STT]       → \"{transcription}\"  [{detected_language}] (local fallback)")
                except Exception as whisper_error:
                    print(f"[STT] Local Whisper also failed: {whisper_error}")
                    return {
                        "success": False,
                        "error": "STT service unavailable. Please try again.",
                        "stage": "whisper_stt"
                    }

            if not used_fallback:
                try:
                    output = result.stdout.strip()
                    json_start = output.find('{')
                    json_end = output.rfind('}') + 1
                    
                    if json_start != -1 and json_end > json_start:
                        json_str = output[json_start:json_end]
                        json_output = json.loads(json_str)
                        
                        if json_output and 'results' in json_output:
                            result_data = json_output['results'][0]
                            alternatives = result_data['alternatives'][0]
                            transcription = alternatives['transcript']
                            language_codes = alternatives.get('languageCode', [])
                            detected_language = language_codes[0] if language_codes else "unknown"
                            print(f"  [STT]       → \"{transcription}\"  [{detected_language}]")
                        else:
                            transcription = output
                            detected_language = "unknown"
                    else:
                        if "Final transcript:" in output:
                            transcription = output.split("Final transcript:")[-1].strip()
                            detected_language = "unknown"
                            print(f"  [STT]       → \"{transcription}\"  [{detected_language}]")
                        else:
                            transcription = output
                            detected_language = "unknown"
                            print(f"  [STT]       → \"{transcription}\"  [{detected_language}]")
                    
                except json.JSONDecodeError as e:
                    output = result.stdout.strip()
                    if "Final transcript:" in output:
                        transcription = output.split("Final transcript:")[-1].strip()
                        detected_language = "unknown"
                        print(f"  [STT]       → \"{transcription}\"  [{detected_language}]")
                    else:
                        transcription = output
                        detected_language = "unknown"
                        print(f"  [STT]       → \"{transcription}\"  [{detected_language}]")
            
        finally:
            try:
                if os.path.exists(temp_filename):
                    os.unlink(temp_filename)
            except Exception:
                pass

        # Store STT results
        results["stages"]["whisper_stt"] = {
            "success": True,
            "model": "whisper-local-fallback" if used_fallback else "whisper-large-v3-nvidia-riva",
            "detected_language": detected_language,
            "transcription": transcription,
            "processing_time": "N/A"
        }

    except Exception as e:
        error_str = str(e)
        results["stages"]["whisper_stt"] = {
            "success": False,
            "error": error_str
        }
        raise HTTPException(500, f"Speech-to-text failed: {error_str}")

    # Handle fast path if is_followup is True
    if is_followup:
        t_lower = transcription.lower() if transcription else ""
        if any(word in t_lower for word in ["oui", "yes", "نعم"]):
           
            return {
                "action": "redirect",
                "url": LOAN_AGENT_URL
            }
        elif any(word in t_lower for word in ["non", "no", "لا"]):
            return {
                "action": "continue",
                "message": "Do you have any other questions?"
            }
        else:
            return {
                "action": "retry",
                "message": "Please answer Yes or No."
            }

    # Step 2: Apply language validation
    detected_language = validate_language(detected_language)
    
    # Step 3: Translation Gate - Conditional routing based on language
    text_for_ingestion = transcription
    text_for_kb = transcription  # Keep original for KB
    translation_applied = False

    if detected_language != "en" and detected_language != "unknown":
        try:
            from app.layer2.shared.model_loader import get_nemotron_model
            nemotron = get_nemotron_model()

            # Translate to English for orchestrator/intent detection
            english_text, safety_label = nemotron.translate_and_sanitize(transcription, detected_language, "en")

            # Apply safety gate
            if safety_label == "unsafe":
                raise HTTPException(400, "Query blocked by safety filter")

            text_for_ingestion = english_text
            translation_applied = True
            print(f"  [TRANSLATE]  → \"{english_text}\"  [{detected_language}→en]")

            results["stages"]["translator"] = {
                "success": True,
                "translation_applied": True,
                "model": "nemotron",
                "source_language": detected_language,
                "target_language": "en",
                "original_text": transcription,
                "translated_text": english_text
            }

        except Exception as e:
            text_for_ingestion = transcription
            results["stages"]["translator"] = {
                "success": False,
                "error": str(e),
                "fallback_used": True
            }
    else:
        # For English, translate to French for KB search
        if detected_language == "en":
            try:
                from deep_translator import GoogleTranslator
                text_for_kb = GoogleTranslator(source="en", target="fr").translate(transcription)
            except Exception as e:
                text_for_kb = transcription
        # For Arabic, translate to French for KB search
        elif detected_language == "ar":
            try:
                from deep_translator import GoogleTranslator
                text_for_kb = GoogleTranslator(source="ar", target="fr").translate(transcription)
            except Exception as e:
                text_for_kb = transcription
        # For French, keep as-is for KB search
        elif detected_language == "fr":
            text_for_kb = transcription
        
        print(f"  [TRANSLATE]  → (no translation needed)")
        results["stages"]["translator"] = {
            "success": True,
            "translation_applied": False,
            "reason": f"Language already English or unknown: {detected_language}",
            "source_language": detected_language,
            "target_language": "en",
            "original_text": transcription,
            "translated_text": transcription
        }

    # Security Layer 1: Input validation before ingestion
    try:
        from app.security_layer1.security_screening import scan_input
        security_check = scan_input(text_for_ingestion)
        
        if not security_check["is_safe"]:
            print(f"  [SECURITY]   → ✗ Blocked: {security_check['reason']}")
            return {
                "success": False,
                "blocked": True,
                "message": security_check["reason"]
            }
        
        print(f"  [SECURITY]   → ✓ Passed")
        
        results["stages"]["security_layer1"] = {
            "success": True,
            "is_safe": True,
            "risk_score": security_check["risk_score"]
        }
    except Exception as e:
        print(f"  [SECURITY]   → ✗ Error: {str(e)}")
        results["stages"]["security_layer1"] = {
            "success": False,
            "error": str(e)
        }

    # Step 3: Pass transcription to Layer 1 ingestion
    try:
        chat_request = ChatRequest(
            message=text_for_ingestion,
            source_language=detected_language,
            source_channel=SourceChannel.VOICE,
            conversation_id=session_id
        )
        
        state = ingest_chat_request(chat_request)
        state.retrieval_context["text_for_kb"] = text_for_kb
        
        # RESTORE orchestrator context from session to preserve multi-turn state
        from app.layer2.shared.session_manager import get_orchestrator_context
        saved_context = get_orchestrator_context(session_id)
        if saved_context:
            state.orchestrator_context.update(saved_context)
        
        # STEP 1: Check if we're in a special state using new conversation context
        conv_context = get_conversation_context(session_id)
        
        # CHECK: Are we waiting for eligibility yes/no answer? (New architecture)
        # Use both new conversation context AND old flag for compatibility
        is_waiting_new = conv_context and conv_context.waiting_for_input_type == "eligibility_answer"
        is_waiting_old = is_waiting_for_eligibility_answer(session_id)
        
        if is_waiting_new or is_waiting_old:
            user_response = state.normalized_text_en.lower()
            # Use conversation context language if available, otherwise fall back to old method
            if conv_context and conv_context.language:
                eligibility_language = conv_context.language
            else:
                eligibility_language = get_eligibility_language(session_id)
            print(f"[Voice Pipeline] ELIGIBILITY INTERCEPTION: language={eligibility_language}, user_response={user_response}, new_check={is_waiting_new}, old_check={is_waiting_old}")
            
            # YES RESPONSES (English, French, Arabic, Moroccan Darija)
            yes_patterns = ["yes", "yeah", "sure", "okay", "ok", "yep", "absolutely", "definitely",
                           "yes please", "yes, please", "yes thanks", "yes, thanks", "yes thank you", "yes, thank you",
                           "oui", "ouais", "d'accord", "bien sûr", "oui merci", "oui s'il vous plaît",
                           "نعم", "أيوا", "طبعا", "نعم من فضلك", "أيوا من فضلك", "أكيد", "بالتأكيد", "أجل",
                           "واه", "يلا", "صافي", "مزيان", "كيما بغيتي"]

            # NO RESPONSES (English, French, Arabic, Moroccan Darija)
            no_patterns = ["no", "nope", "not now", "don't want", "skip", "later", "don't", "no thanks", "no, thanks",
                          "non", "non merci", "pas maintenant", "plus tard", "non s'il vous plaît",
                          "لا", "لاه", "معليش", "لا من فضلك", "لا أريد", "لا شكرا", "بالطبع لا",
                          "ما بغيتش", "ما نقدرش", "ما كاينش"]

            # Normalize user response for matching (lowercase, strip whitespace)
            user_response_normalized = user_response.strip().lower()

            # Check if response is EXACTLY one of the yes/no patterns (or very short with punctuation)
            # This prevents matching "yes" in longer sentences like "yes actually i have a problem"
            def is_exact_match(response: str, patterns: list) -> bool:
                # Check exact match
                if response in patterns:
                    return True
                # Check if it's a pattern with trailing punctuation (e.g., "yes.", "yes!")
                for pattern in patterns:
                    if response == pattern + "." or response == pattern + "!" or response == pattern + "?":
                        return True
                return False

            if is_exact_match(user_response_normalized, yes_patterns):
                # USER SAID YES - REDIRECT IMMEDIATELY
                print(f"[VOICE] ELIGIBILITY: User said YES - Redirecting to eligibility URL")
                clear_eligibility_flag(session_id)
                
                # Record this turn in conversation context
                from app.layer2.shared.session_manager import add_turn_record
                from app.schemas.conversation_context import TurnRecord
                turn = TurnRecord(
                    turn_number=conv_context.current_turn + 1,
                    user_input=transcription,
                    user_input_normalized=state.normalized_text_en,
                    user_language=eligibility_language,
                    agent_routed_to="eligibility_handler",
                    agent_response="[Redirecting to eligibility test]",
                    routing_reason="Eligibility yes detected",
                    metadata={"redirect_url": LOAN_AGENT_URL}
                )
                add_turn_record(session_id, turn)
                
                redirect_response_en = "Great! You can test your loan eligibility here.\n\nPlease fill out the quick assessment form. It will take about 2-3 minutes, and you'll get an instant eligibility result."
                
                # Translate to user's language
                from app.layer3.translation.translator import translate_from_english
                redirect_response_localized = translate_from_english(redirect_response_en, eligibility_language)
                
                # Deliver the response
                from app.layer3.delivery import deliver_response
                from app.schemas.conversation import ConversationState, SourceChannel
                delivery_state = ConversationState(
                    conversation_id=state.conversation_id,
                    source_channel=SourceChannel.VOICE,
                    source_language=eligibility_language,
                    original_text=state.original_text,
                    normalized_text_en=redirect_response_en,
                    final_response_en=redirect_response_en,
                    final_response_localized=redirect_response_localized,
                )
                audio_state = deliver_response(delivery_state)
                
                if audio_state.final_response_audio:
                    import base64
                    results["final_response_audio"] = base64.b64encode(audio_state.final_response_audio).decode("utf-8")
                    results["audio_model_used"] = audio_state.audio_model_used
                    results["audio_sample_rate"] = audio_state.audio_sample_rate
                    results["final_response_localized"] = audio_state.final_response_localized
                    add_to_history(session_id, text_for_ingestion, redirect_response_localized or redirect_response_en)
                
                results["summary"] = {
                    "total_stages": 5,
                    "successful_stages": 3,
                    "conversation_id": str(state.conversation_id),
                    "session_id": session_id,
                    "eligibility_redirect": "yes",
                    "redirect_url": LOAN_AGENT_URL
                }
                
                # Add flags for WebSocket to end call and redirect
                results["end_call"] = True
                results["redirect_url"] = LOAN_AGENT_URL
                
                return results
                
            elif is_exact_match(user_response_normalized, no_patterns):
                # USER SAID NO - STATIC RESPONSE
                print(f"[VOICE] ELIGIBILITY: User said NO - Sending static response")
                clear_eligibility_flag(session_id)

                # Mark that user declined eligibility test, don't ask again in this session
                from app.layer2.shared.session_manager import set_eligibility_declined
                set_eligibility_declined(session_id, True)
                
                # Record this turn in conversation context
                from app.layer2.shared.session_manager import add_turn_record
                from app.schemas.conversation_context import TurnRecord
                turn = TurnRecord(
                    turn_number=conv_context.current_turn + 1,
                    user_input=transcription,
                    user_input_normalized=state.normalized_text_en,
                    user_language=eligibility_language,
                    agent_routed_to="eligibility_handler",
                    agent_response="Do you have other questions?",
                    routing_reason="Eligibility no detected"
                )
                add_turn_record(session_id, turn)
                
                # Use language-appropriate response
                if eligibility_language.lower() in ["fr", "french"]:
                    no_response_text = "D'accord! Avez-vous d'autres questions?"
                elif eligibility_language.lower() in ["ar", "arabic"]:
                    no_response_text = "حسنا! هل لديك أسئلة أخرى؟"
                else:
                    no_response_text = "No problem! Do you have any other questions?"
                
                # Deliver the response
                from app.layer3.delivery import deliver_response
                from app.schemas.conversation import ConversationState, SourceChannel
                delivery_state = ConversationState(
                    conversation_id=state.conversation_id,
                    source_channel=SourceChannel.VOICE,
                    source_language=eligibility_language,
                    original_text=state.original_text,
                    normalized_text_en="Do you have other questions?",
                    final_response_en="Do you have other questions?",
                    final_response_localized=no_response_text,
                )
                audio_state = deliver_response(delivery_state)
                
                if audio_state.final_response_audio:
                    import base64
                    results["final_response_audio"] = base64.b64encode(audio_state.final_response_audio).decode("utf-8")
                    results["audio_model_used"] = audio_state.audio_model_used
                    results["audio_sample_rate"] = audio_state.audio_sample_rate
                    results["final_response_localized"] = audio_state.final_response_localized
                    add_to_history(session_id, text_for_ingestion, no_response_text)
                
                results["summary"] = {
                    "total_stages": 5,
                    "successful_stages": 3,
                    "conversation_id": str(state.conversation_id),
                    "session_id": session_id,
                    "eligibility_response": "no"
                }
                return results
        
        results["stages"]["ingestion"] = {
            "success": True,
            "conversation_id": str(state.conversation_id),
            "original_text": state.original_text,
            "normalized_text_en": state.normalized_text_en,
            "pii_masked": len(state.pii_map) > 0 if state.pii_map else False
        }
        
    except Exception as e:
        results["stages"]["ingestion"] = {
            "success": False,
            "error": str(e)
        }
        raise HTTPException(500, f"Layer 1 ingestion failed: {str(e)}")

    # Helper: decide whether loan followup should be injected (independent of KB)
    def _is_loan_involved(st) -> bool:
        req = getattr(st, "required_agents", None) or []
        intent = getattr(st, "intent", None) or ""
        return (
            ("loan_agent" in req)
            or any("loan" in a.lower() for a in req)
            or ("loan" in str(intent).lower())
        )

    # Step 4: Orchestrator FIRST (so loan detection is based on agent choice, not KB)
    try:
        # STEP 2: Pass conversation history to orchestrator for context
        if conv_context:
            state.conversation_history = conv_context.get_previous_turns(n=3)
        
        result_state = smart_pm_routing(state)
        
        selected_agent = result_state.required_agents[0] if result_state.required_agents else "unknown"
        confidence = result_state.orchestrator_context.get("confidence", 0.0)
        print(f"  [ROUTING]    → {selected_agent}  (score: {confidence:.2f})")
        print(f"               ↳ Intent: {result_state.intent}")

        results["stages"]["orchestrator"] = {
            "success": True,
            "intent": result_state.intent,
            "category": result_state.intent_category,
            "confidence": result_state.orchestrator_context.get("confidence", 0.0),
            "extraction_method": result_state.orchestrator_context.get("extraction_method", "unknown"),
            "model_used": result_state.orchestrator_context.get("model_used", "unknown"),
            "required_agents": result_state.required_agents,
            "final_response": result_state.final_response_en,
        }
    except Exception as e:
        raise HTTPException(500, f"Orchestrator processing failed: {str(e)}")

    # Step 4.5: Removed Quick Knowledge-Base check.
    # The Knowledge Base is now properly executed INSIDE the LangGraph flow.

    try:
        # Execute the graph to run proper agent flow
        from app.layer2.graph import _run_with_langgraph
        final_state = _run_with_langgraph(result_state)
        
        # Update results with final state after graph execution
        if final_state.final_response_en:
            results["stages"]["orchestrator"]["final_response"] = final_state.final_response_en
            results["agent_response"] = final_state.final_response_en
            results["selected_agent"] = final_state.required_agents[0] if final_state.required_agents else "unknown"
            
            # Step 1: Get English response from client_support
            english_response = final_state.final_response_en

            # --- LOAN FOLLOWUP INJECTION (BEFORE SECURITY) ---
            # Requirement: inject the followup sentence before the security layer runs,
            # so the validated/translated response includes it.
            loan_involved = _is_loan_involved(final_state)
            # Only inject followup if user hasn't already declined eligibility test
            from app.layer2.shared.session_manager import is_eligibility_declined
            if loan_involved and not is_eligibility_declined(session_id):
                LOAN_FOLLOWUP_PHRASE_EN = "Would you like to check your eligibility for this loan? Please answer Yes or No."
                english_response = english_response + "\n\n" + LOAN_FOLLOWUP_PHRASE_EN

            results["loan_followup_triggered"] = bool(loan_involved and not is_eligibility_declined(session_id))
            # -------------------------------

            # Security Layer 2: NeMo Guard output validation
            try:
                from app.security_layer2.output_validator import validate_output
                validated_response = validate_output(english_response)
                results["stages"]["security_layer2"] = {
                    "success": True,
                    "modified": validated_response != english_response
                }
                english_response = validated_response
                final_state.final_response_en = english_response
            except Exception as e:
                print(f"  [SECURITY]   → ✗ Output validation error")
                results["stages"]["security_layer2"] = {
                    "success": False,
                    "error": str(e)
                }
            
            # Step 2: Translate back to user's original language
            from app.layer3.translation.translator import translate_from_english
            localized_response = translate_from_english(english_response, detected_language)
            
            # Step 3: Convert to speech
            from app.layer3.delivery import deliver_response
            from app.schemas.conversation import ConversationState, SourceChannel
            
            # Create ConversationState for Layer 3 delivery
            delivery_state = ConversationState(
                conversation_id="voice-pipeline",
                source_channel=SourceChannel.VOICE,
                source_language=detected_language,
                original_text="",
                normalized_text_en=english_response,
                final_response_en=english_response,
                final_response_localized=localized_response
            )
            
            audio_state = deliver_response(delivery_state)
            
            if audio_state.final_response_audio:
                print(f"  [TTS]        → {detected_language} ({audio_state.audio_model_used}) | Audio ready")
                
                # Encode binary audio data as base64 for JSON serialization
                import base64
                audio_base64 = base64.b64encode(audio_state.final_response_audio).decode('utf-8')
                
                results["final_response_audio"] = audio_base64
                results["audio_model_used"] = audio_state.audio_model_used
                results["audio_sample_rate"] = audio_state.audio_sample_rate
                results["final_response_localized"] = audio_state.final_response_localized
        
                add_to_history(session_id, text_for_ingestion, localized_response or english_response)
        
    except Exception as e:
        results["stages"]["orchestrator"] = {
            "success": False,
            "error": str(e)
        }
        raise HTTPException(500, f"Orchestrator processing failed: {str(e)}")

    # Add completion footer
    from app.layer2.shared.session_manager import get_session
    session = get_session(session_id)
    turn_number = len(session.get("history", [])) if session else 1
    print(f"──────────────────────────────────────────────────")
    print(f"  ✓ Turn {turn_number} complete  │  Session: {session_short}")
    print(f"══════════════════════════════════════════════════")

    # Step 5: Extract KB metadata from final_state after graph execution
    if hasattr(final_state, 'kb_result') and final_state.kb_result:
        results["stages"]["knowledge_base"] = {
            "success": True,
            "answer": final_state.kb_result,
            "used": True,
            "confidence": getattr(final_state, 'agent_feedback', {}).get('knowledge_base', {}).get('confidence', 0.0)
        }
    else:
        results["stages"]["knowledge_base"] = {
            "success": False,
            "error": "KB not used or failed in graph"
        }

    # Add summary
    results["summary"] = {
        "total_stages": 5,
        "successful_stages": sum(1 for stage in results["stages"].values() if stage.get("success", False)),
        "conversation_id": str(state.conversation_id),
        "session_id": session_id,  # Return session_id for frontend
        "original_transcription": transcription,
        "detected_language": detected_language,
        "translation_applied": translation_applied
    }

    # Add agent response to results for UI display
    if "orchestrator" in results["stages"] and results["stages"]["orchestrator"]["success"]:
        results["agent_response"] = results["stages"]["orchestrator"]["final_response"]
        results["selected_agent"] = results["stages"]["orchestrator"]["required_agents"][0] if results["stages"]["orchestrator"]["required_agents"] else "unknown"

    # SAVE orchestrator context back to session for next turn
    from app.layer2.shared.session_manager import save_orchestrator_context
    if hasattr(result_state, 'orchestrator_context') and result_state.orchestrator_context:
        save_orchestrator_context(session_id, result_state.orchestrator_context)
        print(f"[Voice Pipeline] Saved orchestrator_context to session: {result_state.orchestrator_context}")

    # STEP 6: Record turn after agent processing
    if conv_context and results.get("agent_response"):
        from app.layer2.shared.session_manager import add_turn_record
        from app.schemas.conversation_context import TurnRecord
        turn = TurnRecord(
            turn_number=conv_context.current_turn + 1,
            user_input=transcription,
            user_input_normalized=state.normalized_text_en,
            user_language=detected_language,
            agent_routed_to=results.get("selected_agent", "unknown"),
            agent_response=results["agent_response"],
            intent=result_state.intent,
            confidence=result_state.orchestrator_context.get("confidence", 0),
            routing_reason="Intent-based routing",
            metadata={
                "audio_duration": "N/A",
                "tts_model": results.get("audio_model_used"),
            }
        )
        add_turn_record(session_id, turn)

    return results


@router.post("/session/create", summary="Create new session")
async def create_session():
    """Create a new conversation session"""
    from app.layer2.shared.session_manager import create_session
    session_id = create_session()
    return {"session_id": session_id}


@router.get("/session/create", summary="Create new session (GET)")
async def create_session_get():
    """Create a new conversation session via GET"""
    from app.layer2.shared.session_manager import create_session
    session_id = create_session()
    return {"session_id": session_id}


@router.delete("/session/{session_id}", summary="End session")
async def end_session(session_id: str):
    """End a conversation session and clean up history"""
    from app.layer2.shared.session_manager import end_session
    end_session(session_id)
    return {"success": True, "message": "Session ended"}


@router.get("/download/{filename}", summary="Download generated audio file")
async def download_audio(filename: str):
    """Serve the generated audio file for download/streaming"""
    
    filepath = os.path.join("outputs", filename)
    print(f"Download request for: {filepath}")
    
    if not os.path.exists(filepath):
        print(f"File not found: {filepath}")
        raise HTTPException(404, "Audio file not found")
    
    # Check file size
    file_size = os.path.getsize(filepath)
    print(f"File size: {file_size} bytes")
    
    if file_size == 0:
        print("File is empty!")
        raise HTTPException(500, "Audio file is empty")
    
    # Return file directly with proper headers for streaming
    def iterfile():
        with open(filepath, mode="rb") as file_like:
            yield from file_like
    
    return StreamingResponse(
        iterfile(),
        media_type="audio/wav",
        headers={
            "Content-Disposition": f"inline; filename={filename}",
            "Content-Length": str(file_size),
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Methods": "GET",
            "Access-Control-Allow-Headers": "*",
            "Cache-Control": "no-cache"
        }
    )