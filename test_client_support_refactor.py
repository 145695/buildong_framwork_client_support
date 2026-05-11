"""
Test the refactored client_support module
"""

import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

from app.schemas.conversation import ConversationState, SourceChannel
from app.layer2.client_support import client_support_node

def test_client_support_refactor():
    """Test the refactored client_support module"""
    print("Testing Refactored Client Support Module...")
    print("=" * 50)
    
    try:
        # Create test state
        state = ConversationState(
            conversation_id="test-123",
            source_channel=SourceChannel.CHAT,
            source_language="en",
            original_text="What are the annual fees for BNA credit cards?",
            normalized_text_en="What are the annual fees for BNA credit cards?",
            intent="card_fees",
            kb_result="The annual fees for BNA credit cards vary by card type. Classic cards have an annual fee of 2,500 DZD, while premium cards may have higher fees up to 5,000 DZD."
        )
        
        print(f"Input question: {state.original_text}")
        print(f"Knowledge base result: {state.kb_result[:100]}...")
        
        # Test client_support_node
        result = client_support_node(state)
        
        print(f"Final response: {result.final_response_en}")
        print(f"Client support module working correctly!")
        
        return True
        
    except Exception as e:
        print(f"ERROR: {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = test_client_support_refactor()
    if success:
        print("\nClient support refactor test PASSED!")
    else:
        print("\nClient support refactor test FAILED!")
