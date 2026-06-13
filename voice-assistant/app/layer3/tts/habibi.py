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
    import logging
    import os
    import io
    import soundfile as sf
    import numpy as np
    
    logger = logging.getLogger(__name__)
    
    try:
        # Clean and validate text for Arabic
        if not text or not text.strip():
            logger.warning("Empty text provided to Arabic TTS")
            raise ValueError("Empty text provided")
        
        # Ensure text is properly encoded for Arabic
        clean_text = text.strip().encode('utf-8', errors='ignore').decode('utf-8')
        
        logger.debug(f"[Arabic-TTS] Converting text: {clean_text[:100]}...")
        
        # Load Habibi-TTS model from main app
        from app.main import ml_models
        
        if not ml_models.get("tts_habibi"):
            logger.error("[Arabic-TTS] Habibi-TTS model not loaded")
            raise Exception("Habibi-TTS model not available")
        
        habibi = ml_models["tts_habibi"]
        
        # Reference audio file for Habibi-TTS
        ref_file = "assets/ref_arabic.wav"
        
        # Check if reference file exists
        if not os.path.exists(ref_file):
            logger.error(f"[Arabic-TTS] Reference file not found: {ref_file}")
            raise Exception(f"Reference file not found: {ref_file}")
        
        # Generate speech using Habibi-TTS
        logger.debug(f"[Arabic-TTS] Using reference file: {ref_file}")
        
        # Habibi-TTS inference with timeout
        import time
        import threading
        from queue import Queue
        
        start_time = time.time()
        
        # Use shorter reference for faster processing
        # and limit text length for speed
        if len(clean_text) > 100:
            clean_text = clean_text[:100] + "..."
            logger.warning(f"[Arabic-TTS] Text truncated for speed: {len(clean_text)} chars")
        
        logger.debug(f"[Arabic-TTS] Starting inference...")
        
        # Run inference with timeout
        result_queue = Queue()
        error_queue = Queue()
        
        def run_inference():
            try:
                # Try different F5-TTS API calls
                try:
                    # Method 1: Basic inference with reference
                    audio_result = habibi.infer(clean_text, ref_file=ref_file)
                except TypeError:
                    try:
                        # Method 2: Inference without ref_file parameter
                        audio_result = habibi.infer(clean_text)
                    except TypeError:
                        # Method 3: Generate with reference path as positional
                        audio_result = habibi.infer(clean_text, ref_file)
                result_queue.put(audio_result)
            except Exception as e:
                error_queue.put(e)
        
        # Start inference thread
        inference_thread = threading.Thread(target=run_inference)
        inference_thread.daemon = True
        inference_thread.start()
        
        # Wait for completion with timeout (30 seconds)
        inference_thread.join(timeout=30.0)
        
        if inference_thread.is_alive():
            logger.warning("[Arabic-TTS] Inference timeout (30s), falling back to gTTS")
            from app.layer3.tts.gtts_fallback import text_to_speech_gtts
            return text_to_speech_gtts(clean_text, "ar")
        
        # Check for errors
        if not error_queue.empty():
            raise error_queue.get()
        
        # Get result
        if result_queue.empty():
            raise Exception("No result from Habibi-TTS")
        
        audio_data = result_queue.get()
        
        inference_time = time.time() - start_time
        logger.info(f"[Arabic-TTS] Inference completed in {inference_time:.2f}s")
        
        # Convert to numpy array if needed
        if isinstance(audio_data, np.ndarray):
            audio_array = audio_data
        else:
            # Convert bytes to numpy array
            buffer = io.BytesIO(audio_data)
            audio_array, sample_rate = sf.read(buffer)
        
        # Standardize sample rate
        sample_rate = 22050  # Habibi-TTS typically uses 22050 Hz
        
        logger.debug(f"[Arabic-TTS] Generated audio: {len(audio_array)} samples, {sample_rate} Hz")
        
        return audio_array, sample_rate, "Habibi-TTS"
        
    except Exception as e:
        logger.error(f"[Arabic-TTS] ERROR: {type(e).__name__}: {str(e)}")
        # Re-raise for fallback handling
        raise e
