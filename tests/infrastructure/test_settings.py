import pytest
from pydantic import SecretStr, ValidationError

from agent.infrastructure.config.settings import AuthProvider, FoundrySettings
from agent.infrastructure.llm.credentials import build_credential


def test_settings_reject_unknown_auth_provider(monkeypatch):
    monkeypatch.setenv("FOUNDRY_AUTH_PROVIDER", "oauth")
    with pytest.raises(ValidationError):
        FoundrySettings(_env_file=None)


def test_settings_hide_api_key(monkeypatch):
    monkeypatch.setenv("FOUNDRY_AUTH_PROVIDER", "api_key")
    monkeypatch.setenv("FOUNDRY_API_KEY", "super-secreta")
    settings = FoundrySettings(_env_file=None)
    assert settings.auth_provider is AuthProvider.API_KEY
    assert settings.api_key.get_secret_value() == "super-secreta"
    assert "super-secreta" not in repr(settings)


def test_api_key_provider_returns_key():
    assert build_credential(AuthProvider.API_KEY, SecretStr("k")) == "k"


def test_api_key_provider_requires_key():
    with pytest.raises(RuntimeError):
        build_credential(AuthProvider.API_KEY, SecretStr(""))


def test_entra_provider_returns_token_provider():
    assert callable(build_credential(AuthProvider.ENTRA_ID, SecretStr("")))
