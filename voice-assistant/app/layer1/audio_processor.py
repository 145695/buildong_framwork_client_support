"""
Audio buffering component for real-time audio streaming.
"""

import numpy as np

class AudioBuffer:
    """Simple audio buffer for PCM audio chunks."""
    def __init__(self):
        self.frames = []  # Store raw PCM frames
        self.sample_rate = 16000  # Fixed sample rate
        self.channels = 1        # Mono audio
        
    def add_frame(self, audio_bytes):
        """Add a PCM audio frame to the buffer."""
        # Convert bytes to numpy array (16-bit signed integers)
        frame = np.frombuffer(audio_bytes, dtype=np.int16)
        self.frames.append(frame)
        
    def get_accumulated(self):
        """Return accumulated audio as numpy array."""
        if not self.frames:
            return np.array([], dtype=np.int16)
        return np.concatenate(self.frames)
        
    def get_duration_ms(self):
        """Calculate total duration in milliseconds."""
        if not self.frames:
            return 0
        total_samples = len(self.frames[0])
        return (total_samples / self.sample_rate) * 1000
        
    def clear(self):
        """Reset the buffer."""
        self.frames = []
        
class AudioProcessor:
    """Process audio frames with buffering and VAD detection."""
    def __init__(self, vad_engine=None, silence_duration_ms=1200):
        self.buffer = AudioBuffer()
        self.vad = vad_engine or VADEngine()
        self.silence_duration_ms = silence_duration_ms
        self.silence_frames = 0
        # Calculate how many frames correspond to the silence duration
        self.frames_per_ms = self.vad.sample_rate / 1000 / (self.vad.frame_size // 2)  # bytes per frame -> samples
        self.silence_frame_threshold = int(self.silence_duration_ms * self.frames_per_ms)
        # Buffer for handling mismatched frame sizes
        self.frame_buffer = bytearray()
        
    def process_frame(self, audio_bytes):
        """Process a single audio frame, run VAD, and buffer if speech detected."""
        # Add incoming frame to buffer
        self.frame_buffer.extend(audio_bytes)
        
        # Process as many VAD-sized frames as possible
        while len(self.frame_buffer) >= self.vad.frame_size:
            # Extract one VAD-sized frame
            vad_frame = bytes(self.frame_buffer[:self.vad.frame_size])
            self.frame_buffer = self.frame_buffer[self.vad.frame_size:]
            
            # Run VAD on the frame
            is_speech = self.vad.is_speech(vad_frame)
            if is_speech:
                self.silence_frames = 0
                self.buffer.add_frame(vad_frame)
            else:
                self.silence_frames += 1
        
    def should_process(self) -> bool:
        """Return True when accumulated silence exceeds threshold, indicating end of speech."""
        return self.silence_frames >= self.silence_frame_threshold
        
    def get_accumulated_audio(self):
        """Return accumulated audio as numpy array."""
        return self.buffer.get_accumulated()
        
    def reset(self):
        """Clear the buffer and VAD state."""
        self.buffer.clear()
        self.silence_frames = 0
        self.vad.reset()
        self.frame_buffer.clear()
