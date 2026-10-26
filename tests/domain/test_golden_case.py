import pytest
from pydantic import ValidationError

from agent.domain.evaluation import GoldenCase


def test_golden_case_rejects_unknown_fields_and_types():
    with pytest.raises(ValidationError):
        GoldenCase(id="x", type="answerable", question="?", expected_intent="greeting", extra=1)
    with pytest.raises(ValidationError):
        GoldenCase(id="x", type="no_existe", question="?", expected_intent="greeting")
