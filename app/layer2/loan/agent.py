"""
Loan Agent - Specialized in loan approval decisions.
Handles multi-turn conversations for loan applications.
"""

from app.schemas.conversation import ConversationState

def run_loan_agent(state: ConversationState) -> ConversationState:
    """
    Loan Agent implementation.
    Evaluates loan applications and handles multi-turn information collection.
    """
    # Get the mission brief from orchestrator
    mission_brief = state.mission_brief.get("loan", "")
    
    # Check if this is a follow-up in a multi-turn conversation
    conversation_context = state.orchestrator_context.get("loan_conversation_active", False)
    
    if not conversation_context:
        # Initial loan application - start information collection
        response = """I'll help you with your loan application. To provide you with the best loan options, I need to collect some information:

REQUIRED INFORMATION:
1. Employment status and monthly income
2. Loan amount requested
3. Loan purpose (home purchase, refinance, etc.)
4. Credit score range (if known)
5. Down payment amount (if applicable)

Please provide this information, and I'll evaluate your loan eligibility and available options.

You can share this information across multiple messages if that's more convenient."""
        
        # Mark that we're in a multi-turn conversation
        state.orchestrator_context["loan_conversation_active"] = True
        state.orchestrator_context["awaiting_client_info"] = True
        state.orchestrator_context["loan_agent_waiting"] = True
        
        # Update state with agent response
        state.agent_feedback = {
            "loan": {
                "status": "completed",
                "response": response,
                "confidence": 0.8,
                "needs_more_info": True,
                "analysis": {
                    "needs_more_work": True,
                    "next_agent_suggested": None  # Wait for client input
                }
            }
        }
        
        state.trace.append("loan:started:information_collection")
        
    else:
        # Follow-up in multi-turn conversation
        # Check if we have enough information to evaluate
        client_info = state.normalized_text_en
        
        # Simple heuristic to check if we have key information
        has_income = any(word in client_info.lower() for word in ["income", "salary", "earn", "make"])
        has_amount = any(word in client_info.lower() for word in ["$", "amount", "need", "request"])
        has_purpose = any(word in client_info.lower() for word in ["home", "house", "car", "personal", "business"])
        
        if has_income and has_amount and has_purpose:
            # We have enough information - evaluate the loan
            response = """Thank you for providing your information. Based on what you've shared:

LOAN EVALUATION SUMMARY:
✅ Information complete - proceeding with evaluation
✅ Eligibility assessment in progress
✅ Available loan options being calculated

NEXT STEPS:
1. I'll calculate your loan eligibility and available rates
2. Client Support will provide you with the complete loan offer
3. You can then proceed with the application or ask questions

Please wait while I complete the evaluation..."""
            
            # Mark evaluation as complete
            state.orchestrator_context["loan_conversation_active"] = False
            state.orchestrator_context["awaiting_client_info"] = False
            state.orchestrator_context["loan_agent_waiting"] = False
            
            # Update state with agent response
            state.agent_feedback = {
                "loan": {
                    "status": "completed",
                    "response": response,
                    "confidence": 0.9,
                    "evaluation_complete": True,
                    "analysis": {
                        "needs_more_work": True,
                        "next_agent_suggested": "client_support"
                    }
                }
            }
            
            state.trace.append("loan:evaluation_complete:ready_for_client_support")
            
        else:
            # Need more information
            missing_info = []
            if not has_income:
                missing_info.append("income/salary information")
            if not has_amount:
                missing_info.append("loan amount needed")
            if not has_purpose:
                missing_info.append("loan purpose")
            
            response = f"""Thank you for the additional information. I still need some details to complete your loan evaluation:

STILL NEEDED:
{chr(10).join([f"- {info}" for info in missing_info])}

Please provide the remaining information so I can evaluate your loan application. You can share this in your next message."""
            
            # Continue waiting for more information
            state.orchestrator_context["awaiting_client_info"] = True
            
            # Update state with agent response
            state.agent_feedback = {
                "loan": {
                    "status": "completed",
                    "response": response,
                    "confidence": 0.7,
                    "needs_more_info": True,
                    "analysis": {
                        "needs_more_work": True,
                        "next_agent_suggested": None  # Still waiting for client input
                    }
                }
            }
            
            state.trace.append("loan:awaiting_more_info")
    
    return state


# Register agent with orchestrator registry
from ..orchestrator.agents.registry import registry

registry.register(
    agent_id="loan_agent",
    description="""
        Handles all loan-related requests: personal loans, mortgage, housing loans,
        car loans, Islamic loans (murabaha, sukuk), loan repayment, credit applications,
        construction financing, loan amounts, guarantees,
        loan eligibility, financing for real estate or vehicles.
    """
)
