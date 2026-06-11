"""
LLM Service - Handles security screening, NVIDIA API calls, and agent responses.
Runs on its own CPU so LLM calls don't block audio or KB.
"""
import os
import logging
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import Optional, List

logger = logging.getLogger(__name__)

app = FastAPI(title="MACES LLM Service")

# Load models at startup
nemotron_model = None

@app.on_event("startup")
async def startup():
    """Load LLM models on startup"""
    global nemotron_model
    try:
        from app.layer2.shared.model_loader import get_nemotron_model
        nemotron_model = get_nemotron_model()
        print("[LLM Service] Nemotron model loaded")
    except Exception as e:
        print(f"[LLM Service] Nemotron loading failed: {e}")


class TranslationRequest(BaseModel):
    text: str
    source_language: str
    target_language: str = "en"


class TranslationResponse(BaseModel):
    translated_text: str
    safety_label: str


class SecurityCheckRequest(BaseModel):
    text: str


class SecurityCheckResponse(BaseModel):
    is_safe: bool
    risk_score: float
    reason: Optional[str] = None


class AgentRequest(BaseModel):
    message: str
    source_language: str
    session_id: Optional[str] = None
    intent: Optional[str] = None
    required_agents: Optional[List[str]] = None


class AgentResponse(BaseModel):
    response: str
    agent_used: str
    intent: Optional[str] = None


@app.post("/translate", response_model=TranslationResponse)
async def translate_text(req: TranslationRequest):
    """Translate text using Nemotron"""
    if not nemotron_model:
        raise HTTPException(503, "Translation model not loaded")
    
    try:
        translated, safety = nemotron_model.translate_and_sanitize(
            req.text, req.source_language, req.target_language
        )
        return TranslationResponse(translated_text=translated, safety_label=safety)
    except Exception as e:
        raise HTTPException(500, f"Translation failed: {str(e)}")


@app.post("/security/check", response_model=SecurityCheckResponse)
async def security_check(req: SecurityCheckRequest):
    """Run security screening on input text"""
    try:
        from app.security_layer1.security_screening import scan_input
        result = scan_input(req.text)
        return SecurityCheckResponse(
            is_safe=result.get("is_safe", True),
            risk_score=result.get("risk_score", 0.0),
            reason=result.get("reason")
        )
    except Exception as e:
        return SecurityCheckResponse(is_safe=False, risk_score=1.0, reason=str(e))


@app.post("/security/validate-output", response_model=SecurityCheckResponse)
async def validate_output(req: SecurityCheckRequest):
    """Validate output for security"""
    try:
        from app.security_layer2.output_validator import validate_output
        validated = validate_output(req.text)
        modified = validated != req.text
        return SecurityCheckResponse(
            is_safe=True,
            risk_score=0.1 if modified else 0.0,
            reason="Output modified" if modified else None
        )
    except Exception as e:
        return SecurityCheckResponse(is_safe=False, risk_score=1.0, reason=str(e))


@app.post("/agent/process", response_model=AgentResponse)
async def process_agent(req: AgentRequest):
    """Process through the agent pipeline"""
    try:
        from app.layer1.ingestion import ingest_chat_request
        from app.layer2.orchestrator import smart_pm_routing
        from app.schemas.conversation import ChatRequest, SourceChannel
        
        # Create chat request
        chat_request = ChatRequest(
            message=req.message,
            source_language=req.source_language,
            source_channel=SourceChannel.VOICE,
            conversation_id=req.session_id
        )
        
        # Ingest
        state = ingest_chat_request(chat_request)
        
        # Route through orchestrator
        result_state = smart_pm_routing(state)
        
        # Get agent response
        from app.layer2.graph import _run_with_langgraph
        final_state = _run_with_langgraph(result_state)
        
        return AgentResponse(
            response=final_state.final_response_en or "",
            agent_used=final_state.required_agents[0] if final_state.required_agents else "unknown",
            intent=final_state.intent
        )
    except Exception as e:
        raise HTTPException(500, f"Agent processing failed: {str(e)}")


@app.get("/health")
async def health():
    return {
        "status": "healthy",
        "service": "llm-service",
        "nemotron_loaded": nemotron_model is not None
    }