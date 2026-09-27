import pytest

from app import bootstrap as bootstrap_module
from app.config import get_settings


@pytest.fixture(autouse=True)
def _fresh_settings():
    """get_settings 带 lru_cache，改环境变量后必须清掉才能生效。"""
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


def _set(monkeypatch, **env):
    for key, value in env.items():
        monkeypatch.setenv(key, value)


def test_default_secrets_are_flagged(monkeypatch):
    """默认值必须被点名——它们的存在就是为了让人忘了改。"""
    _set(
        monkeypatch,
        SECRET_KEY="development-only-change-me",
        ADMIN_PASSWORD="minglie123",
        MODEL_MODE="mock",
    )
    get_settings.cache_clear()

    warnings = bootstrap_module.check_insecure_settings()
    assert any("SECRET_KEY" in item for item in warnings)
    assert any("ADMIN_PASSWORD" in item for item in warnings)


def test_strong_settings_produce_no_warning(monkeypatch):
    _set(
        monkeypatch,
        SECRET_KEY="a-long-enough-random-secret",
        ADMIN_PASSWORD="a-strong-password",
        MODEL_MODE="mock",
    )
    get_settings.cache_clear()

    assert bootstrap_module.check_insecure_settings() == []


def test_cloud_mode_without_chat_key_is_flagged(monkeypatch):
    """MODEL_MODE 指向云端却没有 Key，是最常见的"能启动但一用就报错"。"""
    _set(
        monkeypatch,
        SECRET_KEY="a-long-enough-random-secret",
        ADMIN_PASSWORD="a-strong-password",
        MODEL_MODE="deepseek",
        CHAT_API_KEY="",
        OPENAI_API_KEY="",
    )
    get_settings.cache_clear()

    warnings = bootstrap_module.check_insecure_settings()
    assert any("CHAT_API_KEY" in item for item in warnings)


def test_mock_mode_needs_no_key(monkeypatch):
    """离线演示模式不该被 Key 告警打扰。"""
    _set(
        monkeypatch,
        SECRET_KEY="a-long-enough-random-secret",
        ADMIN_PASSWORD="a-strong-password",
        MODEL_MODE="mock",
        CHAT_API_KEY="",
        OPENAI_API_KEY="",
    )
    get_settings.cache_clear()

    assert bootstrap_module.check_insecure_settings() == []
