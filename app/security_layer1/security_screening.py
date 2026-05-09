"""
Security Layer 1 - Initial Security Screening
Handles basic security checks, PII detection, and initial threat assessment.
"""

from typing import Dict, Any
from app.schemas.conversation import ConversationState

def run_security_screening(state: ConversationState) -> ConversationState:
    """
    Layer 1 Security: Initial security screening and threat detection.
    
    Checks for:
    - PII (Personally Identifiable Information)
    - Basic threat patterns
    - Security keywords
    - Immediate risk assessment
    """
    text = state.normalized_text_en.lower()
    
    # Initialize security context
    if not hasattr(state, 'security_context'):
        state.security_context = {}
    
    # PII Detection
    pii_detected = _detect_pii(text)
    if pii_detected:
        state.security_context['pii_detected'] = True
        state.security_context['pii_types'] = pii_detected
        state.security_status = "pii_review"
        state.security_reasons.append("pii_detected_in_layer1")
    
    # Threat Pattern Detection
    threat_level = _detect_threat_patterns(text)
    state.security_context['threat_level'] = threat_level
    
    # Security Intent Detection
    security_intent = _detect_security_intent(text)
    if security_intent:
        state.security_context['security_intent'] = security_intent
        state.security_context['requires_layer2'] = True
        state.security_status = "security_review"
        state.security_reasons.append("security_intent_detected")
    
    # Store layer 1 results
    state.agent_responses["security_layer1"] = {
        "screening_complete": True,
        "pii_detected": bool(pii_detected),
        "threat_level": threat_level,
        "security_intent": security_intent,
        "requires_layer2": security_intent is not None
    }
    
    state.trace.append("security_layer1:screening_complete")
    return state


def _detect_pii(text: str) -> list:
    """Detect common PII patterns in text."""
    import re
    
    pii_types = []
    
    # Email pattern
    if re.search(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b', text):
        pii_types.append("email")
    
    # Phone pattern
    if re.search(r'\b\d{3}[-.]?\d{3}[-.]?\d{4}\b', text):
        pii_types.append("phone")
    
    # SSN pattern
    if re.search(r'\b\d{3}-\d{2}-\d{4}\b', text):
        pii_types.append("ssn")
    
    # Credit card pattern
    if re.search(r'\b\d{4}[- ]?\d{4}[- ]?\d{4}[- ]?\d{4}\b', text):
        pii_types.append("credit_card")
    
    return pii_types


def _detect_threat_patterns(text: str) -> str:
    """Detect basic threat patterns and assign risk level."""
    high_threats = ["hack", "breach", "compromised", "stolen", "fraud", "scam"]
    medium_threats = ["suspicious", "unauthorized", "weird", "strange"]
    low_threats = ["question", "concern", "check"]
    
    if any(threat in text for threat in high_threats):
        return "high"
    elif any(threat in text for threat in medium_threats):
        return "medium"
    elif any(threat in text for threat in low_threats):
        return "low"
    
    return "none"


def _detect_security_intent(text: str) -> str:
    """Detect if user has security-related intent."""
    security_keywords = {
        "fraud_report": ["fraud", "scam", "deceptive", "tricked"],
        "account_compromise": ["compromised", "hacked", "breach", "unauthorized access"],
        "card_theft": ["stolen card", "lost card", "card theft", "missing card"],
        "identity_theft": ["identity theft", "someone used my identity", "impersonation"],
        "suspicious_activity": ["suspicious activity", "unusual transaction", "didn't make this purchase"]
    }
    
    for intent, keywords in security_keywords.items():
        if any(keyword in text for keyword in keywords):
            return intent
    
    return None
