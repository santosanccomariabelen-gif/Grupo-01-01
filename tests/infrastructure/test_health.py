import pytest
from fakes import FakeChatModel, FakeEmbedder, FakeKnowledgeBase
from fastapi.testclient import TestClient

from agent.infrastructure.bootstrap import create_app
from agent.infrastructure.config.settings import FoundrySettings, IngestSettings, KnowledgeBaseKind, Settings


def test_health():
    settings = Settings(_env_file=None, foundry=FoundrySettings(_env_file=None, auth_provider="api_key"))
    app = create_app(chat_model=FakeChatModel(), settings=settings, embedder=FakeEmbedder(), knowledge_base=FakeKnowledgeBase())
    response = TestClient(app).get("/health")
    assert response.json() == {"status": "ok"}


def test_agent_does_not_start_with_an_empty_knowledge_base(tmp_path):
    settings = Settings(
        _env_file=None,
        foundry=FoundrySettings(_env_file=None, auth_provider="api_key"),
        ingest=IngestSettings(_env_file=None, data_dir=tmp_path),
        knowledge_base=KnowledgeBaseKind.LOCAL,
    )
    # sin knowledge_base inyectada, el agente arma la de la configuración: una base local recién creada, sin chunks
    with pytest.raises(RuntimeError, match="está vacía"):
        create_app(chat_model=FakeChatModel(), settings=settings, embedder=FakeEmbedder())
