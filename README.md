# Multi-Language TTS/STT System

A comprehensive Text-to-Speech (TTS) and Speech-to-Text (STT) system supporting multiple languages with robust fallback mechanisms.

## Features

### Text-to-Speech (TTS) - Layer 3
- **Arabic**: Habibi-TTS (primary) with gTTS and Kokoro fallbacks
- **English**: Kokoro-82m with multiple voice options
- **French**: Kokoro-82m with French voice support
- **Robust encoding**: Proper UTF-8 handling for Arabic text
- **Audio formats**: WAV output with proper sample rates

### Speech-to-Text (STT) - Layer 1
- **Whisper**: Primary STT with FFmpeg dependency
- **Google Speech Recognition**: Online fallback
- **CMU Sphinx**: Offline fallback
- **Automatic fallback**: Graceful degradation when dependencies are missing

## Installation

### Prerequisites
- Python 3.8 or higher
- FFmpeg (optional, for Whisper STT)

### Quick Install

1. **Clone the repository:**
```bash
git clone <repository-url>
cd buildong_framwork_client_support
```

2. **Install Python dependencies:**
```bash
pip install -r requirements.txt
```

3. **Optional: Install FFmpeg for Whisper STT:**

**Windows (recommended):**
```bash
# Using Chocolatey
choco install ffmpeg

# Or download from: https://ffmpeg.org/download.html
# Choose "full-shared" version for complete functionality
```

**Linux/macOS:**
```bash
# Ubuntu/Debian
sudo apt update && sudo apt install ffmpeg

# macOS
brew install ffmpeg
```

### Library Requirements

#### Core Dependencies
- `fastapi` - Web framework
- `uvicorn` - ASGI server
- `torch` - PyTorch for ML models
- `transformers` - Hugging Face transformers
- `kokoro` - TTS model
- `numpy` - Numerical computing
- `soundfile` - Audio file handling

#### TTS Dependencies
- `gTTS` - Google Text-to-Speech (Arabic fallback)
- `pydub` - Audio processing for MP3 conversion

#### STT Dependencies
- `speechrecognition` - Fallback STT library
- `ffmpeg-python` - FFmpeg Python bindings

#### Language Processing
- `langgraph` - Language graph processing
- `langchain-openai` - OpenAI integration
- `langchain-core` - Core language chain functionality

## Usage

### Start the Server
```bash
python main.py
```

The server will start on `http://localhost:8000`

### API Endpoints

#### Text-to-Speech (TTS)
```bash
POST /test/tts
Content-Type: application/json

{
    "text": "Hello world",
    "language": "en"  // "en", "fr", "ar"
}
```

#### Speech-to-Text (STT)
```bash
POST /test/stt
Content-Type: multipart/form-data

audio_file: <audio_file>
```

#### Download Generated Audio
```bash
GET /download/{filename}
```

### Web Interface
Visit `http://localhost:8000/tts-ui` for the interactive web interface.

## Language Support

### Arabic (ar)
- **Primary**: Habibi-TTS (best pronunciation)
- **Fallback 1**: gTTS (Google Arabic TTS)
- **Fallback 2**: Kokoro English (basic pronunciation)

### English (en)
- **Primary**: Kokoro-82m with "af_heart" voice
- **Multiple voices** available

### French (fr)
- **Primary**: Kokoro-82m with "ff_siwis" voice

## Error Handling

The system includes comprehensive error handling:

### TTS Errors
- Model loading failures
- Audio processing errors
- File system issues
- Encoding problems

### STT Errors
- FFmpeg dependency issues (Whisper)
- Network connectivity (Google Speech)
- Audio format compatibility
- Recognition failures

## Troubleshooting

### Whisper STT Not Working
**Error**: "Whisper STT requires FFmpeg libraries"
**Solution**: Install FFmpeg system-wide (see installation section)

### Arabic Text Encoding Issues
**Error**: Garbled Arabic text
**Solution**: The system includes UTF-8 encoding fixes

### Audio File Not Found
**Error**: 404 when downloading audio
**Solution**: Check the `outputs/` directory exists

### Model Loading Failures
**Error**: Model not loaded messages
**Solution**: Restart the server and check console logs

## File Structure

```
buildong_framwork_client_support/
|-- app/
|   |-- main.py              # Main application entry point
|   |-- routers/
|   |   |-- voice.py         # TTS/STT API endpoints
|   |-- models/              # ML model definitions
|   |-- static/              # Static files
|   |-- templates/           # HTML templates
|-- outputs/                 # Generated audio files
|-- requirements.txt         # Python dependencies
|-- README.md               # This file
```

## Configuration

### Environment Variables
- `LOAD_VOICE_MODELS` - Control model loading behavior

### Model Paths
- Models are automatically downloaded and cached
- Audio files are saved to `outputs/` directory

## Performance Notes

### TTS Performance
- Habibi-TTS: Best quality, moderate speed
- gTTS: Fast, requires internet
- Kokoro: Fast, good quality

### STT Performance
- Whisper: Best accuracy, requires FFmpeg
- Google Speech: Good accuracy, requires internet
- Sphinx: Moderate accuracy, offline

## License

This project uses various open-source libraries. Please refer to individual library licenses for more information.

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Test thoroughly
5. Submit a pull request

## Support

For issues and questions:
1. Check the troubleshooting section
2. Review console logs for detailed error messages
3. Verify all dependencies are installed correctly