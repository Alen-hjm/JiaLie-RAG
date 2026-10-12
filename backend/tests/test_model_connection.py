from types import SimpleNamespace

import pytest
from fastapi import HTTPException
from pydantic import ValidationError
from app.config import Settings
from app.schemas import SettingsUpdateIn
from app.routers import settings as router


def offline():
    return Settings(_env_file=None, model_mode="mock", chat_api_key="", openai_api_key="", embedding_provider="hash", embedding_api_key="")


def test_rejects_multiline_config_and_credential_urls():
    for values in ({"api_key": "secret\nMODEL_MODE=mock"}, {"base_url": "https://user:secret@example.com/v1"}, {"base_url": "file:///tmp/a"}, {"embedding_provider": "typo"}):
        with pytest.raises(ValidationError):
            SettingsUpdateIn(**values)


def test_quoted_env_roundtrip_preserves_other_values(tmp_path, monkeypatch):
    path = tmp_path / ".env"
    path.write_text("# keep comment\nDATABASE_URL=sqlite:///keep.db\nCHAT_API_KEY=old\n", encoding="utf-8")
    monkeypatch.setattr(router, "env_path", lambda: path)
    router.write_env({"CHAT_API_KEY": "a'b#c$", "CHAT_MODEL": "test-model"})
    assert router.read_env()["CHAT_API_KEY"] == "a'b#c$"
    assert router.read_env()["DATABASE_URL"] == "sqlite:///keep.db"
    assert "# keep comment" in path.read_text()


def test_mock_is_not_reported_as_real_connection():
    report = router.connection_report(offline())
    assert not report["ok"]
    assert not report["detail"]["chat"]["ok"]
    assert report["detail"]["embedding"]["placeholder"]


def test_draft_is_isolated_and_requires_keys(monkeypatch):
    original = offline()
    monkeypatch.setattr(router, "get_settings", lambda: original)
    with pytest.raises(HTTPException):
        router.draft_settings(SettingsUpdateIn(model_mode="openai"))
    draft = router.draft_settings(SettingsUpdateIn(model_mode="openai", base_url="https://example.com/v1", chat_model="example-chat", api_key="test-key", embedding_provider="custom", embedding_base_url="https://example.com/v1", embedding_model="example-embed", embedding_api_key="test-embed", embedding_dimensions=3, embedding_mode="real"))
    assert draft.chat_api_key == "test-key"
    assert draft.embedding_uses_remote
    assert original.model_mode == "mock"
    assert original.chat_api_key == ""


def test_custom_connection_uses_synthetic_text_and_checks_dimensions(monkeypatch):
    calls = []
    class Client:
        def with_options(self, **kwargs):
            return self
        def create(self, **kwargs):
            calls.append(kwargs)
            return SimpleNamespace(data=[SimpleNamespace(embedding=[0.1, 0.2, 0.3])])
        @property
        def embeddings(self):
            return self
    class Service:
        def __init__(self, db, settings):
            assert db is None
            self.client = self.embedding_client = Client()
        def parse_job(self, text):
            assert "连接测试" in text
    monkeypatch.setattr(router, "ModelService", Service)
    settings = offline().model_copy(update={"model_mode":"openai", "chat_api_key":"test-key", "embedding_provider":"custom", "embedding_base_url":"https://example.com/v1", "embedding_api_key":"test-embed", "embedding_model":"embed", "embedding_dimensions":3, "embedding_mode":"real"})
    assert router.connection_report(settings)["ok"]
    assert "dimensions" not in calls[0]
    assert calls[0]["input"] == ["连接测试"]
    assert not router.connection_report(settings.model_copy(update={"embedding_dimensions":4}))["ok"]


def test_connection_error_does_not_expose_secrets(monkeypatch):
    class Broken:
        def __init__(self, *args, **kwargs):
            raise RuntimeError("secret-key internal-provider-stack")
    monkeypatch.setattr(router, "ModelService", Broken)
    report = router.connection_report(offline().model_copy(update={"model_mode":"openai", "chat_api_key":"secret-key"}))
    assert not report["ok"]
    assert "secret-key" not in str(report)
