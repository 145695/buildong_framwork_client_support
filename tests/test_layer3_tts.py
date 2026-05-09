#!/usr/bin/env python3
"""
Test Layer 3 (Text-to-Voice) in isolation
Tests the TTS system directly without other layers
"""

import os
import sys
from pathlib import Path

# Add app to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.main import ml_models

def test_tts_system():
    """Test the TTS system with sample texts"""
    
    print("🔬 Testing Layer 3 (Text-to-Voice) - Isolated Test")
    print("=" * 60)
    
    # Check if TTS models are loaded
    if not ml_models.get("tts_pipeline"):
        print("❌ TTS pipeline not loaded")
        print("💡 Make sure LOAD_VOICE_MODELS=true in environment")
        return
    
    tts_pipeline = ml_models["tts_pipeline"]
    
    # Test texts in different languages
    test_texts = [
        ("Hello, this is a test of the text-to-speech system.", "en"),
        ("Bonjour, ceci est un test du système de synthèse vocale.", "fr"),
        ("مرحباً، هذا اختبار لنظام تحويل النص إلى كلام.", "ar"),
        ("Thank you for using our banking services.", "en"),
        ("Votre demande a été traitée avec succès.", "fr")
    ]
    
    print("🗣️ Testing Text-to-Voice Generation:")
    print("-" * 40)
    
    # Create output directory
    output_dir = Path("test_tts_outputs")
    output_dir.mkdir(exist_ok=True)
    
    for i, (text, lang) in enumerate(test_texts, 1):
        print(f"\n{i}. Text: {text}")
        print(f"   Language: {lang}")
        print("-" * 50)
        
        try:
            # Generate speech
            if hasattr(tts_pipeline, 'generate_speech'):
                # Kokoro pipeline
                speech = tts_pipeline.generate_speech(text, voice="default")
                audio_path = output_dir / f"test_{i}_{lang}.wav"
                
                # Save audio file
                import soundfile as sf
                sf.write(str(audio_path), speech.numpy(), 24000)
                
                print(f"✅ Audio saved: {audio_path}")
                print(f"📊 Duration: {len(speech) / 24000:.2f} seconds")
                
            else:
                # gTTS fallback
                from gtts import gTTS
                import pygame
                
                tts = gTTS(text=text, lang=lang)
                audio_path = output_dir / f"test_{i}_{lang}.mp3"
                tts.save(str(audio_path))
                
                print(f"✅ Audio saved: {audio_path}")
                
        except Exception as e:
            print(f"❌ Error: {e}")
    
    print("\n" + "=" * 60)
    print("✅ Layer 3 TTS Test Complete!")
    print(f"📁 Output files saved in: {output_dir}")
    
    # Test with a banking response
    print("\n🏦 Testing with Banking Response:")
    print("-" * 40)
    
    banking_response = """Thank you for your inquiry about our personal loan services. 
    Our current interest rates start at 4.5% APR for qualified applicants. 
    Please visit our website or contact your local branch for more information."""
    
    try:
        if hasattr(tts_pipeline, 'generate_speech'):
            speech = tts_pipeline.generate_speech(banking_response, voice="default")
            banking_audio_path = output_dir / "banking_response.wav"
            import soundfile as sf
            sf.write(str(banking_audio_path), speech.numpy(), 24000)
            print(f"✅ Banking response saved: {banking_audio_path}")
            print(f"📊 Duration: {len(speech) / 24000:.2f} seconds")
        
    except Exception as e:
        print(f"❌ Banking response error: {e}")

if __name__ == "__main__":
    test_tts_system()
