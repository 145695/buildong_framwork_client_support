# Real-Time Audio Call Implementation Plan (REVISED)
## WebSocket-based Audio Streaming with Microphone Capture

**Timeline**: 5 days | **Status**: Ready for implementation | **Version**: 2.0

---

## 📋 Executive Summary

Replace file upload with **live microphone capture** via WebSocket.
Use browser-side WebRTC constraints for noise/echo cancellation.
Auto-detect speech end with VAD.
Integrate with existing session manager and voice pipeline.

---

## 🎯 Overview

### What's Happening
1. User clicks **"🎤 Hold to Speak"** button in voice-lab UI
2. Browser captures mic with noise suppression enabled (WebRTC)
3. Audio streams to server via WebSocket
4. Server detects silence with VAD
5. Server passes audio to **existing** voice pipeline (STT → NLP → TTS)
6. Response audio streams back to browser
7. User hears response automatically

### Architecture
```
BROWSER                              SERVER
┌─────────────────────┐             ┌──────────────────────┐
│  Microphone         │             │  WebSocket Endpoint  │
│  (Web Audio API)    ├── binary ──→│  /ws/audio/          │
│                     │             │  {session_id}        │
│  noiseSuppression ✓ │             │                      │
│  echoCancellation ✓ │             ├── VAD Engine         │
│  autoGainControl ✓  │             │   (silence detect)   │
└──────────┬──────────┘             │                      │
           │                        ├── Audio Buffer       │
           │                        │                      │
           │                        ├── EXISTING STT /     │
           │                        │   NLP / TTS          │
           │                        │   Pipeline           │
           │                        │                      │
           │◄── audio binary ───────┤  Stream TTS Response │
           │                        └──────────────────────┘
    ┌──────▼──────┐
    │ Web Audio   │
    │ playback    │
    └─────────────┘
```

---

## 📦 Phase 1: WebSocket + Browser Microphone (2 days)

### Goal
Replace file upload with live microphone capture.

### Backend — New Files

#### `app/routers/ws_audio.py`
```
WebSocket endpoint

Route: /ws/audio/{session_id}

Handler:
  1. Validate session_id exists in existing session_manager
  2. Accept WebSocket connection
  3. Receive binary PCM audio chunks (16kHz, 16-bit mono)
  4. Accumulate audio frames in buffer
  5. Wait for end_of_speech JSON message from client
  6. On speech end → pass to existing STT pipeline
  7. Stream TTS response back as binary frames
```

#### `app/layer1/audio_processor.py`
```
Simple audio buffering — NO noise cancellation

AudioBuffer:
  - add_frame(audio_bytes: bytes)
  - get_accumulated() → np.ndarray
  - get_duration_ms() → int
  - clear()

AudioProcessor:
  - process_frame(audio_bytes)
  - get_accumulated_audio() → np.ndarray
  - reset()
```

### Backend — Modified Files

#### `app/main.py`
```
Register WebSocket router:
  from app.routers.ws_audio import router as audio_router
  app.include_router(audio_router)
```

### Frontend — Modified Files

#### voice-lab UI (HTML/JS)
```
Replace:
  <input type="file" accept="audio/*">

With:
  <button id="mic-button">🎤 Hold to Speak</button>
  <div id="status">Ready...</div>

JavaScript logic:

  On button mousedown:
    - Request microphone with WebRTC constraints:
        noiseSuppression: true
        echoCancellation: true
        autoGainControl: true
        sampleRate: 16000
    - Create AudioContext (16kHz)
    - Create ScriptProcessor (chunk size 512)
    - Connect mic → processor → WebSocket
    - Open WebSocket to /ws/audio/{session_id}
    - Update UI: "🔴 Recording..."

  On each audio frame:
    - Convert Float32 to PCM16 (signed 16-bit)
    - Send as binary WebSocket frame

  On button mouseup:
    - Send JSON: {"type": "end_of_speech"}
    - Update UI: "⏳ Processing..."
    - Stop recording

  On response audio (binary frames):
    - Queue for playback
    - Play via Web Audio API
    - Update UI: "📢 Speaking..."

  On complete:
    - Reset UI to "Ready..."
```

### WebSocket Message Protocol
```
CLIENT → SERVER (binary):
  Raw PCM audio chunks

CLIENT → SERVER (JSON):
  {"type": "end_of_speech"}

SERVER → CLIENT (JSON):
  {"type": "status", "state": "RECORDING|PROCESSING|SPEAKING|ERROR"}
  {"type": "transcript", "text": "<STT result>"}
  {"type": "response_text", "text": "<LLM response>"}

SERVER → CLIENT (binary):
  TTS audio chunks
```

### Phase 1 Deliverables
- app/routers/ws_audio.py — WebSocket endpoint
- app/layer1/audio_processor.py — Audio buffering only
- app/main.py updated — router registered
- voice-lab UI updated — mic button + WebSocket streaming

---

## 🎙️ Phase 2: VAD + State Machine + Pipeline Integration (2 days)

### Goal
Automatic speech detection. Reuse existing session manager.
Connect to existing voice pipeline without rewriting it.

### Backend — New Files

#### `app/layer1/vad_engine.py`
```
Voice Activity Detection wrapper using webrtcvad

VADEngine:
  __init__(sample_rate=16000, frame_duration_ms=30, aggressiveness=2)
  is_speech(audio_frame: bytes) → bool
  reset()
```

### Backend — Modified Files

#### `app/layer1/audio_processor.py`
```
Add VAD integration to existing AudioProcessor:

  - add_frame(audio_bytes) → run VAD check
  - track consecutive silent frames
  - should_process() → bool
      returns True when > 1.2 seconds of silence detected
  - get_accumulated_audio() → np.ndarray
  - reset()
```

#### `app/routers/ws_audio.py`
```
Add state machine + VAD to WebSocket handler:

States: IDLE → RECORDING → PROCESSING → SPEAKING → IDLE

On connect:
  - Load EXISTING session from session_manager (not new session)
  - state = RECORDING
  - send {"type": "status", "state": "RECORDING"}

On audio frame:
  - Add to audio_processor
  - Run VAD check
  - If silence detected (1.2s):
      state = PROCESSING
      get accumulated audio
      call EXISTING STT function from voice.py
      → go to response handling

On STT result:
  - Add to EXISTING session history via session_manager
  - Call EXISTING security_layer1
  - Call EXISTING orchestrator
  - Get response text

On response ready:
  - state = SPEAKING
  - Call EXISTING TTS function from voice.py
  - Stream audio chunks back to client
  - state = RECORDING (loop back for next turn)

On disconnect:
  - Update session in EXISTING session_manager
  - Close gracefully
```

#### `app/layer2/shared/session_manager.py`
```
Add audio state fields to existing session dict:

sessions[session_id] = {
  "history": [...],          # existing — keep as is
  "last_active": time,       # existing — keep as is
  "created_at": time,        # existing — keep as is

  # NEW fields only:
  "audio_state": "IDLE",
  "is_audio_session": False,
}

Add two functions only:
  update_audio_state(session_id, new_state)
  get_audio_state(session_id) → str
```

### Integration with Existing Voice Pipeline
```
The WebSocket handler calls EXISTING functions from voice.py.
NO pipeline rewriting. Just call what already exists:

  1. STT:          existing Riva STT function → text
  2. Security L1:  existing scan_input() → screened text
  3. Translation:  existing translate_text() → English
  4. Orchestrator: existing router_node() → intent + routing
  5. KB + Agents:  existing graph execution → response text
  6. Security L2:  existing validate_output() → safe response
  7. Translation:  existing translate_from_english() → FR/AR
  8. TTS:          existing deliver_response() → audio bytes
  9. Stream:       send audio bytes back to client via WebSocket
```

### Phase 2 Deliverables
- app/layer1/vad_engine.py — VAD wrapper
- app/layer1/audio_processor.py updated — VAD integration
- app/routers/ws_audio.py updated — state machine + full pipeline
- app/layer2/shared/session_manager.py updated — audio state fields

---

## 🧪 Phase 3: Testing + Cleanup (1 day)

### Manual Testing Checklist
- Open UI → click Start Call → mic button appears
- Hold mic button → speak → release → hear response
- Speak again → session history used (query reconstruction works)
- Network disconnect → graceful recovery
- Empty speech → no processing triggered
- 5 min inactivity → session auto-expires
- Click End Call → back to landing page

### Unit Tests (tests/ folder)
```
test_vad_engine.py         — VAD on silence vs speech
test_audio_processor.py    — buffering + silence detection
test_ws_audio_connection.py — WebSocket connect/disconnect
test_audio_pipeline.py     — single turn end-to-end
test_audio_session.py      — multi-turn with history
```

### Cleanup
- Remove old file upload test routes if any
- Update requirements.txt
- Push to GitHub branch feature/full-pipeline-v3

---

## 📂 File Structure

### New Files
```
app/
├── layer1/
│   ├── vad_engine.py          ← Voice Activity Detection
│   └── audio_processor.py     ← Audio buffering + VAD
└── routers/
    └── ws_audio.py            ← WebSocket endpoint
```

### Modified Files
```
app/
├── main.py                              ← Register ws_audio router
├── layer2/shared/session_manager.py     ← Add audio_state fields
└── (voice-lab UI HTML/JS)              ← Mic button + WebSocket
```

### Existing Files — Called But NOT Modified
```
app/
├── routers/voice.py                     ← STT + TTS functions
├── layer2/graph.py                      ← Pipeline graph
├── layer2/shared/model_loader.py        ← Models
├── security_layer1/security_screening.py
└── security_layer2/output_validator.py
```

---

## 🔧 Dependencies

### Add to requirements.txt
```
webrtcvad>=2.0.10    # Voice Activity Detection
pyaudio>=0.2.13      # Audio device access
```

### Do NOT Add
```
❌ librosa           (browser handles noise cancellation)
❌ noisereduce       (browser handles noise cancellation)
❌ scipy             (not needed)
❌ resampy           (not needed)
❌ MQTT              (wrong technology — not noise cancellation)
❌ websockets        (FastAPI already includes this)
❌ aiofiles          (not needed)
❌ python-sounddevice (pyaudio is sufficient)
❌ speech-enhancement (browser handles this)
❌ asyncio-contextmanager (not needed)
```

---

## 🌐 Environment Variables — Add to .env
```
AUDIO_SAMPLE_RATE=16000        # Standard 16kHz for Riva STT
AUDIO_CHUNK_SIZE=512           # Frames per chunk (~32ms)
SILENCE_DURATION_SEC=1.2       # Seconds of silence to trigger STT
VAD_AGGRESSIVENESS=2           # 0=most sensitive, 3=least sensitive
WS_BUFFER_MAX_SIZE=5242880     # 5MB max audio buffer per session
AUDIO_PROCESSING_TIMEOUT=30   # Seconds to wait for STT response
```

---

## 🔄 Full Conversation Flow

```
USER: clicks Start Call
SERVER: creates/loads session → WebSocket ready

USER: holds mic button
BROWSER: opens mic with noiseSuppression + echoCancellation + autoGainControl
BROWSER: streams PCM audio chunks via WebSocket
SERVER: {"type": "status", "state": "RECORDING"}

USER: speaks "ma carte est bloquée"
SERVER: VAD detects speech → accumulates audio frames

USER: stops speaking (1.2s silence)
SERVER: VAD triggers processing
SERVER: {"type": "status", "state": "PROCESSING"}
SERVER: passes audio to existing Riva STT
SERVER: {"type": "transcript", "text": "ma carte est bloquée"}
SERVER: runs full existing pipeline
SERVER: {"type": "response_text", "text": "Your card has been blocked..."}
SERVER: {"type": "status", "state": "SPEAKING"}
SERVER: streams TTS audio binary chunks

BROWSER: plays audio response
SERVER: {"type": "status", "state": "RECORDING"}  ← ready for next turn

USER: speaks again (session history used for context)
[loop repeats]

USER: clicks End Call
SERVER: session ended → history cleared → redirect to landing page
```

---

## 🔐 Security Notes
1. Validate session_id exists before accepting WebSocket connection
2. Limit buffer to 5MB per session
3. Auto-close WebSocket after 5 min inactivity
4. No audio stored by default after processing

---

## 📈 Performance Targets

| Metric                  | Target      |
|-------------------------|-------------|
| Mic capture latency     | < 50ms      |
| VAD processing          | < 5ms/frame |
| STT latency             | < 2s        |
| Response generation     | < 3s        |
| TTS latency             | < 2s        |
| Total turn latency      | < 8 seconds |
| Memory per session      | < 20MB      |

---

## 🚀 5-Day Implementation Checklist

### Day 1-2: Phase 1
- [ ] Create app/routers/ws_audio.py
- [ ] Create app/layer1/audio_processor.py
- [ ] Update app/main.py
- [ ] Update voice-lab UI (mic button + WebSocket JS)
- [ ] Test: WebSocket connects, audio chunks received

### Day 3-4: Phase 2
- [ ] Create app/layer1/vad_engine.py
- [ ] Update audio_processor.py with VAD
- [ ] Update ws_audio.py with state machine
- [ ] Update session_manager.py with audio fields
- [ ] Connect WebSocket to existing pipeline
- [ ] Test: full end-to-end turn works

### Day 5: Phase 3
- [ ] Write unit tests
- [ ] Manual test checklist
- [ ] Push to GitHub feature/full-pipeline-v3

---

**Status**: Ready for implementation
**Version**: 2.0 (REVISED)
**Timeline**: 5 days
**Complexity**: Medium
**Risk**: Low