"""
Security Layer 2 - Advanced Security Processing
Handles deep security analysis, fraud investigation, and advanced threat assessment.
"""

from typing import Dict, Any
from app.schemas.conversation import ConversationState

def run_advanced_security(state: ConversationState) -> ConversationState:
    """
    Layer 2 Security: Advanced security analysis and investigation.
    
    Performs:
    - Deep fraud pattern analysis
    - Risk scoring
    - Security action recommendations
    - Escalation decisions
    """
    text = state.normalized_text_en
    
    # Get layer 1 results
    layer1_results = state.agent_responses.get("security_layer1", {})
    security_context = state.security_context.copy() if hasattr(state, 'security_context') else {}
    
    # Advanced Fraud Analysis
    fraud_analysis = _advanced_fraud_analysis(text, layer1_results)
    security_context['fraud_analysis'] = fraud_analysis
    
    # Risk Scoring
    risk_score = _calculate_risk_score(text, layer1_results, fraud_analysis)
    security_context['risk_score'] = risk_score
    
    # Security Action Recommendations
    actions = _recommend_security_actions(fraud_analysis, risk_score)
    security_context['recommended_actions'] = actions
    
    # Escalation Decision
    escalation_level = _determine_escalation(risk_score, fraud_analysis)
    security_context['escalation_level'] = escalation_level
    
    # Update security status
    if risk_score >= 8:
        state.security_status = "critical"
        state.security_reasons.append("high_risk_detected_layer2")
    elif risk_score >= 5:
        state.security_status = "high"
        state.security_reasons.append("medium_risk_detected_layer2")
    else:
        state.security_status = "monitoring"
        state.security_reasons.append("low_risk_layer2")
    
    # Store layer 2 results
    state.agent_responses["security_layer2"] = {
        "analysis_complete": True,
        "fraud_analysis": fraud_analysis,
        "risk_score": risk_score,
        "recommended_actions": actions,
        "escalation_level": escalation_level
    }
    
    # Update security context
    state.security_context = security_context
    
    state.trace.append("security_layer2:advanced_analysis_complete")
    return state


def _advanced_fraud_analysis(text: str, layer1_results: Dict) -> Dict:
    """Perform advanced fraud pattern analysis."""
    fraud_patterns = {
        "impostor_scenario": _check_impostor_patterns(text),
        "account_takeover": _check_account_takeover_patterns(text),
        "transaction_fraud": _check_transaction_fraud_patterns(text),
        "phishing_attempt": _check_phishing_patterns(text),
        "social_engineering": _check_social_engineering_patterns(text)
    }
    
    # Combine with layer 1 threat level
    threat_level = layer1_results.get("threat_level", "none")
    fraud_patterns["overall_threat"] = threat_level
    
    return fraud_patterns


def _check_impostor_patterns(text: str) -> bool:
    """Check for impostor/scammer patterns."""
    impostor_indicators = [
        "pretending to be", "claiming to be", "said they were from",
        "caller claimed", "email said", "text message claimed",
        "someone called saying", "received call from"
    ]
    return any(indicator in text for indicator in impostor_indicators)


def _check_account_takeover_patterns(text: str) -> bool:
    """Check for account takeover indicators."""
    takeover_indicators = [
        "account locked", "account suspended", "unusual login",
        "someone accessed", "password changed", "email changed",
        "can't access", "account hacked", "security breach"
    ]
    return any(indicator in text for indicator in takeover_indicators)


def _check_transaction_fraud_patterns(text: str) -> bool:
    """Check for transaction fraud patterns."""
    fraud_indicators = [
        "unauthorized charge", "didn't make purchase", "fraudulent transaction",
        "stolen card used", "fake transaction", "suspicious charge",
        "never bought this", "don't recognize charge"
    ]
    return any(indicator in text for indicator in fraud_indicators)


def _check_phishing_patterns(text: str) -> bool:
    """Check for phishing attempt patterns."""
    phishing_indicators = [
        "click the link", "verify account", "update password",
        "suspended account", "urgent action", "immediate attention",
        "act now", "account will be closed", "security alert"
    ]
    return any(indicator in text for indicator in phishing_indicators)


def _check_social_engineering_patterns(text: str) -> bool:
    """Check for social engineering tactics."""
    social_engineering_indicators = [
        "urgent request", "immediate payment", "wire transfer",
        "gift cards", "bitcoin", "cryptocurrency", "keep secret",
        "don't tell anyone", "confidential", "emergency"
    ]
    return any(indicator in text for indicator in social_engineering_indicators)


def _calculate_risk_score(text: str, layer1_results: Dict, fraud_analysis: Dict) -> int:
    """Calculate overall security risk score (1-10)."""
    score = 0
    
    # Base score from threat level
    threat_level = layer1_results.get("threat_level", "none")
    if threat_level == "high":
        score += 4
    elif threat_level == "medium":
        score += 2
    elif threat_level == "low":
        score += 1
    
    # Add points for detected fraud patterns
    fraud_patterns = fraud_analysis.get("fraud_patterns", {})
    for pattern, detected in fraud_patterns.items():
        if detected and pattern != "overall_threat":
            score += 2
    
    # PII detection adds risk
    if layer1_results.get("pii_detected"):
        score += 1
    
    # Cap at 10
    return min(score, 10)


def _recommend_security_actions(fraud_analysis: Dict, risk_score: int) -> list:
    """Recommend security actions based on analysis."""
    actions = []
    
    if risk_score >= 8:
        actions.extend([
            "immediate_account_freeze",
            "contact_security_team",
            "file_police_report",
            "identity_protection_enrollment"
        ])
    elif risk_score >= 5:
        actions.extend([
            "password_reset",
            "two_factor_enforcement",
            "transaction_monitoring",
            "security_review"
        ])
    else:
        actions.extend([
            "password_change_recommendation",
            "security_alert_setup",
            "monitoring_enhancement"
        ])
    
    # Specific actions based on fraud patterns
    if fraud_analysis.get("account_takeover"):
        actions.append("account_recovery_process")
    
    if fraud_analysis.get("transaction_fraud"):
        actions.append("dispute_fraudulent_charges")
    
    return actions


def _determine_escalation(risk_score: int, fraud_analysis: Dict) -> str:
    """Determine escalation level."""
    if risk_score >= 8:
        return "critical_escalation"
    elif risk_score >= 6:
        return "high_escalation"
    elif risk_score >= 4:
        return "medium_escalation"
    else:
        return "low_escalation"
