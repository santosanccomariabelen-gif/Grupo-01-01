from fakes import FakeChatModel, FakeEmbedder, FakeJudge, FakeKnowledgeBase

from agent.application.chat_service import ChatService
from agent.application.evaluation import EvaluateAgent, facts_found, summarize
from agent.domain.evaluation import GoldenCase
from agent.domain.knowledge import Chunk
from agent.infrastructure.persistence.in_memory_store import InMemoryConversationStore

REGULATION = Chunk(id="c1", content="Plazos\n\n60 días.", doc_type="regulation", section="Plazos", source="regulation.pdf")
OLD_POLICY = Chunk(id="c2", content="Política 2022", doc_type="policy", section="Canales", source="policy-2022.md")


def make_evaluation(chunks: list[Chunk], sources: list[int]) -> tuple[EvaluateAgent, FakeKnowledgeBase, FakeJudge]:
    knowledge_base, judge = FakeKnowledgeBase(chunks), FakeJudge()
    service = ChatService(
        model=FakeChatModel(sources=sources), rewriter=FakeChatModel(), embedder=FakeEmbedder(), knowledge_base=knowledge_base,
        store=InMemoryConversationStore(), system_prompt="SYS", max_turns=10, top_k=5,
    )
    return EvaluateAgent(service, judge), knowledge_base, judge


def case(**fields) -> GoldenCase:
    defaults = {"id": "fraud-01", "type": "answerable", "question": "¿Cuál es el plazo de un reclamo?",
                "expected_intent": "product_question"}
    return GoldenCase(**{**defaults, **fields})


def test_facts_are_found_without_accents_or_case():
    assert facts_found("El plazo es de 60 DIAS calendario.", ["60 días calendario"])
    assert not facts_found("El plazo es de 30 días.", ["60 días"])


def test_answerable_case_checks_recall_sources_and_facts():
    evaluation, _, judge = make_evaluation([REGULATION], sources=[1])

    result = evaluation.run_case(case(expected_sources=["regulation.pdf"], key_facts=["intención detectada"]))

    assert (result.recall, result.intent_ok, result.sources_ok, result.facts_ok) == (True, True, True, True)
    assert result.verdict.judge == "fake"
    assert judge.questions == ["¿Cuál es el plazo de un reclamo?"]


def test_citing_a_forbidden_source_fails_the_sources_check():
    evaluation, _, _ = make_evaluation([REGULATION, OLD_POLICY], sources=[1, 2])

    result = evaluation.run_case(case(expected_sources=["regulation.pdf"], forbidden_sources=["policy-2022.md"]))

    assert result.forbidden_cited
    assert not result.sources_ok


def test_history_runs_before_the_question():
    evaluation, knowledge_base, _ = make_evaluation([REGULATION], sources=[1])

    evaluation.run_case(case(type="follow_up", history=["¿Qué es un reclamo?"]))

    assert knowledge_base.queries == ["¿Qué es un reclamo?", "[reescrita] ¿Cuál es el plazo de un reclamo?"]


def test_out_of_scope_cases_are_not_judged():
    evaluation, _, judge = make_evaluation([REGULATION], sources=[])

    result = evaluation.run_case(GoldenCase(id="fraud-27", type="out_of_scope", question="¿A cuánto está el dólar?",
                                            expected_intent="out_of_scope"))

    assert result.intent_ok and result.sources_ok
    assert result.verdict is None and judge.questions == []


def test_summary_averages_only_the_cases_where_each_check_applies():
    evaluation, _, _ = make_evaluation([REGULATION], sources=[1])
    results = [
        evaluation.run_case(case(expected_sources=["regulation.pdf"], key_facts=["no aparece"])),
        evaluation.run_case(GoldenCase(id="fraud-27", type="out_of_scope", question="¿Y el dólar?", expected_intent="out_of_scope")),
    ]

    summary = summarize(results)

    assert summary.cases == 2
    assert summary.recall_at_k == 1.0  # solo el primer caso espera fuentes
    assert summary.facts_ok == 0.0
    assert summary.groundedness == 4
