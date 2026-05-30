import time
import uuid
import logging

logger = logging.getLogger(__name__)

SESSION_TIMEOUT = 300  # 5 minutes of inactivity = session ends

sessions = {}  # in-memory store: session_id → session data

def create_session() -> str:
    session_id = str(uuid.uuid4())
    sessions[session_id] = {
        "history": [],
        "last_active": time.time(),
        "created_at": time.time(),
        "audio_state": "IDLE",
        "is_audio_session": False,
    }
    print(f"🟢 SESSION START: {session_id}")
    logger.debug(f"[Session] Created: {session_id}")
    return session_id

def get_session(session_id: str) -> dict:
    session = sessions.get(session_id)
    if not session:
        return None
    # Check if session expired
    if time.time() - session["last_active"] > SESSION_TIMEOUT:
        end_session(session_id)
        logger.debug(f"[Session] Expired: {session_id}")
        return None
    return session

def add_to_history(session_id: str, user_message: str, avatar_response: str):
    session = get_session(session_id)
    if not session:
        return
    session["history"].append({
        "user": user_message,
        "avatar": avatar_response
    })
    session["last_active"] = time.time()
    # Keep only last 5 turns to avoid token overflow
    if len(session["history"]) > 5:
        session["history"] = session["history"][-5:]
    print(f"💬 SESSION HISTORY: User='{user_message[:50]}...' | Avatar='{avatar_response[:50]}...' | Session={session_id}")
    logger.debug(f"[Session] History updated for: {session_id}")

def end_session(session_id: str):
    if session_id in sessions:
        del sessions[session_id]
        print(f"🔴 SESSION END: {session_id}")
        logger.debug(f"[Session] Ended: {session_id}")

def update_audio_state(session_id: str, new_state: str):
    """Update the audio_state field for a session."""
    session = sessions.get(session_id)
    if session:
        session["audio_state"] = new_state
        session["last_active"] = time.time()
        logger.debug(f"[Session] Audio state updated to {new_state} for {session_id}")

def get_audio_state(session_id: str) -> str:
    """Retrieve the current audio_state for a session, or None if not found."""
    session = sessions.get(session_id)
    return session.get("audio_state") if session else None

def get_history_as_text(session_id: str) -> str:
    session = get_session(session_id)
    if not session or not session["history"]:
        return ""
    lines = []
    for turn in session["history"]:
        lines.append(f"Customer: {turn['user']}")
        lines.append(f"Avatar: {turn['avatar']}")
    return "\n".join(lines)

# Simple session manager wrapper for import compatibility
class SessionManager:
    def __init__(self):
        self.sessions = sessions

    def update_audio_state(self, session_id: str, new_state: str):
        """Update the audio_state field for a session."""
        session = self.sessions.get(session_id)
        if session:
            session["audio_state"] = new_state
            session["last_active"] = time.time()
            logger.debug(f"[Session] Audio state updated to {new_state} for {session_id}")

    def get_audio_state(self, session_id: str) -> str:
        """Retrieve the current audio_state for a session, or None if not found."""
        session = self.sessions.get(session_id)
        return session.get("audio_state") if session else None

# Export a singleton instance
session_manager = SessionManager()
    
