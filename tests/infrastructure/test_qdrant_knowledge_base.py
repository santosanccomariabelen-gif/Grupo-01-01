from datetime import date

from agent.domain.knowledge import Chunk
from agent.infrastructure.search.qdrant_knowledge_base import QdrantKnowledgeBase


def chunk(chunk_id: str, source: str, vector: list[float], content: str = "texto", valid_until: date | None = None) -> Chunk:
    return Chunk(id=chunk_id, content=content, content_vector=vector, doc_type="faq", section="FAQ", source=source,
                 valid_until=valid_until)


A1, A2, A3, B1 = (f"00000000-0000-0000-0000-00000000000{number}" for number in range(1, 5))


def test_publish_replaces_the_chunks_of_each_source(tmp_path):
    index = QdrantKnowledgeBase(tmp_path / "fraud", collection="fraud")
    index.publish([chunk(A1, "a.md", [1, 0]), chunk(A2, "a.md", [0, 1]), chunk(B1, "b.md", [1, 1])])

    index.publish([chunk(A3, "a.md", [1, 0])])

    assert QdrantKnowledgeBase(tmp_path / "fraud", collection="fraud").count() == 2


def test_count_is_zero_before_publishing(tmp_path):
    assert QdrantKnowledgeBase(tmp_path / "fraud", collection="fraud").count() == 0


def test_search_combines_meaning_and_exact_words(tmp_path):
    index = QdrantKnowledgeBase(tmp_path / "fraud", collection="fraud")
    index.publish([chunk(A1, "a.md", [1, 0], "plazo para reclamos"), chunk(A2, "b.md", [0, 1], "contracargo de compras")])

    hits = index.search("contracargo", [1, 0], top_k=2)

    # por significado gana A1, pero solo A2 tiene la palabra: la fusión lo sube al primer lugar
    assert [hit.chunk.id for hit in hits] == [A2, A1]
    assert hits[0].chunk.source == "b.md"


def test_search_skips_expired_chunks(tmp_path):
    index = QdrantKnowledgeBase(tmp_path / "fraud", collection="fraud")
    index.publish([chunk(A1, "2022.md", [1, 0], valid_until=date(2024, 12, 31)), chunk(A2, "current.md", [1, 0])])

    assert [hit.chunk.id for hit in index.search("texto", [1, 0], top_k=5)] == [A2]
