from fastapi.testclient import TestClient

from agent.infrastructure.bootstrap import create_app
from agent.infrastructure.config.settings import FoundrySettings, Settings


def test_health():
    settings = Settings(_env_file=None, foundry=FoundrySettings(_env_file=None, auth_provider="api_key"))
    response = TestClient(create_app(settings=settings)).get("/health")
    assert response.json() == {"status": "ok"}


# TODO autónomo T1: 5 conversaciones de prueba contra /chat con un ChatModel falso (sin red),
#                   más casos de input inválido y de cada falla del agente.
