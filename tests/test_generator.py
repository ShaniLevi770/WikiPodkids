import importlib


def _fake_response(content):
    class Msg:
        def __init__(self, content):
            self.content = content

    class Choice:
        def __init__(self, content):
            self.message = Msg(content)

    return type("Resp", (), {"choices": [Choice(content)]})


def _stub_moderation(gen, monkeypatch, flagged=False):
    """
    Stub the OpenAI Moderation call so tests never hit the real network.
    `flagged` controls whether generate_kids_podcast_script's safety retry fires.
    """
    def fake_moderate(*args, **kwargs):
        Result = type("Result", (), {"flagged": flagged})
        return type("ModResp", (), {"results": [Result()]})

    monkeypatch.setattr(gen.oai.moderations, "create", fake_moderate)


def test_generate_appends_closing_once(monkeypatch):
    """
    The generator should append exactly one closing paragraph and keep the model body intact.
    """
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    gen = importlib.import_module("services.generator")
    _stub_moderation(gen, monkeypatch)

    body_text = "X" * 400  # force a single response without continuation
    monkeypatch.setattr(gen.oai.chat.completions, "create", lambda *a, **k: _fake_response(body_text))

    script = gen.generate_kids_podcast_script(
        summary="test summary",
        topic="test topic",
        minutes=1.0,
        age_label="7-12",
    )

    # Closing should be the last paragraph after a blank line
    parts = script.strip().split("\n\n")
    assert len(parts) >= 2
    closing = parts[-1]

    assert body_text in script
    assert script.count(closing) == 1
    # closing must not be empty and must not equal the body
    assert closing.strip()
    assert closing != body_text


def test_closing_references_topic(monkeypatch):
    """
    The appended closing should be personalized to the episode's topic, not a
    single generic sentence reused verbatim across every episode.
    """
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    gen = importlib.import_module("services.generator")
    _stub_moderation(gen, monkeypatch)

    monkeypatch.setattr(gen.oai.chat.completions, "create", lambda *a, **k: _fake_response("X" * 400))

    script = gen.generate_kids_podcast_script(
        summary="test summary",
        topic="דינוזאורים",
        minutes=1.0,
        age_label="7-12",
    )

    closing = script.strip().split("\n\n")[-1]
    assert "דינוזאורים" in closing


def test_generate_calls_continuation_when_short(monkeypatch):
    """
    When the first model response is too short, a continuation call should be made and merged.
    """
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    gen = importlib.import_module("services.generator")
    _stub_moderation(gen, monkeypatch)

    first_body = "A" * 50   # intentionally short to trigger continuation
    second_body = "CONTINUATION"
    calls = []

    def fake_create(*args, **kwargs):
        calls.append(kwargs)
        content = first_body if len(calls) == 1 else second_body
        return _fake_response(content)

    monkeypatch.setattr(gen.oai.chat.completions, "create", fake_create)

    script = gen.generate_kids_podcast_script(
        summary="short summary",
        topic="topic",
        minutes=0.5,  # small target so thresholds are reachable
        age_label="7-12",
    )

    assert len(calls) == 2  # continuation invoked
    assert first_body in script
    assert second_body in script


def test_closing_preserved_when_trimming(monkeypatch):
    """
    Even when the output must be trimmed, the closing paragraph should be present.
    """
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    gen = importlib.import_module("services.generator")
    _stub_moderation(gen, monkeypatch)

    long_body = " ".join(["word"] * 2000)  # very long to exceed cap
    monkeypatch.setattr(gen.oai.chat.completions, "create", lambda *a, **k: _fake_response(long_body))

    script = gen.generate_kids_podcast_script(
        summary="summary",
        topic="topic",
        minutes=0.5,  # small, forces trimming
        age_label="7-12",
    )

    parts = script.strip().split("\n\n")
    assert len(parts) >= 2
    closing = parts[-1]
    assert closing.strip()
    assert long_body.split()[0] in script  # body retained in trimmed form


def test_flagged_script_triggers_one_safety_retry(monkeypatch):
    """
    If moderation flags the first draft, the generator should regenerate once
    with a stricter safety instruction rather than serving the flagged script.
    """
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    gen = importlib.import_module("services.generator")

    # First draft is "flagged"; the retry is not.
    flags = iter([True, False])
    monkeypatch.setattr(
        gen,
        "_is_flagged",
        lambda text: next(flags),
    )

    system_messages = []

    # Long enough (> body_goal for minutes=1.0) that no continuation call is
    # triggered, so each attempt makes exactly one chat.completions.create call.
    def fake_create(*args, **kwargs):
        system_messages.append(kwargs["messages"][0]["content"])
        return _fake_response("X" * 600)

    monkeypatch.setattr(gen.oai.chat.completions, "create", fake_create)

    gen.generate_kids_podcast_script(
        summary="summary", topic="topic", minutes=1.0, age_label="7-12"
    )

    assert len(system_messages) == 2  # generated twice: normal, then strict retry
    assert system_messages[0] != system_messages[1]


def test_moderation_check_fails_open(monkeypatch):
    """
    A moderation-API error must never break episode generation — _is_flagged
    should swallow it and report "not flagged".
    """
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    gen = importlib.import_module("services.generator")

    def raising_moderate(*args, **kwargs):
        raise ConnectionError("simulated moderation outage")

    monkeypatch.setattr(gen.oai.moderations, "create", raising_moderate)

    assert gen._is_flagged("any text") is False
