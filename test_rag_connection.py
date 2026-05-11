"""
Test script to confirm RAG system is connected and working
"""

import asyncio
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

from app.layer2.knowledgebase.intelligent_rag_system import IntelligentRAGSystem
from app.schemas.conversation import ConversationState

async def test_rag_connection():
    """Test RAG system with a sample English query"""
    print("🧪 Testing RAG System Connection...")
    print("=" * 60)
    
    try:
        # Initialize RAG system
        rag = IntelligentRAGSystem()
        await rag.load_documents()
        
        print(f"✅ RAG system initialized with {len(rag.document_chunks)} chunks")
        print(f"✅ FAISS index ready: {rag.faiss_index is not None}")
        
        # Test with a sample English query that should exist in policies
        test_question = "What are the annual fees for BNA credit cards?"
        
        print(f"\n📝 Testing Question: {test_question}")
        print("-" * 40)
        
        # Process query through RAG
        result = await rag.ask_question(test_question)
        
        print(f"📄 Answer: {result.get('answer', 'No answer')[:200]}...")
        print(f"📚 Sources: {result.get('sources', [])}")
        print(f"🎯 Confidence: {result.get('confidence', 0.0):.3f}")
        
        # Check if we got actual content from documents
        if result.get('sources') and len(result.get('sources')) > 0:
            print("✅ SUCCESS: RAG system found relevant documents!")
            print("✅ Real RAG system is connected and working!")
        else:
            print("❌ ISSUE: No documents found - check RAG system")
        
        print("=" * 60)
        
    except Exception as e:
        print(f"❌ ERROR: {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(test_rag_connection())
