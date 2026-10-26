from datetime import date

from agent.domain.knowledge import Chunk
from agent.infrastructure.search.azure_search_knowledge_base import from_document, still_valid_filter, to_document


def test_documents_use_the_date_format_of_the_index():
    chunk = Chunk(id="c1", content="x", content_vector=[0.1], doc_type="faq", section="FAQ", source="a.md",
                  valid_until=date(2024, 12, 31))

    document = to_document(chunk)

    assert document["valid_until"] == "2024-12-31T00:00:00Z"
    assert document["valid_from"] is None
    assert from_document({**document, "@search.score": 1.0}) == chunk.model_copy(update={"content_vector": []})
    assert still_valid_filter(date(2026, 10, 23)) == "valid_until eq null or valid_until ge 2026-10-23T00:00:00Z"
