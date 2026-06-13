"""
ChromaDB Vector Store Configuration

Lightweight local vector database for storing document embeddings.
No GPU required, runs efficiently on CPU.
"""

import os
import chromadb
from pathlib import Path
from typing import List, Dict, Any, Optional
import logging
from datetime import datetime
import numpy as np

logger = logging.getLogger(__name__)


class ChromaVectorStore:
    """ChromaDB vector store for document embeddings"""
    
    def __init__(self, persist_directory: str = None, collection_name: str = "banking_policies"):
        if persist_directory is None:
            # Default to knowledgebase/chroma_db directory
            persist_directory = Path(__file__).parent / "chroma_db"
        
        self.persist_directory = Path(persist_directory)
        self.collection_name = collection_name
        self.client = None
        self.collection = None
        
        # Initialize ChromaDB
        self._initialize_client()
    
    def _initialize_client(self):
        """Initialize ChromaDB client and collection"""
        try:
            # Create persist directory if it doesn't exist
            self.persist_directory.mkdir(parents=True, exist_ok=True)
            
            # Initialize ChromaDB client
            self.client = chromadb.PersistentClient(path=str(self.persist_directory))
            
            # Get or create collection
            self.collection = self.client.get_or_create_collection(
                name=self.collection_name,
                metadata={"description": "Banking policy documents"}
            )
            
            logger.info(f"ChromaDB initialized at {self.persist_directory}")
            logger.info(f"Collection '{self.collection_name}' ready")
            
        except Exception as e:
            logger.error(f"Failed to initialize ChromaDB: {e}")
            raise
    
    def add_documents(self, documents: List[Dict[str, Any]], embeddings: List[List[float]]):
        """Add documents with their embeddings to the vector store"""
        if not self.collection:
            raise RuntimeError("Vector store not initialized")
        
        try:
            # Prepare data for ChromaDB
            ids = []
            metadatas = []
            documents_text = []
            
            for i, doc in enumerate(documents):
                # Create unique ID
                doc_id = f"{doc['metadata']['filename'].replace('.pdf', '')}_{i}_{datetime.now().timestamp()}"
                ids.append(doc_id)
                
                # Prepare metadata
                metadata = {
                    "filename": doc["metadata"]["filename"],
                    "page_count": doc["metadata"]["page_count"],
                    "file_size": doc["metadata"]["file_size"],
                    "source": doc["source"]
                }
                metadatas.append(metadata)
                
                # Use document content
                documents_text.append(doc["content"])
            
            # Add to collection
            self.collection.add(
                ids=ids,
                embeddings=embeddings,
                documents=documents_text,
                metadatas=metadatas
            )
            
            logger.info(f"Added {len(documents)} documents to vector store")
            
        except Exception as e:
            logger.error(f"Failed to add documents to vector store: {e}")
            raise
    
    def search(self, query_embedding: List[float], n_results: int = 5) -> Dict[str, Any]:
        """Search for similar documents using query embedding"""
        if not self.collection:
            raise RuntimeError("Vector store not initialized")
        
        try:
            results = self.collection.query(
                query_embeddings=[query_embedding],
                n_results=n_results,
                include=["documents", "metadatas", "distances"]
            )
            
            # Format results
            formatted_results = []
            for i in range(len(results["ids"][0])):
                formatted_results.append({
                    "id": results["ids"][0][i],
                    "document": results["documents"][0][i],
                    "metadata": results["metadatas"][0][i],
                    "distance": results["distances"][0][i]
                })
            
            return {
                "results": formatted_results,
                "query_count": len(formatted_results)
            }
            
        except Exception as e:
            logger.error(f"Failed to search vector store: {e}")
            return {"results": [], "query_count": 0}
    
    def get_collection_stats(self) -> Dict[str, Any]:
        """Get statistics about the collection"""
        if not self.collection:
            return {"error": "Vector store not initialized"}
        
        try:
            count = self.collection.count()
            return {
                "collection_name": self.collection_name,
                "document_count": count,
                "persist_directory": str(self.persist_directory)
            }
        except Exception as e:
            logger.error(f"Failed to get collection stats: {e}")
            return {"error": str(e)}
    
    def clear_collection(self):
        """Clear all documents from the collection"""
        if not self.collection:
            raise RuntimeError("Vector store not initialized")
        
        try:
            # Delete the collection and recreate it
            self.client.delete_collection(name=self.collection_name)
            self.collection = self.client.get_or_create_collection(
                name=self.collection_name,
                metadata={"description": "Banking policy documents"}
            )
            logger.info(f"Cleared collection '{self.collection_name}'")
        except Exception as e:
            logger.error(f"Failed to clear collection: {e}")
            raise
    
    def delete_collection(self):
        """Delete the entire collection"""
        if not self.client:
            raise RuntimeError("Vector store not initialized")
        
        try:
            self.client.delete_collection(name=self.collection_name)
            logger.info(f"Deleted collection '{self.collection_name}'")
            self.collection = None
        except Exception as e:
            logger.error(f"Failed to delete collection: {e}")
            raise


# Test function
def test_vector_store():
    """Test ChromaDB vector store"""
    store = ChromaVectorStore()
    
    # Get stats
    stats = store.get_collection_stats()
    print(f"Collection stats: {stats}")
    
    # Test with dummy data
    dummy_docs = [
        {
            "content": "This is a test document about banking loans and credit policies.",
            "metadata": {"filename": "test_loan.pdf", "page_count": 1, "file_size": 1024},
            "source": "test"
        }
    ]
    
    dummy_embeddings = [[0.1] * 384]  # Dummy embedding
    
    try:
        store.add_documents(dummy_docs, dummy_embeddings)
        print("Successfully added test document")
        
        stats = store.get_collection_stats()
        print(f"Updated stats: {stats}")
        
    except Exception as e:
        print(f"Test failed: {e}")


if __name__ == "__main__":
    test_vector_store()
