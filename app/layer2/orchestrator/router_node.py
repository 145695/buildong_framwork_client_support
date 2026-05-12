"""
New Router Node using Agent Registry
Replaces static keyword matching with semantic similarity routing
"""

from .agents.registry import registry
from .classifier_interface import classifier
from app.schemas.conversation import ConversationState

def router_node(state: ConversationState) -> ConversationState:
    """
    Semantic similarity-based agent routing using registry
    """
    # Get current input from state
    current_input = state.normalized_text_en or state.original_text or ""
    session_id = getattr(state, "conversation_id", None)

    # Query reconstruction from history
    reconstructed_query = current_input  # default: no history
    
    if session_id:
        from app.layer2.shared.session_manager import get_session
        session = get_session(session_id)
        if session and len(session["history"]) > 0:
            # Get last 2 user messages only
            last_turns = session["history"][-2:]
            past_messages = [turn["user"] for turn in last_turns]
            # Simple concatenation — no LLM, no hallucination
            reconstructed_query = " ".join(past_messages) + " " + current_input
            print(f"[Orchestrator] Reconstructed query: {reconstructed_query}")

    # Store in state for KB and client_support to use
    state.reconstructed_query = reconstructed_query
    
    # Classify intent using real classifier
    result = classifier.classify(reconstructed_query)
    intent = result.intent
    category = result.category
    
    # If model returns unknown intent, default to client_support
    if intent == "unknown" or category == "unknown":
        target_agent = "client_support"
        print(f"🔍 Router: Unknown intent '{intent}', defaulting to client_support")
    else:
        # Resolve to best matching agent using semantic similarity
        target_agent = registry.resolve(intent)
    
    print(f"🔍 Router: Intent='{intent}', Category='{category}', Target Agent='{target_agent}'")
    
    # Update state with routing decision
    state.intent = intent
    state.intent_category = category
    state.target_agent = target_agent
    
    # Add to trace
    state.trace.append(f"orchestrator:router:intent_{intent}")
    state.trace.append(f"orchestrator:router:category_{category}")
    state.trace.append(f"orchestrator:router:selected_{target_agent}")
    
    return state
