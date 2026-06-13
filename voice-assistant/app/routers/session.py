from fastapi import APIRouter, HTTPException
from app.layer2.shared.session_manager import create_session, end_session

router = APIRouter(prefix="/session", tags=["Session Management"])

@router.post("/create", summary="Create new session")
async def create_session_endpoint():
    """Create a new conversation session"""
    try:
        session_id = create_session()
        return {"session_id": session_id}
    except Exception as e:
        raise HTTPException(500, f"Failed to create session: {str(e)}")

@router.delete("/{session_id}", summary="End session")
async def end_session_endpoint(session_id: str):
    """End a conversation session and clean up history"""
    try:
        end_session(session_id)
        return {"success": True, "message": "Session ended"}
    except Exception as e:
        raise HTTPException(500, f"Failed to end session: {str(e)}")
