import asyncio
import json
import pytest
from fastapi import WebSocket
from fastapi.testclient import TestClient
from app.main import app
from app.layer2.shared.session_manager import session_manager

@pytest.fixture
def client():
    return TestClient(app)

@pytest.fixture
def session_id():
    # Create a dummy session in the session manager
    sid = "test-session"
    session_manager.sessions[sid] = {"history": [], "last_active": None, "created_at": None}
    return sid

def test_ws_audio_echo_and_status(client, session_id):
    with client.websocket_connect(f"/ws/audio/{session_id}") as websocket:
        # Receive initial status
        init_msg = websocket.receive_json()
        assert init_msg["type"] == "status"
        assert init_msg["state"] == "RECORDING"
        # Send a dummy audio frame (30ms of silence)
        silent_frame = (b"\x00\x00" * 480)
        websocket.send_bytes(silent_frame)
        # Echoed back
        echoed = websocket.receive_bytes()
        assert echoed == silent_frame
        # Send end_of_speech message
        websocket.send_json({"type": "end_of_speech"})
        # Should receive processing status
        proc_status = websocket.receive_json()
        assert proc_status["type"] == "status"
        assert proc_status["state"] == "PROCESSING"
        # Receive response text
        resp = websocket.receive_json()
        assert resp["type"] == "response_text"
        # Finally, should get back to recording state
        rec_status = websocket.receive_json()
        assert rec_status["type"] == "status"
        assert rec_status["state"] == "RECORDING"
