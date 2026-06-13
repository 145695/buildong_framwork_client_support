import os
from typing import Any

from app.schemas.conversation import ConversationState

# Client support agent prompt for response synthesis
SUPPORT_AGENT_PROMPT = """You are a Client Support Specialist. Your job is to synthesize information from multiple specialized agents to provide a comprehensive, helpful response to the customer.

CONTEXT:
- Original Request: {original_request}
- Intent: {intent} (Category: {category})
- Priority: {priority}
- Confidence: {confidence}

AGENT RESULTS:
{agent_results}

GUIDELINES:
1. Address the user's original request directly
2. Incorporate relevant information from all agent results
3. Maintain professional, helpful tone
4. If security issues are involved, prioritize safety instructions
5. Provide clear next steps or actions
6. Keep response concise but comprehensive

Formulate a natural, helpful response that addresses all aspects of the user's request.
"""


def _synthesize_response_with_llm(state: ConversationState) -> str:
    """Use LLM to synthesize final response from all agent results"""
    try:
        from langchain_core.messages import HumanMessage, SystemMessage
        from langchain_openai import ChatOpenAI
        
        # Initialize LLM for response synthesis
        llm = ChatOpenAI(
            model="gpt-4o-mini",
            temperature=0.3,  # Slightly higher for natural conversation
            api_key=os.getenv("OPENAI_API_KEY")
        )
        
        # Format agent results for the prompt
        agent_results_text = ""
        for agent_name, result in state.agent_responses.items():
            agent_results_text += f"\n--- {agent_name.upper()} AGENT ---\n{result}\n"
        
        # Add orchestrator context
        orchestrator = state.orchestrator_context
        
        # Format the prompt
        prompt = SUPPORT_AGENT_PROMPT.format(
            original_request=state.original_text,
            intent=state.intent,
            category=state.intent_category,
            priority=orchestrator.get("priority", "normal"),
            confidence=orchestrator.get("confidence", 0.0),
            agent_results=agent_results_text
        )
        
        # Generate response
        messages = [
            SystemMessage(content="You are a helpful banking client support specialist."),
            HumanMessage(content=prompt)
        ]
        
        response = llm.invoke(messages)
        return response.content.strip()
        
    except Exception as e:
        print(f"Error in LLM synthesis: {e}")
        # Fallback to template-based response
        return _fallback_synthesis(state)


def _fallback_synthesis(state: ConversationState) -> str:
    """Fallback template-based response synthesis"""
    agent_responses = state.agent_responses
    
    if "knowledge_base" in agent_responses:
        kb_response = agent_responses["knowledge_base"]
        return f"""Thank you for your inquiry. Here's the information you requested:

{kb_response}

If you need more specific details or have additional questions, please let me know."""
    
    elif "loan" in agent_responses:
        loan_response = agent_responses["loan"]
        return f"""Regarding your loan application:

{loan_response}

I'm here to guide you through the entire process."""
    
    else:
        return """Hello! I'm here to help you with your banking needs. Please let me know how I can assist you today."""


def run_support_agent(state: ConversationState) -> ConversationState:
    """Enhanced support agent with LLM synthesis"""
    try:
        # Use LLM for response synthesis
        final_response = _synthesize_response_with_llm(state)
        
        # Update state
        state.final_response_en = final_response
        state.final_response_localized = final_response
        
        state.agent_feedback = {
            "support": {
                "status": "completed",
                "response": final_response,
                "confidence": 0.9,
                "synthesis_method": "llm"
            }
        }
        
        state.trace.append("support:completed:llm_synthesis")
        return state
        
    except Exception as e:
        print(f"Error in support agent: {e}")
        # Fallback to simple response
        state.final_response_en = "I'm here to help you with your banking needs. Please let me know how I can assist you."
        state.final_response_localized = state.final_response_en
        
        state.agent_feedback = {
            "support": {
                "status": "completed",
                "response": state.final_response_en,
                "confidence": 0.5,
                "synthesis_method": "fallback"
            }
        }
        
        state.trace.append("support:completed:fallback")
        return state
