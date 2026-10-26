from collections import defaultdict

from agent.domain.models import Message


class InMemoryConversationStore:
    """Implementa el puerto ConversationStore en memoria."""

    # ponytail: se pierde al reiniciar y no escala a varias réplicas; Cosmos DB en T4
    def __init__(self) -> None:
        self._sessions: defaultdict[str, list[Message]] = defaultdict(list)

    def get(self, session_id: str) -> list[Message]:
        return list(self._sessions[session_id])

    def append(self, session_id: str, message: Message) -> None:
        self._sessions[session_id].append(message)
