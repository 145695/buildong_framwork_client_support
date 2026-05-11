"""
Debug RAG system to see what documents are actually loaded
"""

import asyncio
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

from app.layer2.knowledgebase.intelligent_rag_system import IntelligentRAGSystem

async def debug_rag():
    """Debug RAG system to see what's loaded"""
    print("🔍 Debugging RAG System...")
    print("=" * 60)
    
    try:
        # Initialize RAG system
        rag = IntelligentRAGSystem()
        await rag.load_documents()
        
        print(f"✅ Total documents loaded: {len(rag.documents)}")
        print(f"✅ Total chunks created: {len(rag.document_chunks)}")
        
        # Show document filenames
        print("\n📄 Document Files:")
        for i, doc in enumerate(rag.documents, 1):
            print(f"  {i}. {doc.get('filename', 'unknown')}")
        
        # Show sample chunks to see content
        print("\n📝 Sample Chunks (first 3):")
        for i, chunk in enumerate(rag.document_chunks[:3], 1):
            content_preview = chunk.get('content', '')[:100]
            print(f"  Chunk {i}: {content_preview}...")
        
        # Test search with credit card query
        test_query = "credit card"
        print(f"\n🔍 Testing search for: '{test_query}'")
        
        # Embed and search
        query_embedding = rag.embedder.encode([test_query])
        import numpy as np
        query_embedding = np.array(query_embedding).astype('float32')
        rag.faiss.normalize_L2(query_embedding)
        
        scores, indices = rag.faiss_index.search(query_embedding, k=5)
        
        print(f"📊 Search Results:")
        for i, (score, idx) in enumerate(zip(scores[0], indices[0]), 1):
            chunk = rag.indexed_chunks[idx]
            filename = chunk.get('filename', 'unknown')
            content_preview = chunk.get('content', '')[:80]
            print(f"  {i}. Score: {score:.4f}, File: {filename}, Content: {content_preview}...")
        
        print("=" * 60)
        
    except Exception as e:
        print(f"❌ ERROR: {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(debug_rag())
