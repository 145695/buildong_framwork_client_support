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
    # Get user input from state
    user_input = state.normalized_text_en or state.original_text or ""
    
    # Classify intent using real classifier
    result = classifier.classify(user_input)
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
