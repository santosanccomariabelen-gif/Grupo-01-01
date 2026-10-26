from enum import StrEnum
from pathlib import Path

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

ROOT = Path(__file__).resolve().parents[4]  # raíz del repo
ENV_FILE = ROOT / ".env"


class AuthProvider(StrEnum):
    API_KEY = "api_key"
    ENTRA_ID = "entra_id"


class KnowledgeBaseKind(StrEnum):
    LOCAL = "local"  # Qdrant en data/index/<dominio>
    AZURE_SEARCH = "azure_search"  # el índice del equipo en Azure AI Search


class JudgeKind(StrEnum):
    LOCAL = "local"  # G-Eval con un modelo generativo de Foundry
    AZURE_EVALUATION = "azure_evaluation"  # Microsoft-Decision-1


class _EnvSettings(BaseSettings):
    model_config = SettingsConfigDict(env_file=ENV_FILE, env_file_encoding="utf-8", extra="ignore")


class FoundrySettings(_EnvSettings):
    """Variables FOUNDRY_*: conexión a Microsoft Foundry."""

    model_config = SettingsConfigDict(env_prefix="FOUNDRY_")

    endpoint: str = ""
    auth_provider: AuthProvider = AuthProvider.ENTRA_ID  # S1 lo fija en api_key para el mock (.env.example)
    api_key: SecretStr = SecretStr("")
    deployment: str = "gpt-5-mini"
    embedding_deployment: str = "text-embedding-3-small"
    judge_deployment: str = "gpt-5-mini"  # juez G-Eval: conviene otro modelo, para que no se califique a sí mismo
    decision_deployment: str = "microsoft-decision-1"
    timeout_s: float = Field(30, gt=0)
    max_retries: int = Field(2, ge=0)


class IngestSettings(_EnvSettings):
    """Variables INGEST_*: ingesta del corpus. Todo vive bajo data/, que no se versiona."""

    model_config = SettingsConfigDict(env_prefix="INGEST_")

    corpus_dir: Path = ROOT / "data" / "corpus"
    data_dir: Path = ROOT / "data"
    chunk_max_chars: int = Field(1500, ge=200)
    batch_size: int = Field(16, ge=1)


class SearchSettings(_EnvSettings):
    """Variables SEARCH_*: búsqueda en el corpus. endpoint e index solo se usan con KNOWLEDGE_BASE=azure_search."""

    model_config = SettingsConfigDict(env_prefix="SEARCH_")

    endpoint: str = ""  # https://<servicio>.search.windows.net
    index: str = ""  # idx-team-NN
    top_k: int = Field(5, ge=1, le=20)


class Settings(_EnvSettings):
    # cada tema agrega su bloque: T2 ingest y search, T3 mcp, T4 cosmos y otel
    domain: str = "fraud"
    max_turns: int = Field(10, ge=1)
    knowledge_base: KnowledgeBaseKind = KnowledgeBaseKind.LOCAL
    judge: JudgeKind = JudgeKind.LOCAL
    foundry: FoundrySettings = Field(default_factory=FoundrySettings)
    ingest: IngestSettings = Field(default_factory=IngestSettings)
    search: SearchSettings = Field(default_factory=SearchSettings)
