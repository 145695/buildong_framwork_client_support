"""
Test full pipeline with corrected routing
"""

import asyncio
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

from app.layer2.knowledgebase.intelligent_rag_system import IntelligentRAGSystem
from app.layer2.shared.model_loader import NemotronTranslationModel
from app.schemas.conversation import ConversationState
from app.layer2.graph import run_multi_agent_core

async def test_full_pipeline():
    """Test full pipeline with corrected routing"""
    print("Testing Full Pipeline with Corrected Routing...")
    print("=" * 60)
    
    try:
        # Test 1: RAG System
        print("1. Testing RAG System...")
        rag = IntelligentRAGSystem()
        await rag.load_documents()
        print(f"   RAG initialized: {len(rag.document_chunks)} chunks")
        
        # Test 2: Translation System
        print("2. Testing Translation System...")
        translator = NemotronTranslationModel()
        
        # Test English (should pass through)
        english_result = translator.translate_and_sanitize("What are the annual fees for BNA credit cards?", "en")
        print(f"   English translation: {english_result[0]}")
        
        # Test Arabic (should use fallback)
        arabic_result = translator.translate_and_sanitize("ما هي الرسوم السنوية لبطاقات البنك الوطني؟", "ar")
        print(f"   Arabic translation: {arabic_result[0]}")
        
        # Test 3: Full Pipeline
        print("3. Testing Full Pipeline...")
        
        # Create test state
        state = ConversationState(
            conversation_id="test-123",
            source_channel="CHAT",
            original_text="ما هي الرسوم السنوية لبطاقات البنك الوطني؟",
            source_language="ar",
            normalized_text="ما هي الرسوم السنوية لبطاقات البنك الوطني؟",
            normalized_text_en=arabic_result[0],  # Use translated result
            intent="card_fees",
            required_agents=["knowledge_base", "client_support"],
            orchestrator_context={"selected_agent": "knowledge_base"}
        )
        
        # Run through pipeline
        result = await run_multi_agent_core(state)
        
        print(f"   Pipeline completed successfully!")
        print(f"   Final response: {result.final_response_en[:100]}...")
        print(f"   KB result: {getattr(result, 'kb_result', 'None')[:100]}...")
        
        print("=" * 60)
        print("Full pipeline test completed!")
        
    except Exception as e:
        print(f"ERROR: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(test_full_pipeline())
