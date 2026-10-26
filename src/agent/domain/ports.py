"""Puertos: lo que el dominio necesita del mundo exterior. Las implementaciones viven en infrastructure."""

from typing import Protocol

from agent.domain.models import Message


class ChatModel(Protocol):
    """Modelo de lenguaje. T1: Foundry directo; T3: Microsoft Agent Framework."""

    # TODO S1: tipar el retorno: AgentReply
    # TODO S2: ModelResult (respuesta tipada + consumo de la llamada)
    def complete(self, messages: list[Message]): ...


class ConversationStore(Protocol):
    """Historial por sesión. T1: memoria; T4: Cosmos DB."""

    def get(self, session_id: str) -> list[Message]: ...
    def append(self, session_id: str, message: Message) -> None: ...
