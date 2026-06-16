"""
WebSocket endpoint for real-time audio streaming.
"""

from fastapi import WebSocket, WebSocketDisconnect, APIRouter
from app.layer2.shared.session_manager import session_manager
from app.layer1.audio_processor import AudioProcessor
from app.layer1.vad_engine import VADEngine
from app.utils.status_messages import get_status_message
import json
import asyncio
import wave
import io
import numpy as np
import soundfile as sf
import base64
from starlette.datastructures import UploadFile

router = APIRouter()

@router.websocket("/ws/audio/{session_id}")
async def websocket_audio_endpoint(websocket: WebSocket, session_id: str):
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

            if msg.get('type') == 'websocket.receive' and isinstance(msg.get('bytes'), (bytes, bytearray)):
                data = msg.get('bytes')
                processor.process_frame(data)
                continue

            if msg.get('type') == 'websocket.receive' and isinstance(msg.get('text'), str):
                try:
                    data = json.loads(msg.get('text'))
                except Exception:
                    data = {}
                msg_type = data.get('type')
                if msg_type == 'end_of_speech' or processor.should_process():
                    is_followup = bool(data.get("is_followup", False))

                    session_manager.update_audio_state(session_id, "PROCESSING")
                    await websocket.send_json({"type": "status", "state": "PROCESSING"})
                    audio_data = processor.get_accumulated_audio()

                    if len(audio_data) == 0:
                        await websocket.send_json({"type": "error", "message": "No speech detected."})
                        processor.reset()
                        session_manager.update_audio_state(session_id, "RECORDING")
                        await websocket.send_json({"type": "status", "state": "RECORDING"})
                        continue

                    async def status_callback(stage: str, message: str, language: str):
                        await websocket.send_json({
                            "type": "status_update",
                            "stage": stage,
                            "message": message,
                            "language": language
                        })
                        try:
                            from app.main import ml_models
                            kokoro = ml_models.get("tts_kokoro_en")
                            if kokoro:
                                generator = kokoro(message, voice="af_heart")
                                chunks = [audio for _, _, audio in generator]
                                if chunks:
                                    tts_audio = np.concatenate(chunks)
                                    wav_buffer = io.BytesIO()
                                    sf.write(wav_buffer, tts_audio, 24000, format="WAV")
                                    wav_buffer.seek(0)
                                    audio_bytes = wav_buffer.read()
                                    audio_base64 = base64.b64encode(audio_bytes).decode('utf-8')
                                    await websocket.send_json({
                                        "type": "status_audio",
                                        "stage": stage,
                                        "audio": f"data:audio/wav;base64,{audio_base64}",
                                        "language": language
                                    })
                                    print(f"[CALLBACK] Audio sent: {message[:30]}...")
                        except Exception as e:
                            print(f"[CALLBACK] TTS error: {e}")

                    pcm_bytes = audio_data.tobytes()
                    wav_buffer = io.BytesIO()
                    with wave.open(wav_buffer, 'wb') as wav_file:
                        wav_file.setnchannels(1)
                        wav_file.setsampwidth(2)
                        wav_file.setframerate(16000)
                        wav_file.writeframes(pcm_bytes)
                    wav_buffer.seek(0)
                    upload_file = UploadFile(filename="audio.wav", file=wav_buffer)
                    
                    from app.routers.voice import _voice_full_pipeline_internal
                    pipeline_result = await _voice_full_pipeline_internal(
                        upload_file, session_id, status_callback, is_followup=is_followup,
                    )

                    print(f"[WebSocket] Pipeline result: end_call={pipeline_result.get('end_call')}")

                    await websocket.send_json({
                        "type": "pipeline_result",
                        "data": pipeline_result
                    })

                    processor.reset()
                    session_manager.update_audio_state(session_id, "RECORDING")
                    await websocket.send_json({"type": "status", "state": "RECORDING"})
                    continue
    except WebSocketDisconnect:
        pass
    finally:
        session_manager.update_audio_state(session_id, "IDLE")