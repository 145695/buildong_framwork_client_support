"""
Mistral LLM implementation for the knowledge base
"""

import os
import requests
import logging
from pathlib import Path
from typing import Optional

# Load environment variables from .env file
env_path = Path(__file__).parent.parent.parent.parent / ".env"
if env_path.exists():
    with open(env_path) as f:
        for line in f:
            if line.strip() and not line.startswith("#") and "=" in line:
                key, value = line.strip().split("=", 1)
                # Remove quotes if present
                value = value.strip('"\'')
                os.environ[key] = value

logger = logging.getLogger(__name__)

class MistralLLM:
    """Mistral API client for LLM operations"""
    
    def __init__(self, model_name: str = "mistral-small", api_key: str = None, temperature: float = 0.0):
        self.model_name = model_name
        self.api_key = api_key or os.getenv("MISTRAL_API_KEY")
        self.temperature = temperature
        self.base_url = "https://api.mistral.ai/v1"
        
        if not self.api_key:
            raise ValueError("MISTRAL_API_KEY not found in environment variables")
        
        self.headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        
        logger.info(f"Initialized Mistral LLM with model: {self.model_name}")
    
    async def ainvoke(self, prompt: str) -> 'MistralResponse':
        """Generate response using Mistral API"""
        try:
            payload = {
                "model": self.model_name,
                "messages": [
                    {
                        "role": "user",
                        "content": prompt
                    }
                ],
                "temperature": self.temperature,
                "max_tokens": 1024
            }
            
            response = requests.post(
                f"{self.base_url}/chat/completions",
                headers=self.headers,
                json=payload,
                timeout=60  # Increased timeout to 60 seconds
            )
            
            if response.status_code == 200:
                data = response.json()
                content = data["choices"][0]["message"]["content"]
                return MistralResponse(content)
            else:
                logger.error(f"Mistral API error: {response.status_code} - {response.text}")
                raise Exception(f"Mistral API error: {response.status_code}")
                
        except Exception as e:
            logger.error(f"Error calling Mistral API: {e}")
            raise
    
    def test_connection(self) -> bool:
        """Test Mistral API connection"""
        try:
            payload = {
                "model": self.model_name,
                "messages": [
                    {
                        "role": "user", 
                        "content": "Hello, test connection"
                    }
                ],
                "temperature": 0.1,
                "max_tokens": 10
            }
            
            response = requests.post(
                f"{self.base_url}/chat/completions",
                headers=self.headers,
                json=payload,
                timeout=10
            )
            
            if response.status_code == 200:
                logger.info("Mistral API connection test successful")
                return True
            else:
                logger.error(f"Mistral API connection test failed: {response.status_code}")
                return False
                
        except Exception as e:
            logger.error(f"Mistral API connection test failed: {e}")
            return False

class MistralResponse:
    """Mistral API response wrapper"""
    
    def __init__(self, content: str):
        self.content = content
