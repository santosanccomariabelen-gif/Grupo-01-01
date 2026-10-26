from pathlib import Path

from pydantic import ValidationError

from agent.domain.evaluation import GoldenCase


def read_golden(path: Path) -> list[GoldenCase]:
    """Lee el golden set: un caso por línea, en JSON. Un caso mal escrito dice en qué línea está."""
    cases = []
    for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        if not line.strip():
            continue
        try:
            cases.append(GoldenCase.model_validate_json(line))
        except ValidationError as error:
            raise ValueError(f"{path.name}, línea {number}: {error}") from error
    return cases
