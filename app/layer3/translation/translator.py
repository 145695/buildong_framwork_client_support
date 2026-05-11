"""
Back-Translation Module for Final Response Localization
"""

from deep_translator import GoogleTranslator
import logging
import time

logger = logging.getLogger(__name__)

def translate_from_english(text: str, target_language: str) -> str:
    """
    Translate text from English to target language for final response.
    
    Args:
        text: English text to translate
        target_language: Target language code (e.g., 'fr', 'ar')
        
    Returns:
        Translated text in target language
    """
    try:
        if target_language == "en" or not target_language:
            return text

        logger.debug(f"[Layer3-Translation] Translating to: {target_language}")

        # Add retry logic with timeout
        max_retries = 3
        for attempt in range(max_retries):
            try:
                translated = GoogleTranslator(
                    source="en",
                    target=target_language,
                    timeout=10  # 10 second timeout
                ).translate(text)
                
                logger.debug(f"[Layer3-Translation] Result: {translated}")
                return translated
                
            except Exception as e:
                if attempt == max_retries - 1:
                    # Last attempt failed
                    logger.error(f"[Layer3-Translation] ERROR: {type(e).__name__}: {str(e)}")
                    logger.warning(f"[Layer3-Translation] Using fallback to English due to translation failure")
                    return text  # fallback to English
                else:
                    logger.warning(f"[Layer3-Translation] Retry {attempt + 1}/{max_retries} failed: {str(e)}")
                    time.sleep(1)  # Wait 1 second before retry
                    continue

    except Exception as e:
        logger.error(f"[Layer3-Translation] ERROR: {type(e).__name__}: {str(e)}")
        return text  # fallback to English
