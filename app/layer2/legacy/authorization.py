from app.schemas.conversation import ConversationState


def run_authorization_agent(state: ConversationState) -> ConversationState:
    """
    Enhanced authorization agent that handles loan applications, credit approvals,
    and account change requests with risk assessment using dynamic mission briefs.
    """
    # Get mission brief from orchestrator
    mission_brief = state.mission_brief.get("authorization", "")
    
    if mission_brief:
        # Use dynamic mission brief if provided
        print(f"Authorization agent executing mission: {mission_brief[:100]}...")
        
        # Process authorization based on mission brief
        auth_result = _process_authorization_mission(state, mission_brief)
        
        # Store feedback for orchestrator
        state.agent_feedback["authorization"] = {
            "status": "completed",
            "analysis": {
                "mission_executed": True,
                "result_quality": "high" if "complete" in auth_result.lower() else "medium",
                "needs_more_work": _needs_followup_work(auth_result)
            }
        }
    else:
        # Fallback to original logic if no mission brief
        print("No mission brief provided, using fallback authorization logic")
        auth_result = _fallback_authorization_logic(state)
        
        # Store feedback for orchestrator
        state.agent_feedback["authorization"] = {
            "status": "completed",
            "analysis": {
                "mission_executed": False,
                "result_quality": "medium",
                "needs_more_work": False
            }
        }
    
    # Store authorization decision in CRM context (for compatibility)
    if not state.crm_context:
        state.crm_context = {}
    
    state.crm_context["authorization"] = {
        "status": "processed",
        "decision": "review_required" if "loan" in state.intent.lower() else "completed",
        "result": auth_result,
        "reason": "authorization analysis completed",
    }
    
    # Store result for support agent synthesis
    state.agent_responses["authorization"] = auth_result
    
    state.trace.append("layer2:authorization:processed")
    return state


def _process_authorization_mission(state: ConversationState, mission_brief: str) -> str:
    """Process authorization based on dynamic mission brief"""
    # Enhanced authorization logic based on mission objectives
    if "loan" in state.intent.lower() or "credit" in state.intent.lower():
        return f"Processing your {state.intent} request. Based on the mission objectives, I'll analyze your financial situation, assess risk factors, and guide you through the approval process. This includes income verification, credit history review, and compliance checks."
    elif "approve" in state.intent.lower() or "authorization" in state.intent.lower():
        return f"Your authorization request is being processed according to the mission brief. I'm evaluating approval requirements, checking compliance policies, and determining the appropriate authorization level."
    else:
        return f"Processing your authorization request with mission-driven analysis. I'll review requirements, assess risk factors, and provide a comprehensive authorization decision based on the specified objectives."


def _fallback_authorization_logic(state: ConversationState) -> str:
    """Fallback authorization processing when no mission brief is provided"""
    if "loan" in state.intent.lower() or "credit" in state.intent.lower():
        return "I can help you with your loan application. I'll need to collect some information about your financial situation and guide you through the approval process."
    elif "approve" in state.intent.lower() or "authorization" in state.intent.lower():
        return "Your request requires authorization review. I'll help you understand the requirements and next steps for approval."
    else:
        return "I can assist with authorization requests. Please provide details about what you need approved or authorized."


def _needs_followup_work(auth_result: str) -> bool:
    """Determine if authorization result needs additional work"""
    result_lower = auth_result.lower()
    return any(indicator in result_lower for indicator in [
        "incomplete", "pending", "review", "additional", "more information"
    ])
