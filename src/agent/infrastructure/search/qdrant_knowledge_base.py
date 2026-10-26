import threading
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import date
from pathlib import Path

from qdrant_client import QdrantClient, models

from agent.domain.knowledge import Chunk, SearchHit
from agent.infrastructure.search.hybrid import fuse_rankings, keyword_scores

CANDIDATES_PER_SEARCH = 20  # cuántos chunks trae cada búsqueda (por significado y por palabras) antes de fusionar
MAX_CHUNKS_READ = 10_000  # techo de chunks que se leen para la búsqueda por palabras
_one_client_at_a_time = threading.Lock()  # el modo local admite un solo cliente abierto por carpeta


class QdrantKnowledgeBase:
    """Implementa KnowledgeBase con Qdrant en modo local: una base vectorial embebida que vive en una carpeta, sin servidor."""

    # ponytail: el modo local compara contra todos los vectores y BM25 recorre todo el corpus en cada búsqueda;
    # alcanza para miles de chunks por dominio. Con más volumen o varios procesos: Azure AI Search (KNOWLEDGE_BASE)
    def __init__(self, path: Path, collection: str) -> None:
        self.path = path
        self.collection = collection

    def __str__(self) -> str:
        return str(self.path)

    def publish(self, chunks: list[Chunk]) -> None:
        if not chunks:
            return
        with self._client() as client:
            if not client.collection_exists(self.collection):
                vector_size = len(chunks[0].content_vector)
                client.create_collection(self.collection, models.VectorParams(size=vector_size, distance=models.Distance.COSINE))
            sources = sorted({chunk.source for chunk in chunks})
            same_sources = models.Filter(must=[models.FieldCondition(key="source", match=models.MatchAny(any=sources))])
            client.delete(self.collection, points_selector=models.FilterSelector(filter=same_sources))
            client.upsert(self.collection, points=[
                models.PointStruct(
                    id=chunk.id, vector=chunk.content_vector, payload=chunk.model_dump(mode="json", exclude={"content_vector"})
                )
                for chunk in chunks
            ])

    def count(self) -> int:
        with self._client() as client:
            return client.count(self.collection).count if client.collection_exists(self.collection) else 0

    def search(self, text: str, vector: list[float], top_k: int) -> list[SearchHit]:
        # un documento vencido no debe responder: se excluye antes de buscar, no después
        expired = models.FieldCondition(key="valid_until", range=models.DatetimeRange(lt=date.today()))
        still_valid = models.Filter(must_not=[expired])
        with self._client() as client:
            if not client.collection_exists(self.collection):
                return []
            closest_by_meaning = client.query_points(
                self.collection, query=vector, query_filter=still_valid, limit=CANDIDATES_PER_SEARCH
            ).points
            valid_records, _ = client.scroll(self.collection, scroll_filter=still_valid, limit=MAX_CHUNKS_READ)

        chunks_by_id = {str(record.id): Chunk.model_validate(record.payload) for record in valid_records}
        word_scores = keyword_scores(text, [chunk.content for chunk in chunks_by_id.values()])
        ranked_by_words = [
            chunk_id
            for chunk_id, score in sorted(zip(chunks_by_id, word_scores), key=lambda id_and_score: id_and_score[1], reverse=True)
            if score > 0
        ]
        ranked_by_meaning = [str(point.id) for point in closest_by_meaning]
        fused = fuse_rankings([ranked_by_meaning, ranked_by_words[:CANDIDATES_PER_SEARCH]])
        return [SearchHit(chunk=chunks_by_id[chunk_id], score=score) for chunk_id, score in fused[:top_k] if chunk_id in chunks_by_id]

    @contextmanager
    def _client(self) -> Iterator[QdrantClient]:
        # se abre y se cierra en cada operación para no dejar la carpeta bloqueada (por ejemplo, para ingest publish)
        with _one_client_at_a_time:
            client = QdrantClient(path=str(self.path))
            try:
                yield client
            finally:
                client.close()
