from fakes import FakeEmbedder

from agent.application.ingest_corpus import IngestCorpus
from agent.domain.knowledge import SourceDocument


def test_build_embeds_every_chunk_in_batches():
    sections = "\n\n".join(f"## Sección {number}\n\nTexto {number}." for number in range(5))
    documents = [SourceDocument(source="faq.md", doc_type="faq", markdown=f"# FAQ\n\n{sections}")]
    embedder = FakeEmbedder()

    chunks = IngestCorpus(embedder, chunk_max_chars=500, batch_size=2).build(documents)

    assert len(chunks) == 5
    assert embedder.calls == [2, 2, 1]
    assert all(len(chunk.content_vector) == FakeEmbedder.DIM for chunk in chunks)


def test_build_masks_personal_data_before_indexing():
    documents = [SourceDocument(source="cases.pdf", doc_type="cases", markdown="# Casos\n\nDNI 70451238, tarjeta 4111 1111 1111 1111.")]

    [chunk] = IngestCorpus(FakeEmbedder(), chunk_max_chars=500, batch_size=2).build(documents)

    assert "70451238" not in chunk.content and "4111" not in chunk.content
    assert "[DNI]" in chunk.content and "[TARJETA]" in chunk.content
