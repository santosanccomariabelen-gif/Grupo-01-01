from enum import StrEnum
from typing import Any

Message = dict[str, Any]  # formato OpenAI: {"role": "system" | "user" | "assistant", "content": ...}


class Intent(StrEnum):
    PRODUCT_QUESTION = "product_question"  # T2: RAG
    DATA_QUERY = "data_query"  # T3: tool MCP
    SENSITIVE_ACTION = "sensitive_action"  # T3: HITL
    GREETING = "greeting"
    OUT_OF_SCOPE = "out_of_scope"


# TODO S1: AgentReply (pydantic.BaseModel), contrato del structured output.
#   - intent: Intent y answer: str, con Field(description=...): el JSON schema se envía al modelo.
#   - extra="forbid" y answer no vacío. Ojo: el modo strict no admite todo JSON Schema.
# TODO S2: Usage (modelos, llamadas, latencia, tokens; sumable), ModelResult (reply + usage)
#          y AgentTurn (resultado de un turno: reply + usage).
