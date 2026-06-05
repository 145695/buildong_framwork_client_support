import os

def run():
    with open('script.js', 'r', encoding='utf-8') as f:
        js = f.read()

    html_template = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>BNA Voice Lab</title>
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
    <link href="https://fonts.googleapis.com/css2?family=Bricolage+Grotesque:opsz,wght@12..96,400..700&family=DM+Mono:ital,wght@0,300;0,400;0,500;1,300;1,400;1,500&display=swap" rel="stylesheet">
    <style>
        :root {{
            --bg-color: #060d09;
            --accent-color: #00e87a;
            --text-color: #c2ddc9;
            --muted-color: #6b9478;
            --danger-color: #ff5555;
            --warning-color: #ffc107;
        }}

        * {{
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }}

        body {{
            font-family: 'Bricolage Grotesque', sans-serif;
            background-color: var(--bg-color);
            color: var(--text-color);
            height: 100vh;
            overflow: hidden;
            display: flex;
            flex-direction: column;
            align-items: center;
            justify-content: center;
            position: relative;
        }}

        .mono {{
            font-family: 'DM Mono', monospace;
        }}

        .call-screen {{
            display: flex;
            flex-direction: column;
            align-items: center;
            justify-content: center;
            width: 100%;
            max-width: 600px;
            padding: 20px;
            height: 100%;
            padding-bottom: 80px;
        }}

        /* Orb and Rings */
        .orb-container {{
            position: relative;
            width: 220px;
            height: 220px;
            display: flex;
            justify-content: center;
            align-items: center;
            cursor: pointer;
            margin-bottom: 10px;
            -webkit-tap-highlight-color: transparent;
        }}

        .orb-ring {{
            position: absolute;
            width: 100%;
            height: 100%;
            border-radius: 50%;
            border: 2px solid rgba(0, 232, 122, 0.4);
            opacity: 0;
            pointer-events: none;
        }}

        body.recording .orb-ring:nth-child(1) {{ animation: expandRing 1.5s infinite 0s; }}
        body.recording .orb-ring:nth-child(2) {{ animation: expandRing 1.5s infinite 0.5s; }}
        body.recording .orb-ring:nth-child(3) {{ animation: expandRing 1.5s infinite 1s; }}

        @keyframes expandRing {{
            0% {{ transform: scale(0.8); opacity: 0.8; }}
            100% {{ transform: scale(1.6); opacity: 0; }}
        }}

        .orb {{
            position: relative;
            width: 160px;
            height: 160px;
            border-radius: 50%;
            background: radial-gradient(circle at 35% 35%, #00e87a 0%, #007a40 50%, #002211 100%);
            box-shadow: 0 0 40px rgba(0, 232, 122, 0.3), inset 0 0 20px rgba(255,255,255,0.2);
            animation: breathe 4s ease-in-out infinite;
            z-index: 10;
            transition: all 0.3s ease;
        }}

        @keyframes breathe {{
            0%, 100% {{ transform: scale(1); box-shadow: 0 0 30px rgba(0, 232, 122, 0.2); }}
            50% {{ transform: scale(1.04); box-shadow: 0 0 50px rgba(0, 232, 122, 0.4); }}
        }}

        body.recording .orb {{
            animation: pulse 1s ease-in-out infinite;
            background: radial-gradient(circle at 35% 35%, #33ffa0 0%, #00e87a 40%, #007a40 100%);
        }}

        @keyframes pulse {{
            0%, 100% {{ transform: scale(1.02); box-shadow: 0 0 50px rgba(0, 232, 122, 0.4); }}
            50% {{ transform: scale(1.08); box-shadow: 0 0 80px rgba(0, 232, 122, 0.7); }}
        }}

        /* Waiting state for followup */
        .orb-container.waiting .orb {{
            animation: pulse-waiting 2s ease-in-out infinite;
            background: radial-gradient(circle at 35% 35%, #ffc107 0%, #ff9800 50%, #e65100 100%);
            box-shadow: 0 0 40px rgba(255, 193, 7, 0.4);
        }}
        @keyframes pulse-waiting {{
            0%, 100% {{ transform: scale(1); opacity: 0.8; }}
            50% {{ transform: scale(1.03); opacity: 1; }}
        }}

        /* Agent Label */
        .agent-label {{
            font-size: 0.8rem;
            color: var(--muted-color);
            margin-bottom: 20px;
            letter-spacing: 1.5px;
            text-transform: uppercase;
        }}

        /* Waves */
        .waves {{
            display: flex;
            gap: 4px;
            height: 30px;
            align-items: center;
            margin-bottom: 10px;
            opacity: 0;
            transition: opacity 0.3s ease;
        }}

        body.recording .waves {{
            opacity: 1;
        }}

        .wave-bar {{
            width: 4px;
            background-color: var(--accent-color);
            border-radius: 2px;
            height: 4px;
        }}

        body.recording .wave-bar {{
            animation: wave 0.8s ease-in-out infinite alternate;
        }}

        body.recording .wave-bar:nth-child(1) {{ animation-delay: 0.1s; }}
        body.recording .wave-bar:nth-child(2) {{ animation-delay: 0.3s; }}
        body.recording .wave-bar:nth-child(3) {{ animation-delay: 0.2s; }}
        body.recording .wave-bar:nth-child(4) {{ animation-delay: 0.5s; }}
        body.recording .wave-bar:nth-child(5) {{ animation-delay: 0.1s; }}
        body.recording .wave-bar:nth-child(6) {{ animation-delay: 0.4s; }}
        body.recording .wave-bar:nth-child(7) {{ animation-delay: 0.2s; }}
        body.recording .wave-bar:nth-child(8) {{ animation-delay: 0.5s; }}
        body.recording .wave-bar:nth-child(9) {{ animation-delay: 0.3s; }}

        @keyframes wave {{
            0% {{ height: 6px; }}
            100% {{ height: 26px; }}
        }}

        /* Status & Timer */
        .status-text {{
            font-size: 0.9rem;
            color: var(--text-color);
            min-height: 20px;
            margin-bottom: 5px;
            text-align: center;
            transition: color 0.3s;
        }}

        .timer-text {{
            font-size: 0.85rem;
            color: var(--accent-color);
            min-height: 20px;
            opacity: 0;
            transition: opacity 0.3s;
        }}
        
        body.recording .timer-text {{
            opacity: 1;
        }}

        /* Response Output */
        #voiceOutputSection {{
            margin-top: 30px;
            text-align: center;
            width: 100%;
            max-width: 500px;
            opacity: 0;
            transition: opacity 0.5s ease-in-out;
            min-height: 100px;
            display: flex;
            flex-direction: column;
            align-items: center;
        }}

        .response-text {{
            font-size: 1.15rem;
            line-height: 1.6;
            color: #ffffff;
            font-weight: 300;
        }}

        /* Audio Player */
        #audioContainer {{
            margin-top: 25px;
            width: 100%;
            max-width: 320px;
        }}
        
        audio {{
            width: 100%;
            height: 40px;
            outline: none;
            border-radius: 20px;
        }}
        
        audio::-webkit-media-controls-panel {{
            background-color: rgba(255, 255, 255, 0.1);
        }}
        audio::-webkit-media-controls-current-time-display,
        audio::-webkit-media-controls-time-remaining-display {{
            color: var(--text-color);
        }}

        /* End Call Button */
        .end-call-btn {{
            position: absolute;
            bottom: 40px;
            width: 64px;
            height: 64px;
            border-radius: 50%;
            background-color: var(--danger-color);
            color: white;
            border: none;
            font-size: 28px;
            display: flex;
            align-items: center;
            justify-content: center;
            cursor: pointer;
            box-shadow: 0 4px 15px rgba(255, 85, 85, 0.4);
            transition: transform 0.2s, background-color 0.2s;
            z-index: 50;
        }}

        .end-call-btn:hover {{
            transform: scale(1.05);
            background-color: #e04444;
        }}

        #resultsSection {{ display: none !important; }}
    </style>
</head>
<body>
    <div class="call-screen">
        <div class="orb-container" id="mic-button"
             onmousedown="startRecording()"
             onmouseup="stopRecording()"
             onmouseleave="stopRecording()"
             ontouchstart="startRecording()"
             ontouchend="stopRecording()">
            <div class="orb-ring"></div>
            <div class="orb-ring"></div>
            <div class="orb-ring"></div>
            <div class="orb"></div>
        </div>

        <div class="agent-label mono">BNA · Agent IA</div>

        <div class="waves" id="waves">
            <div class="wave-bar"></div><div class="wave-bar"></div>
            <div class="wave-bar"></div><div class="wave-bar"></div>
            <div class="wave-bar"></div><div class="wave-bar"></div>
            <div class="wave-bar"></div><div class="wave-bar"></div>
            <div class="wave-bar"></div>
        </div>

        <div id="mic-status" class="status-text mono">Prêt à écouter...</div>
        <div id="call-timer" class="timer-text mono">00:00</div>

        <div id="voiceOutputSection" style="display: none;">
            <div id="localizedResponse" class="response-text"></div>
            
            <div id="audioContainer" style="display: none;">
                <audio id="audioPlayer" controls autoplay>
                    <source id="audioSource" type="audio/wav">
                </audio>
                
                <div style="display: none;">
                    <span id="detectedLang"></span>
                    <span id="audioModel"></span>
                    <span id="sampleRate"></span>
                    <a id="downloadLink"></a>
                </div>
            </div>
        </div>
    </div>

    <button class="end-call-btn" onclick="endCall()">📵</button>

    <div id="resultsSection">
        <div id="statusBadge"></div>
        <div id="progressFill"></div>
        <div id="progressText"></div>
        <div id="summaryGrid"></div>
        <div id="stagesContainer"></div>
    </div>
    <input type="file" id="audioInput" style="display: none;">

    <script>
        // --- INJECTED PROXIES & LOGIC ---
        window.isFollowupMode = false;
        window.followupRetries = 0;
        window.lastDetectedLanguage = 'en';
        window.followupTimeout = null;

        const OriginalWebSocket = window.WebSocket;
        const originalSend = OriginalWebSocket.prototype.send;
        OriginalWebSocket.prototype.send = function(data) {{
            if (window.isFollowupMode && !this._followupSent) {{
                originalSend.call(this, JSON.stringify({{type: 'set_is_followup', value: true}}));
                this._followupSent = true;
            }}
            originalSend.call(this, data);
        }};
{js}
        
        // Wrap displayResults cleanly to handle followup fast-path
        const originalDisplayResults = displayResults;
        displayResults = function(data) {{
            if (data.action === 'redirect') {{
                window.location.href = '/loan-eligibility-form?session_id=' + sessionId + '&lang=' + window.lastDetectedLanguage;
                return;
            }}
            if (data.action === 'continue') {{
                dismissFollowup();
                return;
            }}
            if (data.action === 'retry') {{
                window.followupRetries++;
                if (window.followupRetries > 2) {{
                    dismissFollowup();
                }} else {{
                    document.getElementById('mic-button').classList.add('waiting');
                    const micStatus = document.getElementById('mic-status');
                    micStatus.textContent = "Je n'ai pas compris, répondez Oui ou Non";
                    micStatus.style.color = '#ff5555';
                    resetFollowupTimeout();
                }}
                return;
            }}
            
            // Standard execution
            originalDisplayResults(data);
            
            // Check if pipeline response triggers follow-up
            if (data.loan_followup_triggered) {{
                window.isFollowupMode = true;
                window.followupRetries = 0;
                window.lastDetectedLanguage = data.stages?.whisper_stt?.detected_language || 'en';
                
                document.getElementById('mic-button').classList.add('waiting');
                const micStatus = document.getElementById('mic-status');
                micStatus.textContent = 'Oui / Non ?';
                micStatus.style.color = '#ffc107';
                
                resetFollowupTimeout();
            }}
        }};

        function dismissFollowup() {{
            window.isFollowupMode = false;
            window.followupRetries = 0;
            clearTimeout(window.followupTimeout);
            document.getElementById('mic-button').classList.remove('waiting');
            const micStatus = document.getElementById('mic-status');
            micStatus.textContent = 'Ready to speak';
            micStatus.style.color = '#c2ddc9';
        }}

        function resetFollowupTimeout() {{
            clearTimeout(window.followupTimeout);
            window.followupTimeout = setTimeout(() => {{
                dismissFollowup();
            }}, 15000);
        }}

        // Additional UI Logic
        (function() {{
            let callInterval;
            let callSeconds = 0;

            function formatTime(s) {{
                const mins = Math.floor(s / 60);
                const secs = s % 60;
                return `${{mins.toString().padStart(2, '0')}}:${{secs.toString().padStart(2, '0')}}`;
            }}

            const timerEl = document.getElementById('call-timer');
            const orbBtn = document.getElementById('mic-button');
            const voSection = document.getElementById('voiceOutputSection');
            const locResp = document.getElementById('localizedResponse');

            function startTimerUI() {{
                callSeconds = 0;
                timerEl.textContent = '00:00';
                
                voSection.style.opacity = '0';
                setTimeout(() => {{
                    if(voSection.style.opacity === '0') {{
                        voSection.style.display = 'none';
                        locResp.textContent = '';
                    }}
                }}, 500);

                clearInterval(callInterval);
                callInterval = setInterval(() => {{
                    callSeconds++;
                    timerEl.textContent = formatTime(callSeconds);
                }}, 1000);
            }}

            function stopTimerUI() {{
                clearInterval(callInterval);
            }}

            orbBtn.addEventListener('mousedown', startTimerUI);
            orbBtn.addEventListener('touchstart', startTimerUI);

            orbBtn.addEventListener('mouseup', stopTimerUI);
            orbBtn.addEventListener('mouseleave', stopTimerUI);
            orbBtn.addEventListener('touchend', stopTimerUI);

            const observer = new MutationObserver((mutations) => {{
                mutations.forEach((mutation) => {{
                    if (mutation.attributeName === 'style') {{
                        const display = mutation.target.style.display;
                        if (display === 'flex' || display === 'block') {{
                            setTimeout(() => {{
                                mutation.target.style.opacity = '1';
                            }}, 10);
                        }}
                    }}
                }});
            }});
            observer.observe(voSection, {{ attributes: true }});
        }})();
    </script>
</body>
</html>"""

    with open('voice_lab_complete.html', 'w', encoding='utf-8') as f:
        f.write(html_template)
        
run()
