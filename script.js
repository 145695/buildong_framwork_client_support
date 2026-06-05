

        // WebSocket Audio Streaming (Phase 1)
        let ws = null;
        let audioContext = null;
        let processor = null;
        let mediaStream = null;
        let isRecording = false;
        let sessionId = null;

        async function startRecording() {
            if (isRecording) return;
            
            // Ensure session_id is set before recording
            if (!sessionId) {
                console.error('[Session] No session_id available');
                updateMicStatus('Session not initialized', '#dc3545');
                return;
            }
            
            console.log('[Session] Starting recording with session:', sessionId);
            
            try {
                // Request microphone with WebRTC constraints
                mediaStream = await navigator.mediaDevices.getUserMedia({
                    audio: {
                        echoCancellation: true,
                        noiseSuppression: true,
                        autoGainControl: true,
                        sampleRate: 16000
                    }
                });
                
                // Create AudioContext at 16kHz
                audioContext = new (window.AudioContext || window.webkitAudioContext)({
                    sampleRate: 16000
                });
                
                // Create ScriptProcessor (512 samples per chunk - must be power of 2)
                processor = audioContext.createScriptProcessor(512, 1, 1);
                
                // Connect microphone to processor
                const source = audioContext.createMediaStreamSource(mediaStream);
                source.connect(processor);
                processor.connect(audioContext.destination);
                
                // Open WebSocket connection
                const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
                ws = new WebSocket(`${protocol}//${window.location.host}/ws/audio/${sessionId}`);
                ws.binaryType = 'arraybuffer';
                
                ws.onopen = () => {
                    console.log('[WebSocket] Connected');
                    updateMicStatus('🔴 Recording...', '#dc3545');
                };
                
                ws.onmessage = (event) => {
                    try {
                        const data = JSON.parse(event.data);
                        
                        if (data.type === 'status') {
                            console.log('[WebSocket] Status:', data.state);
                            updateMicStatus(`Status: ${data.state}`, '#17a2b8');
                        } else if (data.type === 'status_update') {
                            console.log('[WebSocket] Status Update:', data.stage, data.message);
                            updateMicStatus(`${data.message}`, '#ffc107');
                        } else if (data.type === 'status_audio') {
                            console.log('[WebSocket] Status Audio:', data.stage);
                            // Play the status audio
                            if (data.audio) {
                                playAudio(data.audio);
                            }
                        } else if (data.type === 'transcript') {
                            console.log('[WebSocket] Transcript:', data.text);
                            updateMicStatus(`Transcript: ${data.text}`, '#17a2b8');
                        } else if (data.type === 'response_text') {
                            console.log('[WebSocket] Response:', data.text);
                            updateMicStatus(`Response: ${data.text}`, '#28a745');
                        } else if (data.type === 'pipeline_result') {
                            console.log('[WebSocket] Pipeline Result:', data.data);
                            console.log('[WebSocket] Pipeline Result keys:', Object.keys(data.data));
                            console.log('[WebSocket] end_call:', data.data.end_call);
                            console.log('[WebSocket] redirect_url:', data.data.redirect_url);
                            updateMicStatus('Pipeline complete!', '#28a745');

                            // Show results section and display pipeline results
                            const resultsSection = document.getElementById('resultsSection');
                            if (resultsSection) {
                                resultsSection.style.display = 'block';
                                updateStatus('success', 'Analysis Complete');
                                try {
                                    displayResults(data.data);
                                    displayVoiceOutput(data.data);
                                } catch (e) {
                                    console.error('[Display] Error displaying results:', e);
                                    console.error('[Display] Data structure:', JSON.stringify(data.data, null, 2));
                                }
                            } else {
                                console.error('[Display] resultsSection not found');
                            }

                            // Check if call should end and redirect
                            if (data.data.end_call && data.data.redirect_url) {
                                console.log('[WebSocket] End call flag detected, redirecting to:', data.data.redirect_url);
                                alert('Redirecting to: ' + data.data.redirect_url);
                                // Wait a moment for audio to start playing, then redirect
                                setTimeout(() => {
                                    console.log('[WebSocket] Performing redirect to:', data.data.redirect_url);
                                    window.location.href = data.data.redirect_url;
                                }, 2000); // 2 second delay to let audio start
                            } else {
                                console.log('[WebSocket] No redirect - end_call:', data.data.end_call, 'redirect_url:', data.data.redirect_url);
                            }
                        } else if (data.type === 'call_end') {
                            console.log('[WebSocket] Call End received:', data);
                            console.log('[WebSocket] Redirect URL:', data.redirect_url);
                            // Redirect to the specified URL immediately
                            if (data.redirect_url) {
                                console.log('[WebSocket] Performing redirect to:', data.redirect_url);
                                // Force redirect using window.location
                                window.location.href = data.redirect_url;
                                // Fallback: reload if redirect doesn't work
                                setTimeout(() => {
                                    if (window.location.href !== data.redirect_url) {
                                        console.log('[WebSocket] Redirect fallback - using replace');
                                        window.location.replace(data.redirect_url);
                                    }
                                }, 100);
                            } else {
                                console.error('[WebSocket] No redirect URL in call_end message');
                            }
                        } else if (data.type === 'error') {
                            console.error('[WebSocket] Error:', data.message);
                            updateMicStatus(`Error: ${data.message}`, '#dc3545');
                        }
                    } catch (e) {
                        console.error('[WebSocket] JSON parse error:', e);
                    }
                };
                
                ws.onerror = (error) => {
                    console.error('[WebSocket] Error:', error);
                    updateMicStatus('Connection error', '#dc3545');
                };
                
                ws.onclose = () => {
                    console.log('[WebSocket] Disconnected');
                    updateMicStatus('Ready to speak', '#666');
                };
                
                // Handle audio frames
                processor.onaudioprocess = (event) => {
                    if (!isRecording || !ws || ws.readyState !== WebSocket.OPEN) return;
                    
                    const inputData = event.inputBuffer.getChannelData(0);
                    
                    // Convert Float32 to PCM16
                    const pcm16 = new Int16Array(inputData.length);
                    for (let i = 0; i < inputData.length; i++) {
                        const s = Math.max(-1, Math.min(1, inputData[i]));
                        pcm16[i] = s < 0 ? s * 0x8000 : s * 0x7FFF;
                    }
                    
                    // Send as binary
                    ws.send(pcm16.buffer);
                };
                
                isRecording = true;
                document.body.classList.add('recording');
                console.log('[Audio] Recording started');
                
            } catch (error) {
                console.error('[Audio] Microphone access error:', error);
                updateMicStatus(`Error: ${error.message}`, '#dc3545');
            }
        }

        function stopRecording() {
            if (!isRecording) return;
            
            isRecording = false;
            document.body.classList.remove('recording');
            console.log('[Audio] Recording stopped');
            
            // Send end_of_speech signal
            if (ws && ws.readyState === WebSocket.OPEN) {
                const msg = JSON.stringify({type: 'end_of_speech'});
                ws.send(msg);
                console.log('[WebSocket] Sent end_of_speech');
                updateMicStatus('⏳ Processing...', '#ffc107');
            }
            
            // Stop audio capture
            if (processor) {
                processor.disconnect();
            }
            if (mediaStream) {
                mediaStream.getTracks().forEach(track => track.stop());
            }
        }

        function updateMicStatus(message, color) {
            const statusEl = document.getElementById('mic-status');
            if (statusEl) {
                statusEl.textContent = message;
                statusEl.style.color = color;
            }
        }

        // Cleanup on page unload
        window.addEventListener('beforeunload', () => {
            if (ws) ws.close();
            if (mediaStream) mediaStream.getTracks().forEach(track => track.stop());
        });

        // Helper function to play audio from base64 data URL
        function playAudio(audioDataUrl) {
            try {
                const audio = new Audio(audioDataUrl);
                audio.play().catch(e => console.error('Error playing audio:', e));
            } catch (e) {
                console.error('Error creating audio element:', e);
            }
        }

        // Upload functionality (kept for reference, not used in Phase 1)
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
        
        // Session ID management
        window.addEventListener('load', async () => {
            // Get session_id from URL
            const urlParams = new URLSearchParams(window.location.search);
            const urlSessionId = urlParams.get('session_id');
            
            if (urlSessionId) {
                sessionId = urlSessionId;
                console.log('[Session] Using existing session:', sessionId);
            } else {
                // Fallback - create new session
                try {
                    const response = await fetch('/session/create', { method: 'POST' });
                    if (!response.ok || !response.headers.get('content-type')?.includes('application/json')) {
                        console.warn('[Session] No valid JSON from /session/create, skipping');
                        return;
                    }
                    const data = await response.json();
                    sessionId = data.session_id;
                    console.log('[Session] Created new session:', sessionId);
                } catch (error) {
                    console.error('[Session] Failed to create session:', error);
                }
            }
        });

        async function endCall() {
            if (sessionId) {
                try {
                    await fetch(`/session/${sessionId}`, { method: 'DELETE' });
                    console.log('[Session] Session ended:', sessionId);
                } catch (error) {
                    console.error('[Session] Failed to end session:', error);
                }
            }
            window.location.href = '/voice-lab';
        }

        async function processFullPipeline() {
            if (!audioInput.files.length) return;

            // Show results section
            resultsSection.style.display = 'block';
            updateStatus('processing', 'Processing voice pipeline...');
            updateProgress(20, 'Analyzing audio...');

            const formData = new FormData();
            formData.append('audio', audioInput.files[0]);
            if (sessionId) {
                formData.append('session_id', sessionId);
            }

            try {
                const response = await fetch('/test/voice-full-pipeline', {
                    method: 'POST',
                    body: formData
                });

                if (!response.ok || !response.headers.get('content-type')?.includes('application/json')) {
                    console.warn('[Pipeline] No valid JSON from /test/voice-full-pipeline, skipping');
                    updateStatus('error', 'Invalid Response');
                    displayError('Backend did not return valid JSON');
                    return;
                }
                const data = await response.json();
                updateProgress(100, 'Analysis complete!');

                if (response.ok) {
                    updateStatus('success', 'Analysis Complete');
                    displayResults(data);
                    displayVoiceOutput(data);
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
            // Display summary - handle missing summary field
            const summary = data.summary || {
                successful_stages: Object.values(data.stages || {}).filter(s => s && s.success).length,
                total_stages: Object.keys(data.stages || {}).length,
                original_transcription: data.stages?.whisper_stt?.transcription || 'N/A',
                detected_language: data.stages?.whisper_stt?.detected_language || 'en',
                translation_applied: data.stages?.translator?.translation_applied || false
            };
            const successRate = summary.total_stages > 0 ? Math.round((summary.successful_stages / summary.total_stages) * 100) : 0;

            summaryGrid.innerHTML = `
                <div class="summary-card">
                    <div class="summary-label">Success Rate</div>
                    <div class="summary-value">${successRate}%</div>
                </div>
                <div class="summary-card">
                    <div class="summary-label">Original Text</div>
                    <div class="summary-value">${(summary.original_transcription || 'N/A').substring(0, 50)}...</div>
                </div>
                <div class="summary-card">
                    <div class="summary-label">Language</div>
                    <div class="summary-value">${(summary.detected_language || 'en').toUpperCase()}</div>
                </div>
                <div class="summary-card">
                    <div class="summary-label">Translation</div>
                    <div class="summary-value">${summary.translation_applied ? 'Applied' : 'Not Needed'}</div>
                </div>
            `;

            // Display ALL stages with complete details
            let stagesHtml = '';
            
            // Security Layer 1: Input Validation
            const securityLayer1 = data.stages.security_layer1;
            if (securityLayer1) {
                stagesHtml += createStageCard('🔒 Security Layer 1 (Input)', securityLayer1, `
                    <div class="stage-details">
                        <div class="detail-row">
                            <span class="detail-label">Is Safe:</span>
                            <span class="detail-value">${securityLayer1.is_safe ? '✅ Yes' : '❌ No'}</span>
                        </div>
                        <div class="detail-row">
                            <span class="detail-label">Risk Score:</span>
                            <span class="detail-value">${securityLayer1.risk_score || 'N/A'}</span>
                        </div>
                        <div class="detail-row">
                            <span class="detail-label">Success:</span>
                            <span class="detail-value">${securityLayer1.success ? '✅ Yes' : '❌ No'}</span>
                        </div>
                    </div>
                `);
            }

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
                    <div class="detail-row">
                        <span class="detail-label">Success:</span>
                        <span class="detail-value">${sttStage.success ? '✅ Yes' : '❌ No'}</span>
                    </div>
                </div>
            `);

            // Translator Stage
            const translatorStage = data.stages.translator;
            if (translatorStage) {
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
                            <span class="detail-label">Original Text:</span>
                            <span class="detail-value">${translatorStage.original_text}</span>
                        </div>
                        <div class="detail-row">
                            <span class="detail-label">Translated Text:</span>
                            <span class="detail-value">${translatorStage.translated_text}</span>
                        </div>
                        <div class="detail-row">
                            <span class="detail-label">Translation Applied:</span>
                            <span class="detail-value">${translatorStage.translation_applied ? '✅ Yes' : '❌ No'}</span>
                        </div>
                        <div class="detail-row">
                            <span class="detail-label">Success:</span>
                            <span class="detail-value">${translatorStage.success ? '✅ Yes' : '❌ No'}</span>
                        </div>
                    </div>
                `);
            }

            // Ingestion Stage
            const ingestionStage = data.stages.ingestion;
            if (ingestionStage) {
                stagesHtml += createStageCard('📥 Ingestion', ingestionStage, `
                    <div class="stage-details">
                        <div class="detail-row">
                            <span class="detail-label">Conversation ID:</span>
                            <span class="detail-value">${ingestionStage.conversation_id}</span>
                        </div>
                        <div class="detail-row">
                            <span class="detail-label">Original Text:</span>
                            <span class="detail-value">${ingestionStage.original_text}</span>
                        </div>
                        <div class="detail-row">
                            <span class="detail-label">Normalized Text:</span>
                            <span class="detail-value">${ingestionStage.normalized_text_en}</span>
                        </div>
                        <div class="detail-row">
                            <span class="detail-label">PII Masked:</span>
                            <span class="detail-value">${ingestionStage.pii_masked ? '✅ Yes' : '❌ No'}</span>
                        </div>
                        <div class="detail-row">
                            <span class="detail-label">Success:</span>
                            <span class="detail-value">${ingestionStage.success ? '✅ Yes' : '❌ No'}</span>
                        </div>
                    </div>
                `);
            }

            // Orchestrator Stage
            const orchestratorStage = data.stages.orchestrator;
            if (orchestratorStage) {
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
                            <span class="detail-label">Required Agents:</span>
                            <span class="detail-value">${orchestratorStage.required_agents.join(', ')}</span>
                        </div>
                        <div class="detail-row">
                            <span class="detail-label">Extraction Method:</span>
                            <span class="detail-value">${orchestratorStage.extraction_method}</span>
                        </div>
                        <div class="detail-row">
                            <span class="detail-label">Model Used:</span>
                            <span class="detail-value">${orchestratorStage.model_used}</span>
                        </div>
                        <div class="detail-row">
                            <span class="detail-label">Success:</span>
                            <span class="detail-value">${orchestratorStage.success ? '✅ Yes' : '❌ No'}</span>
                        </div>
                    </div>
                `);
            }

            // Knowledge Base Stage
            const kbStage = data.stages.knowledge_base;
            if (kbStage) {
                stagesHtml += createStageCard('📚 Knowledge Base', kbStage, `
                    <div class="stage-details">
                        <div class="detail-row">
                            <span class="detail-label">Confidence:</span>
                            <span class="detail-value" style="color: ${kbStage.confidence > 0.7 ? '#28a745' : kbStage.confidence > 0.5 ? '#ffc107' : '#dc3545'};">${(kbStage.confidence * 100).toFixed(1)}%</span>
                        </div>
                        <div class="detail-row">
                            <span class="detail-label">Documents Found:</span>
                            <span class="detail-value">${kbStage.documents_found || 0}</span>
                        </div>
                        <div class="detail-row">
                            <span class="detail-label">KB Used:</span>
                            <span class="detail-value">${kbStage.used ? '✅ Yes' : '❌ No'}</span>
                        </div>
                        <div class="detail-row">
                            <span class="detail-label">Success:</span>
                            <span class="detail-value">${kbStage.success ? '✅ Yes' : '❌ No'}</span>
                        </div>
                    </div>
                    <div class="stage-content" style="margin-top: 15px;">
                        <strong style="margin-top: 15px; display: block;">KB Answer:</strong>
                        <div style="margin-top: 10px; padding: 15px; background: #f8f9fa; border-left: 4px solid #007bff; border-radius: 4px; white-space: pre-wrap; font-family: inherit; line-height: 1.6;">
                            ${kbStage.answer || 'No answer available'}
                        </div>
                    </div>
                `);
            }

            // Client Support Stage
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

            // Security Layer 2: Output Validation
            const securityLayer2 = data.stages.security_layer2;
            if (securityLayer2) {
                stagesHtml += createStageCard('🔒 Security Layer 2 (Output)', securityLayer2, `
                    <div class="stage-details">
                        <div class="detail-row">
                            <span class="detail-label">Success:</span>
                            <span class="detail-value">${securityLayer2.success ? '✅ Yes' : '❌ No'}</span>
                        </div>
                        <div class="detail-row">
                            <span class="detail-label">Modified:</span>
                            <span class="detail-value">${securityLayer2.modified ? '✅ Yes' : '❌ No'}</span>
                        </div>
                        ${securityLayer2.error ? `
                        <div class="detail-row">
                            <span class="detail-label">Error:</span>
                            <span class="detail-value" style="color: #dc3545;">${securityLayer2.error}</span>
                        </div>
                        ` : ''}
                    </div>
                    <div class="stage-content" style="margin-top: 15px;">
                        <strong>Validation Method:</strong>
                        <div style="margin-top: 8px; padding: 10px; background: #e9ecef; border-radius: 4px; font-size: 12px;">
                            NeMo Guard NIM - Content Safety & Topic Control
                        </div>
                    </div>
                `);
            }

            // Agent Selection Info
            if (data.orchestrator_output && data.orchestrator_output.required_agents) {
                stagesHtml += createStageCard('🤖 Agent Selection', {success: true}, `
                    <div class="stage-details">
                        <div class="detail-row">
                            <span class="detail-label">Selected Agent:</span>
                            <span class="detail-value" style="background: #856404; color: white; padding: 4px 8px; border-radius: 12px; font-size: 12px;">${data.selected_agent || 'Unknown'}</span>
                        </div>
                        <div class="detail-row">
                            <span class="detail-label">Required Agents:</span>
                            <span class="detail-value">${data.orchestrator_output.required_agents.join(', ')}</span>
                        </div>
                        <div class="detail-row">
                            <span class="detail-label">Response Type:</span>
                            <span class="detail-value">Final Synthesized Answer</span>
                        </div>
                    </div>
                `);
            }

            // Mission Briefs
            if (data.orchestrator_output && data.orchestrator_output.mission_briefs) {
                stagesHtml += createStageCard('📋 Mission Briefs', {success: true}, `
                    <div class="stage-content">
                        ${Object.entries(data.orchestrator_output.mission_briefs).map(([agent, brief]) => `
                            <div style="margin-top: 10px; padding: 15px; background: #fff3cd; border-left: 4px solid #f39c12; border-radius: 4px;">
                                <strong>${agent}:</strong>
                                <div style="margin-top: 8px; white-space: pre-wrap; font-family: inherit; line-height: 1.5;">${brief.substring(0, 500)}${brief.length > 500 ? '...' : ''}</div>
                            </div>
                        `).join('')}
                    </div>
                `);
            }

            stagesContainer.innerHTML = stagesHtml;
        }

        function displayVoiceOutput(data) {
            // Always show the voice output section
            voiceOutputSection.style.display = 'block';

            // Update localized response - handle missing fields
            const detectedLangEl = document.getElementById('detectedLang');
            const localizedResponseEl = document.getElementById('localizedResponse');
            if (detectedLangEl) detectedLangEl.textContent = data.stages?.whisper_stt?.detected_language || 'Unknown';
            if (localizedResponseEl) localizedResponseEl.textContent = data.agent_response || 'No response available';

            // Update audio if available
            if (data.final_response_audio) {
                audioContainer.style.display = 'block';
                audioModel.textContent = data.audio_model_used || 'No audio model';
                sampleRate.textContent = data.audio_sample_rate || 'Unknown rate';

                // Set audio source
                audioSource.src = `data:audio/wav;base64,${data.final_response_audio}`;
                downloadLink.href = `data:audio/wav;base64,${data.final_response_audio}`;
                
                // Load and play audio
                audioPlayer.load();
            } else {
                audioContainer.style.display = 'none';
            }
        }

        function createStageCard(title, stage, content) {
            const statusClass = stage.success ? 'success' : 'error';
            const statusIcon = stage.success ? '✅' : '❌';
            
            return `
                <div class="stage-card ${statusClass} collapsed">
                    <div class="stage-header" onclick="this.parentElement.classList.toggle('collapsed')">
                        <div style="display: flex; align-items: center;">
                            <div class="stage-icon">${statusIcon}</div>
                            <div class="stage-title">${title}</div>
                        </div>
                        <div class="stage-chevron">▼</div>
                    </div>
                    <div class="stage-content">
                        ${content}
                    </div>
                </div>
            `;
        }

        function displayError(message) {
            stagesContainer.innerHTML = `
                <div class="error-message">
                    <strong>Error:</strong> ${message}
                </div>
            `;
        }
    
    