from enum import StrEnum
from pathlib import Path

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

ENV_FILE = Path(__file__).resolve().parents[4] / ".env"  # raíz del repo


class AuthProvider(StrEnum):
    API_KEY = "api_key"
    ENTRA_ID = "entra_id"


class _EnvSettings(BaseSettings):
    model_config = SettingsConfigDict(env_file=ENV_FILE, env_file_encoding="utf-8", extra="ignore")


class FoundrySettings(_EnvSettings):
    """Variables FOUNDRY_*: conexión a Microsoft Foundry."""

    model_config = SettingsConfigDict(env_prefix="FOUNDRY_")

    endpoint: str = ""
    auth_provider: AuthProvider  # sin default en el starter: lo fija .env (api_key con el mock en S1)
    api_key: SecretStr = SecretStr("")
    deployment: str = "gpt-5-mini"
    timeout_s: float = Field(30, gt=0)
    max_retries: int = Field(2, ge=0)


class Settings(_EnvSettings):
    # cada tema agrega su bloque: T2 search, T3 mcp, T4 cosmos y otel
    domain: str = "fraud"
    max_turns: int = Field(10, ge=1)
    foundry: FoundrySettings = Field(default_factory=FoundrySettings)
