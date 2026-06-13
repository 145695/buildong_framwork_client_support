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


def _seems_french(text: str) -> bool:
    lower_text = text.lower()
    french_markers = [
        " quel ", " quelle ", " est ", " mon ", " ma ", " mes ", " du ", " au ", " des ", " pour ", " avec ", " chez ", " mais ", " non ", " oui "
    ]
    matches = sum(1 for marker in french_markers if marker in lower_text)
    return matches >= 2


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
    
    def translate_text(self, text: str, detected_language: str, target_language: str = "en") -> str:
        """
        Translate text to target language using appropriate model.

        Args:
            text: Input text in source language
            detected_language: Source language code (e.g., 'fr', 'ar')
            target_language: Target language code (e.g., 'en', 'fr')

        Returns:
            Translated text in target language
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

            # Use a stronger, explicit translation prompt and a system role for better output.
            target_lang_name = "French" if target_language == "fr" else "English"
            if detected_language == "ar":
                messages = [
                    {
                        "role": "system",
                        "content": (
                            f"You are a professional banking translator specializing in Algerian Arabic (Darija). "
                            "Customers speak in Algerian dialect with non-standard spellings, French-Arabic mixing, and informal language. "
                            f"Translate the input into clean, standard {target_lang_name} banking language. "
                            f"Return ONLY the {target_lang_name} translation and nothing else."
                        )
                    },
                    {
                        "role": "user",
                        "content": f"Arabic: {text}\n{target_lang_name}:"
                    }
                ]
            else:
                messages = [
                    {
                        "role": "system",
                        "content": (
                            f"You are a professional translator. Translate the following text into clear, natural {target_lang_name}. "
                            f"Return ONLY the {target_lang_name} translation and nothing else."
                        )
                    },
                    {
                        "role": "user",
                        "content": f"Source language: {detected_language}\nText: {text}\n{target_lang_name}:"
                    }
                ]
            response = client.invoke(messages)
            translated_text = response.content.strip()

            logger.debug(f"[Translation] Result: {translated_text}")

            # If we still see output that appears to be French when targeting English, fallback to GoogleTranslator.
            if target_language == "en" and detected_language == "fr" and _seems_french(translated_text):
                logger.warning("[Translation] Nemotron output appears to still be French, using fallback translator")
                raise ValueError("Nemotron output appears to still be French")

            return translated_text

        except Exception as e:
                logger.warning(f"[Translation] NVIDIA failed or returned non-{target_language} output: {e}. Trying fallback...")
                try:
                    from deep_translator import GoogleTranslator
                    source_lang = detected_language if detected_language != "en" else "auto"
                    translated = GoogleTranslator(
                        source=source_lang,
                        target=target_language
                    ).translate(text)
                    logger.debug(f"[Translation] Fallback result: {translated}")
                    return translated
                except Exception as fallback_error:
                    logger.error(f"[Translation] Fallback also failed: {fallback_error}")
                    logger.warning("[Translation] Gateway timeout - using original text without translation")
                    return text
                else:
                    logger.warning("[Translation] API error - using original text")
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
    
    def translate_and_sanitize(self, text: str, source_language: str, target_language: str = "en") -> tuple:
        """
        Translate text to target language and apply content safety checks using NVIDIA API.

        Args:
            text: Input text in source language
            source_language: Source language code (e.g., 'fr', 'ar')
            target_language: Target language code (e.g., 'en', 'fr')

        Returns:
            Tuple of (translated_text, safety_label)
        """
        # Step 1: Translate text to target language
        translated_text = self.translate_text(text, source_language, target_language)

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
