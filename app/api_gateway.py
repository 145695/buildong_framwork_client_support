"""
API Gateway - Routes between services and handles WebSocket connections.
Lightweight container that coordinates the other 3 services.
"""
import os
import json
import io
import asyncio
import httpx
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException, UploadFile, File, Form
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from typing import Optional

app = FastAPI(title="MACES API Gateway")

# Service URLs (containers communicate via localhost)
VOICE_SERVICE = os.getenv("VOICE_SERVICE_URL", "http://localhost:8001")
LLM_SERVICE = os.getenv("LLM_SERVICE_URL", "http://localhost:8002")
KB_SERVICE = os.getenv("KB_SERVICE_URL", "http://localhost:8003")

# HTTP client with connection pooling
client = httpx.AsyncClient(
    limits=httpx.Limits(max_keepalive_connections=20, max_connections=100),
    timeout=httpx.Timeout(120.0)
)

# Add CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Serve static files
app.mount("/static", StaticFiles(directory="app/static"), name="static")


@app.get("/")
async def index():
    """Serve landing page"""
    html_path = os.path.join(os.path.dirname(__file__), "templates", "index.html")
    with open(html_path, "r", encoding="utf-8") as f:
        return HTMLResponse(content=f.read())


@app.get("/call")
async def call_page():
    """Serve call interface"""
    html_path = os.path.join(os.path.dirname(__file__), "templates", "voice_lab_complete.html")
    with open(html_path, "r", encoding="utf-8") as f:
        return HTMLResponse(content=f.read())


@app.post("/session/create")
async def create_session():
    """Create new session"""
    from app.layer2.shared.session_manager import create_session
    session_id = create_session()
    return {"session_id": session_id}


@app.websocket("/ws/audio/{session_id}")
async def websocket_audio(websocket: WebSocket, session_id: str):
    """WebSocket endpoint - coordinates between services"""
    from app.layer2.shared.session_manager import session_manager
    from app.layer1.audio_processor import AudioProcessor
    from app.layer1.vad_engine import VADEngine
    
    if session_id not in session_manager.sessions:
        await websocket.close(code=1008)
        return
    
    await websocket.accept()
    processor = AudioProcessor(vad_engine=VADEngine())
    session_manager.update_audio_state(session_id, "RECORDING")
    await websocket.send_json({"type": "status", "state": "RECORDING"})
    
    try:
        while True:
            msg = await websocket.receive()
            
            if msg.get('type') == 'websocket.disconnect':
                break
            
            # Handle binary audio
            if isinstance(msg.get('bytes'), (bytes, bytearray)):
                processor.process_frame(msg.get('bytes'))
                continue
            
            # Handle JSON control messages
            if isinstance(msg.get('text'), str):
                try:
                    data = json.loads(msg.get('text'))
                except:
                    continue
                
                if data.get('type') == 'end_of_speech':
                    session_manager.update_audio_state(session_id, "PROCESSING")
                    await websocket.send_json({"type": "status", "state": "PROCESSING"})
                    
                    audio_data = processor.get_accumulated_audio()
                    
                    if len(audio_data) == 0:
                        await websocket.send_json({"type": "error", "message": "No speech detected"})
                        processor.reset()
                        continue
                    
                    # Convert to WAV
                    import wave
                    pcm_bytes = audio_data.tobytes()
                    wav_buffer = io.BytesIO()
                    with wave.open(wav_buffer, 'wb') as wav_file:
                        wav_file.setnchannels(1)
                        wav_file.setsampwidth(2)
                        wav_file.setframerate(16000)
                        wav_file.writeframes(pcm_bytes)
                    wav_buffer.seek(0)
                    
                    # NOW CALL SERVICES IN PARALLEL!
                    try:
                        # Send audio to voice service for STT
                        voice_response = await client.post(
                            f"{VOICE_SERVICE}/stt",
                            files={"audio": ("audio.wav", wav_buffer.read(), "audio/wav")}
                        )
                        stt_result = voice_response.json()
                        
                        transcription = stt_result.get("transcription", "")
                        detected_language = stt_result.get("detected_language", "fr")
                        
                        # Send status
                        await websocket.send_json({
                            "type": "status_update",
                            "stage": "stt_complete",
                            "message": f"Transcribed: {transcription}",
                            "language": detected_language
                        })
                        
                        # Translate if needed (voice service)
                        if detected_language != "en":
                            translate_response = await client.post(
                                f"{VOICE_SERVICE}/translate",
                                json={
                                    "text": transcription,
                                    "source_language": detected_language,
                                    "target_language": "en"
                                }
                            )
                            translated = translate_response.json()
                            text_for_processing = translated.get("translated_text", transcription)
                        else:
                            text_for_processing = transcription
                        
                        # SECURITY CHECK + KB SEARCH + LLM PROCESSING - ALL IN PARALLEL!
                        security_task = client.post(
                            f"{LLM_SERVICE}/security/check",
                            json={"text": text_for_processing}
                        )
                        kb_task = client.post(
                            f"{KB_SERVICE}/search",
                            json={"query": transcription, "language": detected_language}
                        )
                        
                        # Wait for both
                        security_resp, kb_resp = await asyncio.gather(security_task, kb_task)
                        
                        security = security_resp.json()
                        kb = kb_resp.json()
                        
                        await websocket.send_json({
                            "type": "status_update",
                            "stage": "kb_complete",
                            "message": f"KB found: {kb.get('documents_found', 0)} documents",
                            "language": detected_language
                        })
                        
                        # Process with agent
                        agent_response = await client.post(
                            f"{LLM_SERVICE}/agent/process",
                            json={
                                "message": text_for_processing,
                                "source_language": detected_language,
                                "session_id": session_id
                            }
                        )
                        agent_result = agent_response.json()
                        
                        # Generate TTS for response
                        tts_response = await client.post(
                            f"{VOICE_SERVICE}/tts",
                            json={
                                "text": agent_result.get("response", ""),
                                "language": detected_language
                            }
                        )
                        tts_result = tts_response.json()
                        
                        # Send final result
                        await websocket.send_json({
                            "type": "pipeline_result",
                            "data": {
                                "success": True,
                                "transcription": transcription,
                                "detected_language": detected_language,
                                "kb_answer": kb.get("answer", ""),
                                "agent_response": agent_result.get("response", ""),
                                "final_response_audio": tts_result.get("audio_base64", ""),
                                "audio_model_used": tts_result.get("model_used", ""),
                            }
                        })
                        
                    except Exception as e:
                        await websocket.send_json({"type": "error", "message": str(e)})
                    
                    processor.reset()
                    session_manager.update_audio_state(session_id, "RECORDING")
                    await websocket.send_json({"type": "status", "state": "RECORDING"})
    
    except WebSocketDisconnect:
        pass
    finally:
        session_manager.update_audio_state(session_id, "IDLE")


@app.get("/health")
async def health():
    """Check health of all services"""
    services = {}
    try:
        resp = await client.get(f"{VOICE_SERVICE}/health")
        services["voice"] = "healthy" if resp.status_code == 200 else "unhealthy"
    except:
        services["voice"] = "unavailable"
    
    try:
        resp = await client.get(f"{LLM_SERVICE}/health")
        services["llm"] = "healthy" if resp.status_code == 200 else "unhealthy"
    except:
        services["llm"] = "unavailable"
    
    try:
        resp = await client.get(f"{KB_SERVICE}/health")
        services["kb"] = "healthy" if resp.status_code == 200 else "unhealthy"
    except:
        services["kb"] = "unavailable"
    
    return {"status": "healthy", "service": "api-gateway", "services": services}


@app.on_event("shutdown")
async def shutdown():
    await client.aclose()