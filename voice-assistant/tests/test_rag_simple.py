"""
Simple test to check RAG system initialization
"""

import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

try:
    from app.layer2.knowledgebase.intelligent_rag_system import IntelligentRAGSystem
    print("✅ Import successful")
    
    # Check vector components
    import sentence_transformers
    import faiss
    print("✅ Vector components available")
    
    # Test initialization
    rag = IntelligentRAGSystem()
    print(f"✅ RAG system created")
    print(f"✅ Embedder: {type(rag.embedder)}")
    print(f"✅ FAISS index: {rag.faiss_index}")
    
except Exception as e:
    print(f"❌ Import failed: {e}")
    import traceback
    traceback.print_exc()
