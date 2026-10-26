"""Puertos: lo que el dominio necesita del mundo exterior. Las implementaciones viven en infrastructure."""

from collections.abc import Iterator
from typing import Protocol

from agent.domain.evaluation import Verdict
from agent.domain.knowledge import Chunk, Citation, SearchHit
from agent.domain.models import Message, ModelEvent, ModelResult, RewriteResult


class ChatModel(Protocol):
    """Modelo de lenguaje. T1: Foundry directo; T3: Microsoft Agent Framework."""

    def complete(self, messages: list[Message]) -> ModelResult: ...

    def stream(self, messages: list[Message]) -> Iterator[ModelEvent]:
        """Igual que complete, pero entrega la respuesta mientras se escribe. El último evento es el ModelResult."""
        ...


class QueryRewriter(Protocol):
    """Reescribe una pregunta de seguimiento para que se entienda sin el historial. S4: el mismo modelo de chat."""

    def rewrite(self, messages: list[Message]) -> RewriteResult: ...


class ConversationStore(Protocol):
    """Historial por sesión. T1: memoria; T4: Cosmos DB."""

    def get(self, session_id: str) -> list[Message]: ...
    def append(self, session_id: str, message: Message) -> None: ...


class Embedder(Protocol):
    """Texto → vector. T2: Foundry text-embedding-3-small."""

    def embed(self, texts: list[str]) -> list[list[float]]: ...


class KnowledgeBase(Protocol):
    """Índice de conocimiento. Qdrant en modo local o Azure AI Search, según KNOWLEDGE_BASE."""

    def publish(self, chunks: list[Chunk]) -> None:
        """Reemplaza todos los chunks de cada fuente publicada."""
        ...

    def count(self) -> int: ...

    def search(self, text: str, vector: list[float], top_k: int) -> list[SearchHit]:
        """Los top_k chunks vigentes más relevantes para la pregunta, del más al menos relevante."""
        ...


class Judge(Protocol):
    """Califica una respuesta contra los fragmentos que vio el modelo. S5: G-Eval o Microsoft-Decision-1, según JUDGE."""

    def evaluate(self, question: str, fragments: list[SearchHit], answer: str, cited: list[Citation]) -> Verdict: ...
