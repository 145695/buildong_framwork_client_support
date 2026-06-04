import time
import uuid
import logging
from typing import Dict

logger = logging.getLogger(__name__)

from app.schemas.conversation_context import ConversationContext, TurnRecord

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
        "orchestrator_context": {},  # Store context between turns
        "waiting_for_eligibility": False,  # Track if waiting for yes/no answer
        "eligibility_language": "en",  # Language for eligibility response
        "conversation_context": ConversationContext(session_id=session_id),
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

def save_orchestrator_context(session_id: str, orchestrator_context: dict):
    """Save orchestrator context for this session."""
    session = sessions.get(session_id)
    if session:
        session["orchestrator_context"] = orchestrator_context
        session["last_active"] = time.time()
        logger.debug(f"[Session] Orchestrator context saved for {session_id}")
        print(f"💾 SESSION CONTEXT: Saved eligibility_test_asked={orchestrator_context.get('eligibility_test_asked', False)} for {session_id}")

def get_orchestrator_context(session_id: str) -> dict:
    """Retrieve stored orchestrator context for this session."""
    session = sessions.get(session_id)
    if session:
        context = session.get("orchestrator_context", {})
        logger.debug(f"[Session] Orchestrator context retrieved for {session_id}")
        print(f"📖 SESSION CONTEXT: Retrieved eligibility_test_asked={context.get('eligibility_test_asked', False)} for {session_id}")
        return context
    return {}

def set_waiting_for_eligibility_answer(session_id: str, language: str = "en"):
    """Mark that we're waiting for eligibility yes/no answer in next turn."""
    session = sessions.get(session_id)
    if session:
        session["waiting_for_eligibility"] = True
        session["eligibility_language"] = language  # Store user language for static response
        session["last_active"] = time.time()
        print(f"⏳ ELIGIBILITY: Waiting for yes/no answer in {language} for {session_id}")
        logger.debug(f"[Session] Waiting for eligibility answer for {session_id}")

def is_waiting_for_eligibility_answer(session_id: str) -> bool:
    """Check if session is waiting for eligibility yes/no answer."""
    session = sessions.get(session_id)
    return session.get("waiting_for_eligibility", False) if session else False

def get_eligibility_language(session_id: str) -> str:
    """Get the language for eligibility response."""
    session = sessions.get(session_id)
    return session.get("eligibility_language", "en") if session else "en"

def clear_eligibility_flag(session_id: str):
    """Clear the waiting-for-eligibility flag after processing response."""
    session = sessions.get(session_id)
    if session:
        session["waiting_for_eligibility"] = False
        session["last_active"] = time.time()
        print(f"✅ ELIGIBILITY: Flag cleared for {session_id}")
        logger.debug(f"[Session] Eligibility flag cleared for {session_id}")

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

    def save_orchestrator_context(self, session_id: str, orchestrator_context: dict):
        """Save orchestrator context for this session."""
        save_orchestrator_context(session_id, orchestrator_context)

    def get_orchestrator_context(self, session_id: str) -> dict:
        """Retrieve stored orchestrator context for this session."""
        return get_orchestrator_context(session_id)

def get_conversation_context(session_id: str) -> ConversationContext:
    """Retrieve conversation context"""
    session = get_session(session_id)
    if not session:
        return None
    return session.get("conversation_context", ConversationContext(session_id=session_id))

def add_turn_record(session_id: str, turn: TurnRecord):
    """Record a new turn in conversation"""
    session = get_session(session_id)
    if session:
        ctx = session.get("conversation_context", ConversationContext(session_id=session_id))
        ctx.add_turn(turn)
        session["conversation_context"] = ctx
        session["last_active"] = time.time()
        print(f"📝 TURN {turn.turn_number}: User='{turn.user_input[:40]}' Agent={turn.agent_routed_to}")

def set_agent_waiting_state(session_id: str, agent_name: str, input_type: str, context_data: Dict = None):
    """Set what agent is expecting next"""
    session = get_session(session_id)
    if session:
        ctx = session.get("conversation_context", ConversationContext(session_id=session_id))
        ctx.active_agent = agent_name
        ctx.waiting_for_response_from = agent_name
        ctx.waiting_for_input_type = input_type
        if context_data:
            ctx.agent_context.update(context_data)
        session["conversation_context"] = ctx
        print(f"⏳ WAITING: {agent_name} expects {input_type}")

def set_eligibility_declined(session_id: str, declined: bool = True):
    """Mark that user declined eligibility test, don't ask again"""
    session = get_session(session_id)
    if session:
        ctx = session.get("conversation_context", ConversationContext(session_id=session_id))
        ctx.eligibility_declined = declined
        session["conversation_context"] = ctx
        print(f"🚫 ELIGIBILITY: Declined flag set to {declined} for {session_id}")

def is_eligibility_declined(session_id: str) -> bool:
    """Check if user already declined eligibility test"""
    session = get_session(session_id)
    if session:
        ctx = session.get("conversation_context", ConversationContext(session_id=session_id))
        return ctx.eligibility_declined
    return False

# Export a singleton instance
session_manager = SessionManager()
