"""
Test RAG system connection after fixing async issues
"""

import asyncio
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

from app.layer2.knowledgebase.intelligent_rag_system import IntelligentRAGSystem
from app.schemas.conversation import ConversationState

async def test_rag_connection_fixed():
    """Test RAG system with fixed connection"""
    print("🧪 Testing RAG System Connection (Fixed)...")
    print("=" * 60)
    
    try:
        # Initialize RAG system
        rag = IntelligentRAGSystem()
        await rag.load_documents()
        
        print(f"✅ RAG system initialized with {len(rag.document_chunks)} chunks")
        print(f"✅ FAISS index ready: {rag.faiss_index is not None}")
        
        # Test with multiple questions that should work
        test_questions = [
            "What are the annual fees for BNA credit cards?",
            "How much does it cost to request an account history statement?",
            "What is the maximum financing percentage for real estate loans?",
            "How much do bank transfers cost between agencies?",
            "What are the fees for cash withdrawals at other branches?"
        ]
        
        print(f"\n📝 Testing {len(test_questions)} questions:")
        print("-" * 60)
        
        success_count = 0
        for i, question in enumerate(test_questions, 1):
            print(f"\n{i}. {question}")
            
            # Process question through RAG
            result = await rag.ask_question(question)
            
            answer = result.get('answer', 'No answer')
            sources = result.get('sources', [])
            confidence = result.get('confidence', 0.0)
            
            print(f"   📄 Answer: {answer[:100]}...")
            print(f"   📚 Sources: {sources}")
            print(f"   🎯 Confidence: {confidence:.3f}")
            
            # Check if we got actual content from documents
            if sources and len(sources) > 0:
                success_count += 1
                print(f"   ✅ SUCCESS: Found relevant documents!")
            else:
                print(f"   ❌ No documents found")
        
        print(f"\n📊 Summary:")
        print(f"   ✅ Successful queries: {success_count}/{len(test_questions)} ({success_count/len(test_questions)*100:.1f}%)")
        print(f"   📄 Total chunks available: {len(rag.document_chunks)}")
        print(f"   📚 Total documents: {len(rag.documents)}")
        
        if success_count > 0:
            print(f"\n🎉 RAG SYSTEM IS WORKING! Real documents are being retrieved!")
        else:
            print(f"\n❌ RAG system still having issues")
        
        print("=" * 60)
        
    except Exception as e:
        print(f"❌ ERROR: {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(test_rag_connection_fixed())
