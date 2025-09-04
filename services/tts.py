# services/tts.py
import os
import uuid
import textwrap
from google.cloud import texttospeech

def split_text_safe(text: str, max_chars: int = 1200):
    return textwrap.wrap(text, max_chars, break_long_words=False, replace_whitespace=False)

def _build_ssml(text: str) -> str:
    safe = text.replace("&","&amp;").replace("<","&lt;").replace(">","&gt;")
    safe = safe.replace("!", "!<break time=\"500ms\"/>") \
               .replace("?", "?<break time=\"500ms\"/>") \
               .replace(".", ".<break time=\"400ms\"/>")
    paragraphs = [p for p in safe.split("\n") if p.strip()]
    body = "".join(f"<p>{p}</p>" for p in paragraphs)
    return f"<speak><prosody rate=\"90%\" pitch=\"-2st\">{body}</prosody></speak>"

def synthesize_chunks_to_file(chunks, voice_name, filename="podcast.mp3"):
    client = texttospeech.TextToSpeechClient()
    voice = texttospeech.VoiceSelectionParams(language_code="he-IL", name=voice_name)
    audio_config = texttospeech.AudioConfig(audio_encoding=texttospeech.AudioEncoding.MP3, speaking_rate=1.0)
    os.makedirs("audio", exist_ok=True)
    out_path = f"audio/{uuid.uuid4()}_{filename}"
    with open(out_path, "wb") as f:
        for chunk in chunks:
            ssml = _build_ssml(chunk.strip())
            resp = client.synthesize_speech(
                input=texttospeech.SynthesisInput(ssml=ssml),
                voice=voice,
                audio_config=audio_config
            )
            f.write(resp.audio_content)
    return out_path
