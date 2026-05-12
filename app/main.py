import os
from contextlib import asynccontextmanager
from dotenv import load_dotenv

import torch
from fastapi import FastAPI
from fastapi.responses import HTMLResponse
from kokoro import KPipeline
from transformers import pipeline

# Load environment variables from .env file
load_dotenv()

DEVICE = "cuda" if torch.cuda.is_available() else "cpu"
WHISPER_MODEL = os.getenv("WHISPER_MODEL", "openai/whisper-tiny")
LOAD_VOICE_MODELS = os.getenv("LOAD_VOICE_MODELS", "true").lower() == "true"
ml_models: dict[str, object] = {}


@asynccontextmanager
async def lifespan(_: FastAPI):
    print(f"Using device: {DEVICE}")
    print("Preparing runtime...")

    
    # Load intent model at startup
    try:
        from app.layer2.shared.model_loader import load_model_at_startup
        load_model_at_startup()
    except Exception as exc:
        print(f"Intent model loading failed: {exc}")

    # Load Nemotron translation model at startup
    try:
        from app.layer2.shared.model_loader import load_nemotron_at_startup
        load_nemotron_at_startup()
    except Exception as exc:
        print(f"Nemotron model loading failed: {exc}")

    print(f"LOAD_VOICE_MODELS = {LOAD_VOICE_MODELS}")
    if LOAD_VOICE_MODELS:
        print("Loading voice models...")
        # Layer 1: STT (NVIDIA Riva gRPC - whisper-large-v3)
        ml_models["stt_whisper"] = "nvidia_riva_grpc"
        print("STT configured: NVIDIA Riva gRPC (whisper-large-v3)")

        try:
            print("Loading Kokoro EN...")
            ml_models["tts_kokoro_en"] = KPipeline(lang_code="a")
            print("Kokoro EN loaded successfully")
        except Exception as exc:
            print(f"Kokoro EN loading failed: {exc}")
            ml_models["tts_kokoro_en"] = None

        try:
            print("Loading Kokoro FR...")
            ml_models["tts_kokoro_fr"] = KPipeline(lang_code="f")
            print("Kokoro FR loaded successfully")
        except Exception as exc:
            print(f"Kokoro FR loading failed: {exc}")
            ml_models["tts_kokoro_fr"] = None

        if ml_models.get("tts_kokoro_en") or ml_models.get("tts_kokoro_fr"):
            print("Layer 3: Kokoro loaded (EN + FR)")

        try:
            print("Installing f5_tts...")
            # Try to install f5_tts if not available
            import subprocess
            import sys
            try:
                # Try different package names for f5-tts
                packages_to_try = ["f5-tts", "f5-tts-pytorch", "F5-TTS"]
                for package in packages_to_try:
                    try:
                        subprocess.check_call([sys.executable, "-m", "pip", "install", package])
                        print(f"f5_tts installed successfully using {package}")
                        break
                    except:
                        continue
                else:
                    print("All f5_tts package attempts failed")
            except:
                print("f5_tts installation failed, using existing installation")
            
            from f5_tts.api import F5TTS
            print("Loading Habibi-TTS...")
            ml_models["tts_habibi"] = F5TTS()
            print("Layer 3: Habibi-TTS loaded (ALG)")
        except Exception as exc:
            ml_models["tts_habibi"] = None
            print(f"Layer 3: Habibi-TTS not available: {exc}")
            print("Arabic TTS will use gTTS as fallback")
    else:
        ml_models["stt_whisper"] = None
        ml_models["tts_kokoro_en"] = None
        ml_models["tts_kokoro_fr"] = None
        ml_models["tts_habibi"] = None
        print("Voice models skipped (set LOAD_VOICE_MODELS=true to enable).")
    
    print(f"Final ml_models keys: {list(ml_models.keys())}")

    yield

    print("Shutting down...")
    ml_models.clear()


from fastapi.middleware.cors import CORSMiddleware

app = FastAPI(title="AI Client Support System", lifespan=lifespan)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

from app.routers.chat import router as chat_router
from app.routers.voice import router as voice_router
from app.routers.session import router as session_router

app.include_router(chat_router)
app.include_router(voice_router)
app.include_router(session_router)


@app.get("/")
async def root():
    return {
        "status": "online",
        "device": DEVICE,
        "whisper_model": WHISPER_MODEL,
        "loaded_models": {k: (v is not None) for k, v in ml_models.items()},
        "load_voice_models": LOAD_VOICE_MODELS,
        "milestone": "A",
        "capabilities": ["chat_flow", "stt_test", "tts_test", "layer2_framework"],
    }


@app.get("/tts-ui", summary="TTS UI with clickable download links")
async def tts_ui():
    """Simple HTML page for TTS with clickable download links"""
    html_content = """
    <!DOCTYPE html>
    <html>
    <head>
        <title>TTS Text-to-Speech</title>
        <style>
            body { font-family: Arial, sans-serif; margin: 40px; }
            .container { max-width: 600px; margin: 0 auto; }
            input, select, button { width: 100%; padding: 10px; margin: 5px 0; }
            button { background-color: #007bff; color: white; border: none; cursor: pointer; }
            button:hover { background-color: #0056b3; }
            .result { margin-top: 20px; padding: 15px; background-color: #f8f9fa; border-radius: 5px; }
            .download-link { color: #007bff; text-decoration: none; font-weight: bold; }
            .download-link:hover { text-decoration: underline; }
            .error { color: red; }
            .success { color: green; }
        </style>
    </head>
    <body>
        <div class="container">
            <h1>Text-to-Speech Generator</h1>
            
            <div>
                <label for="text">Text to convert:</label>
                <input type="text" id="text" placeholder="Enter text here..." value="Hello world, this is a test!">
            </div>
            
            <div>
                <label for="language">Language:</label>
                <select id="language">
                    <option value="en">English</option>
                    <option value="fr">French</option>
                    <option value="ar">Arabic</option>
                </select>
            </div>
            
            <button onclick="generateSpeech()">Generate Speech</button>
            
            <div id="result" class="result" style="display: none;">
                <h3>Result:</h3>
                <div id="result-content"></div>
            </div>
        </div>

        <script>
            async function generateSpeech() {
                const text = document.getElementById('text').value;
                const language = document.getElementById('language').value;
                const resultDiv = document.getElementById('result');
                const resultContent = document.getElementById('result-content');
                
                if (!text.trim()) {
                    alert('Please enter some text');
                    return;
                }
                
                resultDiv.style.display = 'block';
                resultContent.innerHTML = '<div class="success">Generating speech... please wait...</div>';
                
                try {
                    const response = await fetch('/test/tts', {
                        method: 'POST',
                        headers: {
                            'Content-Type': 'application/json',
                        },
                        body: JSON.stringify({
                            text: text,
                            language: language
                        })
                    });
                    
                    const data = await response.json();
                    
                    if (response.ok) {
                        const fileSize = data.file_size ? `${(data.file_size / 1024).toFixed(2)} KB` : 'Unknown size';
                        resultContent.innerHTML = `
                            <div class="success">Speech generated successfully!</div>
                            <p><strong>Model used:</strong> ${data.model_used}</p>
                            <p><strong>Sample rate:</strong> ${data.sample_rate} Hz</p>
                            <p><strong>File size:</strong> ${fileSize}</p>
                            <p><strong>Text:</strong> "${data.text}"</p>
                            <p><strong>Language:</strong> ${data.language}</p>
                            <p><strong>Play Audio:</strong></p>
                            <audio controls style="width: 100%; margin: 10px 0;">
                                <source src="${data.audio_base64}" type="audio/wav">
                                <source src="${data.download_url}" type="audio/wav">
                                Your browser does not support the audio element.
                            </audio>
                            <p><strong>Download:</strong> <a href="${data.download_url}" class="download-link" download="${data.filename}">Click here to download ${data.filename}</a></p>
                        `;
                    } else {
                        resultContent.innerHTML = `<div class="error">Error: ${data.detail || 'Unknown error'}</div>`;
                    }
                } catch (error) {
                    resultContent.innerHTML = `<div class="error">Network error: ${error.message}</div>`;
                }
            }
        </script>
    </body>
    </html>
    """
    from fastapi.responses import HTMLResponse
    return HTMLResponse(content=html_content)


@app.get("/voice-orchestrator-ui", summary="Voice to Orchestrator Testing UI")
async def voice_orchestrator_ui():
    """Simple HTML page for testing voice-to-orchestrator pipeline"""
    html_content = """
    <!DOCTYPE html>
    <html>
    <head>
        <title>Voice to Orchestrator</title>
        <style>
            body { font-family: Arial, sans-serif; margin: 40px; }
            .container { max-width: 800px; margin: 0 auto; }
            input, button { width: 100%; padding: 10px; margin: 5px 0; }
            button { background-color: #007bff; color: white; border: none; cursor: pointer; }
            button:hover { background-color: #0056b3; }
            .result { margin-top: 20px; padding: 15px; background-color: #f8f9fa; border-radius: 5px; }
            .error { color: red; }
            .success { color: green; }
            .section { margin-top: 15px; padding: 10px; background-color: #e9ecef; border-radius: 5px; }
            .agent-tag { display: inline-block; background-color: #007bff; color: white; padding: 3px 8px; margin: 2px; border-radius: 3px; font-size: 12px; }
            pre { background-color: #f1f1f1; padding: 10px; border-radius: 5px; overflow-x: auto; }
        </style>
    </head>
    <body>
        <div class="container">
            <h1>Voice to Orchestrator Pipeline</h1>
            <p>Upload an audio file to test the complete voice pipeline: STT → Ingestion → Orchestrator → Output</p>
            
            <div>
                <label for="audio">Select audio file (WAV, MP3, etc.):</label>
                <input type="file" id="audio" accept="audio/*">
            </div>
            
            <button onclick="processVoice()">Process Voice</button>
            
            <div id="result" class="result" style="display: none;">
                <h3>Results:</h3>
                <div id="result-content"></div>
            </div>
        </div>

        <script>
            async function processVoice() {
                const audioInput = document.getElementById('audio');
                const resultDiv = document.getElementById('result');
                const resultContent = document.getElementById('result-content');
                
                if (!audioInput.files || audioInput.files.length === 0) {
                    alert('Please select an audio file');
                    return;
                }
                
                const formData = new FormData();
                formData.append('audio', audioInput.files[0]);
                
                resultDiv.style.display = 'block';
                resultContent.innerHTML = '<div class="success">Processing voice... please wait...</div>';
                
                try {
                    const response = await fetch('/test/voice-to-orchestrator', {
                        method: 'POST',
                        body: formData
                    });
                    
                    const data = await response.json();
                    
                    if (response.ok) {
                        const agentsHtml = data.orchestrator_output.required_agents
                            .map(agent => `<span class="agent-tag">${agent}</span>`)
                            .join('');
                        
                        resultContent.innerHTML = `
                            <div class="success">Voice processing successful!</div>
                            
                            <div class="section">
                                <h4>Transcription</h4>
                                <p><strong>Text:</strong> "${data.transcription}"</p>
                                <p><strong>Detected Language:</strong> ${data.detected_language}</p>
                            </div>
                            
                            ${data.translation_applied ? `
                            <div class="section" style="background-color: #d4edda; border: 1px solid #c3e6cb;">
                                <h4>Translation Applied</h4>
                                <p><strong>Original (${data.detected_language}):</strong> "${data.transcription}"</p>
                                <p><strong>Translated (English):</strong> "${data.text_for_ingestion}"</p>
                            </div>
                            ` : ''}
                            
                            <div class="section">
                                <h4>Orchestrator Output</h4>
                                <p><strong>Intent:</strong> ${data.orchestrator_output.intent}</p>
                                <p><strong>Category:</strong> ${data.orchestrator_output.category}</p>
                                <p><strong>Confidence:</strong> ${data.orchestrator_output.confidence}</p>
                                <p><strong>Extraction Method:</strong> ${data.orchestrator_output.extraction_method}</p>
                                <p><strong>Model Used:</strong> ${data.orchestrator_output.model_used}</p>
                            </div>
                            
                            <div class="section">
                                <h4>Required Agents</h4>
                                <div>${agentsHtml}</div>
                            </div>
                            
                            <!-- Final Voice Response Section - Always Visible -->
                            <div class="section" style="background-color: #e8f5e8; border: 2px solid #d4edda;">
                                <h4>🔊 Final Voice Output</h4>
                                <p><strong>🌍 Localized Response (${data.detected_language}):</strong></p>
                                <p>${data.final_response_localized || 'No localized response available'}</p>
                                
                                ${data.final_response_audio ? `
                                <p><strong>🎵 Audio Generated:</strong> ${data.audio_model_used || 'No audio model'} (${data.audio_sample_rate || 'Unknown rate'}Hz)</p>
                                <div class="audio-player">
                                    <audio controls autoplay style="width: 100%; max-height: 200px;">
                                        <source src="data:audio/wav;base64,${data.final_response_audio}" type="audio/wav">
                                        Your browser does not support the audio element.
                                    </audio>
                                    <br>
                                    <a href="data:audio/wav;base64,${data.final_response_audio}" download="voice_response.wav" style="display: inline-block; margin-top: 10px; padding: 8px 16px; background: #007bff; color: white; text-decoration: none; border-radius: 4px;">
                                        💾 Download Audio
                                    </a>
                                </div>
                                ` : `
                            </div>
                            
                            <div class="section">
                                <h4>Mission Briefs</h4>
                                ${Object.entries(data.orchestrator_output.mission_briefs).map(([agent, brief]) => `
                                    <div style="margin-top: 10px;">
                                        <strong>${agent}:</strong>
                                        <pre style="white-space: pre-wrap; word-wrap: break-word;">${brief.substring(0, 500)}${brief.length > 500 ? '...' : ''}</pre>
                                    </div>
                                `).join('')}
                            </div>
                            
                            <div class="section">
                                <h4>Final Response</h4>
                                <pre style="white-space: pre-wrap; word-wrap: break-word;">${data.orchestrator_output.final_response}</pre>
                            </div>
                            
                            <p><strong>Conversation ID:</strong> ${data.conversation_id}</p>
                        `;
                    } else {
                        resultContent.innerHTML = `<div class="error">Error: ${data.detail || 'Unknown error'}</div>`;
                    }
                } catch (error) {
                    resultContent.innerHTML = `<div class="error">Network error: ${error.message}</div>`;
                }
            }
        </script>
    </body>
    </html>
    """
    from fastapi.responses import HTMLResponse
    return HTMLResponse(content=html_content)


@app.get("/voice-lab", summary="BNA Virtual Agent Landing Page")
async def voice_lab_landing():
    """Simple landing page for starting conversations"""
    from fastapi.responses import HTMLResponse
    html_content = """
    <!DOCTYPE html>
    <html>
    <head>
        <title>BNA Virtual Agent</title>
        <style>
            body { font-family: Arial, sans-serif; margin: 0; padding: 0; height: 100vh; display: flex; align-items: center; justify-content: center; background: #f5f5f5; }
            .container { text-align: center; padding: 40px; background: white; border-radius: 10px; box-shadow: 0 4px 6px rgba(0,0,0,0.1); }
            h1 { color: #333; margin-bottom: 30px; }
            .start-btn { background: #007bff; color: white; border: none; padding: 20px 40px; font-size: 18px; border-radius: 5px; cursor: pointer; text-decoration: none; display: inline-block; transition: background 0.3s; }
            .start-btn:hover { background: #0056b3; }
        </style>
    </head>
    <body>
        <div class="container">
            <h1>BNA Virtual Agent</h1>
            <button class="start-btn" onclick="startConversation()">📞 Start Conversation</button>
        </div>
        <script>
            async function startConversation() {
                try {
                    const response = await fetch('/test/session/create', { method: 'POST' });
                    const data = await response.json();
                    const sessionId = data.session_id;
                    window.location.href = '/voice-lab/session/' + sessionId;
                } catch (error) {
                    console.error('Failed to start conversation:', error);
                    alert('Failed to start conversation. Please try again.');
                }
            }
        </script>
    </body>
    </html>
    """
    return HTMLResponse(content=html_content)


@app.get("/voice-lab/session/{session_id}", summary="Voice Pipeline with Session")
async def voice_lab_session(session_id: str):
    """Voice pipeline interface with session management"""
    from fastapi.responses import HTMLResponse
    html_content = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <title>BNA Virtual Agent - Session {session_id[:8]}...</title>
        <style>
            body {{ font-family: Arial, sans-serif; margin: 20px; background: #f5f5f5; }}
            .header {{ background: white; padding: 15px; border-radius: 5px; margin-bottom: 20px; box-shadow: 0 2px 4px rgba(0,0,0,0.1); }}
            .session-info {{ color: #666; font-size: 14px; }}
            .end-btn {{ background: #dc3545; color: white; border: none; padding: 10px 20px; border-radius: 5px; cursor: pointer; float: right; }}
            .end-btn:hover {{ background: #c82333; }}
            .container {{ max-width: 1200px; margin: 0 auto; }}
        </style>
    </head>
    <body>
        <div class="container">
            <div class="header">
                <div class="session-info">Session ID: {session_id}</div>
                <button class="end-btn" onclick="endCall()">📵 End Call</button>
                <div style="clear: both;"></div>
            </div>
            <iframe src="/voice-lab-complete?session_id={session_id}" style="width: 100%; height: 800px; border: none; border-radius: 5px; box-shadow: 0 4px 6px rgba(0,0,0,0.1);"></iframe>
        </div>
        <script>
            const sessionId = '{session_id}';
            
            async function endCall() {{
                if (confirm('Are you sure you want to end this call?')) {{
                    try {{
                        const response = await fetch(`/test/session/${{sessionId}}`, {{ method: 'DELETE' }});
                        const data = await response.json();
                        if (data.success) {{
                            window.location.href = '/voice-lab';
                        }}
                    }} catch (error) {{
                        console.error('Failed to end call:', error);
                        alert('Failed to end call. Please try again.');
                    }}
                }}
            }}
        </script>
    </body>
    </html>
    """
    return HTMLResponse(content=html_content)


@app.get("/voice-lab-complete", summary="Complete Voice Pipeline Laboratory")
async def voice_lab_complete():
    """Complete voice pipeline testing interface with final voice output"""
    from fastapi.responses import HTMLResponse
    with open('voice_lab_complete.html', 'r', encoding='utf-8') as f:
        html_content = f.read()
    return HTMLResponse(content=html_content)


@app.get("/test_tts_web", response_class=HTMLResponse)
async def tts_test_page():
    """Serve the TTS test web page"""
    html_content = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Layer 3 TTS Test</title>
    <style>
        body {
            font-family: Arial, sans-serif;
            max-width: 800px;
            margin: 0 auto;
            padding: 20px;
            background-color: #f5f5f5;
        }
        .container {
            background: white;
            padding: 30px;
            border-radius: 10px;
            box-shadow: 0 2px 10px rgba(0,0,0,0.1);
        }
        h1 {
            color: #333;
            text-align: center;
        }
        .test-section {
            margin: 20px 0;
            padding: 20px;
            border: 1px solid #ddd;
            border-radius: 5px;
        }
        textarea {
            width: 100%;
            height: 100px;
            margin: 10px 0;
            padding: 10px;
            border: 1px solid #ddd;
            border-radius: 5px;
        }
        select, button {
            padding: 10px 20px;
            margin: 5px;
            border: none;
            border-radius: 5px;
            cursor: pointer;
        }
        button {
            background-color: #007bff;
            color: white;
        }
        button:hover {
            background-color: #0056b3;
        }
        .result {
            margin-top: 20px;
            padding: 15px;
            background-color: #f8f9fa;
            border-radius: 5px;
        }
        .audio-player {
            margin: 10px 0;
        }
        .loading {
            color: #666;
            font-style: italic;
        }
    </style>
</head>
<body>
    <div class="container">
        <h1>🔬 Layer 3 TTS Test - Web Interface</h1>
        
        <div class="test-section">
            <h3>Test Text-to-Speech</h3>
            <textarea id="testText" placeholder="Enter text to convert to speech...">Hello, this is a test of the text-to-speech system.</textarea>
            
            <label for="language">Language:</label>
            <select id="language">
                <option value="en">English</option>
                <option value="fr">French</option>
                <option value="ar">Arabic</option>
            </select>
            
            <button onclick="testTTS()">🗣️ Generate Speech</button>
            <button onclick="testBankingResponse()">🏦 Test Banking Response</button>
        </div>
        
        <div class="result" id="result" style="display: none;">
            <h4>Result:</h4>
            <div id="resultContent"></div>
        </div>
    </div>

    <script>
        async function testTTS() {
            const text = document.getElementById('testText').value;
            const language = document.getElementById('language').value;
            const resultDiv = document.getElementById('result');
            const resultContent = document.getElementById('resultContent');
            
            if (!text.trim()) {
                alert('Please enter some text to convert');
                return;
            }
            
            resultDiv.style.display = 'block';
            resultContent.innerHTML = '<div class="loading">🔄 Generating speech...</div>';
            
            try {
                const response = await fetch('/test/tts', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                    },
                    body: JSON.stringify({
                        text: text,
                        language: language
                    })
                });
                
                if (response.ok) {
                    const data = await response.json();
                    
                    if (data.success) {
                        // Use base64 audio data directly
                        const audioSrc = data.audio_base64;
                        
                        resultContent.innerHTML = `
                            <div class="audio-player">
                                <audio controls autoplay>
                                    <source src="${audioSrc}" type="audio/wav">
                                    Your browser does not support the audio element.
                                </audio>
                            </div>
                            <p><strong>✅ Speech generated successfully!</strong></p>
                            <p><em>Text:</em> "${text}"</p>
                            <p><em>Language:</em> ${language}</p>
                            <p><em>Model:</em> ${data.model_used}</p>
                            <p><em>Sample Rate:</em> ${data.sample_rate} Hz</p>
                            <p><em>File Size:</em> ${data.file_size} bytes</p>
                            <a href="${audioSrc}" download="${data.filename}">
                                <button>💾 Download Audio</button>
                            </a>
                        `;
                    } else {
                        throw new Error(data.error || 'TTS generation failed');
                    }
                } else {
                    throw new Error(`HTTP error! status: ${response.status}`);
                }
            } catch (error) {
                resultContent.innerHTML = `
                    <p><strong>❌ Error:</strong> ${error.message}</p>
                    <p>Make sure the server is running and TTS models are loaded.</p>
                `;
            }
        }
        
        async function testBankingResponse() {
            const bankingText = `Thank you for your inquiry about our personal loan services. 
            Our current interest rates start at 4.5% APR for qualified applicants. 
            Please visit our website or contact your local branch for more information.`;
            
            document.getElementById('testText').value = bankingText;
            document.getElementById('language').value = 'en';
            
            await testTTS();
        }
    </script>
</body>
</html>
    """
    return HTMLResponse(content=html_content)
