from fastapi import APIRouter

from app.layer1.ingestion import ingest_chat_request
from app.layer2.graph import run_multi_agent_core
from app.layer3.delivery import deliver_response
from app.schemas.conversation import ChatRequest, ChatResponse

router = APIRouter(prefix="/chat", tags=["Client Support"])


@router.post("", response_model=ChatResponse, summary="Milestone A chat flow")
async def chat(payload: ChatRequest) -> ChatResponse:
    state = ingest_chat_request(payload)
    
    # Security is now handled within the multi-agent core through security layers
    state = await run_multi_agent_core(state)
    
    if state.security_status != "blocked":
        state = deliver_response(state)

    return ChatResponse(
        conversation_id=state.conversation_id,
        source_channel=state.source_channel,
        source_language=state.source_language,
        response=state.final_response_localized or state.final_response_en,
        response_en=state.final_response_en,
        intent=state.intent,
        required_agents=state.required_agents,
        security_status=state.security_status,
        trace=state.trace,
    )
