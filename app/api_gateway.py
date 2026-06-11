"""
API Gateway - Routes between services and handles WebSocket connections.
All audio/VAD processing is delegated to voice-service.
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

# Service URLs
VOICE_SERVICE = os.getenv("VOICE_SERVICE_URL", "http://localhost:8001")
LLM_SERVICE = os.getenv("LLM_SERVICE_URL", "http://localhost:8002")
KB_SERVICE = os.getenv("KB_SERVICE_URL", "http://localhost:8003")

# HTTP client
client = httpx.AsyncClient(
    limits=httpx.Limits(max_keepalive_connections=20, max_connections=100),
    timeout=httpx.Timeout(120.0)
)

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
    html_path = os.path.join(os.path.dirname(__file__), "templates", "index.html")
    with open(html_path, "r", encoding="utf-8") as f:
        return HTMLResponse(content=f.read())


@app.get("/call")
async def call_page():
    html_path = os.path.join(os.path.dirname(__file__), "templates", "voice_lab_complete.html")
    with open(html_path, "r", encoding="utf-8") as f:
        return HTMLResponse(content=f.read())


@app.post("/session/create")
async def create_session():
    from app.layer2.shared.session_manager import create_session
    session_id = create_session()
    return {"session_id": session_id}


@app.websocket("/ws/audio/{session_id}")
async def websocket_audio(websocket: WebSocket, session_id: str):
    """WebSocket endpoint - delegates all processing to microservices"""
    from app.layer2.shared.session_manager import session_manager
    
    if session_id not in session_manager.sessions:
        await websocket.close(code=1008)
        return
    
    await websocket.accept()
    
    # Audio buffer
    audio_buffer = io.BytesIO()
    is_recording = False
    
    await websocket.send_json({"type": "status", "state": "READY"})
    
    try:
        while True:
            msg = await websocket.receive()
            
            if msg.get('type') == 'websocket.disconnect':
                break
            
            # Binary audio - accumulate
            if isinstance(msg.get('bytes'), (bytes, bytearray)):
                if not is_recording:
                    is_recording = True
                    await websocket.send_json({"type": "status", "state": "RECORDING"})
                audio_buffer.write(msg.get('bytes'))
                continue
            
            # JSON control messages
            if isinstance(msg.get('text'), str):
                try:
                    data = json.loads(msg.get('text'))
                except:
                    continue
                
                if data.get('type') == 'end_of_speech':
                    await websocket.send_json({"type": "status", "state": "PROCESSING"})
                    
                    audio_buffer.seek(0)
                    audio_data = audio_buffer.read()
                    audio_buffer = io.BytesIO()  # Reset
                    is_recording = False
                    
                    if len(audio_data) < 1000:
                        await websocket.send_json({"type": "error", "message": "No speech detected"})
                        await websocket.send_json({"type": "status", "state": "READY"})
                        continue
                    
                    try:
                        # STEP 1: Send audio to Voice Service for STT
                        stt_resp = await client.post(
                            f"{VOICE_SERVICE}/stt",
                            files={"audio": ("audio.webm", audio_data, "audio/webm")}
                        )
                        stt = stt_resp.json()
                        transcription = stt.get("transcription", "")
                        detected_language = stt.get("detected_language", "fr")
                        
                        await websocket.send_json({
                            "type": "status_update",
                            "stage": "stt",
                            "message": f"Transcription: {transcription}",
                            "language": detected_language
                        })
                        
                        # STEP 2: Translate if needed (via Voice Service)
                        if detected_language != "en" and detected_language != "unknown":
                            trans_resp = await client.post(
                                f"{VOICE_SERVICE}/translate",
                                json={
                                    "text": transcription,
                                    "source_language": detected_language,
                                    "target_language": "en"
                                }
                            )
                            trans = trans_resp.json()
                            text_for_processing = trans.get("translated_text", transcription)
                        else:
                            text_for_processing = transcription
                        
                        await websocket.send_json({
                            "type": "status_update",
                            "stage": "translate",
                            "message": "Translation complete",
                            "language": detected_language
                        })
                        
                        # STEP 3: Security Check + KB Search IN PARALLEL
                        security_task = client.post(
                            f"{LLM_SERVICE}/security/check",
                            json={"text": text_for_processing}
                        )
                        kb_task = client.post(
                            f"{KB_SERVICE}/search",
                            json={"query": transcription, "language": detected_language}
                        )
                        
                        security_resp, kb_resp = await asyncio.gather(security_task, kb_task)
                        security = security_resp.json()
                        kb = kb_resp.json()
                        
                        if not security.get("is_safe", True):
                            await websocket.send_json({
                                "type": "error",
                                "message": security.get("reason", "Content blocked by security")
                            })
                            await websocket.send_json({"type": "status", "state": "READY"})
                            continue
                        
                        await websocket.send_json({
                            "type": "status_update",
                            "stage": "kb",
                            "message": f"Found {kb.get('documents_found', 0)} documents",
                            "language": detected_language
                        })
                        
                        # STEP 4: Process with LLM Agent
                        agent_resp = await client.post(
                            f"{LLM_SERVICE}/agent/process",
                            json={
                                "message": text_for_processing,
                                "source_language": detected_language,
                                "session_id": session_id
                            }
                        )
                        agent = agent_resp.json()
                        
                        await websocket.send_json({
                            "type": "status_update",
                            "stage": "agent",
                            "message": "Generating response...",
                            "language": detected_language
                        })
                        
                        # STEP 5: Generate TTS
                        tts_resp = await client.post(
                            f"{VOICE_SERVICE}/tts",
                            json={
                                "text": agent.get("response", "I'm sorry, I couldn't process that."),
                                "language": detected_language
                            }
                        )
                        tts = tts_resp.json()
                        
                        # Send final result
                        await websocket.send_json({
                            "type": "pipeline_result",
                            "data": {
                                "success": True,
                                "transcription": transcription,
                                "detected_language": detected_language,
                                "kb_answer": kb.get("answer", ""),
                                "agent_response": agent.get("response", ""),
                                "final_response_audio": tts.get("audio_base64", ""),
                                "audio_model_used": tts.get("model_used", ""),
                            }
                        })
                        
                    except Exception as e:
                        import traceback
                        traceback.print_exc()
                        await websocket.send_json({"type": "error", "message": str(e)})
                    
                    await websocket.send_json({"type": "status", "state": "READY"})
    
    except WebSocketDisconnect:
        pass


@app.get("/health")
async def health():
    services = {}
    for name, url in [("voice", VOICE_SERVICE), ("llm", LLM_SERVICE), ("kb", KB_SERVICE)]:
        try:
            resp = await client.get(f"{url}/health", timeout=5)
            services[name] = "healthy" if resp.status_code == 200 else "unhealthy"
        except:
            services[name] = "unavailable"
    return {"status": "healthy", "service": "api-gateway", "services": services}


@app.on_event("shutdown")
async def shutdown():
    await client.aclose()