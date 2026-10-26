"""Evaluación del RAG: los casos del golden set, la nota del juez y el resultado de cada caso."""

from enum import StrEnum

from pydantic import BaseModel, ConfigDict

from agent.domain.models import Intent, Usage


class CaseType(StrEnum):
    ANSWERABLE = "answerable"  # la respuesta está en el corpus
    FOLLOW_UP = "follow_up"  # pregunta de seguimiento: solo se entiende con el historial
    EXPIRED = "expired"  # tienta a usar un documento vencido
    NOISE = "noise"  # tienta a usar un documento que no tiene nada que ver
    OUT_OF_SCOPE = "out_of_scope"  # fuera del dominio
    PERSONAL_DATA = "personal_data"  # pregunta por casos que tienen DNI y tarjetas


class GoldenCase(BaseModel):
    """Un caso del golden set: la pregunta y lo que se espera del agente."""

    model_config = ConfigDict(extra="forbid")

    id: str
    type: CaseType
    history: list[str] = []  # mensajes anteriores del cliente, en orden
    question: str
    expected_intent: Intent
    expected_sources: list[str] = []  # alguna de estas debe aparecer entre lo recuperado y lo citado
    forbidden_sources: list[str] = []  # documentos vencidos o de ruido: nunca se deben citar
    key_facts: list[str] = []  # textos exactos que la respuesta debe incluir


class Verdict(BaseModel):
    """La nota del juez sobre una respuesta."""

    groundedness: float  # de 1 a 5: todo lo que dice la respuesta está en los fragmentos
    relevance: float  # de 1 a 5: responde lo que se preguntó
    citation_correct: float  # de 0 a 1: las fuentes citadas dicen lo que afirma la respuesta
    reasoning: str = ""  # solo G-Eval explica su nota
    judge: str


class CaseResult(BaseModel):
    """Lo que pasó con un caso: la respuesta y cada control. None quiere decir que el control no aplica al caso."""

    case_id: str
    case_type: CaseType
    answer: str
    intent: Intent
    cited_sources: list[str]
    retrieved_sources: list[str]
    recall: bool | None
    intent_ok: bool
    sources_ok: bool
    facts_ok: bool | None
    personal_data_leak: bool
    forbidden_cited: bool
    verdict: Verdict | None
    usage: Usage


class EvalSummary(BaseModel):
    """El promedio de cada control sobre los casos donde aplica."""

    cases: int
    recall_at_k: float
    intent_accuracy: float
    sources_ok: float
    facts_ok: float
    groundedness: float | None
    relevance: float | None
    citation_correct: float | None
    personal_data_leaks: int
    forbidden_citations: int
    prompt_tokens: int
    completion_tokens: int
