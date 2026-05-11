"""
Knowledge Base Agent - Knows all banking policies and procedures.
Provides policy information and regulatory guidance.
"""

from app.schemas.conversation import ConversationState

def run_knowledge_base_agent(state: ConversationState) -> ConversationState:
    """
    Knowledge Base Agent implementation.
    Retrieves policy information and provides regulatory guidance.
    """
    # Get the mission brief from orchestrator
    mission_brief = state.mission_brief.get("knowledge_base", "")
    
    # Process the request based on policy knowledge
    if "mortgage" in state.normalized_text_en.lower() or "loan" in state.normalized_text_en.lower():
        response = """Based on our current policies:

MORTGAGE LOAN POLICIES:
- Maximum loan-to-value ratio: 80% for first homes
- Interest rates: Variable based on credit score and income
- Required documentation: Proof of income, bank statements, employment verification
- Processing time: 2-3 weeks for complete applications

For specific loan terms and conditions, I recommend consulting with our loan specialist who can provide personalized rates based on your financial situation."""
    elif "account" in state.normalized_text_en.lower():
        response = """ACCOUNT POLICIES:
- Minimum balance requirements: None for basic accounts
- Transaction limits: $10,000 daily withdrawal limit
- Monthly fees: $0 for accounts with direct deposit
- Overdraft protection: Available upon request

Is there a specific aspect of account management you'd like to know more about?"""
    else:
        response = """I can help you with information about:
- Banking policies and procedures
- Account management guidelines
- Loan requirements and processes
- Regulatory compliance information
- Service terms and conditions

Please let me know which specific policy area you're interested in."""
    
    # Store KB result in state for client_support to use
    state.kb_result = response
    
    # Update state with agent feedback
    state.agent_feedback = {
        "knowledge_base": {
            "status": "completed",
            "response": response,
            "confidence": 0.9,
            "analysis": {
                "needs_more_work": False,
                "next_agent_suggested": "client_support"
            }
        }
    }
    
    state.trace.append("knowledge_base:completed:policy_provided")
    return state


# Register agent with orchestrator registry
from ..orchestrator.agents.registry import registry

registry.register(
    agent_id="kb_agent",
    description="""
        Answers questions about bank policies, procedures, fees, interest rates,
        regulatory compliance, account opening conditions, document requirements,
        banking regulations, product information, service explanations, Islamic
        compliance rules, and general banking advice.
    """
)
