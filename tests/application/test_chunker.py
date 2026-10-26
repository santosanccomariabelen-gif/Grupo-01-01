from agent.application.chunker import chunk_document
from agent.domain.knowledge import SourceDocument


def document(markdown: str, source: str = "doc.md") -> SourceDocument:
    return SourceDocument(source=source, doc_type="regulation", markdown=markdown)


REGULATION = """# Reglamento

## 4. Plazos de respuesta

El banco responde en 15 días hábiles.

### 4.1 Ampliación del plazo

Puede ampliarse una vez por 15 días hábiles.
"""


def test_chunks_keep_their_heading_path():
    chunks = chunk_document(document(REGULATION), max_chars=500)

    assert [chunk.section for chunk in chunks] == [
        "Reglamento > 4. Plazos de respuesta",
        "Reglamento > 4. Plazos de respuesta > 4.1 Ampliación del plazo",
    ]
    assert chunks[1].content.startswith("Reglamento > 4. Plazos de respuesta > 4.1 Ampliación del plazo\n\n")
    assert all(chunk.source == "doc.md" and chunk.doc_type == "regulation" for chunk in chunks)


def test_long_section_is_split_under_max_chars():
    body = "\n\n".join(f"Párrafo {number}. " + "texto " * 30 for number in range(10))
    chunks = chunk_document(document(f"# Guía\n\n{body}"), max_chars=400)

    assert len(chunks) > 1
    assert all(len(chunk.content) <= 400 + len("Guía\n\n") for chunk in chunks)


def test_table_chunks_repeat_the_header():
    rows = "\n".join(f"| tipo_{number} | {number} |" for number in range(40))
    chunks = chunk_document(document(f"# plazos\n\n| tipo | dias |\n| --- | --- |\n{rows}"), max_chars=200)

    assert len(chunks) > 1
    assert all("| tipo | dias |\n| --- | --- |" in chunk.content for chunk in chunks)


def test_ids_are_stable_and_unique():
    first = chunk_document(document(REGULATION), max_chars=500)
    again = chunk_document(document(REGULATION), max_chars=500)
    other = chunk_document(document(REGULATION, source="other.md"), max_chars=500)

    assert [chunk.id for chunk in first] == [chunk.id for chunk in again]
    assert len({chunk.id for chunk in first + other}) == len(first) + len(other)


def test_headings_without_text_produce_no_chunks():
    assert chunk_document(document("# Título\n\n## Vacía\n\n## También vacía\n"), max_chars=500) == []
