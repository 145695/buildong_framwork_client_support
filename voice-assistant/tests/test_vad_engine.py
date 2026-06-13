import pytest
from app.layer1.vad_engine import VADEngine

@pytest.fixture
def vad():
    return VADEngine()

def test_silence_detection(vad):
    # Generate silent audio frame (16-bit PCM zeros)
    silent_frame = (b"\x00\x00" * 480)  # 30ms at 16kHz
    assert not vad.is_speech(silent_frame)

def test_speech_detection(vad):
    # Simple non-silent frame (alternating pattern)
    speech_frame = (b"\x01\x02" * 480)
    assert vad.is_speech(speech_frame)
