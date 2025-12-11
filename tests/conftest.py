import os
import sys
import types

# Ensure OpenAI key exists for services.config import
os.environ.setdefault("OPENAI_API_KEY", "test-key")

# ---- Stub streamlit ----
if "streamlit" not in sys.modules:
    st = types.ModuleType("streamlit")

    class _Secrets(dict):
        def get(self, k, default=None):
            return super().get(k, default)

    def cache_resource(func=None, *_, **__):
        if func is None:
            def wrapper(f):
                return f
            return wrapper
        return func

    st.secrets = _Secrets()
    st.cache_resource = cache_resource
    sys.modules["streamlit"] = st

# ---- Stub google cloud texttospeech ----
if "google" not in sys.modules:
    sys.modules["google"] = types.ModuleType("google")
google = sys.modules["google"]

cloud = types.ModuleType("google.cloud")
texttospeech = types.ModuleType("google.cloud.texttospeech")

class _DummyAudioEncoding:
    MP3 = "MP3"

class _DummyVoiceSelectionParams:
    def __init__(self, **kwargs): ...

class _DummyAudioConfig:
    def __init__(self, **kwargs): ...

class _DummySynthesisInput:
    def __init__(self, **kwargs): ...

class _DummyClient:
    def __init__(self, *_, **__): ...
    def synthesize_speech(self, input=None, voice=None, audio_config=None):
        class Resp:
            audio_content = b""
        return Resp()

texttospeech.AudioEncoding = _DummyAudioEncoding
texttospeech.VoiceSelectionParams = _DummyVoiceSelectionParams
texttospeech.AudioConfig = _DummyAudioConfig
texttospeech.SynthesisInput = _DummySynthesisInput
texttospeech.TextToSpeechClient = _DummyClient

cloud.texttospeech = texttospeech
sys.modules["google.cloud"] = cloud
sys.modules["google.cloud.texttospeech"] = texttospeech
google.cloud = cloud

# ---- Stub google.oauth2.service_account ----
oauth2 = types.ModuleType("google.oauth2")
service_account = types.ModuleType("google.oauth2.service_account")

class _DummyCreds:
    @classmethod
    def from_service_account_info(cls, info):
        return cls()
    @classmethod
    def from_service_account_file(cls, path):
        return cls()

service_account.Credentials = _DummyCreds
oauth2.service_account = service_account
sys.modules["google.oauth2"] = oauth2
sys.modules["google.oauth2.service_account"] = service_account
google.oauth2 = oauth2

# ---- Stub google.protobuf to satisfy streamlit deps if loaded ----
protobuf = types.ModuleType("google.protobuf")
sys.modules["google.protobuf"] = protobuf
google.protobuf = protobuf
