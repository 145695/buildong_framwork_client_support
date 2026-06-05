"""
Test RAG system to show actual chunk content
"""

import asyncio
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

from app.layer2.knowledgebase.intelligent_rag_system import IntelligentRAGSystem

async def test_rag_content():
    """Test RAG system to show actual chunk content"""
    print("🔍 Testing RAG System Content...")
    print("=" * 60)
    
    try:
        # Initialize RAG system
        rag = IntelligentRAGSystem()
        await rag.load_documents()
        
        print(f"✅ RAG system initialized with {len(rag.document_chunks)} chunks")
        
        # Show chunks that contain "carte" (card in French)
        print("\n📄 Chunks containing 'carte' (card):")
        card_chunks = []
        for i, chunk in enumerate(rag.document_chunks, 1):
            content = chunk.get('content', '').lower()
            if 'carte' in content:
                card_chunks.append((i, chunk))
                content_preview = content[:100]
                print(f"  Chunk {i}: {content_preview}...")
        
        print(f"\n📊 Found {len(card_chunks)} chunks with 'carte' (card) content")
        
        if card_chunks:
            # Test search with credit card query
            test_query = "credit card"
            print(f"\n🔍 Testing search for: '{test_query}'")
            
            # Embed and search
            query_embedding = rag.embedder.encode([test_query])
            import numpy as np
            query_embedding = np.array(query_embedding).astype('float32')
            rag.faiss.normalize_L2(query_embedding)
            
            scores, indices = rag.faiss_index.search(query_embedding, k=5)
            
            print(f"\n📊 Search Results:")
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
    asyncio.run(test_rag_content())
