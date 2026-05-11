"""
Debug what the RAG system returns for the blocked card query
"""

import asyncio
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

from app.layer2.knowledgebase.intelligent_rag_system import IntelligentRAGSystem

async def debug_rag_query():
    """Debug RAG system for blocked card query"""
    print("Debugging RAG System for Blocked Card Query...")
    print("=" * 60)
    
    try:
        # Initialize RAG system
        rag = IntelligentRAGSystem()
        await rag.load_documents()
        
        print(f"RAG initialized: {len(rag.document_chunks)} chunks")
        
        # Test the exact query that's failing
        query = "My bank card is blocked, what should I do?"
        print(f"Query: {query}")
        
        # Process through RAG
        result = await rag.ask_question(query)
        
        print(f"Answer: {result.get('answer', 'No answer')}")
        print(f"Sources: {result.get('sources', [])}")
        print(f"Confidence: {result.get('confidence', 0.0)}")
        
        # Check if there are chunks with relevant content
        print(f"\nSearching for 'blocked' or 'card' in chunks:")
        card_chunks = []
        for i, chunk in enumerate(rag.document_chunks, 1):
            content = chunk.get('content', '').lower()
            if 'blocked' in content or 'carte' in content:
                card_chunks.append((i, chunk))
                if len(card_chunks) <= 3:  # Show first 3
                    content_preview = content[:100]
                    print(f"  Chunk {i}: {content_preview}...")
        
        print(f"Total chunks with 'blocked' or 'carte': {len(card_chunks)}")
        
    except Exception as e:
        print(f"ERROR: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(debug_rag_query())
