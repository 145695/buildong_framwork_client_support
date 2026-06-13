from enum import Enum
from typing import Any, Optional, List

from pydantic import BaseModel, Field


class SourceChannel(str, Enum):
    VOICE = "VOICE"
    CHAT = "CHAT"
    EMAIL = "EMAIL"


class ChatRequest(BaseModel):
    message: str = Field(min_length=1, description="Raw user message.")
    source_channel: SourceChannel = SourceChannel.CHAT
    source_language: str = "en"
    conversation_id: str | None = None
    audio: bytes | None = Field(default=None, description="Audio data for voice input.")


class ConversationState(BaseModel):
    conversation_id: str
    source_channel: SourceChannel
    source_language: str
    original_text: str
    normalized_text_en: str
    pii_map: dict[str, str] = Field(default_factory=dict)
    security_status: str = "pass"
    security_reasons: list[str] = Field(default_factory=list)
    intent: str = "general_support"
    intent_category: str = "general"
    target_agent: str = "client_support"
    required_agents: list[str] = Field(default_factory=list)
    agent_responses: dict[str, Any] = Field(default_factory=dict)
    orchestrator_context: dict[str, Any] = Field(default_factory=dict)
    security_context: dict[str, Any] = Field(default_factory=dict)
    retrieval_context: dict[str, Any] = Field(default_factory=dict)
    crm_context: dict[str, Any] = Field(default_factory=dict)
    final_response_en: str = ""
    final_response_localized: str = ""
    final_response_audio: bytes | None = None
    audio_model_used: str | None = None
    audio_sample_rate: int | None = None
    trace: list[str] = Field(default_factory=list)
    mission_brief: dict[str, Any] = Field(default_factory=dict)
    agent_feedback: dict[str, Any] = Field(default_factory=dict)
    kb_result: str | None = None
    loan_result: Any | None = None
    reconstructed_query: Optional[str] = None
    conversation_history: List[Any] = Field(default_factory=list)  # Previous turns for context


class ChatResponse(BaseModel):
    conversation_id: str
    source_channel: SourceChannel
    source_language: str
    response: str
    response_en: str
    intent: str
    required_agents: list[str]
    security_status: str
    trace: list[str]
    response_audio: bytes | None = None
    audio_model_used: str | None = None
    audio_sample_rate: int | None = None
