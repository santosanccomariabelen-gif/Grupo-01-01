import json
import urllib.error
import urllib.request
from typing import Any

from agent.domain.errors import AgentError, ErrorKind
from agent.domain.evaluation import Verdict
from agent.domain.knowledge import Citation, SearchHit
from agent.infrastructure.llm.credentials import Credential

GROUNDEDNESS_LEVELS = [
    "Inventada: no está en los fragmentos o los contradice",
    "Mayormente inventada",
    "La mitad está en los fragmentos",
    "Casi todo está en los fragmentos",
    "Todo está en los fragmentos",
]
RELEVANCE_LEVELS = [
    "No contesta la pregunta",
    "Contesta muy poco",
    "Contesta una parte",
    "Contesta casi todo",
    "Contesta exactamente lo que se preguntó",
]


class DecisionJudge:
    """JUDGE=azure_evaluation: Microsoft-Decision-1, un modelo de decisión de Foundry. No escribe: devuelve números."""

    def __init__(self, endpoint: str, credential: Credential, deployment: str, timeout_s: float) -> None:
        self.url = f"{endpoint.rstrip('/')}/providers/microsoft/v1/systemone"
        self.credential = credential
        self.deployment = deployment
        self.timeout_s = timeout_s

    def evaluate(self, question: str, fragments: list[SearchHit], answer: str, cited: list[Citation]) -> Verdict:
        body = decision_request(self.deployment, question, fragments, answer, cited)
        request = urllib.request.Request(
            self.url,
            data=json.dumps(body, ensure_ascii=False).encode("utf-8"),
            headers={"Content-Type": "application/json", **_authorization(self.credential)},
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=self.timeout_s) as response:
                return verdict_from(json.loads(response.read().decode("utf-8")))
        except urllib.error.HTTPError as error:
            raise AgentError(ErrorKind.UPSTREAM, f"Microsoft-Decision-1 respondió {error.code}") from error
        except TimeoutError as error:
            raise AgentError(ErrorKind.TIMEOUT, "Microsoft-Decision-1 no respondió a tiempo") from error
        except urllib.error.URLError as error:
            raise AgentError(ErrorKind.UPSTREAM, f"no se pudo llamar a Microsoft-Decision-1: {error.reason}") from error


def _authorization(credential: Credential) -> dict[str, str]:
    # Entra ID: un token renovable (az login o Managed Identity). Una key fija solo la usa el mock
    return {"Authorization": f"Bearer {credential()}"} if callable(credential) else {"api-key": credential}


def decision_request(
    deployment: str, question: str, fragments: list[SearchHit], answer: str, cited: list[Citation]
) -> dict[str, Any]:
    """Una sola llamada con las tres preguntas sobre el mismo estado: la pregunta, los fragmentos y la respuesta."""
    return {
        "model": deployment,
        "state": {
            "question": question,
            "fragments": [
                {"number": number, "source": hit.chunk.source, "text": hit.chunk.content}
                for number, hit in enumerate(fragments, start=1)
            ],
            "answer": answer,
            "cited_sources": [citation.source for citation in cited],
        },
        "questions": {
            "groundedness": {
                "type": "score",
                "instructions": "¿Todo lo que afirma la respuesta está en los fragmentos?",
                "criteria": GROUNDEDNESS_LEVELS,
            },
            "relevance": {
                "type": "score",
                "instructions": "¿La respuesta contesta lo que preguntó el cliente?",
                "criteria": RELEVANCE_LEVELS,
            },
            "citation_correct": {
                "type": "noul",
                "instructions": "¿Las fuentes citadas contienen lo que afirma la respuesta?",
                "criteria": {
                    "true": "Las fuentes citadas respaldan la respuesta",
                    "false": "Las fuentes citadas no la respaldan, o no se citó ninguna",
                },
            },
        },
    }


def verdict_from(payload: dict[str, Any]) -> Verdict:
    answers = payload.get("answers", {})
    return Verdict(
        # el puntaje es el promedio de los niveles pesado por su probabilidad, de 0 a 4: se lleva a la escala de 1 a 5
        groundedness=_number(answers, "groundedness", "score", "value") + 1,
        relevance=_number(answers, "relevance", "score", "value") + 1,
        citation_correct=_number(answers, "citation_correct", "probability", "value"),
        judge="microsoft-decision-1",
    )


def _number(answers: dict[str, Any], question: str, *field_names: str) -> float:
    # ponytail: la documentación pública solo muestra la respuesta de "choice"; se aceptan los dos nombres posibles del
    # campo hasta confirmar el formato con la primera llamada real
    answer = answers.get(question, {})
    for name in field_names:
        if isinstance(answer.get(name), int | float):
            return float(answer[name])
    raise AgentError(ErrorKind.INVALID_OUTPUT, f"Microsoft-Decision-1 no devolvió un número para {question}: {answer}")
