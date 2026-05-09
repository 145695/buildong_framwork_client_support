from .capability_registry import (
    generate_mission_brief, 
    get_agent_capability,
    AgentCapabilityType
)
from .router_node import router_node
from app.schemas.conversation import ConversationState, SourceChannel




def _llama_intent_extraction(state: ConversationState) -> dict[str, any]:
    """
    Use fine-tuned Llama model for intent/category extraction.
    Smart PM approach: dynamic agent selection based on capabilities.
    """
    # Get Llama model
    llama_model = get_llama_model()
    
    # Extract intent and category using Llama
    extraction_result = llama_model.extract_intent_category(state.normalized_text_en)
    
    # Handle new Colab Gradio API response format
    if 'agent_to_call' in extraction_result and 'agent_prompt' in extraction_result:
        # New format: category, intent, agent_to_call, agent_prompt
        intent = extraction_result['intent']
        category = extraction_result['category']
        agent_to_call = extraction_result['agent_to_call']
        agent_prompt = extraction_result['agent_prompt']
        confidence = 0.8  # Default confidence for new format
        
        # Map old agent names to new ones
        agent_mapping = {
            'security_layer1': 'knowledge_base',
            'security_layer2': 'loan', 
            'authorization': 'loan',
            'support': 'client_support',
            'channel_refinement': 'client_support'
        }
        agent_to_call = agent_mapping.get(agent_to_call, 'client_support')
        
        # Log the extraction for debugging
        state.trace.append(f"orchestrator:llama_extraction:{intent}:{category}:{agent_to_call}")
        
        # Use the agent_to_call from the model directly
        suitable_agents = [agent_to_call] if agent_to_call else []
        
        return {
            "intent": intent,
            "category": category,
            "confidence": confidence,
            "suitable_agents": suitable_agents,
            "agent_to_call": agent_to_call,
            "agent_prompt": agent_prompt,
            "extraction_method": extraction_result['extraction_method'],
            "model_used": extraction_result['model_used']
        }
    else:
        # Old format: intent, category, confidence
        intent = extraction_result['intent']
        category = extraction_result['category']
        confidence = extraction_result['confidence']
        
        # Log the extraction for debugging
        state.trace.append(f"orchestrator:llama_extraction:{intent}:{category}:{confidence}")
        
        # Find suitable agents using capability registry
        suitable_agents = find_suitable_agents(intent, category, {
            "original_request": state.normalized_text_en,
            "confidence": confidence,
            "extraction_method": extraction_result['extraction_method'],
            "model_used": extraction_result['model_used']
        })
        
        return {
            "intent": intent,
            "category": category,
            "confidence": confidence,
            "suitable_agents": suitable_agents,
            "extraction_method": extraction_result['extraction_method'],
            "model_used": extraction_result['model_used']
        }


def smart_pm_routing(state: ConversationState) -> ConversationState:
    """
    Smart PM orchestrator in PLANNING MODE - shows intent, agents, and mission briefs without executing.
    """
    # Use new router node for semantic agent selection
    state = router_node(state)
    
    # Get selected agent from router
    target_agent = state.target_agent
    
    # Convert to agent object
    agent_obj = get_agent_capability(target_agent)
    if not agent_obj:
        agent_obj = get_agent_capability("client_support")
    else:
        agent_obj = get_agent_capability(target_agent)
    
    # Generate mission brief for selected agent
    brief_text = generate_mission_brief(
        agent_name=agent_obj.name,
        intent=state.intent,
        category=state.intent_category,
        context={
            "original_request": state.normalized_text_en,
            "confidence": 0.8,  # Router confidence
            "extraction_method": "semantic_similarity",
            "model_used": "sentence_transformers",
            "source_channel": state.source_channel.value,
            "priority": agent_obj.priority
        },
        previous_feedback=state.agent_feedback
    )
    
    # Update state with routing decision
    state.required_agents = [agent_obj.name]
    state.mission_brief = {agent_obj.name: brief_text}
    
    # Store orchestrator context (without planning mode)
    state.orchestrator_context = {
        "priority": agent_obj.priority,
        "confidence": 0.8,
        "extraction_method": "semantic_similarity",
        "model_used": "sentence_transformers",
        "original_request": state.normalized_text_en,
        "selected_agent": agent_obj.name,
        "mission_brief_generated": True,
        "planning_mode": False
    }
    
    # Don't set final_response yet - let agents execute and client_support synthesize
    # state.final_response_en and final_response_localized will be set by client_support
    
    state.trace.append(f"layer2:semantic_routing:enabled")
    state.trace.append(f"layer2:router:intent_{state.intent}")
    state.trace.append(f"layer2:router:selected_{target_agent}")
    state.trace.append(f"layer2:planning_complete:mission_brief_generated")
    
    return state


def analyze_agent_feedback(state: ConversationState) -> ConversationState:
    """
    Analyze feedback from completed agent and determine next steps.
    Smart PM feedback loop for multi-agent coordination.
    Special handling for multi-turn loan conversations.
    """
    if not state.agent_feedback:
        return state
    
    # Get feedback from the last completed agent
    last_agent_feedback = None
    completed_agents = []
    
    for agent_name, feedback in state.agent_feedback.items():
        if feedback.get("status") == "completed":
            completed_agents.append(agent_name)
            last_agent_feedback = feedback
    
    if not last_agent_feedback:
        return state
    
    # Analyze feedback to determine if more work is needed
    feedback_analysis = last_agent_feedback.get("analysis", {})
    needs_more_work = feedback_analysis.get("needs_more_work", False)
    next_agent_suggested = feedback_analysis.get("next_agent_suggested")
    
    # Special handling for loan agent multi-turn conversations
    if "loan" in completed_agents:
        loan_feedback = state.agent_feedback.get("loan", {})
        if loan_feedback.get("needs_more_info", False):
            # Loan agent needs more client information
            # Update orchestrator context for multi-turn conversation
            state.orchestrator_context["loan_conversation_active"] = True
            state.orchestrator_context["awaiting_client_info"] = True
            state.orchestrator_context["loan_agent_waiting"] = True
            
            # Don't call client_support yet - wait for more client info
            if "client_support" in state.required_agents:
                state.required_agents.remove("client_support")
            
            state.trace.append("orchestrator:loan_multi_turn:awaiting_more_info")
            return state
        
        elif loan_feedback.get("evaluation_complete", False):
            # Loan evaluation is complete, now call client_support
            if "client_support" not in state.required_agents:
                state.required_agents.append("client_support")
            
            state.orchestrator_context["loan_conversation_active"] = False
            state.orchestrator_context["awaiting_client_info"] = False
            state.orchestrator_context["loan_agent_waiting"] = False
            
            state.trace.append("orchestrator:loan_evaluation_complete:calling_client_support")
    
    # Standard feedback loop for other agents
    if needs_more_work and next_agent_suggested:
        # Generate new mission brief for the next agent
        next_agent_cap = get_agent_capability(next_agent_suggested)
        if next_agent_cap:
            mission_brief_text = generate_mission_brief(
                agent_name=next_agent_suggested,
                intent=state.intent,
                category=state.intent_category,
                context={
                    "original_request": state.normalized_text_en,
                    "previous_agent": completed_agents[-1] if completed_agents else None,
                    "previous_feedback": last_agent_feedback,
                    "feedback_analysis": feedback_analysis,
                    "source_channel": state.source_channel.value
                },
                previous_feedback=state.agent_feedback
            )
            
            # Update mission brief for next agent
            state.mission_brief[next_agent_suggested] = mission_brief_text
            
            # Add to required agents if not already present
            if next_agent_suggested not in state.required_agents:
                state.required_agents.append(next_agent_suggested)
            
            state.trace.append(f"layer2:smart_pm:feedback_loop:{next_agent_suggested}")
    
    return state


def route_intent(state: ConversationState) -> ConversationState:
    """
    Smart PM Orchestrator with dynamic mission generation and feedback loops.
    Uses Llama model for intent extraction and Agent Registry for semantic agent selection.
    """
    # Use new router node for semantic agent selection
    state = router_node(state)
    
    # Second Pass: Will be handled by individual agents returning feedback
    # The feedback loop is implemented in analyze_agent_feedback
    
    return state
