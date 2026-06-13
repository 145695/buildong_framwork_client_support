import numpy as np
import pytest
from app.layer1.audio_processor import AudioProcessor, AudioBuffer

class DummyVAD:
    """Simple VAD that treats any non‑zero frame as speech."""
    def __init__(self, sample_rate=16000, frame_size=480):
        self.sample_rate = sample_rate
        self.frame_size = frame_size  # bytes per frame (30 ms @ 16 kHz → 480 samples → 960 bytes)
    def is_speech(self, audio_bytes: bytes) -> bool:
        # If any byte is non‑zero, consider it speech
        return any(b != 0 for b in audio_bytes)
    def reset(self):
        pass

@pytest.fixture
def processor():
    # Use the dummy VAD with a short silence threshold for fast tests
    return AudioProcessor(vad_engine=DummyVAD(), silence_duration_ms=200)

def generate_frame(is_speech: bool) -> bytes:
    """Generate a 30 ms PCM frame (480 samples, 16‑bit)."""
    if is_speech:
        # Simple pattern of non‑zero bytes
        return (b"\x01\x02" * 480)
    else:
        # Silent frame – all zeros
        return (b"\x00\x00" * 480)

def test_buffering_and_silence_detection(processor: AudioProcessor):
    # Feed three speech frames – they should be buffered
    for _ in range(3):
        processor.process_frame(generate_frame(True))
    # Buffer should contain three frames
    assert len(processor.buffer.frames) == 3
    # Now feed silence frames until the processor decides to process
    silence_frames_needed = processor.silence_frame_threshold
    for _ in range(silence_frames_needed):
        processor.process_frame(generate_frame(False))
    assert processor.should_process() is True
    # Accumulated audio should be the concatenation of the three speech frames
    accumulated = processor.get_accumulated_audio()
    # Each speech frame is 480 samples → total 1440 samples
    assert isinstance(accumulated, np.ndarray)
    assert accumulated.shape[0] == 480 * 3

def test_reset_clears_state(processor: AudioProcessor):
    processor.process_frame(generate_frame(True))
    processor.process_frame(generate_frame(False))
    processor.reset()
    assert processor.buffer.frames == []
    assert processor.silence_frames == 0
