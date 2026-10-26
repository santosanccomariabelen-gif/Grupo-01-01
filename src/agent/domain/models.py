from enum import StrEnum
from typing import Annotated, Any, Self

from pydantic import AfterValidator, BaseModel, ConfigDict, Field

from agent.domain.knowledge import Citation, SearchHit

Message = dict[str, Any]  # formato OpenAI; T3 suma role "tool" sin cambiar el tipo


class Intent(StrEnum):
    PRODUCT_QUESTION = "product_question"  # T2: RAG
    DATA_QUERY = "data_query"  # T3: tool MCP
    SENSITIVE_ACTION = "sensitive_action"  # T3: HITL
    GREETING = "greeting"
    OUT_OF_SCOPE = "out_of_scope"


def _not_blank(value: str) -> str:
    value = value.strip()
    if not value:
        raise ValueError("no puede estar vacío")
    return value


class AgentReply(BaseModel):
    """Respuesta final del modelo (structured output). Su JSON schema y descriptions se envían al modelo."""

    model_config = ConfigDict(extra="forbid")

    # el modelo escribe los campos en este orden: con streaming, intent llega antes que answer y sources al final
    intent: Intent = Field(description="Intención del último mensaje del cliente.")
    # validación posterior y no en el schema: el modo strict no admite todo JSON Schema (p. ej. minLength)
    answer: Annotated[str, AfterValidator(_not_blank)] = Field(
        description="Respuesta al cliente en español, breve y clara."
    )
    sources: list[int] = Field(
        description="Números de los fragmentos del contexto que usaste para responder, por ejemplo [1, 3]. "
        "Lista vacía si no usaste ninguno."
    )


class SearchQuery(BaseModel):
    """Pregunta reescrita para buscar en el corpus (structured output del rewrite)."""

    model_config = ConfigDict(extra="forbid")

    query: Annotated[str, AfterValidator(_not_blank)] = Field(
        description="La última pregunta del cliente reescrita para que se entienda sola, sin leer la conversación."
    )


class Usage(BaseModel):
    """Consumo de un turno. Es sumable porque desde T2 un turno hace varias llamadas al modelo."""

    models: list[str] = []
    llm_calls: int = 0
    latency_ms: int = 0
    prompt_tokens: int = 0
    completion_tokens: int = 0

    def __add__(self, other: Self) -> Self:
        return type(self)(
            models=list(dict.fromkeys(self.models + other.models)),
            llm_calls=self.llm_calls + other.llm_calls,
            latency_ms=self.latency_ms + other.latency_ms,
            prompt_tokens=self.prompt_tokens + other.prompt_tokens,
            completion_tokens=self.completion_tokens + other.completion_tokens,
        )


class ModelResult(BaseModel):
    """Una llamada al modelo: respuesta tipada + consumo."""

    reply: AgentReply
    usage: Usage


class RewriteResult(BaseModel):
    """Una llamada de rewrite: la pregunta para buscar + consumo."""

    query: str
    usage: Usage


class AgentTurn(BaseModel):
    """Resultado de un turno, con las fuentes que citó. T3 agrega tool_calls y pending_action."""

    reply: AgentReply
    usage: Usage
    citations: list[Citation] = []
    hits: list[SearchHit] = []  # lo que se recuperó: lo usan la evaluación y el juez; no sale en la API


class IntentDetected(BaseModel):
    """Streaming: ya se sabe la intención, antes de que empiece el texto de la respuesta."""

    intent: Intent


class AnswerDelta(BaseModel):
    """Streaming: un pedazo nuevo de la respuesta, mientras el modelo la escribe."""

    text: str


type ModelEvent = IntentDetected | AnswerDelta | ModelResult  # lo que entrega ChatModel.stream; el último es ModelResult
type TurnEvent = IntentDetected | AnswerDelta | AgentTurn  # lo que entrega ChatService.handle_stream; el último es AgentTurn
