import io
import logging
import soundfile as sf
from app.schemas.conversation import ConversationState, SourceChannel

# Import from new TTS modules
from app.layer3.tts.habibi import text_to_speech_arabic
from app.layer3.tts.kokoro import text_to_speech_french, text_to_speech_english
from app.layer3.tts.gtts_fallback import text_to_speech_gtts
from app.layer3.translation.translator import translate_from_english

logger = logging.getLogger(__name__)


def _unmask_pii(text: str, pii_map: dict[str, str]) -> str:
    result = text
    for token, original in pii_map.items():
        result = result.replace(token, original)
    return result


def _channel_refine(text: str, channel: SourceChannel) -> str:
    if channel == SourceChannel.EMAIL:
        return f"Dear Client,\n\n{text}\n\nSincerely,\nClient Support Team"
    if channel == SourceChannel.VOICE:
        return text.replace("(", "").replace(")", "")
    return text


def _text_to_speech(text: str, language: str) -> tuple[bytes, int, str]:
    """
    Convert text to speech using appropriate TTS model based on language.
    Routes to specialized TTS modules.
    """
    try:
        if language == "ar":
            return text_to_speech_arabic(text)
        elif language == "fr":
            return text_to_speech_french(text)
        else:
            return text_to_speech_english(text)
    except Exception as e:
        # Fallback to gTTS if primary TTS fails
        print(f"Primary TTS failed for language {language}: {e}, using gTTS fallback")
        return text_to_speech_gtts(text, language)


def deliver_response(state: ConversationState) -> ConversationState:
    # Use localized response if available, otherwise translate from English
    if state.final_response_localized and state.final_response_localized != state.final_response_en:
        text = _unmask_pii(state.final_response_localized, state.pii_map)
        logger.debug(f"[Layer3] Using localized response: {text[:50]}...")
    else:
        text = _unmask_pii(state.final_response_en, state.pii_map)
        text = translate_from_english(text, state.source_language)
        logger.debug(f"[Layer3] Translated from English: {text[:50]}...")
    text = _channel_refine(text, state.source_channel)

    # Generate audio if voice channel
    if state.source_channel == SourceChannel.VOICE:
        try:
            audio_data, sample_rate, model_used = _text_to_speech(text, state.source_language)
            
            # Convert to bytes
            buffer = io.BytesIO()
            sf.write(buffer, audio_data, sample_rate, format="WAV")
            buffer.seek(0)
            
            state.final_response_audio = buffer.getvalue()
            state.audio_model_used = model_used
            state.audio_sample_rate = sample_rate
        except Exception as exc:
            state.trace.append(f"layer3:tts_failed:{exc}")
            state.final_response_audio = None

    state.final_response_localized = text
    state.trace.append("layer3:delivery_complete")
    return state
