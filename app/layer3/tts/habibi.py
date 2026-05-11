"""
Habibi-TTS Arabic Text-to-Speech Module
"""

def text_to_speech_arabic(text: str) -> tuple:
    """
    Convert text to speech using gTTS fallback for Arabic.
    
    Args:
        text: Text to convert to speech
        
    Returns:
        Tuple of (audio_data, sample_rate, model_name)
    """
    import logging
    logger = logging.getLogger(__name__)
    
    try:
        # Force fallback to gTTS for Arabic due to Habibi-TTS issues
        logger.warning("[Arabic-TTS] Habibi-TTS has issues, forcing gTTS fallback for Arabic")
        from app.layer3.tts.gtts_fallback import text_to_speech_gtts
        
        # Clean and validate text for Arabic
        if not text or not text.strip():
            logger.warning("Empty text provided to Arabic TTS")
            raise ValueError("Empty text provided")
        
        # Ensure text is properly encoded for Arabic
        clean_text = text.strip().encode('utf-8', errors='ignore').decode('utf-8')
        
        logger.debug(f"[Arabic-TTS] Converting text with gTTS fallback: {clean_text[:100]}...")
        
        # Use gTTS fallback for Arabic
        return text_to_speech_gtts(clean_text, "ar")
        
    except Exception as e:
        logger.error(f"[Arabic-TTS] ERROR: {type(e).__name__}: {str(e)}")
        # Re-raise for fallback handling
        raise e
