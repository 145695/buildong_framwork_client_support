"""
Client Support Agent

Provides customer service functionality for BNA banking queries.
Uses LLaMA model to generate helpful responses based on knowledge base results.
"""

import logging
from app.schemas.conversation import ConversationState
from app.layer2.shared.session_manager import get_history_as_text

# Load environment variables
import os
from dotenv import load_dotenv
load_dotenv()

# Settings for different model API keys
class settings:
    NVIDIA_API_KEY_LLAMA = os.getenv("NVIDIA_API_KEY_LLAMA", "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")

logger = logging.getLogger(__name__)

def client_support_node(state: ConversationState) -> ConversationState:
    """
    Client Support node using LLaMA for final response generation
    
    This node takes results from knowledge base (RAG system) and loan evaluation
    and generates a helpful, conversational response for the customer.
    
    Args:
        state: ConversationState containing kb_result, loan_result, and user query
        
    Returns:
        ConversationState with final_response_en and final_response_localized populated
    """
    try:
        from langchain_nvidia_ai_endpoints import ChatNVIDIA
        
        # Get results from previous nodes
        kb_result = getattr(state, "kb_result", None)
        loan_result = getattr(state, "loan_result", None)
        question = getattr(state, "reconstructed_query", None) \
                   or getattr(state, "normalized_text_en", "") \
                   or getattr(state, "original_text", "")
        intent = getattr(state, "intent", "")
        
        # Get conversation history if session_id exists
        history_text = ""
        if hasattr(state, 'conversation_id') and state.conversation_id:
            history_text = get_history_as_text(state.conversation_id)
        
        # Build context from knowledge base and loan results
        context = f"Bank information: {kb_result}" if kb_result else ""
        if loan_result:
            context += f"\nLoan evaluation: {loan_result}"
        
        # Create prompt for LLaMA model
        prompt = (
            "You are a friendly BNA bank customer service agent.\n"
            "Using information below, answer in 2-3 natural conversational sentences.\n"
            "No bullet points, no formatting, no markdown, plain text only.\n\n"
            f"{f'Conversation so far:{chr(10)}{history_text}{chr(10)}' if history_text else ''}"
            f"Customer question: {question}\n"
            f"Intent: {intent}\n"
            f"{context}\n\n"
            "Answer:"
        )
        
        # Initialize LLaMA client
        client = ChatNVIDIA(
            model="meta/llama-3.1-70b-instruct",
            api_key=settings.NVIDIA_API_KEY_LLAMA,
            temperature=0.7,
            max_tokens=150,
        )
        
        # Generate response
        response = client.invoke([{"role": "user", "content": prompt}])
        final_response = response.content.strip()
        
        logger.debug(f"[ClientSupport] Response: {final_response}")
        
        # Set final responses
        state.final_response_en = final_response
        state.final_response_localized = final_response
        
        return state
        
    except Exception as e:
        logger.error(f"[ClientSupport] ERROR: {type(e).__name__}: {str(e)}", exc_info=True)
        
        # Fallback response
        fallback_response = getattr(state, "kb_result", "I'm sorry, I could not find information on that.")
        state.final_response_en = fallback_response
        state.final_response_localized = fallback_response
        
        return state

def run_client_support_agent(state: ConversationState) -> ConversationState:
    """
    Alias function for backward compatibility
    
    Args:
        state: ConversationState
        
    Returns:
        ConversationState with client support response
    """
    return client_support_node(state)
