"""
Final connection test for RAG system with translator
"""

import asyncio
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

from app.layer2.knowledgebase.intelligent_rag_system import IntelligentRAGSystem

async def test_connection_final():
    """Final connection test"""
    print("🧪 Final Connection Test...")
    print("=" * 50)
    
    try:
        # Test RAG system
        rag = IntelligentRAGSystem()
        await rag.load_documents()
        
        print(f"✅ RAG initialized: {len(rag.document_chunks)} chunks")
        print(f"✅ FAISS index: {rag.faiss_index is not None}")
        
        # Test English question
        question = "What are the annual fees for BNA credit cards?"
        result = await rag.ask_question(question)
        
        print(f"📝 Question: {question}")
        print(f"📄 Answer: {result.get('answer', 'No answer')[:100]}...")
        print(f"📚 Sources: {result.get('sources', [])}")
        
        if result.get('sources'):
            print("✅ SUCCESS: RAG system is connected and working!")
        else:
            print("❌ No sources found")
        
        print("=" * 50)
        
    except Exception as e:
        print(f"❌ ERROR: {e}")

if __name__ == "__main__":
    asyncio.run(test_connection_final())
