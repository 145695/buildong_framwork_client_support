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
    """
    WebSocket endpoint for audio streaming.
    
    Route: /ws/audio/{session_id}
    Handler:
      1. Validate session_id exists in existing session_manager
      2. Accept WebSocket connection
      3. Receive binary PCM audio chunks (16kHz, 16-bit mono)
      4. Accumulate audio frames in buffer
      5. Wait for end_of_speech JSON message from client
      6. On speech end → pass to existing STT pipeline
      7. Stream TTS response back as binary frames
    """
    # Validate session_id exists
    if session_id not in session_manager.sessions:
        await websocket.close(code=1008)
        return

    await websocket.accept()
    # Initialize processor with VAD
    processor = AudioProcessor(vad_engine=VADEngine())
    # Set initial state
    session_manager.update_audio_state(session_id, "RECORDING")
    await websocket.send_json({"type": "status", "state": "RECORDING"})

    try:
        while True:
            msg = await websocket.receive()
            # Handle disconnect messages gracefully
            if msg.get('type') == 'websocket.disconnect':
                break

            # Binary audio frame
            if msg.get('type') == 'websocket.receive' and isinstance(msg.get('bytes'), (bytes, bytearray)):
                data = msg.get('bytes')
                processor.process_frame(data)
                # Don't echo back audio - it causes JSON parse errors
                continue

            # Text/JSON control messages
            if msg.get('type') == 'websocket.receive' and isinstance(msg.get('text'), str):
                try:
                    data = json.loads(msg.get('text'))
                except Exception:
                    data = {}
                msg_type = data.get('type')
                if msg_type == 'end_of_speech' or processor.should_process():
                    # Bugfix: propagate follow-up state into the voice pipeline.
                    # Client should send it in the control message, e.g.:
                    # {"type": "end_of_speech", "is_followup": true}
                    is_followup = bool(data.get("is_followup", False))

                    session_manager.update_audio_state(session_id, "PROCESSING")
                    await websocket.send_json({"type": "status", "state": "PROCESSING"})
                    audio_data = processor.get_accumulated_audio()

                    # Check if any audio was captured
                    if len(audio_data) == 0:
                        await websocket.send_json({"type": "error", "message": "No speech detected. Please try speaking louder or closer to the microphone."})
                        processor.reset()
                        session_manager.update_audio_state(session_id, "RECORDING")
                        await websocket.send_json({"type": "status", "state": "RECORDING"})
                        continue

                    # Create callback for status updates from pipeline
                    async def status_callback(stage: str, message: str, language: str):
                        # Send text status update
                        await websocket.send_json({
                            "type": "status_update",
                            "stage": stage,
                            "message": message,
                            "language": language
                        })

                        # Generate and send TTS audio for status message
                        try:
                            from app.main import ml_models

                            # Select TTS model based on language
                            tts_audio_data = None
                            sample_rate = 24000

                            if language == "ar":
                                # Use gTTS for Arabic (F5TTS requires reference file which we don't have)
                                try:
                                    from gtts import gTTS
                                    tts = gTTS(text=message, lang='ar')
                                    wav_buffer = io.BytesIO()
                                    tts.write_to_fp(wav_buffer)
                                    wav_buffer.seek(0)
                                    # Convert MP3 to WAV using soundfile
                                    tts_audio_data, sample_rate = sf.read(wav_buffer)
                                    # Convert to mono if stereo
                                    if len(tts_audio_data.shape) > 1:
                                        tts_audio_data = tts_audio_data[:, 0]
                                except Exception as e:
                                    tts_audio_data = None
                            elif language == "fr":
                                # For French, use gTTS as fallback since Kokoro FR may not have good French voices
                                try:
                                    from gtts import gTTS
                                    tts = gTTS(text=message, lang='fr')
                                    wav_buffer = io.BytesIO()
                                    tts.write_to_fp(wav_buffer)
                                    wav_buffer.seek(0)
                                    # Convert MP3 to WAV using soundfile
                                    tts_audio_data, sample_rate = sf.read(wav_buffer)
                                    # Convert to mono if stereo
                                    if len(tts_audio_data.shape) > 1:
                                        tts_audio_data = tts_audio_data[:, 0]
                                except Exception as e:
                                    # Fallback to Kokoro EN
                                    kokoro_en = ml_models.get("tts_kokoro_en")
                                    if kokoro_en:
                                        generator = kokoro_en(message, voice="af_heart")
                                        chunks = []
                                        for i, (phonemes, duration, audio) in enumerate(generator):
                                            chunks.append(audio)
                                        if chunks:
                                            tts_audio_data = np.concatenate(chunks)
                                            sample_rate = 24000
                            else:
                                # Use Kokoro EN for English and others
                                kokoro_en = ml_models.get("tts_kokoro_en")
                                if kokoro_en:
                                    generator = kokoro_en(message, voice="af_heart")
                                    chunks = []
                                    for i, (phonemes, duration, audio) in enumerate(generator):
                                        chunks.append(audio)
                                    if chunks:
                                        tts_audio_data = np.concatenate(chunks)

                            if tts_audio_data is not None:
                                # Convert to WAV bytes
                                wav_buffer = io.BytesIO()
                                sf.write(wav_buffer, tts_audio_data, sample_rate, format="WAV")
                                wav_buffer.seek(0)
                                audio_bytes = wav_buffer.read()
                                # Send audio as base64
                                audio_base64 = base64.b64encode(audio_bytes).decode('utf-8')
                                await websocket.send_json({
                                    "type": "status_audio",
                                    "stage": stage,
                                    "audio": f"data:audio/wav;base64,{audio_base64}",
                                    "language": language
                                })
                        except Exception as e:
                            import traceback
                            traceback.print_exc()

                    # Convert numpy array to raw PCM bytes
                    pcm_bytes = audio_data.tobytes()
                    # Convert raw PCM to WAV format
                    wav_buffer = io.BytesIO()
                    with wave.open(wav_buffer, 'wb') as wav_file:
                        wav_file.setnchannels(1)  # Mono
                        wav_file.setsampwidth(2)  # 16-bit
                        wav_file.setframerate(16000)  # 16kHz
                        wav_file.writeframes(pcm_bytes)
                    wav_buffer.seek(0)
                    # Create an UploadFile-like object for the full pipeline endpoint
                    upload_file = UploadFile(filename="audio.wav", file=wav_buffer)
                    # Call the INTERNAL voice pipeline with status callback
                    from app.routers.voice import _voice_full_pipeline_internal
                    pipeline_result = await _voice_full_pipeline_internal(
                        upload_file,
                        session_id,
                        status_callback,
                        is_followup=is_followup,
                    )

                    print(f"[WebSocket] Pipeline result received, end_call={pipeline_result.get('end_call')}, redirect_url={pipeline_result.get('redirect_url')}")

                    # Send the complete pipeline results back to client
                    await websocket.send_json({
                        "type": "pipeline_result",
                        "data": pipeline_result
                    })
                    print(f"[WebSocket] pipeline_result message sent")

                    processor.reset()
                    session_manager.update_audio_state(session_id, "RECORDING")
                    await websocket.send_json({"type": "status", "state": "RECORDING"})
                    continue
    except WebSocketDisconnect:
        pass
    finally:
        session_manager.update_audio_state(session_id, "IDLE")