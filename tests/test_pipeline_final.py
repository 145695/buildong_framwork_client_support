#!/usr/bin/env python3
"""
Final test for the voice full pipeline endpoint
"""

import requests
import json
import os

def test_full_pipeline():
    """Test the new /test/voice-full-pipeline endpoint"""
    
    # Use an existing audio file
    test_audio_path = "outputs/output_en_105df781.wav"
    if not os.path.exists(test_audio_path):
        print(f"ERROR: Test audio file not found: {test_audio_path}")
        return False
    
    print(f"Testing full pipeline with audio file: {test_audio_path}")
    print(f"File size: {os.path.getsize(test_audio_path)} bytes")
    
    # Prepare the request
    url = "http://localhost:8000/test/voice-full-pipeline"
    
    try:
        print("Sending request to full pipeline endpoint...")
        with open(test_audio_path, 'rb') as audio_file:
            files = {'audio': audio_file}
            response = requests.post(url, files=files, timeout=300)
        
        print(f"Response status: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            print("SUCCESS: Full pipeline test successful!")
            print("\n=== PIPELINE SUMMARY ===")
            if 'summary' in data:
                summary = data['summary']
                print(f"Successful stages: {summary.get('successful_stages')}/{summary.get('total_stages')}")
                print(f"Original transcription: {summary.get('original_transcription')}")
                print(f"Detected language: {summary.get('detected_language')}")
                print(f"Translation applied: {summary.get('translation_applied')}")
            
            print("\n=== STAGE RESULTS ===")
            if 'stages' in data:
                for stage_name, stage_data in data['stages'].items():
                    print(f"\n{stage_name.upper()}:")
                    print(f"  Success: {stage_data.get('success')}")
                    if stage_data.get('success'):
                        if stage_name == 'whisper_stt':
                            print(f"  Transcription: {stage_data.get('transcription')}")
                            print(f"  Language: {stage_data.get('detected_language')}")
                        elif stage_name == 'translator':
                            if stage_data.get('translation_applied'):
                                print(f"  Original: {stage_data.get('original_text')}")
                                print(f"  Translated: {stage_data.get('translated_text')}")
                        elif stage_name == 'orchestrator':
                            print(f"  Intent: {stage_data.get('intent')}")
                            print(f"  Category: {stage_data.get('category')}")
                            print(f"  Confidence: {stage_data.get('confidence')}")
                        elif stage_name == 'knowledge_base':
                            print(f"  Answer: {stage_data.get('answer')}")
                            print(f"  Sources: {stage_data.get('sources')}")
                            print(f"  Documents found: {stage_data.get('documents_found')}")
                    else:
                        print(f"  Error: {stage_data.get('error')}")
            
            return True
        else:
            print(f"ERROR: Full pipeline test failed with status {response.status_code}")
            print(f"Response: {response.text[:500]}")
            return False
            
    except requests.exceptions.ConnectionError as e:
        print(f"ERROR: Connection failed - {e}")
        return False
    except requests.exceptions.Timeout as e:
        print(f"ERROR: Request timed out - {e}")
        return False
    except Exception as e:
        print(f"ERROR: Test failed with error: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    test_full_pipeline()
