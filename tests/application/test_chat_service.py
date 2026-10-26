import pytest
from fakes import FailingChatModel, FakeEmbedder, FakeKnowledgeBase, InterruptedChatModel, RecordingChatModel

from agent.application.chat_service import ChatService
from agent.domain.errors import AgentError, ErrorKind
from agent.domain.knowledge import Chunk, Citation
from agent.domain.models import AgentTurn, AnswerDelta, Intent, IntentDetected
from agent.infrastructure.persistence.in_memory_store import InMemoryConversationStore

DEADLINES = Chunk(id="c1", content="Plazos\n\nSe responde en 15 días.", doc_type="regulation", section="Plazos", source="regulation.pdf")
CHANNELS = Chunk(id="c2", content="Canales\n\nApp y agencias.", doc_type="faq", section="Canales", source="channels.html")


def make_service(model, max_turns: int = 10, chunks: list[Chunk] | None = None) -> ChatService:
    return ChatService(
        model=model,
        rewriter=model,
        embedder=FakeEmbedder(),
        knowledge_base=FakeKnowledgeBase(chunks),
        store=InMemoryConversationStore(),
        system_prompt="SYS",
        max_turns=max_turns,
        top_k=5,
    )


def roles(messages) -> list[str]:
    return [message["role"] for message in messages]


def test_returns_typed_turn():
    turn = make_service(RecordingChatModel()).handle("s1", "Me robaron la tarjeta")
    assert turn.reply.intent is Intent.SENSITIVE_ACTION
    assert turn.usage.llm_calls == 1


def test_history_is_sent_on_next_turn():
    model = RecordingChatModel()
    service = make_service(model)

    service.handle("s1", "Hola")
    service.handle("s1", "Me robaron la tarjeta")

    assert roles(model.calls[1]) == ["system", "user", "assistant", "system", "user"]
    assert model.calls[1][0]["content"] == "SYS"
    assert model.calls[1][1]["content"] == "Hola"


def test_sessions_are_isolated():
    model = RecordingChatModel()
    service = make_service(model)

    service.handle("s1", "Hola")
    service.handle("s2", "Hola")

    assert roles(model.calls[1]) == ["system", "system", "user"]


def test_history_is_trimmed_to_max_turns():
    model = RecordingChatModel()
    service = make_service(model, max_turns=1)

    for text in ("uno", "dos", "tres"):
        service.handle("s1", text)

    assert [message["content"] for message in model.calls[2][1:-2]] == ["dos", "[fake] intención detectada: out_of_scope"]


def test_failed_turn_is_not_saved():
    model = RecordingChatModel()
    service = make_service(model)
    service.handle("s1", "Hola")

    service.model = FailingChatModel(ErrorKind.UPSTREAM)
    with pytest.raises(AgentError):
        service.handle("s1", "¿sigues?")

    service.model = model
    service.handle("s1", "Me robaron la tarjeta")
    assert roles(model.calls[-1]) == ["system", "user", "assistant", "system", "user"]


def test_context_numbers_the_chunks_found():
    model = RecordingChatModel()
    make_service(model, chunks=[DEADLINES, CHANNELS]).handle("s1", "¿Cuál es el plazo?")

    context = model.calls[0][-2]["content"]
    assert "[1] regulation.pdf\nPlazos" in context
    assert "[2] channels.html\nCanales" in context


def test_without_chunks_the_model_is_told_there_is_no_context():
    model = RecordingChatModel()
    make_service(model).handle("s1", "¿Cuál es el plazo?")
    assert model.calls[0][-2]["content"].startswith("No se encontraron fragmentos")


def test_citations_come_only_from_fragments_that_exist():
    model = RecordingChatModel(sources=[2, 7, 2])
    turn = make_service(model, chunks=[DEADLINES, CHANNELS]).handle("s1", "¿Por dónde reclamo?")
    assert turn.citations == [Citation(source="channels.html", section="Canales", chunk_id="c2")]


def test_follow_up_question_is_rewritten_before_searching():
    model = RecordingChatModel()
    service = make_service(model)

    service.handle("s1", "¿Cuál es el plazo de un reclamo?")
    turn = service.handle("s1", "¿y si es fraude?")

    assert service.knowledge_base.queries == ["¿Cuál es el plazo de un reclamo?", "[reescrita] ¿y si es fraude?"]
    assert roles(model.rewrites[0]) == ["system", "user", "assistant", "user"]
    assert turn.usage.llm_calls == 2


def test_stream_sends_the_intent_then_the_answer_in_pieces_then_the_turn():
    service = make_service(RecordingChatModel(sources=[1]), chunks=[DEADLINES])

    events = list(service.handle_stream("s1", "¿Cuál es el plazo?"))

    assert events[0] == IntentDetected(intent=Intent.PRODUCT_QUESTION)
    assert all(isinstance(event, AnswerDelta) for event in events[1:-1])
    turn = events[-1]
    assert isinstance(turn, AgentTurn)
    assert "".join(event.text for event in events[1:-1]).strip() == turn.reply.answer
    assert turn.citations == [Citation(source="regulation.pdf", section="Plazos", chunk_id="c1")]
    assert roles(service.store.get("s1")) == ["user", "assistant"]


def test_stream_cut_in_the_middle_does_not_save_the_turn():
    service = make_service(InterruptedChatModel())

    with pytest.raises(AgentError):
        list(service.handle_stream("s1", "¿Cuál es el plazo?"))

    assert service.store.get("s1") == []
