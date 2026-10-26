from agent.domain.ports import ChatModel, ConversationStore


class ChatService:
    """Caso de uso: resolver un turno de conversación. Solo conoce puertos, nunca infraestructura."""

    def __init__(self, model: ChatModel, store: ConversationStore, system_prompt: str, max_turns: int) -> None:
        self.model = model
        self.store = store
        self.system_prompt = system_prompt
        self.max_turns = max_turns

    def handle(self, session_id: str, message: str):
        # TODO S1: armar [system, ...últimos max_turns del historial, user], llamar a self.model.complete
        #          y devolver el AgentReply.
        # TODO S2: guardar el turno en el historial solo si el modelo respondió y devolver AgentTurn.
        raise NotImplementedError("TODO S1: ChatService.handle")
