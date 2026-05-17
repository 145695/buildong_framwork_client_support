"""
Security Layer 1 - Input Validation with llm-guard
Handles prompt injection detection and off-topic filtering.
"""

import logging
from llm_guard.input_scanners import PromptInjection, BanTopics
from llm_guard.input_scanners.prompt_injection import MatchType

logger = logging.getLogger(__name__)

# Topics that are not banking related — block them
BANNED_TOPICS = [
    "politics", "religion", "violence", "adult content",
    "coding", "hacking", "personal advice"
]

def scan_input(text: str) -> dict:
    """
    Scan input text for security threats using llm-guard.
    
    Args:
        text: Input text to scan
        
    Returns:
        dict: {
            "is_safe": bool,
            "reason": str or None,
            "risk_score": float
        }
    """
    try:
        # Check 1: Prompt injection attack
        injection_scanner = PromptInjection(threshold=0.8)
        sanitized, is_valid, risk_score = injection_scanner.scan(text)
        
        if not is_valid:
            logger.warning(f"[Security-L1] Prompt injection detected. Score: {risk_score}")
            return {
                "is_safe": False,
                "reason": "Security threat detected. Your request cannot be processed.",
                "risk_score": risk_score
            }

        # Check 2: Off-topic detection
        topic_scanner = BanTopics(topics=BANNED_TOPICS, threshold=0.6)
        sanitized, is_valid, risk_score = topic_scanner.scan(text)

        if not is_valid:
            logger.warning(f"[Security-L1] Off-topic request detected. Score: {risk_score}")
            return {
                "is_safe": False,
                "reason": "I can only assist with BNA banking related questions.",
                "risk_score": risk_score
            }

        logger.debug(f"[Security-L1] Input passed all checks.")
        return {"is_safe": True, "reason": None, "risk_score": 0.0}

    except Exception as e:
        logger.error(f"[Security-L1] ERROR: {type(e).__name__}: {str(e)}")
        # On error → let it pass, do not block the user
        return {"is_safe": True, "reason": None, "risk_score": 0.0}
