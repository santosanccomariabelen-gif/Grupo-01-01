import pytest
from openai.lib._pydantic import to_strict_json_schema
from pydantic import ValidationError

from agent.domain.models import AgentReply, Intent, Usage


def test_agent_reply_schema_is_strict():
    schema = to_strict_json_schema(AgentReply)
    assert schema["additionalProperties"] is False
    assert set(schema["required"]) == {"intent", "answer", "sources"}
    assert "description" in schema["properties"]["sources"]


@pytest.mark.parametrize(
    "data",
    [
        {"intent": "greeting", "answer": "   ", "sources": []},
        {"intent": "greeting", "answer": "Hola", "sources": [], "extra": 1},
        {"intent": "no_existe", "answer": "Hola", "sources": []},
        {"intent": "greeting", "answer": "Hola"},
    ],
)
def test_agent_reply_rejects_invalid_output(data):
    with pytest.raises(ValidationError):
        AgentReply.model_validate(data)


def test_agent_reply_strips_answer():
    assert AgentReply(intent=Intent.GREETING, answer="  Hola  ", sources=[]).answer == "Hola"


def test_usage_adds_up():
    total = Usage(models=["gpt-5-nano"], llm_calls=1, latency_ms=100, prompt_tokens=50, completion_tokens=5) + Usage(
        models=["gpt-5-mini"], llm_calls=1, latency_ms=900, prompt_tokens=800, completion_tokens=120
    )
    assert total == Usage(
        models=["gpt-5-nano", "gpt-5-mini"], llm_calls=2, latency_ms=1000, prompt_tokens=850, completion_tokens=125
    )
