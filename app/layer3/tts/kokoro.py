"""
Kokoro TTS Module for French and English
"""

import numpy as np


def text_to_speech_french(text: str) -> tuple:
    """
    Convert text to speech using Kokoro for French.
    
    Args:
        text: Text to convert to speech
        
    Returns:
        Tuple of (audio_data, sample_rate, model_name)
    """
    from app.main import ml_models
    
    # Use Kokoro for French
    kokoro = ml_models.get("tts_kokoro_fr")
    if kokoro is None:
        raise Exception("Kokoro FR not loaded")
    
    chunks = [audio for _, _, audio in kokoro(text, voice="ff_siwis")]
    audio_data = np.concatenate(chunks)
    return audio_data, 24000, "kokoro-82m (FR)"


def text_to_speech_english(text: str) -> tuple:
    """
    Convert text to speech using Kokoro for English.
    
    Args:
        text: Text to convert to speech
        
    Returns:
        Tuple of (audio_data, sample_rate, model_name)
    """
    from app.main import ml_models
    
    # Use Kokoro for English (default)
    kokoro = ml_models.get("tts_kokoro_en")
    if kokoro is None:
        raise Exception("Kokoro EN not loaded")
    
    chunks = [audio for _, _, audio in kokoro(text, voice="af_heart")]
    audio_data = np.concatenate(chunks)
    return audio_data, 24000, "kokoro-82m (EN)"
