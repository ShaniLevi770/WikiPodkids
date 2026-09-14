import importlib


def _import_app_state():
    import os

    os.environ.setdefault("OPENAI_API_KEY", "test-key")
    return importlib.import_module("services.app_state")


class _RaisingQuery:
    """Mimics the supabase-py fluent query builder but always fails on execute()."""

    def select(self, *_, **__):
        return self

    def eq(self, *_, **__):
        return self

    def single(self):
        return self

    def insert(self, *_, **__):
        return self

    def update(self, *_, **__):
        return self

    def execute(self):
        raise ConnectionError("simulated Supabase outage")


class _RaisingClient:
    def table(self, _name):
        return _RaisingQuery()


def test_get_state_fails_open_on_connection_error(monkeypatch):
    """
    A Supabase outage (e.g. httpx.ConnectError) must not propagate — get_state()
    should fall back to the safe default instead of crashing the caller.
    """
    app_state = _import_app_state()
    monkeypatch.setattr(app_state, "_client", lambda: _RaisingClient())

    assert app_state.get_state() == {"app_enabled": True, "searches_total": 0}


def test_is_enabled_fails_open_on_connection_error(monkeypatch):
    """
    app.py gates the whole app on is_enabled() before rendering anything —
    it must never raise, or the app becomes fully unreachable on a DB blip.
    """
    app_state = _import_app_state()
    monkeypatch.setattr(app_state, "_client", lambda: _RaisingClient())

    assert app_state.is_enabled() is True


def test_increment_searches_returns_zero_on_connection_error(monkeypatch):
    app_state = _import_app_state()
    monkeypatch.setattr(app_state, "_client", lambda: _RaisingClient())

    assert app_state.increment_searches_and_maybe_notify(every=10) == 0


def test_set_enabled_swallows_connection_error(monkeypatch):
    app_state = _import_app_state()
    monkeypatch.setattr(app_state, "_client", lambda: _RaisingClient())

    # Should not raise.
    app_state.set_enabled(False)
