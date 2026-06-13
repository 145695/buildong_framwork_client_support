import webrtcvad
import collections
import numpy as np

class VADEngine:
    """Voice Activity Detection wrapper using webrtcvad.

    Parameters
    ----------
    sample_rate: int, default 16000
        Sample rate of the audio. Must be 8000, 16000, 32000, or 48000.
    frame_duration_ms: int, default 30
        Frame size in ms. Valid values are 10, 20, or 30.
    aggressiveness: int, default 2
        VAD aggressiveness mode. 0 is least aggressive, 3 is most aggressive.
    """

    def __init__(self, sample_rate: int = 16000, frame_duration_ms: int = 30, aggressiveness: int = 2):
        if sample_rate not in (8000, 16000, 32000, 48000):
            raise ValueError("sample_rate must be 8000, 16000, 32000, or 48000")
        if frame_duration_ms not in (10, 20, 30):
            raise ValueError("frame_duration_ms must be 10, 20, or 30")
        if not (0 <= aggressiveness <= 3):
            raise ValueError("aggressiveness must be between 0 and 3")
        self.sample_rate = sample_rate
        self.frame_duration_ms = frame_duration_ms
        self.frame_size = int(sample_rate * frame_duration_ms / 1000) * 2  # 16-bit PCM => 2 bytes per sample
        self.vad = webrtcvad.Vad(aggressiveness)
        self.buffer = collections.deque()

    def is_speech(self, audio_frame: bytes) -> bool:
        """Return True if the given PCM audio frame contains speech.

        The frame must be exactly ``self.frame_size`` bytes long.
        """
        if len(audio_frame) != self.frame_size:
            raise ValueError(f"Audio frame must be {self.frame_size} bytes long")
        return self.vad.is_speech(audio_frame, self.sample_rate)

    def reset(self) -> None:
        """Clear any internal state.
        """
        self.buffer.clear()

    # Helper to split raw PCM into frames of the correct size
    def frame_generator(self, pcm_data: bytes):
        """Yield successive frames from PCM data.
        """
        offset = 0
        while offset + self.frame_size <= len(pcm_data):
            yield pcm_data[offset: offset + self.frame_size]
            offset += self.frame_size
