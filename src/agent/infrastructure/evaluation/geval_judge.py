from typing import Annotated, Protocol

from pydantic import AfterValidator, BaseModel, ConfigDict, Field

from agent.domain.evaluation import Verdict
from agent.domain.knowledge import Citation, SearchHit
from agent.domain.models import Message, Usage

GEVAL_PROMPT = """Eres un evaluador estricto de un asistente bancario. Calificas una respuesta comparándola con los fragmentos
del corpus que el asistente tenía para responder.

Criterios:
- groundedness, de 1 a 5: ¿todo lo que afirma la respuesta está en los fragmentos? 5 = todo; 3 = la mitad; 1 = inventa o contradice.
- relevance, de 1 a 5: ¿la respuesta contesta lo que preguntó el cliente? 5 = exactamente; 1 = no lo contesta.
- citation_correct, de 1 a 5: ¿las fuentes citadas contienen lo que afirma la respuesta? 5 = sí; 1 = no, o no citó nada.

Pasos:
1. Lee la pregunta.
2. Separa la respuesta en afirmaciones.
3. Busca cada afirmación en los fragmentos.
4. Revisa si las fuentes citadas contienen esas afirmaciones.
5. Escribe tu razonamiento en dos o tres frases y después pon los puntajes."""


def _one_to_five(value: int) -> int:
    if not 1 <= value <= 5:
        raise ValueError("el puntaje va de 1 a 5")
    return value


Score = Annotated[int, AfterValidator(_one_to_five)]


class GEvalScores(BaseModel):
    """La respuesta del juez (structured output). El razonamiento va primero: el modelo piensa antes de poner la nota."""

    model_config = ConfigDict(extra="forbid")

    reasoning: str = Field(description="Los pasos de evaluación aplicados, en dos o tres frases.")
    groundedness: Score = Field(description="De 1 a 5: todo lo que afirma la respuesta está en los fragmentos.")
    relevance: Score = Field(description="De 1 a 5: la respuesta contesta lo que preguntó el cliente.")
    citation_correct: Score = Field(description="De 1 a 5: las fuentes citadas contienen lo que afirma la respuesta.")


class StructuredModel(Protocol):
    """Lo único que el juez necesita de un modelo: una respuesta con forma de un modelo Pydantic."""

    def parse[Output: BaseModel](self, messages: list[Message], schema: type[Output]) -> tuple[Output, Usage]: ...


class GEvalJudge:
    """JUDGE=local: G-Eval. Un modelo generativo sigue criterios y pasos, explica su razonamiento y pone la nota."""

    def __init__(self, model: StructuredModel) -> None:
        self.model = model

    def evaluate(self, question: str, fragments: list[SearchHit], answer: str, cited: list[Citation]) -> Verdict:
        scores, _ = self.model.parse(judge_messages(question, fragments, answer, cited), GEvalScores)
        return Verdict(
            groundedness=scores.groundedness,
            relevance=scores.relevance,
            citation_correct=(scores.citation_correct - 1) / 4,  # de 1-5 a 0-1, la misma escala que Microsoft-Decision-1
            reasoning=scores.reasoning,
            judge="g-eval",
        )


def judge_messages(question: str, fragments: list[SearchHit], answer: str, cited: list[Citation]) -> list[Message]:
    blocks = [f"[{number}] {hit.chunk.source}\n{hit.chunk.content}" for number, hit in enumerate(fragments, start=1)]
    material = "\n\n".join([
        f"Pregunta del cliente:\n{question}",
        "Fragmentos:\n\n" + "\n\n".join(blocks),
        f"Respuesta del asistente:\n{answer}",
        "Fuentes citadas: " + (", ".join(citation.source for citation in cited) or "ninguna"),
    ])
    return [{"role": "system", "content": GEVAL_PROMPT}, {"role": "user", "content": material}]
