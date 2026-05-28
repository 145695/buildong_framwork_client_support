"""
Security Layer 1 - Input Validation with llm-guard
Handles prompt injection detection and off-topic filtering.
"""

import logging
import re
from llm_guard.input_scanners import PromptInjection, BanTopics

logger = logging.getLogger(__name__)

# Topics that are not banking related — block them
BANNED_TOPICS = [
    "politics", "religion", "violence", "hacking"
]

# Banking-related terms used to reduce false positives for legitimate queries
BANKING_TERMS = [
    "account", "card", "loan", "mortgage", "deposit", "balance",
    "transaction", "branch", "customer service", "BNA", "bank", "payment"
]


def _is_bank_related(text: str) -> bool:
    lower_text = text.lower()
    return any(term in lower_text for term in BANKING_TERMS)


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
        # Basic normalization to reduce false positives (collapse ellipses, trim)
        text_clean = re.sub(r'\.{2,}', '.', (text or '').strip())

        # Explicit phrases that commonly indicate prompt-injection attempts
        TRIGGER_PHRASES = [
            "ignore previous",
            "ignore all previous",
            "forget",
            "do not follow",
            "don't follow",
            "only answer",
            "follow these instructions",
            "bypass",
            "jailbreak",
            "system message"
        ]

        lower_text = (text_clean or '').lower()

        # If trigger phrases present, keep strict threshold. Otherwise relax for
        # short, clearly banking-related queries to reduce false positives.
        if any(phrase in lower_text for phrase in TRIGGER_PHRASES):
            injection_threshold = 0.8
            logger.info("[Security-L1] Detected potential trigger phrase; running strict injection scan.")
        elif _is_bank_related(text_clean) and len(text_clean) < 300:
            injection_threshold = 0.95
            logger.info(f"[Security-L1] Banking-related short query detected; using higher injection threshold {injection_threshold} to avoid false positives.")
        else:
            injection_threshold = 0.8

        # Check 1: Prompt injection attack
        injection_scanner = PromptInjection(threshold=injection_threshold)
        sanitized, is_valid, risk_score = injection_scanner.scan(text_clean)

        if not is_valid:
            # Conservative bypass: short, clearly banking-related queries
            # may be falsely flagged by model-based scanners. Allow them
            # while logging the incident for review (but keep the risk_score).
            if _is_bank_related(text_clean) and len(text_clean) < 300 and not any(phrase in lower_text for phrase in TRIGGER_PHRASES):
                logger.info(f"[Security-L1] Injection scanner flagged query (score={risk_score}) but allowed due to banking-related short query.")
                return {"is_safe": True, "reason": None, "risk_score": risk_score}

            logger.warning(f"[Security-L1] Prompt injection detected. Score: {risk_score}")
            return {
                "is_safe": False,
                "reason": "Security threat detected. Your request cannot be processed.",
                "risk_score": risk_score
            }

        # Check 2: Off-topic detection
        topic_scanner = BanTopics(topics=BANNED_TOPICS, threshold=0.75)
        sanitized, is_valid, risk_score = topic_scanner.scan(text_clean)

        if not is_valid:
            if _is_bank_related(text_clean):
                logger.info(f"[Security-L1] Off-topic scanner flagged query, but banking terms were detected. Allowing input. Score: {risk_score}")
                return {"is_safe": True, "reason": None, "risk_score": risk_score}

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
