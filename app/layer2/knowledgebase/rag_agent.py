"""
Main RAG Knowledge Base Agent

Integrates PDF parsing, embeddings, vector store, and LLM to create
a complete Retrieval-Augmented Generation system for banking policy queries.
"""

import os
import logging
from pathlib import Path
from typing import List, Dict, Any, Optional
from dotenv import load_dotenv

from .pdf_parser import PDFParser
from .embeddings import EmbeddingsManager
from .vector_store import ChromaVectorStore
from .llm import LLMManager

logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()


class KnowledgeBaseAgent:
    """Main RAG agent for banking knowledge base"""
    
    def __init__(
        self,
        policies_dir: str = None,
        use_local_embeddings: bool = False,
        use_langchain_llm: bool = True,
        collection_name: str = "banking_policies"
    ):
        self.policies_dir = policies_dir or str(Path(__file__).parent.parent.parent.parent / "policies")
        self.collection_name = collection_name
        
        # Initialize components
        self.pdf_parser = PDFParser(self.policies_dir)
        self.embeddings_manager = EmbeddingsManager(use_local=use_local_embeddings)
        self.vector_store = ChromaVectorStore(collection_name=collection_name)
        self.llm_manager = LLMManager(use_langchain=use_langchain_llm)
        
        # Status tracking
        self.is_initialized = False
        self.document_count = 0
        
        logger.info("KnowledgeBaseAgent initialized")
    
    def initialize(self, force_rebuild: bool = False) -> bool:
        """Initialize the knowledge base with documents"""
        try:
            # Check if vector store already has data
            stats = self.vector_store.get_collection_stats()
            if not force_rebuild and stats.get("document_count", 0) > 0:
                logger.info(f"Knowledge base already initialized with {stats['document_count']} documents")
                self.is_initialized = True
                self.document_count = stats["document_count"]
                return True
            
            logger.info("Initializing knowledge base...")
            
            # Load and parse PDFs
            documents = self.pdf_parser.load_all_pdfs()
            if not documents:
                logger.error("No documents found to initialize knowledge base")
                return False
            
            # Generate embeddings
            logger.info("Generating embeddings for documents...")
            texts = [doc["content"] for doc in documents]
            embeddings = self.embeddings_manager.embed_texts(texts)
            
            if not embeddings or len(embeddings) != len(documents):
                logger.error("Failed to generate embeddings for all documents")
                return False
            
            # Add to vector store
            logger.info("Adding documents to vector store...")
            self.vector_store.add_documents(documents, embeddings)
            
            # Update status
            self.is_initialized = True
            self.document_count = len(documents)
            
            logger.info(f"Knowledge base initialized with {self.document_count} documents")
            return True
            
        except Exception as e:
            logger.error(f"Failed to initialize knowledge base: {e}")
            return False
    
    def query(self, question: str, n_results: int = 5) -> Dict[str, Any]:
        """Query the knowledge base"""
        if not self.is_initialized:
            if not self.initialize():
                return {
                    "answer": "Knowledge base is not initialized. Please check the logs.",
                    "sources": [],
                    "error": "Knowledge base not initialized"
                }
        
        try:
            # Generate query embedding
            query_embedding = self.embeddings_manager.embed_query(question)
            if not query_embedding:
                return {
                    "answer": "Failed to process query. Please try again.",
                    "sources": [],
                    "error": "Query embedding failed"
                }
            
            # Search vector store
            search_results = self.vector_store.search(query_embedding, n_results)
            
            if not search_results["results"]:
                return {
                    "answer": "I don't have enough information in the provided policies to answer this question.",
                    "sources": [],
                    "confidence": 0.0
                }
            
            # Prepare context for LLM
            context_parts = []
            sources = []
            
            for result in search_results["results"]:
                context_parts.append(result["document"])
                sources.append({
                    "filename": result["metadata"]["filename"],
                    "distance": result["distance"]
                })
            
            context = "\n\n---\n\n".join(context_parts)
            
            # Generate response using LLM
            response = self.llm_manager.generate_response(
                query=question,
                context=context
            )
            
            return {
                "answer": response,
                "sources": sources,
                "context_used": len(context_parts),
                "total_documents": self.document_count,
                "confidence": max(0.0, 1.0 - min(s["distance"] for s in sources) if sources else 0.0)
            }
            
        except Exception as e:
            logger.error(f"Error processing query: {e}")
            return {
                "answer": "I apologize, but I encountered an error while processing your request.",
                "sources": [],
                "error": str(e)
            }
    
    def get_stats(self) -> Dict[str, Any]:
        """Get knowledge base statistics"""
        try:
            vector_stats = self.vector_store.get_collection_stats()
            
            return {
                "is_initialized": self.is_initialized,
                "document_count": self.document_count,
                "vector_store_stats": vector_stats,
                "policies_directory": self.policies_dir,
                "collection_name": self.collection_name
            }
        except Exception as e:
            logger.error(f"Error getting stats: {e}")
            return {"error": str(e)}
    
    def rebuild(self) -> bool:
        """Rebuild the knowledge base from scratch"""
        try:
            logger.info("Rebuilding knowledge base...")
            
            # Clear vector store
            self.vector_store.clear_collection()
            
            # Reset status
            self.is_initialized = False
            self.document_count = 0
            
            # Reinitialize
            return self.initialize(force_rebuild=True)
            
        except Exception as e:
            logger.error(f"Failed to rebuild knowledge base: {e}")
            return False
    
    def test_system(self) -> Dict[str, Any]:
        """Test all components of the system"""
        results = {
            "pdf_parser": False,
            "embeddings": False,
            "vector_store": False,
            "llm": False,
            "overall": False
        }
        
        try:
            # Test PDF parser
            docs = self.pdf_parser.load_all_pdfs()
            results["pdf_parser"] = len(docs) > 0
            
            # Test embeddings
            results["embeddings"] = self.embeddings_manager.test_embeddings()
            
            # Test vector store
            stats = self.vector_store.get_collection_stats()
            results["vector_store"] = "error" not in stats
            
            # Test LLM
            results["llm"] = self.llm_manager.test_llm()
            
            # Overall status
            results["overall"] = all(results.values())
            
        except Exception as e:
            logger.error(f"Error during system test: {e}")
            results["error"] = str(e)
        
        return results


# Global instance for easy access
_global_agent = None


def get_knowledge_base_agent(**kwargs) -> KnowledgeBaseAgent:
    """Get or create global knowledge base agent instance"""
    global _global_agent
    
    if _global_agent is None:
        _global_agent = KnowledgeBaseAgent(**kwargs)
    
    return _global_agent


def initialize_knowledge_base(**kwargs) -> bool:
    """Initialize the global knowledge base agent"""
    agent = get_knowledge_base_agent(**kwargs)
    return agent.initialize()


def query_knowledge_base(question: str, n_results: int = 5) -> Dict[str, Any]:
    """Query the global knowledge base agent"""
    agent = get_knowledge_base_agent()
    return agent.query(question, n_results)


# Test function
def test_rag_agent():
    """Test the complete RAG system"""
    print("Testing RAG Knowledge Base Agent...")
    
    # Initialize agent
    agent = KnowledgeBaseAgent()
    
    # Test system components
    print("\n1. Testing system components...")
    test_results = agent.test_system()
    for component, status in test_results.items():
        status_icon = "✅" if status else "❌"
        print(f"   {component}: {status_icon}")
    
    if not test_results.get("overall", False):
        print("\n❌ System test failed. Please check the configuration.")
        return
    
    # Initialize knowledge base
    print("\n2. Initializing knowledge base...")
    if agent.initialize():
        print("✅ Knowledge base initialized successfully")
        
        # Get stats
        stats = agent.get_stats()
        print(f"   Documents loaded: {stats.get('document_count', 'Unknown')}")
        print(f"   Collection name: {stats.get('collection_name', 'Unknown')}")
    else:
        print("❌ Failed to initialize knowledge base")
        return
    
    # Test queries
    print("\n3. Testing sample queries...")
    test_queries = [
        "What are the requirements for getting a bank loan?",
        "How do I transfer money to another account?",
        "What types of credit cards are available?",
        "How do I change my account information?"
    ]
    
    for query in test_queries:
        print(f"\n   Query: {query}")
        result = agent.query(query)
        print(f"   Answer: {result['answer'][:150]}...")
        print(f"   Sources: {len(result.get('sources', []))}")
        print(f"   Confidence: {result.get('confidence', 0):.2f}")


if __name__ == "__main__":
    # Set up logging
    logging.basicConfig(level=logging.INFO)
    
    test_rag_agent()
