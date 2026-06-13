"""
Client Support Agent - Assembles agent responses into client-friendly answers.
Always included in the workflow, waits for other agents' responses.
"""

from app.schemas.conversation import ConversationState

def run_client_support_agent(state: ConversationState) -> ConversationState:
    """
    Client Support Agent implementation.
    Assembles responses from other agents into client-friendly format.
    """
    # Get responses from other agents
    agent_responses = {}
    
    if state.agent_feedback:
        for agent_name, feedback in state.agent_feedback.items():
            if feedback.get("status") == "completed":
                agent_responses[agent_name] = feedback.get("response", "")
    
    # Generate final response based on available agent responses
    if "knowledge_base" in agent_responses:
        # Policy information from knowledge base
        kb_response = agent_responses["knowledge_base"]
        final_response = f"""Thank you for your inquiry. Here's the information you requested:

{kb_response}

If you need more specific details or have additional questions, please let me know. I'm here to help you understand our policies and find the best solution for your needs."""
    
    elif "loan" in agent_responses:
        # Loan agent response
        loan_response = agent_responses["loan"]
        final_response = f"""Regarding your loan application:

{loan_response}

I'm here to guide you through the entire process. If you have any questions about the information requested or need clarification on any step, please don't hesitate to ask."""
    
    else:
        # General support response
        final_response = """Hello! I'm here to help you with your banking needs.

I can assist you with:
- Account information and balances
- Loan applications and inquiries
- Policy questions and procedures
- General banking services

Please let me know how I can help you today, and I'll make sure you get the assistance you need."""
    
    # Format for specific channels if needed
    if state.source_channel.value == "email":
        final_response = f"""Subject: Response to Your Banking Inquiry

Dear Customer,

{final_response}

Best regards,
Customer Support Team
[Your Bank Name]

---
This email response was generated based on your specific inquiry.
"""
    
    elif state.source_channel.value == "voice":
        # More conversational tone for voice
        final_response = f"""{final_response}

Is there anything else I can help you with today?"""
    
    # Update state with final response
    state.final_response_en = final_response
    state.final_response_localized = final_response
    
    state.agent_feedback = {
        "client_support": {
            "status": "completed",
            "response": final_response,
            "confidence": 0.95,
            "analysis": {
                "needs_more_work": False,
                "next_agent_suggested": None
            }
        }
    }
    
    state.trace.append("client_support:completed:final_response_generated")
    return state


# Register agent with orchestrator registry
from ..orchestrator.agents.registry import registry

registry.register(
    agent_id="client_support",
    description="""
        Manages operational banking requests: card issues, account management,
        transfers, withdrawals, complaints, identity verification, blocked cards,
        account unblocking, transaction disputes, PIN issues, balance inquiries,
        and general customer support.
    """
)
