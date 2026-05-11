"""
Final test to confirm RAG system works with actual production setup
"""

import asyncio
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

from app.layer2.knowledgebase.intelligent_rag_system import IntelligentRAGSystem
from app.schemas.conversation import ConversationState

async def test_rag_production():
    """Test RAG system with production setup"""
    print("🧪 Testing RAG System in Production Setup...")
    print("=" * 60)
    
    try:
        # Initialize RAG system (this will load from cache or rebuild)
        rag = IntelligentRAGSystem()
        await rag.load_documents()
        
        print(f"✅ RAG system initialized")
        print(f"✅ Documents loaded: {len(rag.documents)}")
        print(f"✅ Chunks created: {len(rag.document_chunks)}")
        print(f"✅ FAISS index: {rag.faiss_index is not None}")
        
        # Test with the same query that should work
        test_question = "What are annual fees for BNA credit cards?"
        
        print(f"\n📝 Testing Question: {test_question}")
        print("-" * 40)
        
        # Process query through RAG
        result = await rag.ask_question(test_question)
        
        print(f"📄 Answer: {result.get('answer', 'No answer')[:200]}...")
        print(f"📚 Sources: {result.get('sources', [])}")
        print(f"🎯 Confidence: {result.get('confidence', 0.0):.3f}")
        
        # Check success
        if result.get('sources') and len(result.get('sources')) > 0:
            print("✅ SUCCESS: RAG system is working!")
            print("✅ Found relevant documents from knowledge base!")
            print("✅ Real RAG system is connected to production pipeline!")
        else:
            print("❌ ISSUE: No documents found")
        
        print("=" * 60)
        
    except Exception as e:
        print(f"❌ ERROR: {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(test_rag_production())
