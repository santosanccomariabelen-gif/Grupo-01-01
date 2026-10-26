import pytest

from agent.domain.errors import AgentError
from agent.domain.knowledge import Chunk, Citation, SearchHit
from agent.infrastructure.evaluation.decision_judge import decision_request, verdict_from

HIT = SearchHit(chunk=Chunk(id="c1", content="Plazos: 60 días.", doc_type="faq", section="FAQ", source="faq.md"), score=1.0)


def test_the_request_asks_three_questions_about_the_same_state():
    body = decision_request("microsoft-decision-1", "¿Plazo?", [HIT], "60 días.", [Citation(source="faq.md", section="FAQ", chunk_id="c1")])

    assert body["model"] == "microsoft-decision-1"
    assert body["state"]["fragments"] == [{"number": 1, "source": "faq.md", "text": "Plazos: 60 días."}]
    assert body["state"]["cited_sources"] == ["faq.md"]
    assert {name: question["type"] for name, question in body["questions"].items()} == {
        "groundedness": "score", "relevance": "score", "citation_correct": "noul",
    }
    assert len(body["questions"]["groundedness"]["criteria"]) == 5


def test_scores_go_from_levels_0_to_4_to_the_scale_1_to_5():
    verdict = verdict_from({"answers": {"groundedness": {"score": 3.5}, "relevance": {"value": 4}, "citation_correct": {"probability": 0.9}}})

    assert (verdict.groundedness, verdict.relevance, verdict.citation_correct) == (4.5, 5.0, 0.9)
    assert verdict.judge == "microsoft-decision-1"


def test_an_unexpected_answer_is_an_agent_error():
    with pytest.raises(AgentError):
        verdict_from({"answers": {"groundedness": {"choice": "x"}}})
