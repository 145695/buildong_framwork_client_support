#!/usr/bin/env python3
"""
Check voice-lab endpoint for final voice output functionality
"""

import re

def check_voice_lab_endpoint():
    """Check if voice-lab endpoint has final voice output section"""
    print('=== Voice Lab Endpoint Check ===')
    
    try:
        with open('app/main.py', 'r', encoding='utf-8') as f:
            content = f.read()
            
            # Find voice-lab endpoint
            lab_match = re.search(r'@app\.get\(.*voice-lab.*\)', content)
            if lab_match:
                print('✅ Found voice-lab endpoint')
                
                # Check if it has final voice output
                if 'final_response_audio' in content or 'final_response_localized' in content:
                    print('✅ Has final voice output section')
                    
                    # Look for voice output elements
                    voice_elements = re.findall(r'(final_response_audio|final_response_localized|🔊|🎵)', content)
                    if voice_elements:
                        print(f'✅ Voice elements found: {len(voice_elements)}')
                        for elem in voice_elements:
                            print(f'  - {elem}')
                    else:
                        print('❌ No voice output elements found')
                else:
                    print('❌ Missing final voice output section')
            else:
                print('❌ voice-lab endpoint not found')
                
    except Exception as e:
        print(f'❌ Error reading file: {e}')

if __name__ == "__main__":
    check_voice_lab_endpoint()
