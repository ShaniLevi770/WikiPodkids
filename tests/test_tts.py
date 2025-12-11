import importlib


def test_clean_for_tts_strips_headings_and_bold(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    tts = importlib.import_module("services.tts")

    raw = "# heading\n**Short bold heading**\nRegular line with **bold text** kept\nAnother line"
    cleaned = tts._clean_for_tts(raw)

    assert "# heading" not in cleaned
    assert "Short bold heading" not in cleaned  # short bold-only line removed
    assert "**" not in cleaned  # markers removed
    assert "Regular line with bold text kept" in cleaned
    assert "Another line" in cleaned


def test_split_text_safe_respects_max_length(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    tts = importlib.import_module("services.tts")

    text = "word " * 400  # ~2000 characters including spaces
    chunks = tts.split_text_safe(text, max_chars=300)

    assert len(chunks) > 1  # should split
    assert all(len(c) <= 300 for c in chunks)
