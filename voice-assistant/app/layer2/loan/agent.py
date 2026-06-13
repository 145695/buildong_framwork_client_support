"""
Loan Agent - Specialized in loan approval decisions.
Handles multi-turn conversations for loan applications and eligibility tests.
"""

from app.schemas.conversation import ConversationState

def run_loan_agent(state: ConversationState) -> ConversationState:
    """
    Loan Agent implementation.
    Handles eligibility test flow and loan applications.
    Now context-aware with turn-based conversation architecture.
    """
    print(f"[Loan Agent] ENTER run_loan_agent for session {state.conversation_id}")
    
    # Get conversation context from session
    from app.layer2.shared.session_manager import get_conversation_context, set_agent_waiting_state, add_turn_record
    from app.schemas.conversation_context import TurnRecord
    conv_ctx = get_conversation_context(state.conversation_id)
    print(f"[Loan Agent] conv_ctx={conv_ctx is not None}")
    
    # Check if THIS agent was the last active agent
    last_turn = conv_ctx.get_last_turn() if conv_ctx else None
    agent_history = conv_ctx.get_agent_history("loan_agent") if conv_ctx else []
    
    # Build agent memory from conversation history
    agent_memory = ""
    if agent_history:
        agent_memory = "Your previous responses in this conversation:\n"
        for turn in agent_history:
            agent_memory += f"- You said: {turn.agent_response}\n"
    
    # Get the mission brief from orchestrator
    mission_brief = state.mission_brief.get("loan", "")
    
    # Check if we're in eligibility test mode
    eligibility_test_active = state.orchestrator_context.get("eligibility_test_active", False)
    eligibility_test_asked = state.orchestrator_context.get("eligibility_test_asked", False)
    eligibility_test_answer = state.orchestrator_context.get("eligibility_test_answer", None)
    
    print(f"[Loan Agent] eligibility_test_active={eligibility_test_active}, eligibility_test_asked={eligibility_test_asked}, eligibility_test_answer={eligibility_test_answer}")

    # Check if user already declined eligibility test in this session
    from app.layer2.shared.session_manager import is_eligibility_declined
    if is_eligibility_declined(state.conversation_id):
        print(f"[Loan Agent] User already declined eligibility test, skipping question")
        # Skip eligibility question and proceed with normal loan response
        pass
    elif not eligibility_test_active and not eligibility_test_asked:
        # Initial loan query - ask about eligibility test
        response = """Would you like to test if you're eligible for a loan? I can quickly assess your eligibility or you can start a full application. Just say 'yes' or 'no'."""
        
        # Mark that we're asking about eligibility test
        state.orchestrator_context["eligibility_test_active"] = True
        state.orchestrator_context["eligibility_test_asked"] = True
        state.orchestrator_context["awaiting_eligibility_answer"] = True
        
        # Mark in session that we're waiting for eligibility answer
        from app.layer2.shared.session_manager import set_waiting_for_eligibility_answer, get_session
        set_waiting_for_eligibility_answer(state.conversation_id, state.source_language)
        
        # Record this turn in conversation context
        if conv_ctx:
            turn = TurnRecord(
                turn_number=conv_ctx.current_turn + 1,
                user_input=state.original_text,
                user_input_normalized=state.normalized_text_en,
                user_language=state.source_language,
                agent_routed_to="loan_agent",
                agent_response=response,
                intent=state.intent,
                confidence=state.orchestrator_context.get("confidence", 0),
                routing_reason="Loan intent detected",
            )
            add_turn_record(state.conversation_id, turn)
            
            # Update conversation context language
            conv_ctx.language = state.source_language
            
            # Set waiting state in conversation context (this will persist the updated conv_ctx)
            set_agent_waiting_state(
                state.conversation_id,
                agent_name="loan_agent",
                input_type="eligibility_answer",
                context_data={"asked_turn": conv_ctx.current_turn}
            )
            print(f"[Loan Agent] Set waiting state: eligibility_answer for session {state.conversation_id}")
            
            # Ensure the session has the updated conversation context
            session = get_session(state.conversation_id)
            if session:
                session["conversation_context"] = conv_ctx
                print(f"[Loan Agent] Updated conversation context language to: {state.source_language}")
        
        # Update state with agent response
        state.agent_feedback = {
            "loan": {
                "status": "completed",
                "response": response,
                "confidence": 0.9,
                "needs_more_info": True,
                "analysis": {
                    "needs_more_work": False,
                    "next_agent_suggested": None  # Wait for client answer
                }
            }
        }
        
        state.trace.append("loan:eligibility_test:asking_client")
        
    elif eligibility_test_asked and eligibility_test_answer is None:
        # Waiting for client's yes/no answer - this should be intercepted at router level now
        # But keep this as fallback for edge cases
        response = """I didn't quite understand. Would you like to test your loan eligibility? Please say 'yes' or 'no'."""
        
        state.agent_feedback = {
            "loan": {
                "status": "completed",
                "response": response,
                "confidence": 0.7,
                "needs_more_info": True,
                "analysis": {
                    "needs_more_work": False,
                    "next_agent_suggested": None
                }
            }
        }
        
        state.trace.append("loan:eligibility_test:unclear_answer:asking_again")
    
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
