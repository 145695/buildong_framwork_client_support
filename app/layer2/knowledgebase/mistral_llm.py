"""
Mistral LLM implementation for the knowledge base
"""

import os
import requests
import logging
import time
import random
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
        max_retries = 5
        last_exception = None

        for attempt in range(max_retries):
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
                elif response.status_code == 429:
                    error_msg = f"Mistral API error: {response.status_code} - {response.text}"
                    logger.error(error_msg)
                    last_exception = Exception(error_msg)
                    # Retry with exponential backoff
                    wait_time = (2 ** attempt) + random.uniform(0, 1)
                    print(f"⏳ Mistral free tier busy, retrying in {wait_time:.1f}s... (attempt {attempt + 1}/{max_retries})")
                    time.sleep(wait_time)
                else:
                    error_msg = f"Mistral API error: {response.status_code} - {response.text}"
                    logger.error(error_msg)
                    raise Exception(error_msg)

            except Exception as e:
                error_str = str(e)
                if "429" in error_str or "capacity exceeded" in error_str.lower():
                    logger.error(f"Error calling Mistral API: {e}")
                    last_exception = e
                    # Retry with exponential backoff
                    wait_time = (2 ** attempt) + random.uniform(0, 1)
                    print(f"⏳ Mistral free tier busy, retrying in {wait_time:.1f}s... (attempt {attempt + 1}/{max_retries})")
                    time.sleep(wait_time)
                else:
                    logger.error(f"Error calling Mistral API: {e}")
                    raise

        # All retries failed
        if last_exception:
            raise last_exception
        else:
            raise Exception("Mistral API: All retries failed")
    
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
