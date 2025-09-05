# services/tts.py
import os
import uuid
import textwrap
from google.cloud import texttospeech
from services.config import get_gcp_creds  # use lazy creds from config

# Cache the TTS client across Streamlit reruns (and still work outside Streamlit)
try:
    import streamlit as st

    @st.cache_resource
    def get_tts_client():
        return texttospeech.TextToSpeechClient(credentials=get_gcp_creds())
except Exception:
    def get_tts_client():
        return texttospeech.TextToSpeechClient(credentials=get_gcp_creds())


def split_text_safe(text: str, max_chars: int = 1200):
    """Split long text into safe chunks without breaking words."""
    return textwrap.wrap(
        text,
        max_chars,
        break_long_words=False,
        replace_whitespace=False,
    )


def _build_ssml(text: str) -> str:
    """Convert plain text to SSML with gentle pauses."""
    safe = (
        text.replace("&", "&amp;")
            .replace("<", "&lt;")
            .replace(">", "&gt;")
    )
    # Add short breaks after sentence-ending punctuation
    safe = (
        safe.replace("!", "!<break time=\"500ms\"/>")
            .replace("?", "?<break time=\"500ms\"/>")
            .replace(".", ".<break time=\"400ms\"/>")
    )
    paragraphs = [p for p in safe.split("\n") if p.strip()]
    body = "".join(f"<p>{p}</p>" for p in paragraphs)
    return f"<speak><prosody rate=\"90%\" pitch=\"-2st\">{body}</prosody></speak>"


def synthesize_chunks_to_file(chunks, voice_name: str, filename: str = "podcast.mp3") -> str:
    """
    Synthesize a list of text chunks to a single MP3 file.
    Example voice_name: "he-IL-Wavenet-A" / "he-IL-Wavenet-B"
    """
    client = get_tts_client()

    voice = texttospeech.VoiceSelectionParams(
        language_code="he-IL",
        name=voice_name,
    )
    audio_config = texttospeech.AudioConfig(
        audio_encoding=texttospeech.AudioEncoding.MP3,
        speaking_rate=1.0,
    )

    os.makedirs("audio", exist_ok=True)
    out_path = f"audio/{uuid.uuid4()}_{filename}"

    with open(out_path, "wb") as f:
        for chunk in chunks:
            ssml = _build_ssml(chunk.strip())
            resp = client.synthesize_speech(
                input=texttospeech.SynthesisInput(ssml=ssml),
                voice=voice,
                audio_config=audio_config,
            )
            f.write(resp.audio_content)

    return out_path
