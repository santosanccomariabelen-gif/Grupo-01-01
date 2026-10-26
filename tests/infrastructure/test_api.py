import json
from uuid import UUID

import pytest
from fakes import FailingChatModel, FakeChatModel, FakeEmbedder, FakeKnowledgeBase, InterruptedChatModel
from fastapi.testclient import TestClient

from agent.domain.errors import ErrorKind
from agent.domain.knowledge import Chunk
from agent.infrastructure.bootstrap import create_app
from agent.infrastructure.config.settings import FoundrySettings, Settings


def make_client(chat_model, chunks: list[Chunk] | None = None) -> TestClient:
    settings = Settings(_env_file=None, foundry=FoundrySettings(_env_file=None, auth_provider="api_key"))
    app = create_app(chat_model=chat_model, settings=settings, embedder=FakeEmbedder(), knowledge_base=FakeKnowledgeBase(chunks))
    return TestClient(app)


# las 5 conversaciones de prueba del entregable de la semana 1
CONVERSATIONS = [
    ("Hola, buenos días", "greeting"),
    ("Me robaron la tarjeta, ¿qué hago?", "sensitive_action"),
    ("¿Cuál es el plazo para presentar un reclamo?", "product_question"),
    ("Quiero ver mis movimientos de ayer", "data_query"),
    ("¿A cuánto está el dólar hoy?", "out_of_scope"),
]


@pytest.mark.parametrize(("message", "intent"), CONVERSATIONS)
def test_chat_returns_typed_reply(message, intent):
    response = make_client(FakeChatModel()).post("/chat", json={"message": message})

    assert response.status_code == 200
    body = response.json()
    assert body["intent"] == intent
    assert body["answer"]
    assert body["usage"]["llm_calls"] == 1
    UUID(body["session_id"])


def test_chat_keeps_session_id():
    client = make_client(FakeChatModel())
    first = client.post("/chat", json={"message": "Hola"}).json()
    second = client.post("/chat", json={"session_id": first["session_id"], "message": "Gracias"}).json()
    assert second["session_id"] == first["session_id"]


def test_chat_returns_citations():
    deadlines = Chunk(id="c1", content="Plazos", doc_type="regulation", section="Reglamento > Plazos", source="regulation.pdf")
    body = make_client(FakeChatModel(sources=[1]), chunks=[deadlines]).post("/chat", json={"message": "¿Plazo?"}).json()
    assert body["citations"] == [{"source": "regulation.pdf", "section": "Reglamento > Plazos", "chunk_id": "c1"}]


@pytest.mark.parametrize(
    "payload",
    [
        {"message": ""},
        {"message": "   "},
        {"message": "x" * 2001},
        {"session_id": "no-es-uuid", "message": "Hola"},
        {},
    ],
)
def test_invalid_request_is_422(payload):
    assert make_client(FakeChatModel()).post("/chat", json=payload).status_code == 422


@pytest.mark.parametrize(
    ("kind", "status"),
    [
        (ErrorKind.TIMEOUT, 504),
        (ErrorKind.RATE_LIMIT, 429),
        (ErrorKind.INVALID_OUTPUT, 502),
        (ErrorKind.UPSTREAM, 502),
    ],
)
def test_agent_errors_map_to_http(kind, status):
    response = make_client(FailingChatModel(kind)).post("/chat", json={"message": "Hola"})

    assert response.status_code == status
    assert response.json() == {"error": kind.value, "detail": "falla simulada"}


def read_events(response) -> list[tuple[str, dict]]:
    """Separa la respuesta de /chat/stream en (nombre del evento, datos)."""
    events = []
    for block in response.text.strip().split("\n\n"):
        name_line, data_line = block.split("\n")
        events.append((name_line.removeprefix("event: "), json.loads(data_line.removeprefix("data: "))))
    return events


def test_chat_stream_sends_the_answer_in_pieces():
    deadlines = Chunk(id="c1", content="Plazos", doc_type="regulation", section="Reglamento > Plazos", source="regulation.pdf")
    response = make_client(FakeChatModel(sources=[1]), chunks=[deadlines]).post("/chat/stream", json={"message": "¿Plazo?"})

    assert response.headers["content-type"].startswith("text/event-stream")
    events = read_events(response)
    names = [name for name, _ in events]
    assert names[:2] == ["start", "intent"]
    assert names[-1] == "end"
    assert set(names[2:-1]) == {"delta"}
    end = events[-1][1]
    assert "".join(data["text"] for name, data in events if name == "delta").strip() == end["answer"]
    assert end["citations"][0]["chunk_id"] == "c1"


def test_chat_stream_cut_in_the_middle_ends_with_an_error_event():
    events = read_events(make_client(InterruptedChatModel()).post("/chat/stream", json={"message": "¿Plazo?"}))
    assert events[-1] == ("error", {"error": "upstream", "detail": "se cortó la respuesta"})
