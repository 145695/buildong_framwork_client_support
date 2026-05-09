import re
import uuid

from app.schemas.conversation import ChatRequest, ConversationState


PII_PATTERN = re.compile(r"\b\d{10,16}\b")


def _mask_pii(text: str) -> tuple[str, dict[str, str]]:
    pii_map: dict[str, str] = {}
    token_index = 1

    def replacer(match: re.Match[str]) -> str:
        nonlocal token_index
        token = f"[PII_{token_index}]"
        pii_map[token] = match.group(0)
        token_index += 1
        return token

    masked = PII_PATTERN.sub(replacer, text)
    return masked, pii_map


def _translate_to_english(text: str, source_language: str) -> str:
    # Milestone A stub: keep text unchanged.
    _ = source_language
    return text


def ingest_chat_request(payload: ChatRequest) -> ConversationState:
    masked_text, pii_map = _mask_pii(payload.message)
    normalized_text_en = _translate_to_english(masked_text, payload.source_language)

    state = ConversationState(
        conversation_id=payload.conversation_id or str(uuid.uuid4()),
        source_channel=payload.source_channel,
        source_language=payload.source_language,
        original_text=payload.message,
        normalized_text_en=normalized_text_en,
        pii_map=pii_map,
    )
    state.trace.append("layer1:ingestion_complete")
    return state
