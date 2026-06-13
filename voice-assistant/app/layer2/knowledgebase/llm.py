"""
LLM Module using Groq API

Fast, free LLM inference using Groq's API with Llama3 or Mixtral models.
No local GPU required - all processing happens remotely.
"""

import os
from typing import List, Dict, Any, Optional
import logging
from dotenv import load_dotenv

try:
    from langchain_groq import ChatGroq
    from langchain.schema import HumanMessage, SystemMessage
    LANGCHAIN_AVAILABLE = True
except ImportError:
    LANGCHAIN_AVAILABLE = False
    logging.warning("langchain-groq not installed. Install with: pip install langchain-groq")

logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()


class GroqLLM:
    """Groq API LLM client using LangChain"""
    
    def __init__(self, model_name: str = None, api_key: str = None, temperature: float = 0.1):
        if not LANGCHAIN_AVAILABLE:
            raise ImportError("langchain-groq is required. Install with: pip install langchain-groq")
        
        # Default to Llama3 8B for good balance of speed and quality
        self.model_name = model_name or "llama3-8b-8192"
        self.api_key = api_key or os.getenv("GROQ_API_KEY")
        self.temperature = temperature
        
        if not self.api_key:
            raise ValueError("GROQ_API_KEY not found in environment variables")
        
        # Initialize LangChain ChatGroq
        self.llm = ChatGroq(
            model=self.model_name,
            api_key=self.api_key,
            temperature=self.temperature,
            max_tokens=1024
        )
        
        logger.info(f"Initialized Groq LLM with model: {self.model_name}")
    
    def generate_response(self, query: str, context: str = None, system_prompt: str = None) -> str:
        """Generate response using Groq LLM"""
        try:
            messages = []
            
            # Add system prompt
            if system_prompt:
                messages.append(SystemMessage(content=system_prompt))
            elif context:
                # Default system prompt for RAG
                system_prompt = """You are a helpful banking assistant. Answer the user's question based on the provided context from banking policy documents.

Rules:
1. Use only the information from the provided context
2. If the context doesn't contain the answer, say "I don't have enough information in the provided policies to answer this question."
3. Be clear, concise, and professional
4. Support Arabic, French, and English queries
5. For loan questions, mention eligibility requirements and procedures
6. For deposit/transfer questions, mention limits and procedures
7. For card questions, mention types and application procedures
8. For account changes, mention required documentation and procedures"""
                messages.append(SystemMessage(content=system_prompt))
            
            # Add context if provided
            if context:
                context_message = f"""Context from banking policy documents:
{context}

Please answer the user's question based on this context."""
                messages.append(HumanMessage(content=context_message))
            
            # Add user query
            messages.append(HumanMessage(content=query))
            
            # Generate response
            response = self.llm(messages)
            return response.content
            
        except Exception as e:
            logger.error(f"Error generating response: {e}")
            return "I apologize, but I encountered an error while processing your request."
    
    def test_connection(self) -> bool:
        """Test Groq API connection"""
        try:
            test_response = self.generate_response(
                "Hello, can you help me with banking questions?",
                system_prompt="You are a helpful assistant. Respond briefly."
            )
            
            if test_response and len(test_response) > 0:
                logger.info("Groq API connection test successful")
                return True
            else:
                logger.error("Groq API connection test failed: No response")
                return False
                
        except Exception as e:
            logger.error(f"Groq API connection test failed: {e}")
            return False


class DirectGroqLLM:
    """Direct Groq API client without LangChain dependency"""
    
    def __init__(self, model_name: str = None, api_key: str = None, temperature: float = 0.1):
        import requests
        
        self.model_name = model_name or "llama3-8b-8192"
        self.api_key = api_key or os.getenv("GROQ_API_KEY")
        self.temperature = temperature
        self.base_url = "https://api.groq.com/openai/v1"
        
        if not self.api_key:
            raise ValueError("GROQ_API_KEY not found in environment variables")
        
        self.headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        
        logger.info(f"Initialized direct Groq LLM with model: {self.model_name}")
    
    def generate_response(self, query: str, context: str = None, system_prompt: str = None) -> str:
        """Generate response using direct Groq API"""
        try:
            import requests
            
            messages = []
            
            # Add system prompt
            if system_prompt:
                messages.append({"role": "system", "content": system_prompt})
            elif context:
                messages.append({
                    "role": "system", 
                    "content": """You are a helpful banking assistant. Answer the user's question based on the provided context from banking policy documents.

Rules:
1. Use only the information from the provided context
2. If the context doesn't contain the answer, say "I don't have enough information in the provided policies to answer this question."
3. Be clear, concise, and professional
4. Support Arabic, French, and English queries
5. For loan questions, mention eligibility requirements and procedures
6. For deposit/transfer questions, mention limits and procedures
7. For card questions, mention types and application procedures
8. For account changes, mention required documentation and procedures"""
                })
            
            # Add context if provided
            if context:
                messages.append({
                    "role": "user",
                    "content": f"""Context from banking policy documents:
{context}

Please answer the user's question based on this context."""
                })
            
            # Add user query
            messages.append({"role": "user", "content": query})
            
            # Make API request
            payload = {
                "model": self.model_name,
                "messages": messages,
                "temperature": self.temperature,
                "max_tokens": 1024
            }
            
            response = requests.post(
                f"{self.base_url}/chat/completions",
                headers=self.headers,
                json=payload,
                timeout=30
            )
            
            if response.status_code == 200:
                result = response.json()
                return result["choices"][0]["message"]["content"]
            else:
                logger.error(f"Groq API error: {response.status_code} - {response.text}")
                return "I apologize, but I encountered an error while processing your request."
                
        except Exception as e:
            logger.error(f"Error generating response: {e}")
            return "I apologize, but I encountered an error while processing your request."
    
    def test_connection(self) -> bool:
        """Test Groq API connection"""
        try:
            test_response = self.generate_response(
                "Hello, can you help me with banking questions?",
                system_prompt="You are a helpful assistant. Respond briefly."
            )
            
            if test_response and len(test_response) > 0:
                logger.info("Direct Groq API connection test successful")
                return True
            else:
                logger.error("Direct Groq API connection test failed: No response")
                return False
                
        except Exception as e:
            logger.error(f"Direct Groq API connection test failed: {e}")
            return False


class LLMManager:
    """Manager for LLM with fallback support"""
    
    def __init__(self, use_langchain: bool = True):
        self.use_langchain = use_langchain and LANGCHAIN_AVAILABLE
        self.llm = None
        self._initialize_llm()
    
    def _initialize_llm(self):
        """Initialize appropriate LLM"""
        try:
            if self.use_langchain:
                self.llm = GroqLLM()
                logger.info("Using LangChain Groq LLM")
            else:
                self.llm = DirectGroqLLM()
                logger.info("Using direct Groq API")
        except Exception as e:
            logger.error(f"Failed to initialize primary LLM: {e}")
            # Try fallback
            try:
                self.llm = DirectGroqLLM()
                self.use_langchain = False
                logger.info("Fell back to direct Groq API")
            except Exception as fallback_error:
                logger.error(f"Fallback LLM also failed: {fallback_error}")
                raise
    
    def generate_response(self, query: str, context: str = None, system_prompt: str = None) -> str:
        """Generate response using configured LLM"""
        if not self.llm:
            raise RuntimeError("LLM not initialized")
        
        return self.llm.generate_response(query, context, system_prompt)
    
    def test_llm(self) -> bool:
        """Test LLM system"""
        if not self.llm:
            logger.error("No LLM initialized")
            return False
        
        return self.llm.test_connection()


# Test function
def test_llm():
    """Test LLM functionality"""
    print("Testing LLM...")
    
    # Check for API key
    if not os.getenv("GROQ_API_KEY"):
        print("❌ GROQ_API_KEY not found in environment variables")
        print("Please set GROQ_API_KEY in your .env file")
        return
    
    # Test LangChain version
    print("\n1. Testing LangChain Groq LLM...")
    try:
        llm_langchain = GroqLLM()
        if llm_langchain.test_connection():
            response = llm_langchain.generate_response(
                "What are the basic requirements for a bank loan?",
                context="To apply for a bank loan, customers must be 18+ years old, have a steady income, and provide proof of residence."
            )
            print(f"✅ LangChain test successful. Response: {response[:100]}...")
        else:
            print("❌ LangChain test failed")
    except Exception as e:
        print(f"❌ LangChain test failed: {e}")
    
    # Test direct API version
    print("\n2. Testing direct Groq API...")
    try:
        llm_direct = DirectGroqLLM()
        if llm_direct.test_connection():
            response = llm_direct.generate_response(
                "What are the basic requirements for a bank loan?",
                context="To apply for a bank loan, customers must be 18+ years old, have a steady income, and provide proof of residence."
            )
            print(f"✅ Direct API test successful. Response: {response[:100]}...")
        else:
            print("❌ Direct API test failed")
    except Exception as e:
        print(f"❌ Direct API test failed: {e}")


if __name__ == "__main__":
    test_llm()
