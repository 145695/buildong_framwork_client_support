"""
Text Embeddings Module

Uses HuggingFace Inference API for free embeddings generation.
No local GPU required - all processing happens remotely.
"""

import os
import requests
import json
from typing import List, Dict, Any, Optional
import logging
from dotenv import load_dotenv

logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()


class HuggingFaceEmbeddings:
    """HuggingFace Inference API embeddings client"""
    
    def __init__(self, model_name: str = None, api_token: str = None):
        # Default model for multilingual support (Arabic, French, English)
        self.model_name = model_name or "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
        self.api_token = api_token or os.getenv("HUGGINGFACE_API_TOKEN")
        self.api_url = f"https://api-inference.huggingface.co/models/{self.model_name}"
        
        if not self.api_token:
            logger.warning("No HuggingFace API token found. Using free tier with rate limits.")
            # Use the public API without token (limited)
            self.headers = {"Content-Type": "application/json"}
        else:
            self.headers = {
                "Authorization": f"Bearer {self.api_token}",
                "Content-Type": "application/json"
            }
        
        logger.info(f"Initialized HuggingFace embeddings with model: {self.model_name}")
    
    def embed_text(self, text: str) -> List[float]:
        """Generate embedding for a single text"""
        try:
            payload = {"inputs": text}
            
            response = requests.post(
                self.api_url,
                headers=self.headers,
                json=payload,
                timeout=30
            )
            
            if response.status_code == 200:
                result = response.json()
                if isinstance(result, list) and len(result) > 0:
                    return result[0]
                elif isinstance(result, dict) and "embeddings" in result:
                    return result["embeddings"][0]
                else:
                    logger.error(f"Unexpected response format: {result}")
                    return None
            else:
                logger.error(f"API request failed: {response.status_code} - {response.text}")
                return None
                
        except Exception as e:
            logger.error(f"Error generating embedding: {e}")
            return None
    
    def embed_texts(self, texts: List[str], batch_size: int = 10) -> List[List[float]]:
        """Generate embeddings for multiple texts (batch processing)"""
        embeddings = []
        
        for i in range(0, len(texts), batch_size):
            batch = texts[i:i + batch_size]
            batch_embeddings = []
            
            for text in batch:
                embedding = self.embed_text(text)
                if embedding:
                    batch_embeddings.append(embedding)
                else:
                    # Fallback: zero embedding
                    logger.warning(f"Failed to embed text, using zero vector: {text[:50]}...")
                    batch_embeddings.append([0.0] * 384)  # Default dimension
            
            embeddings.extend(batch_embeddings)
            
            # Rate limiting for free tier
            if i + batch_size < len(texts):
                import time
                time.sleep(1)
        
        logger.info(f"Generated {len(embeddings)} embeddings")
        return embeddings
    
    def test_connection(self) -> bool:
        """Test API connection"""
        try:
            test_text = "This is a test sentence for embedding generation."
            embedding = self.embed_text(test_text)
            
            if embedding and len(embedding) > 0:
                logger.info(f"Connection test successful. Embedding dimension: {len(embedding)}")
                return True
            else:
                logger.error("Connection test failed: No embedding generated")
                return False
                
        except Exception as e:
            logger.error(f"Connection test failed: {e}")
            return False


class LocalSentenceTransformer:
    """Fallback local embeddings using sentence-transformers"""
    
    def __init__(self, model_name: str = None):
        # Lightweight multilingual model
        self.model_name = model_name or "all-MiniLM-L6-v2"
        self.model = None
        self._load_model()
    
    def _load_model(self):
        """Load the sentence transformer model"""
        try:
            from sentence_transformers import SentenceTransformer
            self.model = SentenceTransformer(self.model_name)
            logger.info(f"Loaded local model: {self.model_name}")
        except ImportError:
            logger.error("sentence-transformers not installed. Install with: pip install sentence-transformers")
            raise
        except Exception as e:
            logger.error(f"Failed to load model: {e}")
            raise
    
    def embed_text(self, text: str) -> List[float]:
        """Generate embedding for a single text"""
        try:
            embedding = self.model.encode(text, convert_to_tensor=False)
            return embedding.tolist()
        except Exception as e:
            logger.error(f"Error generating embedding: {e}")
            return None
    
    def embed_texts(self, texts: List[str], batch_size: int = 32) -> List[List[float]]:
        """Generate embeddings for multiple texts"""
        try:
            embeddings = self.model.encode(
                texts,
                batch_size=batch_size,
                convert_to_tensor=False,
                show_progress_bar=True
            )
            return embeddings.tolist()
        except Exception as e:
            logger.error(f"Error generating batch embeddings: {e}")
            return None
    
    def test_connection(self) -> bool:
        """Test the model"""
        try:
            test_text = "This is a test sentence."
            embedding = self.embed_text(test_text)
            
            if embedding and len(embedding) > 0:
                logger.info(f"Local model test successful. Embedding dimension: {len(embedding)}")
                return True
            else:
                logger.error("Local model test failed")
                return False
                
        except Exception as e:
            logger.error(f"Local model test failed: {e}")
            return False


class EmbeddingsManager:
    """Manager for embeddings with fallback support"""
    
    def __init__(self, use_local: bool = False):
        self.use_local = use_local
        self.embedder = None
        self._initialize_embedder()
    
    def _initialize_embedder(self):
        """Initialize the appropriate embedder"""
        if self.use_local:
            try:
                self.embedder = LocalSentenceTransformer()
                logger.info("Using local sentence-transformers embeddings")
            except Exception as e:
                logger.warning(f"Failed to initialize local embedder: {e}")
                self.use_local = False
        
        if not self.use_local:
            self.embedder = HuggingFaceEmbeddings()
            logger.info("Using HuggingFace Inference API embeddings")
    
    def embed_texts(self, texts: List[str]) -> List[List[float]]:
        """Generate embeddings for texts"""
        if not self.embedder:
            raise RuntimeError("Embedder not initialized")
        
        return self.embedder.embed_texts(texts)
    
    def embed_query(self, query: str) -> List[float]:
        """Generate embedding for query"""
        if not self.embedder:
            raise RuntimeError("Embedder not initialized")
        
        return self.embedder.embed_text(query)
    
    def test_embeddings(self) -> bool:
        """Test the embeddings system"""
        if not self.embedder:
            logger.error("No embedder initialized")
            return False
        
        return self.embedder.test_connection()


# Test function
def test_embeddings():
    """Test embeddings functionality"""
    print("Testing embeddings...")
    
    # Test with HuggingFace API
    print("\n1. Testing HuggingFace Inference API...")
    hf_embeddings = HuggingFaceEmbeddings()
    if hf_embeddings.test_connection():
        test_text = "What are the requirements for a bank loan?"
        embedding = hf_embeddings.embed_text(test_text)
        print(f"Generated embedding dimension: {len(embedding) if embedding else 'None'}")
    else:
        print("HuggingFace API test failed")
    
    # Test with local model
    print("\n2. Testing local sentence-transformers...")
    try:
        local_embeddings = LocalSentenceTransformer()
        if local_embeddings.test_connection():
            test_text = "What are the requirements for a bank loan?"
            embedding = local_embeddings.embed_text(test_text)
            print(f"Generated embedding dimension: {len(embedding) if embedding else 'None'}")
        else:
            print("Local model test failed")
    except Exception as e:
        print(f"Local model not available: {e}")
    
    # Test with manager
    print("\n3. Testing EmbeddingsManager...")
    manager = EmbeddingsManager(use_local=False)
    if manager.test_embeddings():
        test_texts = [
            "Loan requirements and eligibility",
            "Bank account opening procedures",
            "Credit card application process"
        ]
        embeddings = manager.embed_texts(test_texts)
        print(f"Generated {len(embeddings)} embeddings")
        if embeddings:
            print(f"Embedding dimension: {len(embeddings[0])}")
    else:
        print("EmbeddingsManager test failed")


if __name__ == "__main__":
    test_embeddings()
