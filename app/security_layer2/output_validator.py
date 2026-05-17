import logging
import time
import os
from langchain_nvidia_ai_endpoints import ChatNVIDIA
from app.layer2.shared.model_loader import settings
import re

logger = logging.getLogger(__name__)

SAFE_RESPONSE = (
    "For security reasons, I cannot share that information. "
    "Please visit your nearest BNA branch for assistance."
)

# Simple fallback patterns for when API is unavailable
FORBIDDEN_PATTERNS = [
    r'\bPIN\s*(?:code|number|is|:)?\s*\d{4,6}\b',
    r'\bpassword\s*(?:is|:)\s*\S+\b',
    r'\bCVV\s*(?:is|:)?\s*\d{3,4}\b',
    r'\bsecret\s*code\s*(?:is|:)?\s*\d+\b',
]

def _pattern_fallback(text: str) -> str:
    for pattern in FORBIDDEN_PATTERNS:
        if re.search(pattern, text, re.IGNORECASE):
            logger.warning("[Security-L2] Fallback: sensitive pattern detected.")
            return SAFE_RESPONSE
    return text

def _call_nemoguard(text: str, max_retries: int = 3) -> str:
    for attempt in range(max_retries):
        try:
            # Check 1: Content Safety
            safety_client = ChatNVIDIA(
                model="nvidia/llama-3.1-nemoguard-8b-content-safety",
                api_key=settings.NVIDIA_API_KEY_LLAMA,
                temperature=0,
                max_tokens=10,
            )
            safety_result = safety_client.invoke([
                {"role": "user", "content": text}
            ])
            safety_label = safety_result.content.strip().lower()
            logger.debug(f"[Security-L2] Content safety: {safety_label}")

            if "unsafe" in safety_label:
                logger.warning("[Security-L2] Unsafe content blocked.")
                return SAFE_RESPONSE

            # Check 2: Topic Control
            topic_client = ChatNVIDIA(
                model="nvidia/llama-3.1-nemoguard-8b-topic-control",
                api_key=settings.NVIDIA_API_KEY_LLAMA,
                temperature=0,
                max_tokens=10,
            )
            topic_result = topic_client.invoke([
                {
                    "role": "system",
                    "content": (
                        "You are a topic validator for BNA bank. "
                        "Only banking-related content is allowed. "
                        "Reply 'on-topic' or 'off-topic' only."
                    )
                },
                {"role": "user", "content": text}
            ])
            topic_label = topic_result.content.strip().lower()
            logger.debug(f"[Security-L2] Topic control: {topic_label}")

            if "off-topic" in topic_label:
                logger.warning("[Security-L2] Off-topic response blocked.")
                return SAFE_RESPONSE

            logger.debug("[Security-L2] Output passed all NeMo checks.")
            return text

        except Exception as e:
            logger.warning(
                f"[Security-L2] Attempt {attempt + 1}/{max_retries} failed: {str(e)}"
            )
            if attempt < max_retries - 1:
                time.sleep(2 ** attempt)  # 1s, 2s, 4s
            else:
                logger.error(
                    "[Security-L2] NeMo API unavailable after retries. "
                    "Switching to pattern fallback."
                )
                return _pattern_fallback(text)

def validate_output(text: str) -> str:
    return _call_nemoguard(text)
