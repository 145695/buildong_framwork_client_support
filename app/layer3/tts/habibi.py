"""
Habibi-TTS Arabic Text-to-Speech Module
"""

def text_to_speech_arabic(text: str) -> tuple:
    """
    Convert text to speech using Habibi-TTS for Arabic.
    
    Args:
        text: Text to convert to speech
        
    Returns:
        Tuple of (audio_data, sample_rate, model_name)
    """
    from app.main import ml_models
    
    # Use Habibi-TTS for Arabic
    habibi = ml_models.get("tts_habibi")
    if habibi is None:
        raise Exception("Habibi-TTS not loaded")
    
    wav, sr, _ = habibi.infer(
        ref_file="assets/ref_arabic.wav",
        ref_text="",
        gen_text=text,
    )
    return wav, sr, "habibi-tts (ALG)"
