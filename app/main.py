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

app.include_router(chat_router)
app.include_router(voice_router)


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


@app.get("/voice-lab", summary="Modern Voice Pipeline Laboratory")
async def voice_lab():
    """Modern voice pipeline testing interface with dynamic agent selection"""
    html_content = """
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Voice Lab - AI Pipeline Testing</title>
        <style>
            * {
                margin: 0;
                padding: 0;
                box-sizing: border-box;
            }

            body {
                font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, Cantarell, sans-serif;
                background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                min-height: 100vh;
                color: #333;
            }

            .container {
                max-width: 1400px;
                margin: 0 auto;
                padding: 20px;
            }

            header {
                text-align: center;
                margin-bottom: 40px;
                color: white;
            }

            .header-content {
                background: rgba(255, 255, 255, 0.1);
                backdrop-filter: blur(10px);
                border-radius: 20px;
                padding: 30px;
                border: 1px solid rgba(255, 255, 255, 0.2);
            }

            h1 {
                font-size: 2.5rem;
                margin-bottom: 10px;
                font-weight: 700;
            }

            .subtitle {
                font-size: 1.1rem;
                opacity: 0.9;
                margin-bottom: 20px;
            }

            .pipeline-flow {
                display: flex;
                justify-content: center;
                align-items: center;
                gap: 15px;
                margin: 20px 0;
                flex-wrap: wrap;
            }

            .flow-step {
                background: rgba(255, 255, 255, 0.2);
                padding: 8px 16px;
                border-radius: 20px;
                font-size: 0.9rem;
                border: 1px solid rgba(255, 255, 255, 0.3);
            }

            .flow-arrow {
                color: rgba(255, 255, 255, 0.7);
                font-size: 1.2rem;
            }

            .main-content {
                display: grid;
                grid-template-columns: 1fr 2fr;
                gap: 30px;
                margin-bottom: 30px;
            }

            .upload-section {
                background: white;
                border-radius: 20px;
                padding: 30px;
                box-shadow: 0 20px 40px rgba(0, 0, 0, 0.1);
                height: fit-content;
            }

            .upload-area {
                border: 3px dashed #667eea;
                border-radius: 15px;
                padding: 40px 20px;
                text-align: center;
                transition: all 0.3s ease;
                cursor: pointer;
                background: #f8f9ff;
            }

            .upload-area:hover {
                border-color: #764ba2;
                background: #f0f2ff;
            }

            .upload-area.dragover {
                border-color: #28a745;
                background: #f0fff4;
            }

            .upload-icon {
                font-size: 3rem;
                margin-bottom: 15px;
                color: #667eea;
            }

            .file-input {
                display: none;
            }

            .upload-text {
                color: #666;
                margin-bottom: 15px;
            }

            .selected-file {
                background: #e8f5e8;
                border: 1px solid #28a745;
                border-radius: 10px;
                padding: 15px;
                margin-top: 15px;
                color: #155724;
            }

            .process-btn {
                width: 100%;
                padding: 15px;
                background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                color: white;
                border: none;
                border-radius: 12px;
                font-size: 1.1rem;
                font-weight: 600;
                cursor: pointer;
                transition: all 0.3s ease;
                margin-top: 20px;
            }

            .process-btn:hover:not(:disabled) {
                transform: translateY(-2px);
                box-shadow: 0 10px 25px rgba(102, 126, 234, 0.3);
            }

            .process-btn:disabled {
                opacity: 0.6;
                cursor: not-allowed;
            }

            .results-section {
                background: white;
                border-radius: 20px;
                padding: 30px;
                box-shadow: 0 20px 40px rgba(0, 0, 0, 0.1);
            }

            .results-header {
                display: flex;
                justify-content: space-between;
                align-items: center;
                margin-bottom: 25px;
                padding-bottom: 15px;
                border-bottom: 2px solid #f0f0f0;
            }

            .results-title {
                font-size: 1.5rem;
                font-weight: 600;
                color: #333;
            }

            .status-badge {
                padding: 8px 16px;
                border-radius: 20px;
                font-size: 0.9rem;
                font-weight: 600;
            }

            .status-processing {
                background: #fff3cd;
                color: #856404;
                border: 1px solid #ffeaa7;
            }

            .status-success {
                background: #d4edda;
                color: #155724;
                border: 1px solid #c3e6cb;
            }

            .status-error {
                background: #f8d7da;
                color: #721c24;
                border: 1px solid #f5c6cb;
            }

            .progress-container {
                margin-bottom: 30px;
            }

            .progress-bar {
                width: 100%;
                height: 8px;
                background: #e9ecef;
                border-radius: 10px;
                overflow: hidden;
                margin-bottom: 10px;
            }

            .progress-fill {
                height: 100%;
                background: linear-gradient(90deg, #667eea, #764ba2);
                transition: width 0.5s ease;
                border-radius: 10px;
            }

            .progress-text {
                font-size: 0.9rem;
                color: #666;
                text-align: center;
            }

            .summary-grid {
                display: grid;
                grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
                gap: 20px;
                margin-bottom: 30px;
            }

            .summary-card {
                background: #f8f9fa;
                padding: 20px;
                border-radius: 12px;
                border-left: 4px solid #667eea;
            }

            .summary-label {
                font-size: 0.9rem;
                color: #666;
                margin-bottom: 5px;
            }

            .summary-value {
                font-size: 1.1rem;
                font-weight: 600;
                color: #333;
            }

            .stages-container {
                display: grid;
                gap: 20px;
            }

            .stage-card {
                background: #f8f9fa;
                border-radius: 15px;
                padding: 25px;
                border-left: 4px solid #667eea;
                transition: all 0.3s ease;
            }

            .stage-card.success {
                border-left-color: #28a745;
                background: #f0fff4;
            }

            .stage-card.error {
                border-left-color: #dc3545;
                background: #fff5f5;
            }

            .stage-header {
                display: flex;
                align-items: center;
                margin-bottom: 20px;
            }

            .stage-icon {
                font-size: 1.5rem;
                margin-right: 15px;
            }

            .stage-title {
                font-size: 1.2rem;
                font-weight: 600;
                color: #333;
            }

            .stage-content {
                color: #666;
                line-height: 1.6;
            }

            .stage-details {
                display: grid;
                gap: 10px;
                margin-top: 15px;
            }

            .detail-row {
                display: flex;
                justify-content: space-between;
                padding: 8px 0;
                border-bottom: 1px solid #e9ecef;
            }

            .detail-label {
                font-weight: 600;
                color: #495057;
            }

            .detail-value {
                color: #666;
                text-align: right;
            }

            .agent-response-card {
                background: linear-gradient(135deg, #fff3cd 0%, #ffeaa7 100%);
                border-left: 4px solid #f39c12;
                border-radius: 15px;
                padding: 25px;
                margin: 20px 0;
            }

            .agent-header {
                display: flex;
                align-items: center;
                margin-bottom: 15px;
            }

            .agent-badge {
                background: #f39c12;
                color: white;
                padding: 6px 12px;
                border-radius: 20px;
                font-size: 0.9rem;
                font-weight: 600;
                margin-left: 10px;
            }

            .agent-response-text {
                background: white;
                padding: 20px;
                border-radius: 10px;
                font-family: 'Courier New', monospace;
                line-height: 1.5;
                white-space: pre-wrap;
                word-wrap: break-word;
                max-height: 300px;
                overflow-y: auto;
            }

            .error-message {
                background: #f8d7da;
                color: #721c24;
                padding: 20px;
                border-radius: 10px;
                border: 1px solid #f5c6cb;
            }

            .loading-spinner {
                display: inline-block;
                width: 20px;
                height: 20px;
                border: 3px solid #f3f3f3;
                border-top: 3px solid #667eea;
                border-radius: 50%;
                animation: spin 1s linear infinite;
                margin-right: 10px;
            }

            @keyframes spin {
                0% { transform: rotate(0deg); }
                100% { transform: rotate(360deg); }
            }

            @media (max-width: 768px) {
                .main-content {
                    grid-template-columns: 1fr;
                }
                
                .pipeline-flow {
                    flex-direction: column;
                }
                
                .flow-arrow {
                    transform: rotate(90deg);
                }
            }
        </style>
    </head>
    <body>
        <div class="container">
            <header>
                <div class="header-content">
                    <h1>🎙️ Voice Lab</h1>
                    <p class="subtitle">Advanced AI Voice Pipeline Testing Platform</p>
                    <div class="pipeline-flow">
                        <div class="flow-step">🎤 Speech Detection</div>
                        <div class="flow-arrow">→</div>
                        <div class="flow-step">🌍 Translation</div>
                        <div class="flow-arrow">→</div>
                        <div class="flow-step">🎯 Intent Analysis</div>
                        <div class="flow-arrow">→</div>
                        <div class="flow-step">🤖 Agent Selection</div>
                        <div class="flow-arrow">→</div>
                        <div class="flow-step">📚 Knowledge Base</div>
                    </div>
                </div>
            </header>

            <div class="main-content">
                <div class="upload-section">
                    <h2 style="margin-bottom: 20px; color: #333;">Upload Audio</h2>
                    <div class="upload-area" id="uploadArea">
                        <div class="upload-icon">🎤</div>
                        <p class="upload-text">Drag & drop your audio file here or click to browse</p>
                        <p style="font-size: 0.9rem; color: #999;">Supports WAV, MP3, M4A, FLAC</p>
                        <input type="file" id="audioInput" class="file-input" accept="audio/*">
                    </div>
                    <div id="selectedFile" style="display: none;" class="selected-file">
                        <strong>Selected:</strong> <span id="fileName"></span>
                    </div>
                    <button id="processBtn" class="process-btn" disabled>
                        🚀 Start Pipeline Analysis
                    </button>
                </div>

                <div class="results-section" id="resultsSection" style="display: none;">
                    <div class="results-header">
                        <h2 class="results-title">Pipeline Results</h2>
                        <div id="statusBadge" class="status-badge status-processing">
                            <div class="loading-spinner"></div>
                            Processing...
                        </div>
                    </div>

                    <div class="progress-container">
                        <div class="progress-bar">
                            <div id="progressFill" class="progress-fill" style="width: 0%"></div>
                        </div>
                        <div id="progressText" class="progress-text">Initializing pipeline...</div>
                    </div>

                    <div id="summaryGrid" class="summary-grid"></div>
                    <div id="stagesContainer" class="stages-container"></div>
                </div>
            </div>
        </div>

        <script>
            // Upload functionality
            const uploadArea = document.getElementById('uploadArea');
            const audioInput = document.getElementById('audioInput');
            const selectedFile = document.getElementById('selectedFile');
            const fileName = document.getElementById('fileName');
            const processBtn = document.getElementById('processBtn');
            const resultsSection = document.getElementById('resultsSection');
            const statusBadge = document.getElementById('statusBadge');
            const progressFill = document.getElementById('progressFill');
            const progressText = document.getElementById('progressText');
            const summaryGrid = document.getElementById('summaryGrid');
            const stagesContainer = document.getElementById('stagesContainer');

            // Drag and drop
            uploadArea.addEventListener('click', () => audioInput.click());
            
            uploadArea.addEventListener('dragover', (e) => {
                e.preventDefault();
                uploadArea.classList.add('dragover');
            });
            
            uploadArea.addEventListener('dragleave', () => {
                uploadArea.classList.remove('dragover');
            });
            
            uploadArea.addEventListener('drop', (e) => {
                e.preventDefault();
                uploadArea.classList.remove('dragover');
                const files = e.dataTransfer.files;
                if (files.length > 0) {
                    handleFileSelect(files[0]);
                }
            });

            audioInput.addEventListener('change', (e) => {
                if (e.target.files.length > 0) {
                    handleFileSelect(e.target.files[0]);
                }
            });

            function handleFileSelect(file) {
                fileName.textContent = file.name;
                selectedFile.style.display = 'block';
                processBtn.disabled = false;
            }

            processBtn.addEventListener('click', processFullPipeline);

            async function processFullPipeline() {
                if (!audioInput.files.length) return;

                // Show results section
                resultsSection.style.display = 'block';
                updateStatus('processing', 'Processing voice pipeline...');
                updateProgress(20, 'Analyzing audio...');

                const formData = new FormData();
                formData.append('audio', audioInput.files[0]);

                try {
                    const response = await fetch('/test/voice-full-pipeline', {
                        method: 'POST',
                        body: formData
                    });

                    const data = await response.json();
                    updateProgress(100, 'Analysis complete!');

                    if (response.ok) {
                        updateStatus('success', 'Analysis Complete');
                        displayResults(data);
                    } else {
                        updateStatus('error', 'Analysis Failed');
                        displayError(data.detail || 'Unknown error occurred');
                    }
                } catch (error) {
                    updateStatus('error', 'Network Error');
                    displayError(error.message);
                }
            }

            function updateStatus(type, text) {
                statusBadge.className = `status-badge status-${type}`;
                if (type === 'processing') {
                    statusBadge.innerHTML = '<div class="loading-spinner"></div>' + text;
                } else {
                    statusBadge.textContent = text;
                }
            }

            function updateProgress(percent, text) {
                progressFill.style.width = percent + '%';
                progressText.textContent = text;
            }

            function displayResults(data) {
                // Display summary
                const summary = data.summary;
                const successRate = Math.round((summary.successful_stages / summary.total_stages) * 100);
                
                summaryGrid.innerHTML = `
                    <div class="summary-card">
                        <div class="summary-label">Success Rate</div>
                        <div class="summary-value">${successRate}%</div>
                    </div>
                    <div class="summary-card">
                        <div class="summary-label">Original Text</div>
                        <div class="summary-value">${summary.original_transcription.substring(0, 50)}...</div>
                    </div>
                    <div class="summary-card">
                        <div class="summary-label">Language</div>
                        <div class="summary-value">${summary.detected_language.toUpperCase()}</div>
                    </div>
                    <div class="summary-card">
                        <div class="summary-label">Translation</div>
                        <div class="summary-value">${summary.translation_applied ? 'Applied' : 'Not Needed'}</div>
                    </div>
                `;

                // Display stages
                let stagesHtml = '';
                
                // STT Stage
                const sttStage = data.stages.whisper_stt;
                stagesHtml += createStageCard('🎤 Speech-to-Text', sttStage, `
                    <div class="stage-details">
                        <div class="detail-row">
                            <span class="detail-label">Model:</span>
                            <span class="detail-value">${sttStage.model}</span>
                        </div>
                        <div class="detail-row">
                            <span class="detail-label">Language:</span>
                            <span class="detail-value">${sttStage.detected_language}</span>
                        </div>
                        <div class="detail-row">
                            <span class="detail-label">Transcription:</span>
                            <span class="detail-value">${sttStage.transcription}</span>
                        </div>
                    </div>
                `);

                // Translator Stage
                const translatorStage = data.stages.translator;
                if (translatorStage.success && translatorStage.translation_applied) {
                    stagesHtml += createStageCard('🌍 Translation', translatorStage, `
                        <div class="stage-details">
                            <div class="detail-row">
                                <span class="detail-label">Source Language:</span>
                                <span class="detail-value">${translatorStage.source_language}</span>
                            </div>
                            <div class="detail-row">
                                <span class="detail-label">Target Language:</span>
                                <span class="detail-value">${translatorStage.target_language}</span>
                            </div>
                            <div class="detail-row">
                                <span class="detail-label">Original:</span>
                                <span class="detail-value">${translatorStage.original_text}</span>
                            </div>
                            <div class="detail-row">
                                <span class="detail-label">Translated:</span>
                                <span class="detail-value">${translatorStage.translated_text}</span>
                            </div>
                        </div>
                    `);
                } else {
                    stagesHtml += createStageCard('🌍 Translation', translatorStage, `
                        <div class="stage-content">
                            <p>No translation needed - ${translatorStage.reason || 'Already in English'}</p>
                        </div>
                    `);
                }

                // Orchestrator Stage
                const orchestratorStage = data.stages.orchestrator;
                stagesHtml += createStageCard('🎯 Intent Analysis', orchestratorStage, `
                    <div class="stage-details">
                        <div class="detail-row">
                            <span class="detail-label">Intent:</span>
                            <span class="detail-value">${orchestratorStage.intent}</span>
                        </div>
                        <div class="detail-row">
                            <span class="detail-label">Category:</span>
                            <span class="detail-value">${orchestratorStage.category}</span>
                        </div>
                        <div class="detail-row">
                            <span class="detail-label">Confidence:</span>
                            <span class="detail-value">${(orchestratorStage.confidence * 100).toFixed(1)}%</span>
                        </div>
                        <div class="detail-row">
                            <span class="detail-label">Selected Agent:</span>
                            <span class="detail-value">${orchestratorStage.required_agents.join(', ')}</span>
                        </div>
                    </div>
                `);

                // Agent Response (DYNAMIC) - Enhanced display
                if (data.agent_response) {
                    stagesHtml += createStageCard('🤖 Agent Response', {success: true}, `
                        <div class="stage-details">
                            <div class="detail-row">
                                <span class="detail-label">Selected Agent:</span>
                                <span class="detail-value" style="background: #856404; color: white; padding: 4px 8px; border-radius: 12px; font-size: 12px;">${data.selected_agent || 'Unknown'}</span>
                            </div>
                            <div class="detail-row">
                                <span class="detail-label">Response Type:</span>
                                <span class="detail-value">Final Synthesized Answer</span>
                            </div>
                        </div>
                        <div class="stage-content" style="margin-top: 15px;">
                            <strong>Agent Response:</strong>
                            <div class="agent-response-text" style="margin-top: 10px; padding: 15px; background: #f8f9fa; border-left: 4px solid #856404; border-radius: 4px; white-space: pre-wrap; font-family: inherit;">${data.agent_response}</div>
                        </div>
                    `);
                }

                // Knowledge Base Stage - Enhanced display
                const kbStage = data.stages.knowledge_base;
                stagesHtml += createStageCard('📚 Knowledge Base', kbStage, `
                    <div class="stage-details">
                        <div class="detail-row">
                            <span class="detail-label">Confidence:</span>
                            <span class="detail-value" style="color: ${kbStage.confidence > 0.7 ? '#28a745' : kbStage.confidence > 0.5 ? '#ffc107' : '#dc3545'};">${(kbStage.confidence * 100).toFixed(1)}%</span>
                        </div>
                        <div class="detail-row">
                            <span class="detail-label">Documents Found:</span>
                            <span class="detail-value">${kbStage.documents_found}</span>
                        </div>
                        <div class="detail-row">
                            <span class="detail-label">Needs Clarification:</span>
                            <span class="detail-value">${kbStage.needs_clarification ? 'Yes' : 'No'}</span>
                        </div>
                    </div>
                    <div class="stage-content" style="margin-top: 15px;">
                        <strong>Sources (${kbStage.sources.length}):</strong>
                        <div style="margin-top: 8px; padding: 10px; background: #e9ecef; border-radius: 4px; font-size: 12px;">
                            ${kbStage.sources.map(source => `• ${source}`).join('<br>')}
                        </div>
                        <strong style="margin-top: 15px; display: block;">KB Answer:</strong>
                        <div style="margin-top: 10px; padding: 15px; background: #f8f9fa; border-left: 4px solid #007bff; border-radius: 4px; white-space: pre-wrap; font-family: inherit; line-height: 1.6;">${kbStage.answer}</div>
                    </div>
                `);

                // Client Support Stage - Final Response
                if (data.agent_response) {
                    stagesHtml += createStageCard('🎯 Client Support', {success: true}, `
                        <div class="stage-details">
                            <div class="detail-row">
                                <span class="detail-label">Agent Type:</span>
                                <span class="detail-value" style="background: #28a745; color: white; padding: 4px 8px; border-radius: 12px; font-size: 12px;">Client Support Agent</span>
                            </div>
                            <div class="detail-row">
                                <span class="detail-label">Response Type:</span>
                                <span class="detail-value">Final User-Facing Answer</span>
                            </div>
                            <div class="detail-row">
                                <span class="detail-label">Input Sources:</span>
                                <span class="detail-value">KB Results + Context</span>
                            </div>
                        </div>
                        <div class="stage-content" style="margin-top: 15px;">
                            <strong>Final Response to User:</strong>
                            <div style="margin-top: 10px; padding: 15px; background: #d4edda; border-left: 4px solid #28a745; border-radius: 4px; white-space: pre-wrap; font-family: inherit; line-height: 1.6; font-size: 16px; color: #155724;">
                                ${data.agent_response}
                            </div>
                        </div>
                    `);
                }

                stagesContainer.innerHTML = stagesHtml;
            }

            function createStageCard(title, stage, content) {
                const statusClass = stage.success ? 'success' : 'error';
                const statusIcon = stage.success ? '✅' : '❌';
                
                return `
                    <div class="stage-card ${statusClass}">
                        <div class="stage-header">
                            <div class="stage-icon">${statusIcon}</div>
                            <div class="stage-title">${title}</div>
                        </div>
                        <div class="stage-content">
                            ${content}
                        </div>
                        ${!stage.success && stage.error ? `<div class="error-message">${stage.error}</div>` : ''}
                    </div>
                `;
            }

            function displayError(message) {
                stagesContainer.innerHTML = `
                    <div class="stage-card error">
                        <div class="stage-header">
                            <div class="stage-icon">❌</div>
                            <div class="stage-title">Error</div>
                        </div>
                        <div class="error-message">${message}</div>
                    </div>
                `;
            }
        </script>
    </body>
    </html>
    """
    from fastapi.responses import HTMLResponse
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
