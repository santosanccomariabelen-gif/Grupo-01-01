from collections.abc import Iterator
from contextlib import contextmanager
from datetime import date
from typing import Any

from azure.core.credentials import TokenCredential
from azure.core.exceptions import AzureError, ResourceNotFoundError
from azure.search.documents import SearchClient
from azure.search.documents.indexes import SearchIndexClient
from azure.search.documents.indexes.models import (
    HnswAlgorithmConfiguration,
    SearchableField,
    SearchField,
    SearchFieldDataType,
    SearchIndex,
    SemanticConfiguration,
    SemanticField,
    SemanticPrioritizedFields,
    SemanticSearch,
    SimpleField,
    VectorSearch,
    VectorSearchProfile,
)
from azure.search.documents.models import VectorizedQuery

from agent.domain.errors import AgentError, ErrorKind
from agent.domain.knowledge import Chunk, SearchHit

VECTOR_NEIGHBORS = 20  # cuántos chunks por significado trae AI Search antes de fusionarlos con la búsqueda por palabras
DATE_FIELDS = ("valid_from", "valid_until")
FIELDS_WITHOUT_VECTOR = [name for name in Chunk.model_fields if name != "content_vector"]


class AzureSearchKnowledgeBase:
    """Implementa KnowledgeBase con Azure AI Search: híbrida (texto + vector) y reranking semántico en el servicio."""

    def __init__(self, endpoint: str, index: str, credential: TokenCredential) -> None:
        self.endpoint = endpoint
        self.index = index
        self.indexes = SearchIndexClient(endpoint, credential)
        self.client = SearchClient(endpoint, index, credential)

    def __str__(self) -> str:
        return f"{self.endpoint} (índice {self.index})"

    def publish(self, chunks: list[Chunk]) -> None:
        if not chunks:
            return
        with _search_errors():
            if not self._exists():
                self.indexes.create_index(_index_definition(self.index, len(chunks[0].content_vector)))
            sources = ",".join(sorted({chunk.source for chunk in chunks}))
            old_documents = self.client.search(search_text="*", filter=f"search.in(source, '{sources}', ',')", select=["id"])
            if old_ids := [{"id": document["id"]} for document in old_documents]:
                self.client.delete_documents(old_ids)
            # ponytail: una sola carga; con más de 1000 chunks por publicación, usar SearchIndexingBufferedSender
            self.client.upload_documents([to_document(chunk) for chunk in chunks])

    def count(self) -> int:
        with _search_errors():
            return self.client.get_document_count() if self._exists() else 0

    def search(self, text: str, vector: list[float], top_k: int) -> list[SearchHit]:
        with _search_errors():
            results = self.client.search(
                search_text=text,
                vector_queries=[VectorizedQuery(vector=vector, k_nearest_neighbors=VECTOR_NEIGHBORS, fields="content_vector")],
                filter=still_valid_filter(date.today()),
                query_type="semantic",
                semantic_configuration_name="default",
                select=FIELDS_WITHOUT_VECTOR,
                top=top_k,
            )
            return [
                SearchHit(chunk=from_document(document), score=document.get("@search.reranker_score") or document["@search.score"])
                for document in results
            ]

    def _exists(self) -> bool:
        try:
            self.client.get_document_count()
            return True
        except ResourceNotFoundError:
            return False


def still_valid_filter(today: date) -> str:
    """Filtro OData: deja fuera los chunks vencidos antes de buscar."""
    return f"valid_until eq null or valid_until ge {today.isoformat()}T00:00:00Z"


def to_document(chunk: Chunk) -> dict[str, Any]:
    document = chunk.model_dump(mode="json")
    for name in DATE_FIELDS:  # el índice guarda fechas como Edm.DateTimeOffset
        document[name] = f"{document[name]}T00:00:00Z" if document[name] else None
    return document


def from_document(document: dict[str, Any]) -> Chunk:
    values = {name: document.get(name) for name in FIELDS_WITHOUT_VECTOR}
    for name in DATE_FIELDS:
        values[name] = values[name][:10] if values[name] else None
    return Chunk.model_validate(values)


def _index_definition(name: str, vector_size: int) -> SearchIndex:
    text_type, date_type = SearchFieldDataType.String, SearchFieldDataType.DateTimeOffset
    return SearchIndex(
        name=name,
        fields=[
            SimpleField(name="id", type=text_type, key=True),
            SearchableField(name="content", analyzer_name="es.microsoft"),
            SearchField(
                name="content_vector",
                type=SearchFieldDataType.Collection(SearchFieldDataType.Single),
                searchable=True,
                vector_search_dimensions=vector_size,
                vector_search_profile_name="hnsw",
            ),
            SimpleField(name="doc_type", type=text_type, filterable=True),
            SimpleField(name="product", type=text_type, filterable=True),
            SearchableField(name="section", analyzer_name="es.microsoft"),
            SimpleField(name="valid_from", type=date_type, filterable=True),
            SimpleField(name="valid_until", type=date_type, filterable=True),
            SimpleField(name="source", type=text_type, filterable=True),
        ],
        vector_search=VectorSearch(
            algorithms=[HnswAlgorithmConfiguration(name="hnsw-config")],
            profiles=[VectorSearchProfile(name="hnsw", algorithm_configuration_name="hnsw-config")],
        ),
        semantic_search=SemanticSearch(
            configurations=[
                SemanticConfiguration(
                    name="default",
                    prioritized_fields=SemanticPrioritizedFields(
                        title_field=SemanticField(field_name="section"),
                        content_fields=[SemanticField(field_name="content")],
                    ),
                )
            ]
        ),
    )


@contextmanager
def _search_errors() -> Iterator[None]:
    try:
        yield
    except AzureError as error:
        raise AgentError(ErrorKind.UPSTREAM, f"error de Azure AI Search: {type(error).__name__}") from error
