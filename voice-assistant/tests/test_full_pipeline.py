#!/usr/bin/env python3
"""
Test script for the new voice full pipeline endpoint
"""

import requests
import json
import os

def test_full_pipeline_endpoint():
    """Test the new /test/voice-full-pipeline endpoint"""
    
    # Check if we have a test audio file
    test_audio_path = "outputs/output_en_105df781.wav"
    if not os.path.exists(test_audio_path):
        print(f"ERROR: Test audio file not found: {test_audio_path}")
        return False
    
    print(f"Testing full pipeline with audio file: {test_audio_path}")
    
    # Prepare the request
    url = "http://localhost:8000/test/voice-full-pipeline"
    
    try:
        print(f"Sending request to {url}...")
        with open(test_audio_path, 'rb') as audio_file:
            files = {'audio': audio_file}
            response = requests.post(url, files=files, timeout=180)
        
        print(f"Response status: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            print("SUCCESS: Full pipeline test successful!")
            print(json.dumps(data, indent=2, ensure_ascii=False))
            return True
        else:
            print(f"ERROR: Full pipeline test failed with status {response.status_code}")
            print(f"Error: {response.text}")
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
    test_full_pipeline_endpoint()
