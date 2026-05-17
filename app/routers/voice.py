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

logger = logging.getLogger(__name__)
import soundfile as sf
from fastapi import APIRouter, File, HTTPException, UploadFile, Form
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from typing import Optional

router = APIRouter(prefix="/test", tags=["Layer Tests"])


def validate_language(detected_language: str) -> str:
    """Validate and normalize detected language to supported languages"""
    SUPPORTED_LANGUAGES = ["ar", "fr", "en"]
    if detected_language in SUPPORTED_LANGUAGES:
        return detected_language
    # Default to Arabic for unsupported languages
    # since BNA customers are primarily Algerian
    logger.warning(
        f"[Language] Unsupported language detected: '{detected_language}'. "
        f"Defaulting to Arabic."
    )
    return "ar"


@router.post("/stt", summary="Test Layer 1: Whisper STT (NVIDIA Riva gRPC)")
async def test_stt(audio: UploadFile = File(...)):
    from app.main import ml_models

    if not ml_models.get("stt_whisper"):
        raise HTTPException(503, "Whisper not configured")

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
            sf.write(temp_filename, audio_array, sample_rate, format="WAV")
            
            print(f"Audio file written: {temp_filename}, sample_rate: {sample_rate}")
            print(f"Sending request to NVIDIA Riva gRPC API")
            
            # Clone Riva Python clients if not already present
            project_root = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
            riva_clients_dir = os.path.join(project_root, "python-clients")
            if not os.path.exists(riva_clients_dir):
                print(f"Cloning NVIDIA Riva Python clients to {riva_clients_dir}")
                subprocess.run(
                    ["git", "clone", "https://github.com/nvidia-riva/python-clients.git", riva_clients_dir],
                    check=True, capture_output=True
                )
            
            # Path to the transcribe script
            transcribe_script = os.path.join(riva_clients_dir, "scripts", "asr", "transcribe_file_offline.py")
            
            if not os.path.exists(transcribe_script):
                raise HTTPException(500, f"Riva client script not found at {transcribe_script}")
            
            # Build command for NVIDIA Riva client
            cmd = [
                sys.executable,
                transcribe_script,
                "--server", "grpc.nvcf.nvidia.com:443",
                "--use-ssl",
                "--metadata", "function-id", "b702f636-f60c-4a3d-a6f4-f3568c13bd7d",
                "--metadata", "authorization", f"Bearer {api_key}",
                "--language-code", "multi",  # Auto language detection
                "--input-file", temp_filename
            ]
            
            print(f"Running command: {' '.join(cmd)}")
            
            # Set environment variables for subprocess
            env = os.environ.copy()
            env['PYTHONHASHSEED'] = 'random'
            env['PYTHONIOENCODING'] = 'utf-8'
            
            # Run the command with UTF-8 encoding
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=60, env=env, encoding='utf-8', errors='replace')
            
            if result.returncode != 0:
                print(f"Riva client error: {result.stderr}")
                raise HTTPException(500, f"Riva client failed: {result.stderr}")
            
            print(f"Riva client output: {result.stdout}")
            
            # Parse the JSON output from Riva client
            # The output contains JSON followed by "Final transcript: <text>"
            # We need to extract the JSON to get language and transcript
            try:
                # Find the JSON object (it starts with { and ends with })
                output = result.stdout.strip()
                
                # Try to find where JSON ends and "Final transcript" begins
                json_start = output.find('{')
                json_end = output.rfind('}') + 1
                
                if json_start != -1 and json_end > json_start:
                    json_str = output[json_start:json_end]
                    json_output = json.loads(json_str)
                    
                    if json_output and 'results' in json_output:
                        # Extract transcript and language from JSON
                        result_data = json_output['results'][0]
                        alternatives = result_data['alternatives'][0]
                        transcription = alternatives['transcript']
                        language_codes = alternatives.get('languageCode', [])
                        detected_language = language_codes[0] if language_codes else "unknown"
                        
                        print(f"Parsed transcription: {transcription[:100]}...")
                        print(f"Detected language: {detected_language}")
                    else:
                        # Fallback to entire output
                        transcription = output
                        detected_language = "unknown"
                        print(f"JSON parsing failed, using raw output")
                else:
                    # No JSON found, try to find "Final transcript:"
                    if "Final transcript:" in output:
                        transcription = output.split("Final transcript:")[-1].strip()
                        detected_language = "unknown"
                    else:
                        transcription = output
                        detected_language = "unknown"
                        print(f"JSON parsing failed, using raw output")
                
            except json.JSONDecodeError as e:
                # If JSON parsing fails, try to find "Final transcript:"
                output = result.stdout.strip()
                if "Final transcript:" in output:
                    transcription = output.split("Final transcript:")[-1].strip()
                    detected_language = "unknown"
                    print(f"JSON parsing failed ({e}), using final transcript line")
                else:
                    transcription = output
                    detected_language = "unknown"
                    print(f"JSON parsing failed ({e}), using raw output")
            
            return {
                "layer": 1,
                "model": "whisper-large-v3-nvidia-riva",
                "detected_language": detected_language,
                "transcription": transcription,
            }
            
        finally:
            # Clean up temp file
            try:
                if os.path.exists(temp_filename):
                    os.unlink(temp_filename)
            except Exception as cleanup_error:
                print(f"Warning: Could not clean up temp file {temp_filename}: {cleanup_error}")
                
    except Exception as e:
        error_str = str(e)
        print(f"NVIDIA Riva API error: {error_str}")
        raise HTTPException(500, f"Speech-to-text failed: {error_str}")


@router.post("/voice-to-orchestrator", summary="Voice Input -> Layer 1 STT -> Translation Gate -> Layer 2 Orchestrator -> Output")
async def voice_to_orchestrator(audio: UploadFile = File(...)):
    """
    Complete voice pipeline: Voice input -> Layer 1 STT -> Translation Gate -> Layer 1 Ingestion -> Layer 2 Orchestrator -> Output
    """
    from app.main import ml_models
    from app.layer1.ingestion import ingest_chat_request
    from app.layer2.orchestrator import smart_pm_routing
    from app.schemas.conversation import ChatRequest, SourceChannel

    # Step 1: Load and transcribe audio using Layer 1 STT
    if not ml_models.get("stt_whisper"):
        raise HTTPException(503, "Whisper not configured")

    transcription = None
    detected_language = "unknown"
    
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
            sf.write(temp_filename, audio_array, sample_rate, format="WAV")
            
            print(f"Audio file written: {temp_filename}, sample_rate: {sample_rate}")
            print(f"Sending request to NVIDIA Riva gRPC API")
            
            # Clone Riva Python clients if not already present
            project_root = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
            riva_clients_dir = os.path.join(project_root, "python-clients")
            if not os.path.exists(riva_clients_dir):
                print(f"Cloning NVIDIA Riva Python clients to {riva_clients_dir}")
                subprocess.run(
                    ["git", "clone", "https://github.com/nvidia-riva/python-clients.git", riva_clients_dir],
                    check=True, capture_output=True
                )
            
            # Path to the transcribe script
            transcribe_script = os.path.join(riva_clients_dir, "scripts", "asr", "transcribe_file_offline.py")
            
            if not os.path.exists(transcribe_script):
                raise HTTPException(500, f"Riva client script not found at {transcribe_script}")
            
            # Build command for NVIDIA Riva client
            cmd = [
                sys.executable,
                transcribe_script,
                "--server", "grpc.nvcf.nvidia.com:443",
                "--use-ssl",
                "--metadata", "function-id", "b702f636-f60c-4a3d-a6f4-f3568c13bd7d",
                "--metadata", "authorization", f"Bearer {api_key}",
                "--language-code", "multi",  # Auto language detection
                "--input-file", temp_filename
            ]
            
            print(f"Running command: {' '.join(cmd)}")
            
            # Set environment variables for subprocess
            env = os.environ.copy()
            env['PYTHONHASHSEED'] = 'random'
            env['PYTHONIOENCODING'] = 'utf-8'
            
            # Run the command with UTF-8 encoding
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=60, env=env, encoding='utf-8', errors='replace')
            
            if result.returncode != 0:
                print(f"Riva client error: {result.stderr}")
                raise HTTPException(500, f"Riva client failed: {result.stderr}")
            
            print(f"Riva client output: {result.stdout}")
            
            # Parse the JSON output from Riva client
            # The output contains JSON followed by "Final transcript: <text>"
            # We need to extract the JSON to get language and transcript
            try:
                # Find the JSON object (it starts with { and ends with })
                output = result.stdout.strip()
                
                # Try to find where JSON ends and "Final transcript" begins
                json_start = output.find('{')
                json_end = output.rfind('}') + 1
                
                if json_start != -1 and json_end > json_start:
                    json_str = output[json_start:json_end]
                    json_output = json.loads(json_str)
                    
                    if json_output and 'results' in json_output:
                        # Extract transcript and language from JSON
                        result_data = json_output['results'][0]
                        alternatives = result_data['alternatives'][0]
                        transcription = alternatives['transcript']
                        language_codes = alternatives.get('languageCode', [])
                        detected_language = language_codes[0] if language_codes else "unknown"
                        
                        print(f"Parsed transcription: {transcription[:100]}...")
                        print(f"Detected language: {detected_language}")
                    else:
                        # Fallback to entire output
                        transcription = output
                        detected_language = "unknown"
                        print(f"JSON parsing failed, using raw output")
                else:
                    # No JSON found, try to find "Final transcript:"
                    if "Final transcript:" in output:
                        transcription = output.split("Final transcript:")[-1].strip()
                        detected_language = "unknown"
                    else:
                        transcription = output
                        detected_language = "unknown"
                        print(f"JSON parsing failed, using raw output")
                
            except json.JSONDecodeError as e:
                # If JSON parsing fails, try to find "Final transcript:"
                output = result.stdout.strip()
                if "Final transcript:" in output:
                    transcription = output.split("Final transcript:")[-1].strip()
                    detected_language = "unknown"
                    print(f"JSON parsing failed ({e}), using final transcript line")
                else:
                    transcription = output
                    detected_language = "unknown"
                    print(f"JSON parsing failed ({e}), using raw output")
            
        finally:
            # Clean up temp file
            try:
                if os.path.exists(temp_filename):
                    os.unlink(temp_filename)
            except Exception as cleanup_error:
                print(f"Warning: Could not clean up temp file {temp_filename}: {cleanup_error}")
                
    except Exception as e:
        error_str = str(e)
        print(f"NVIDIA Riva API error: {error_str}")
        raise HTTPException(500, f"Speech-to-text failed: {error_str}")

    # Step 2: Apply language validation
    detected_language = validate_language(detected_language)
    
    # Step 3: Translation Gate - Conditional routing based on language
    text_for_ingestion = transcription
    translation_applied = False

    if detected_language != "en" and detected_language != "unknown":
        print(f"Detected non-English language: {detected_language}. Routing through Nemotron translation gate...")
        try:
            from app.layer2.shared.model_loader import get_nemotron_model
            nemotron = get_nemotron_model()
            
            # Translate and sanitize using Nemotron
            translated_text, safety_label = nemotron.translate_and_sanitize(transcription, detected_language)
            
            # Apply safety gate
            if safety_label == "unsafe":
                print(f"🚫 Safety gate blocked: {safety_label}")
                raise HTTPException(400, "Query blocked by safety filter")
            
            text_for_ingestion = translated_text
            translation_applied = True
            print(f"Nemotron translation applied: {transcription[:50]}... -> {translated_text[:50]}...")
            
        except Exception as e:
            print(f"Nemotron translation failed: {e}. Using original transcription.")
            # Fallback to original transcription if translation fails
            text_for_ingestion = transcription
    else:
        print(f"Detected English language. Direct flow to orchestrator.")

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

    # Step 5: Return orchestrator output
    return {
        "success": True,
        "transcription": transcription,
        "detected_language": detected_language,
        "translation_applied": translation_applied,
        "text_for_ingestion": text_for_ingestion,
        "conversation_id": str(state.conversation_id),
        "orchestrator_output": {
            "intent": result_state.intent,
            "category": result_state.intent_category,
            "confidence": result_state.orchestrator_context.get("confidence", 0.0),
            "extraction_method": result_state.orchestrator_context.get("extraction_method", "unknown"),
            "model_used": result_state.orchestrator_context.get("model_used", "unknown"),
            "required_agents": result_state.required_agents,
            "mission_briefs": result_state.mission_brief,
            "final_response": result_state.final_response_en
        }
    }


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
        print(f"Original text: {repr(req.text)}")
        print(f"Text type: {type(req.text)}")
        
        # Ensure text is properly encoded for display
        display_text = req.text
        if isinstance(req.text, str):
            # Handle potential encoding issues
            try:
                display_text = req.text.encode('utf-8', errors='replace').decode('utf-8')
            except UnicodeEncodeError as e:
                print(f"Encoding error: {e}")
                display_text = req.text  # Fallback to original
        
        print(f"TTS Request: text='{display_text}', language='{req.language}'")
        print(f"Available models: {list(ml_models.keys())}")
    except Exception as e:
        print(f"Text processing error: {e}")
        print(f"TTS Request: text='{req.text}', language='{req.language}'")
        print(f"Available models: {list(ml_models.keys())}")

    if req.language == "ar":
        # Use Habibi-TTS as primary method for Arabic text
        habibi = ml_models.get("tts_habibi")
        if habibi is not None:
            try:
                print("Using Habibi-TTS for Arabic TTS...")
                wav, sr, _ = habibi.infer(
                    ref_file=None,  # Don't require reference file
                    ref_text="",
                    gen_text=req.text,
                )
                audio_data = wav
                sample_rate = sr
                model_used = "habibi-tts (ALG)"
                print(f"Arabic TTS generated with Habibi: shape={audio_data.shape if hasattr(audio_data, 'shape') else 'unknown'}")
            except Exception as e:
                print(f"Habibi-TTS error: {e}")
                # Fall back to gTTS if Habibi fails
                print("Falling back to gTTS for Arabic TTS...")
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
                        print(f"Arabic TTS generated with gTTS fallback: shape={audio_data.shape}, sample_rate={sample_rate}")
                        
                    finally:
                        # Clean up temp file with proper error handling
                        try:
                            if os.path.exists(temp_filename):
                                os.unlink(temp_filename)
                                print(f"Cleaned up temp file: {temp_filename}")
                        except Exception as cleanup_error:
                            print(f"Warning: Could not clean up temp file {temp_filename}: {cleanup_error}")
                            
                except ImportError:
                    print("gTTS not available, falling back to Kokoro with transliteration")
                    # Final fallback to Kokoro English for Arabic text
                    kokoro = ml_models.get("tts_kokoro_en")
                    if kokoro is None:
                        raise HTTPException(503, "No TTS models available for Arabic")
                    
                    try:
                        print("Generating Arabic TTS with Kokoro English fallback...")
                        generator = kokoro(req.text, voice="af_heart")
                        chunks = []
                        for i, (phonemes, duration, audio) in enumerate(generator):
                            print(f"Chunk {i}: audio shape={audio.shape if hasattr(audio, 'shape') else 'unknown'}")
                            chunks.append(audio)
                        
                        if not chunks:
                            raise HTTPException(500, "No audio chunks generated for Arabic fallback")
                        
                        audio_data = np.concatenate(chunks)
                        model_used = "kokoro-82m (EN fallback for Arabic)"
                        print(f"Arabic fallback TTS generated: shape={audio_data.shape}, chunks={len(chunks)}")
                    except Exception as e:
                        print(f"Arabic fallback TTS error: {e}")
                        raise HTTPException(500, f"Arabic TTS fallback failed: {str(e)}")
        else:
            # Habibi-TTS not available, use gTTS as primary
            print("Habibi-TTS not available, using gTTS for Arabic TTS...")
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
                    print(f"Arabic TTS generated with gTTS: shape={audio_data.shape}, sample_rate={sample_rate}")
                    
                finally:
                    # Clean up temp file with proper error handling
                    try:
                        if os.path.exists(temp_filename):
                            os.unlink(temp_filename)
                            print(f"Cleaned up temp file: {temp_filename}")
                    except Exception as cleanup_error:
                        print(f"Warning: Could not clean up temp file {temp_filename}: {cleanup_error}")
                        
            except ImportError:
                print("gTTS not available, falling back to Kokoro with transliteration")
                # Final fallback to Kokoro English for Arabic text
                kokoro = ml_models.get("tts_kokoro_en")
                if kokoro is None:
                    raise HTTPException(503, "No TTS models available for Arabic")
                
                try:
                    print("Generating Arabic TTS with Kokoro English fallback...")
                    generator = kokoro(req.text, voice="af_heart")
                    chunks = []
                    for i, (phonemes, duration, audio) in enumerate(generator):
                        print(f"Chunk {i}: audio shape={audio.shape if hasattr(audio, 'shape') else 'unknown'}")
                        chunks.append(audio)
                    
                    if not chunks:
                        raise HTTPException(500, "No audio chunks generated for Arabic fallback")
                    
                    audio_data = np.concatenate(chunks)
                    model_used = "kokoro-82m (EN fallback for Arabic)"
                    print(f"Arabic fallback TTS generated: shape={audio_data.shape}, chunks={len(chunks)}")
                except Exception as e:
                    print(f"Arabic fallback TTS error: {e}")
                    raise HTTPException(500, f"Arabic TTS fallback failed: {str(e)}")

    elif req.language == "fr":
        kokoro = ml_models.get("tts_kokoro_fr")
        if kokoro is None:
            raise HTTPException(503, "Kokoro FR not loaded")
        try:
            print("Generating French TTS...")
            generator = kokoro(req.text, voice="ff_siwis")
            chunks = []
            for i, (phonemes, duration, audio) in enumerate(generator):
                print(f"Chunk {i}: audio shape={audio.shape if hasattr(audio, 'shape') else 'unknown'}")
                chunks.append(audio)
            
            if not chunks:
                raise HTTPException(500, "No audio chunks generated")
            
            audio_data = np.concatenate(chunks)
            model_used = "kokoro-82m (FR)"
            print(f"French TTS generated: shape={audio_data.shape}, chunks={len(chunks)}")
        except Exception as e:
            print(f"French TTS error: {e}")
            raise HTTPException(500, f"French TTS failed: {str(e)}")

    else:
        kokoro = ml_models.get("tts_kokoro_en")
        if kokoro is None:
            raise HTTPException(503, "Kokoro EN not loaded")
        try:
            print("Generating English TTS...")
            generator = kokoro(req.text, voice="af_heart")
            chunks = []
            for i, (phonemes, duration, audio) in enumerate(generator):
                print(f"Chunk {i}: audio shape={audio.shape if hasattr(audio, 'shape') else 'unknown'}")
                chunks.append(audio)
            
            if not chunks:
                raise HTTPException(500, "No audio chunks generated")
            
            audio_data = np.concatenate(chunks)
            model_used = "kokoro-82m (EN)"
            print(f"English TTS generated: shape={audio_data.shape}, chunks={len(chunks)}")
        except Exception as e:
            print(f"English TTS error: {e}")
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
    from app.main import ml_models
    from app.layer1.ingestion import ingest_chat_request
    from app.layer2.orchestrator import smart_pm_routing
    from app.layer2.knowledgebase.intelligent_rag_system import IntelligentRAGSystem
    from app.layer2.shared.session_manager import create_session, get_session, add_to_history
    from app.schemas.conversation import ChatRequest, SourceChannel

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

    # Step 1: Load and transcribe audio using Layer 1 STT
    if not ml_models.get("stt_whisper"):
        raise HTTPException(503, "Whisper not configured")

    transcription = None
    detected_language = "unknown"
    
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
            sf.write(temp_filename, audio_array, sample_rate, format="WAV")
            
            print(f"Audio file written: {temp_filename}, sample_rate: {sample_rate}")
            print(f"Sending request to NVIDIA Riva gRPC API")
            
            # Clone Riva Python clients if not already present
            project_root = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
            riva_clients_dir = os.path.join(project_root, "python-clients")
            if not os.path.exists(riva_clients_dir):
                print(f"Cloning NVIDIA Riva Python clients to {riva_clients_dir}")
                subprocess.run(
                    ["git", "clone", "https://github.com/nvidia-riva/python-clients.git", riva_clients_dir],
                    check=True, capture_output=True
                )
            
            # Path to the transcribe script
            transcribe_script = os.path.join(riva_clients_dir, "scripts", "asr", "transcribe_file_offline.py")
            
            if not os.path.exists(transcribe_script):
                raise HTTPException(500, f"Riva client script not found at {transcribe_script}")
            
            # Build command for NVIDIA Riva client
            cmd = [
                sys.executable,
                transcribe_script,
                "--server", "grpc.nvcf.nvidia.com:443",
                "--use-ssl",
                "--metadata", "function-id", "b702f636-f60c-4a3d-a6f4-f3568c13bd7d",
                "--metadata", "authorization", f"Bearer {api_key}",
                "--language-code", "multi",  # Auto language detection
                "--input-file", temp_filename
            ]
            
            print(f"Running command: {' '.join(cmd)}")
            
            # Set environment variables for subprocess
            env = os.environ.copy()
            env['PYTHONHASHSEED'] = 'random'
            env['PYTHONIOENCODING'] = 'utf-8'
            
            # Run the command with UTF-8 encoding
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=60, env=env, encoding='utf-8', errors='replace')
            
            if result.returncode != 0:
                print(f"Riva client error: {result.stderr}")
                stderr_lower = result.stderr.lower() if result.stderr else ""
                stdout_lower = result.stdout.lower() if result.stdout else ""
                
                error_keywords = ["failed", "error", "unknown", "timeout", "handshaker", "connect", "grpc", "exception"]
                
                is_stt_error = any(keyword in stderr_lower for keyword in error_keywords) or any(keyword in stdout_lower for keyword in error_keywords)
                
                if is_stt_error:
                    print(f" STT Error detected: {result.stderr}")
                    return {
                        "success": False,
                        "error": "STT service unavailable. Please try again.",
                        "stage": "whisper_stt"
                    }
                else:
                    raise HTTPException(500, f"Riva client failed: {result.stderr}")
            
            print(f"Riva client output: {result.stdout}")
            
            # Parse the JSON output from Riva client
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
                        
                        print(f"Parsed transcription: {transcription[:100]}...")
                        print(f"Detected language: {detected_language}")
                    else:
                        transcription = output
                        detected_language = "unknown"
                        print(f"JSON parsing failed, using raw output")
                else:
                    if "Final transcript:" in output:
                        transcription = output.split("Final transcript:")[-1].strip()
                        detected_language = "unknown"
                    else:
                        transcription = output
                        detected_language = "unknown"
                        print(f"JSON parsing failed, using raw output")
                
            except json.JSONDecodeError as e:
                output = result.stdout.strip()
                if "Final transcript:" in output:
                    transcription = output.split("Final transcript:")[-1].strip()
                    detected_language = "unknown"
                    print(f"JSON parsing failed ({e}), using final transcript line")
                else:
                    transcription = output
                    detected_language = "unknown"
                    print(f"JSON parsing failed ({e}), using raw output")
            
        finally:
            # Clean up temp file
            try:
                if os.path.exists(temp_filename):
                    os.unlink(temp_filename)
            except Exception as cleanup_error:
                print(f"Warning: Could not clean up temp file {temp_filename}: {cleanup_error}")

        # Store STT results
        results["stages"]["whisper_stt"] = {
            "success": True,
            "model": "whisper-large-v3-nvidia-riva",
            "detected_language": detected_language,
            "transcription": transcription,
            "processing_time": "N/A"
        }
                
    except Exception as e:
        error_str = str(e)
        print(f"NVIDIA Riva API error: {error_str}")
        results["stages"]["whisper_stt"] = {
            "success": False,
            "error": error_str
        }
        raise HTTPException(500, f"Speech-to-text failed: {error_str}")

    # Step 2: Apply language validation
    detected_language = validate_language(detected_language)
    
    # Step 3: Translation Gate - Conditional routing based on language
    text_for_ingestion = transcription
    translation_applied = False

    if detected_language != "en" and detected_language != "unknown":
        print(f"Detected non-English language: {detected_language}. Routing through Nemotron translation gate...")
        try:
            from app.layer2.shared.model_loader import get_nemotron_model
            nemotron = get_nemotron_model()
            
            # Translate and sanitize using Nemotron
            translated_text, safety_label = nemotron.translate_and_sanitize(transcription, detected_language)
            
            # Apply safety gate
            if safety_label == "unsafe":
                print(f"🚫 Safety gate blocked: {safety_label}")
                raise HTTPException(400, "Query blocked by safety filter")
            
            text_for_ingestion = translated_text
            translation_applied = True
            print(f"Nemotron translation applied: {transcription[:50]}... -> {translated_text[:50]}...")
            
            results["stages"]["translator"] = {
                "success": True,
                "translation_applied": True,
                "model": "nemotron",
                "source_language": detected_language,
                "target_language": "en",
                "original_text": transcription,
                "translated_text": translated_text
            }
            
        except Exception as e:
            print(f"Nemotron translation failed: {e}. Using original transcription.")
            text_for_ingestion = transcription
            results["stages"]["translator"] = {
                "success": False,
                "error": str(e),
                "fallback_used": True
            }
    else:
        print(f"Detected English language. Direct flow to orchestrator.")
        results["stages"]["translator"] = {
            "success": True,
            "translation_applied": False,
            "reason": f"Language already English or unknown: {detected_language}"
        }

    # Security Layer 1: Input validation before ingestion
    try:
        from app.security_layer1.security_screening import scan_input
        security_check = scan_input(text_for_ingestion)
        
        if not security_check["is_safe"]:
            logger.warning(f"[Security-L1] Blocked: {security_check['reason']}")
            return {
                "success": False,
                "blocked": True,
                "message": security_check["reason"]
            }
        
        results["stages"]["security_layer1"] = {
            "success": True,
            "is_safe": True,
            "risk_score": security_check["risk_score"]
        }
    except Exception as e:
        logger.error(f"[Security-L1] ERROR: {str(e)}")
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

    # Step 4: Pass to Layer 2 Orchestrator
    try:
        result_state = smart_pm_routing(state)
        
        results["stages"]["orchestrator"] = {
            "success": True,
            "intent": result_state.intent,
            "category": result_state.intent_category,
            "confidence": result_state.orchestrator_context.get("confidence", 0.0),
            "extraction_method": result_state.orchestrator_context.get("extraction_method", "unknown"),
            "model_used": result_state.orchestrator_context.get("model_used", "unknown"),
            "required_agents": result_state.required_agents,
            "final_response": result_state.final_response_en
        }
        
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
                logger.error(f"[Security-L2] ERROR: {str(e)}")
                results["stages"]["security_layer2"] = {
                    "success": False,
                    "error": str(e)
                }
            
            # Step 2: Translate back to user's original language
            from app.layer3.translation.translator import translate_from_english
            localized_response = translate_from_english(
                english_response, 
                detected_language  # "fr" or "ar" from STT stage
            )
            logger.debug(f"[Layer3] Localized response: {localized_response}")
            
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
            
            # Step 4: Add audio to pipeline response
            if audio_state.final_response_audio:
                # Encode binary audio data as base64 for JSON serialization
                import base64
                audio_base64 = base64.b64encode(audio_state.final_response_audio).decode('utf-8')
                
                results["final_response_audio"] = audio_base64
                results["audio_model_used"] = audio_state.audio_model_used
                results["audio_sample_rate"] = audio_state.audio_sample_rate
                results["final_response_localized"] = audio_state.final_response_localized
                logger.debug(f"[Layer3] Audio generated: {len(audio_state.final_response_audio)} bytes")
                
                # Step 4.5: Add to conversation history
                add_to_history(session_id, text_for_ingestion, localized_response or english_response)
        
    except Exception as e:
        results["stages"]["orchestrator"] = {
            "success": False,
            "error": str(e)
        }
        raise HTTPException(500, f"Orchestrator processing failed: {str(e)}")

    # Step 5: Knowledge Base Query
    try:
        # Initialize knowledge base system
        kb_system = IntelligentRAGSystem()
        
        # Load documents synchronously before querying
        import asyncio
        if asyncio.iscoroutinefunction(kb_system.load_documents):
            await kb_system.load_documents()
        else:
            kb_system.load_documents()
        
        # Query knowledge base with original transcription
        if asyncio.iscoroutinefunction(kb_system.ask_question):
            kb_result = await kb_system.ask_question(transcription)
        else:
            kb_result = kb_system.ask_question(transcription)
        
        results["stages"]["knowledge_base"] = {
            "success": True,
            "answer": kb_result.get("answer", "No answer available"),
            "sources": kb_result.get("sources", []),
            "confidence": kb_result.get("confidence", 0.0),
            "documents_found": kb_result.get("documents_found", 0),
            "needs_clarification": kb_result.get("needs_clarification", False)
        }
        
    except Exception as e:
        print(f"Knowledge base error: {e}")
        results["stages"]["knowledge_base"] = {
            "success": False,
            "error": str(e),
            "fallback_answer": "Knowledge base temporarily unavailable"
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