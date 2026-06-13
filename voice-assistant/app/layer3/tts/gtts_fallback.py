"""
gTTS Fallback Text-to-Speech Module
"""

def text_to_speech_gtts(text: str, language: str) -> tuple:
    """
    Convert text to speech using gTTS as fallback.
    
    Args:
        text: Text to convert to speech
        language: Target language code
        
    Returns:
        Tuple of (audio_data, sample_rate, model_name)
    """
    try:
        from gtts import gTTS
        import io
        import soundfile as sf
        import numpy as np
        
        # Generate speech using gTTS
        tts = gTTS(text=text, lang=language, slow=False)
        
        # Save to bytes buffer
        buffer = io.BytesIO()
        tts.write_to_fp(buffer)
        buffer.seek(0)
        
        # Convert to numpy array
        audio_data, sample_rate = sf.read(buffer)
        
        return audio_data, sample_rate, f"gTTS ({language})"
        
    except Exception as e:
        raise Exception(f"gTTS fallback failed: {e}")
