import importlib


def test_generate_appends_closing_once(monkeypatch):
    """
    The generator should append exactly one closing paragraph and keep the model body intact.
    """
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    gen = importlib.import_module("services.generator")

    body_text = "X" * 400  # force a single response without continuation

    def fake_create(*args, **kwargs):
        class Msg:
            def __init__(self, content):
                self.content = content

        class Choice:
            def __init__(self, content):
                self.message = Msg(content)

        return type("Resp", (), {"choices": [Choice(body_text)]})

    monkeypatch.setattr(gen.oai.chat.completions, "create", fake_create)

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


def test_generate_calls_continuation_when_short(monkeypatch):
    """
    When the first model response is too short, a continuation call should be made and merged.
    """
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    gen = importlib.import_module("services.generator")

    first_body = "A" * 50   # intentionally short to trigger continuation
    second_body = "CONTINUATION"
    calls = []

    def fake_create(*args, **kwargs):
        # record call order
        calls.append(kwargs)
        content = first_body if len(calls) == 1 else second_body

        class Msg:
            def __init__(self, content):
                self.content = content

        class Choice:
            def __init__(self, content):
                self.message = Msg(content)

        return type("Resp", (), {"choices": [Choice(content)]})

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

    long_body = " ".join(["word"] * 2000)  # very long to exceed cap

    def fake_create(*args, **kwargs):
        class Msg:
            def __init__(self, content):
                self.content = content

        class Choice:
            def __init__(self, content):
                self.message = Msg(content)

        return type("Resp", (), {"choices": [Choice(long_body)]})

    monkeypatch.setattr(gen.oai.chat.completions, "create", fake_create)

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
