"""Implementaciones de prueba de los puertos: sin red, Foundry ni base vectorial."""

from collections.abc import Iterator

from agent.domain.errors import AgentError, ErrorKind
from agent.domain.evaluation import Verdict
from agent.domain.knowledge import Chunk, Citation, SearchHit
from agent.domain.models import (
    AgentReply,
    AnswerDelta,
    Intent,
    IntentDetected,
    Message,
    ModelEvent,
    ModelResult,
    RewriteResult,
    Usage,
)


class FakeChatModel:
    # ponytail: heurística naive por palabras clave, solo para tests
    RULES = [
        (Intent.SENSITIVE_ACTION, ("bloque", "robaron", "robo", "perdí", "registrar reclamo")),
        (Intent.DATA_QUERY, ("mis movimientos", "estado de mi reclamo", "estado del reclamo")),
        (Intent.PRODUCT_QUESTION, ("fraude", "contracargo", "plazo", "reclamo", "no reconozco")),
        (Intent.GREETING, ("hola", "buenos", "buenas", "gracias", "adiós")),
    ]

    def __init__(self, sources: list[int] | None = None) -> None:
        self.sources = sources or []  # los números de fragmento que "cita" en cada respuesta

    def complete(self, messages: list[Message]) -> ModelResult:
        text = messages[-1]["content"].lower()
        intent = next(
            (intent for intent, words in self.RULES if any(word in text for word in words)), Intent.OUT_OF_SCOPE
        )
        reply = AgentReply(intent=intent, answer=f"[fake] intención detectada: {intent}", sources=self.sources)
        usage = Usage(models=["fake"], llm_calls=1, prompt_tokens=10, completion_tokens=5)
        return ModelResult(reply=reply, usage=usage)

    def stream(self, messages: list[Message]) -> Iterator[ModelEvent]:
        result = self.complete(messages)
        yield IntentDetected(intent=result.reply.intent)
        for word in result.reply.answer.split(" "):  # una palabra por evento, como un modelo que va escribiendo
            yield AnswerDelta(text=f"{word} ")
        yield result

    def rewrite(self, messages: list[Message]) -> RewriteResult:
        usage = Usage(models=["fake"], llm_calls=1, prompt_tokens=8, completion_tokens=4)
        return RewriteResult(query=f"[reescrita] {messages[-1]['content']}", usage=usage)


class RecordingChatModel(FakeChatModel):
    def __init__(self, sources: list[int] | None = None) -> None:
        super().__init__(sources)
        self.calls: list[list[Message]] = []
        self.rewrites: list[list[Message]] = []

    def complete(self, messages: list[Message]) -> ModelResult:
        self.calls.append(messages)
        return super().complete(messages)

    def rewrite(self, messages: list[Message]) -> RewriteResult:
        self.rewrites.append(messages)
        return super().rewrite(messages)


class FailingChatModel:
    def __init__(self, kind: ErrorKind) -> None:
        self.kind = kind

    def complete(self, messages: list[Message]) -> ModelResult:
        raise AgentError(self.kind, "falla simulada")

    def stream(self, messages: list[Message]) -> Iterator[ModelEvent]:
        raise AgentError(self.kind, "falla simulada")


class InterruptedChatModel(FakeChatModel):
    """Empieza a responder y se corta a la mitad, como una conexión que se cae."""

    def stream(self, messages: list[Message]) -> Iterator[ModelEvent]:
        yield IntentDetected(intent=Intent.PRODUCT_QUESTION)
        yield AnswerDelta(text="El plazo es ")
        raise AgentError(ErrorKind.UPSTREAM, "se cortó la respuesta")


class FakeEmbedder:
    DIM = 8

    def __init__(self) -> None:
        self.calls: list[int] = []

    def embed(self, texts: list[str]) -> list[list[float]]:
        self.calls.append(len(texts))
        return [[float(len(text))] * self.DIM for text in texts]


class FakeKnowledgeBase:
    """Devuelve siempre los mismos chunks, en orden, y anota qué se buscó."""

    def __init__(self, chunks: list[Chunk] | None = None) -> None:
        self.chunks = chunks or []
        self.queries: list[str] = []

    def publish(self, chunks: list[Chunk]) -> None:
        self.chunks = chunks

    def count(self) -> int:
        return len(self.chunks)

    def search(self, text: str, vector: list[float], top_k: int) -> list[SearchHit]:
        self.queries.append(text)
        return [SearchHit(chunk=chunk, score=1.0) for chunk in self.chunks[:top_k]]


class FakeJudge:
    """Pone siempre la misma nota y anota qué preguntas calificó."""

    def __init__(self) -> None:
        self.questions: list[str] = []

    def evaluate(self, question: str, fragments: list[SearchHit], answer: str, cited: list[Citation]) -> Verdict:
        self.questions.append(question)
        return Verdict(groundedness=4, relevance=5, citation_correct=1.0, judge="fake")
