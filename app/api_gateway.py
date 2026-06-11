"""
API Gateway - Keeps WebSocket handling, delegates to services.
Uses voice_service for STT/TTS, llm_service for agents, kb_service for search.
"""
import os
import json
import io
import asyncio
import httpx
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, UploadFile, File
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI(title="MACES API Gateway")

VOICE_SERVICE = os.getenv("VOICE_SERVICE_URL", "http://localhost:8001")
LLM_SERVICE = os.getenv("LLM_SERVICE_URL", "http://localhost:8002")
KB_SERVICE = os.getenv("KB_SERVICE_URL", "http://localhost:8003")

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
    """WebSocket - uses voice_service for STT/TTS, delegates everything else"""
    from app.layer2.shared.session_manager import session_manager
    
    if session_id not in session_manager.sessions:
        await websocket.close(code=1008)
        return
    
    await websocket.accept()
    
    # Audio accumulation
    audio_chunks = []
    session_manager.update_audio_state(session_id, "RECORDING")
    await websocket.send_json({"type": "status", "state": "RECORDING"})
    
    try:
        while True:
            msg = await websocket.receive()
            
            if msg.get('type') == 'websocket.disconnect':
                break
            
            # Binary audio - accumulate
            if isinstance(msg.get('bytes'), (bytes, bytearray)):
                audio_chunks.append(msg.get('bytes'))
                continue
            
            # Control messages
            if isinstance(msg.get('text'), str):
                try:
                    data = json.loads(msg.get('text'))
                except:
                    continue
                
                if data.get('type') == 'end_of_speech':
                    session_manager.update_audio_state(session_id, "PROCESSING")
                    await websocket.send_json({"type": "status", "state": "PROCESSING"})
                    
                    if not audio_chunks:
                        await websocket.send_json({"type": "error", "message": "No audio received"})
                        session_manager.update_audio_state(session_id, "RECORDING")
                        await websocket.send_json({"type": "status", "state": "RECORDING"})
                        continue
                    
                    # Combine all audio chunks
                    full_audio = b''.join(audio_chunks)
                    audio_chunks = []  # Reset
                    
                    try:
                        # === STEP 1: STT via Voice Service ===
                        await websocket.send_json({
                            "type": "status_update",
                            "stage": "stt",
                            "message": "Transcribing...",
                            "language": "fr"
                        })
                        
                        stt_resp = await client.post(
                            f"{VOICE_SERVICE}/stt",
                            files={"audio": ("audio.webm", full_audio, "audio/webm")}
                        )
                        stt = stt_resp.json()
                        transcription = stt.get("transcription", "")
                        detected_language = stt.get("detected_language", "fr")
                        
                        await websocket.send_json({
                            "type": "status_update",
                            "stage": "stt_complete",
                            "message": transcription,
                            "language": detected_language
                        })
                        
                        # === STEP 2: Translation if needed ===
                        text_for_processing = transcription
                        if detected_language != "en" and detected_language != "unknown":
                            await websocket.send_json({
                                "type": "status_update",
                                "stage": "translate",
                                "message": "Translating...",
                                "language": detected_language
                            })
                            
                            try:
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
                            except:
                                pass  # Keep original if translation fails
                        
                        # === STEP 3: Security + KB in PARALLEL ===
                        await websocket.send_json({
                            "type": "status_update",
                            "stage": "processing",
                            "message": "Searching knowledge base...",
                            "language": detected_language
                        })
                        
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
                                "message": security.get("reason", "Content blocked")
                            })
                            session_manager.update_audio_state(session_id, "RECORDING")
                            await websocket.send_json({"type": "status", "state": "RECORDING"})
                            continue
                        
                        await websocket.send_json({
                            "type": "status_update",
                            "stage": "kb_done",
                            "message": f"Found {kb.get('documents_found', 0)} relevant documents",
                            "language": detected_language
                        })
                        
                        # === STEP 4: Agent Processing ===
                        await websocket.send_json({
                            "type": "status_update",
                            "stage": "agent",
                            "message": "Generating response...",
                            "language": detected_language
                        })
                        
                        agent_resp = await client.post(
                            f"{LLM_SERVICE}/agent/process",
                            json={
                                "message": text_for_processing,
                                "source_language": detected_language,
                                "session_id": session_id
                            }
                        )
                        agent = agent_resp.json()
                        response_text = agent.get("response", "")
                        
                        # === STEP 5: TTS via Voice Service ===
                        await websocket.send_json({
                            "type": "status_update",
                            "stage": "tts",
                            "message": "Generating voice response...",
                            "language": detected_language
                        })
                        
                        tts_resp = await client.post(
                            f"{VOICE_SERVICE}/tts",
                            json={"text": response_text, "language": detected_language}
                        )
                        tts = tts_resp.json()
                        
                        # === DONE - Send result ===
                        await websocket.send_json({
                            "type": "pipeline_result",
                            "data": {
                                "success": True,
                                "transcription": transcription,
                                "detected_language": detected_language,
                                "kb_answer": kb.get("answer", ""),
                                "agent_response": response_text,
                                "final_response_audio": tts.get("audio_base64", ""),
                                "audio_model_used": tts.get("model_used", ""),
                            }
                        })
                        
                    except Exception as e:
                        import traceback
                        traceback.print_exc()
                        await websocket.send_json({"type": "error", "message": str(e)})
                    
                    session_manager.update_audio_state(session_id, "RECORDING")
                    await websocket.send_json({"type": "status", "state": "RECORDING"})
    
    except WebSocketDisconnect:
        pass
    finally:
        session_manager.update_audio_state(session_id, "IDLE")


@app.get("/health")
async def health():
    services = {}
    for name, url in [("voice", VOICE_SERVICE), ("llm", LLM_SERVICE), ("kb", KB_SERVICE)]:
        try:
            resp = await client.get(f"{url}/health", timeout=3)
            services[name] = "healthy" if resp.status_code == 200 else "unhealthy"
        except:
            services[name] = "unavailable"
    return {"status": "healthy", "service": "api-gateway", "services": services}


@app.on_event("shutdown")
async def shutdown():
    await client.aclose()