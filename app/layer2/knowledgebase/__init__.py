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

from .rag_agent import KnowledgeBaseAgent
# from .dify_integration import BankingKnowledgeBase, DifyKnowledgeBase  # Commented out - module doesn't exist

__all__ = [
    'KnowledgeBaseAgent',      # Local RAG system
    'BankingKnowledgeBase',    # Cloud RAG system (recommended)
    'DifyKnowledgeBase'       # Dify integration
]
