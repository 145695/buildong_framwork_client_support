"""
Status message translations for intermediate pipeline updates
"""

STATUS_MESSAGES = {
    "transcribing": {
        "ar": "انتظر معي، أنا أستمع إليك",
        "fr": "Attends avec moi, je t'écoute",
        "en": "Wait with me, I'm listening to you"
    },
    "translating": {
        "ar": "انتظر معي، أنا أفهم رسالتك",
        "fr": "Attends avec moi, je comprends ton message",
        "en": "Wait with me, I'm understanding your message"
    },
    "searching_kb": {
        "ar": "انتظر معي، أنا أبحث عن إجابة لسؤالك",
        "fr": "Attends avec moi, je cherche la réponse à ta question",
        "en": "Wait with me, I'm searching for the answer to your question"
    },
    "generating_response": {
        "ar": "انتظر معي، أنا أعد ردك",
        "fr": "Attends avec moi, je prépare ta réponse",
        "en": "Wait with me, I'm preparing your response"
    },
    "synthesizing_speech": {
        "ar": "انتظر معي، أنا أستعد للتحدث",
        "fr": "Attends avec moi, je me prépare à te parler",
        "en": "Wait with me, I'm getting ready to speak"
    },
    "complete": {
        "ar": "إليك إجابتك!",
        "fr": "Voici ta réponse!",
        "en": "Here's your answer!"
    }
}

def get_status_message(stage: str, language: str) -> str:
    """
    Get status message for a given stage and language
    
    Args:
        stage: Stage identifier (e.g., "processing", "transcribing")
        language: Language code (e.g., "ar", "fr", "en")
    
    Returns:
        Status message in the specified language, or English fallback
    """
    if stage not in STATUS_MESSAGES:
        stage = "processing"
    
    messages = STATUS_MESSAGES[stage]
    return messages.get(language, messages.get("en", "Processing..."))
