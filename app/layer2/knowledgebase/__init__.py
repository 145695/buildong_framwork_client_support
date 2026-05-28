"""
Banking Knowledge Base Agent

Dual RAG (Retrieval-Augmented Generation) system for answering client questions
about banking policies, loans, deposits, cards, and account changes.

Local Stack:
- PDF parsing: pdfplumber (lightweight, no GPU)
- Embeddings: HuggingFace Inference API (free tier)
- Vector store: ChromaDB (local, lightweight)
- LLM: Groq API (free tier - llama3 or mixtral)
- Framework: LangChain

Cloud Stack (Recommended):
- LLM: NVIDIA Nemotron (excellent French reasoning)
- Embeddings: NV-EmbedQA (multilingual, 26 languages)
- Reranking: Llama-Nemotron-Rerank (precision filtering)
- Orchestration: Dify.ai (cloud workflow)
- Vector Store: Pinecone (hosted database)
"""

# NOTE:
# Keep imports lightweight here so environments missing optional deps (e.g., chromadb)
# can still import other modules (like intelligent_rag_system) successfully.
try:
    from .rag_agent import KnowledgeBaseAgent  # Local RAG system (ChromaDB-based)
except Exception:
    KnowledgeBaseAgent = None  # type: ignore

__all__ = ["KnowledgeBaseAgent"]
