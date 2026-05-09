import os
import json
import logging
from typing import Dict, Any

# Settings for different model API keys
class settings:
    NVIDIA_API_KEY_LLAMA = os.getenv("NVIDIA_API_KEY_LLAMA", "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")
    NVIDIA_API_KEY_MISTRAL = os.getenv("NVIDIA_API_KEY_MISTRAL", "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")

# Global Nemotron model instance
_nemotron_instance = None


class NemotronTranslationModel:
    """
    Wrapper for Nemotron-3-Content-Safety model using NVIDIA API endpoint.
    """
    
    def __init__(self, api_key: str = None):
        """
        Initialize the Nemotron model with NVIDIA API.
        
        Args:
            api_key: NVIDIA API key for Nemotron-3-Content-Safety
        """
        self.api_key = api_key or os.getenv("NVIDIA_NEMOTRON_API_KEY", "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")
        self.api_url = "https://integrate.api.nvidia.com/v1/chat/completions"
        self.model_id = "nvidia/nemotron-3-content-safety"
        
        print(f"Nemotron model initialized with NVIDIA API")
    
    def translate_text(self, text: str, detected_language: str) -> str:
        """
        Translate text to English using appropriate model.
        
        Args:
            text: Input text in source language
            detected_language: Source language code (e.g., 'fr', 'ar')
            
        Returns:
            Translated English text
        """
        logger = logging.getLogger(__name__)
        
        try:
            from langchain_nvidia_ai_endpoints import ChatNVIDIA

            logger.debug(f"[Translation] Language: {detected_language}, Model: meta/llama-3.1-8b-instruct")

            client = ChatNVIDIA(
                model="meta/llama-3.1-8b-instruct",
                api_key=settings.NVIDIA_API_KEY_LLAMA,
                temperature=0.2,
                top_p=0.7,
                max_tokens=512,
            )

            # Use stronger prompt for Arabic to prevent returning original text
            if detected_language == "ar":
                prompt = (
                    "You are a professional banking translator specializing in "
                    "Algerian Arabic (Darija). "
                    
                    "Customers speak in Algerian dialect with non-standard spellings, "
                    "French-Arabic mixing, and informal language. "
                    
                    "Your job: "
                    "1. Understand the customer's intent regardless of spelling or dialect "
                    "2. Translate it into clean, standard English banking language "
                    "3. If a word is unclear, infer from banking context "
                    "4. Return ONLY the English translation, nothing else. "
                    
                    f"Arabic: {text}\n"
                    "English:"
                )
            else:
                prompt = f"Translate to English, return only the translation, nothing else:\n{text}"
            response = client.invoke([{"role": "user", "content": prompt}])
            translated_text = response.content.strip()

            logger.debug(f"[Translation] Result: {translated_text}")
            return translated_text

        except Exception as e:
            logger.error(f"[Translation] ERROR: {type(e).__name__}: {str(e)}", exc_info=True)
            return text
    
    def check_safety(self, text: str) -> str:
        """
        Check if text is safe using Nemotron content safety model.
        
        Args:
            text: English text to check for safety
            
        Returns:
            Safety label: "safe" or "unsafe"
        """
        import httpx
        
        if not self.api_key:
            print("NVIDIA API key not provided, returning safe")
            return "safe"
        
        try:
            safety_prompt = f"""You are a safety classifier for BNA (Banque Nationale d'Algérie) banking customer service.

CONTEXT: This is a banking system. Questions about loans, borrowing limits, interest rates, mortgage conditions, account fees, card issues, and all standard banking products are ALWAYS SAFE by definition.

TASK: Classify if the following English text is safe or unsafe.

SAFETY CRITERIA:
- SAFE: All banking-related questions, loan inquiries, account questions, financial advice requests
- UNSAFE: Hate speech, personal data harvesting, social engineering, abuse directed at staff, threats

Text: {text}

Respond in this exact format:
User Safety: [safe|unsafe]"""
            
            # Prepare API request
            headers = {
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json"
            }
            
            payload = {
                "model": self.model_id,
                "messages": [
                    {
                        "role": "user",
                        "content": safety_prompt
                    }
                ],
                "temperature": 0.3,
                "max_tokens": 512,
                "top_p": 0.9
            }
            
            # Make API call
            with httpx.Client(timeout=60.0) as client:
                response = client.post(self.api_url, headers=headers, json=payload)
                response.raise_for_status()
                
                result = response.json()
                response_content = result["choices"][0]["message"]["content"].strip()
                
                # Parse safety response
                safety_label = "safe"
                for line in response_content.split('\n'):
                    line = line.strip()
                    if line.startswith("User Safety:"):
                        safety_label = line.replace("User Safety:", "").strip().lower()
                
                return safety_label
                
        except httpx.HTTPStatusError as e:
            print(f"NVIDIA API HTTP error: {e}")
            return "safe"
        except Exception as e:
            print(f"Safety check API error: {e}")
            return "safe"
    
    def translate_and_sanitize(self, text: str, source_language: str) -> tuple:
        """
        Translate text to English and apply content safety checks using NVIDIA API.
        
        Args:
            text: Input text in source language
            source_language: Source language code (e.g., 'fr', 'ar')
            
        Returns:
            Tuple of (translated_text, safety_label)
        """
        # Step 1: Translate text to English
        translated_text = self.translate_text(text, source_language)
        
        # Step 2: Check safety of translated text
        safety_label = self.check_safety(translated_text)
        
        return translated_text, safety_label


def get_nemotron_model(api_key: str = None) -> NemotronTranslationModel:
    """
    Get the global Nemotron model instance (lazy loading).
    
    Args:
        api_key: NVIDIA API key (only used on first call)
        
    Returns:
        NemotronTranslationModel instance
    """
    global _nemotron_instance
    
    if _nemotron_instance is None:
        _nemotron_instance = NemotronTranslationModel(api_key)
    
    return _nemotron_instance


def load_nemotron_at_startup():
    """
    Initialize the Nemotron API client when the application starts.
    Call this function in your main.py or app startup.
    """
    api_key = os.getenv("NVIDIA_NEMOTRON_API_KEY")
    get_nemotron_model(api_key)
    print("Nemotron translation API client initialized at startup")
