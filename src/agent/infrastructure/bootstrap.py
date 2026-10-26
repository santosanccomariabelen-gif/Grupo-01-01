"""Composition root: conecta cada puerto del dominio con su implementación.

Arranque: uv run uvicorn agent.infrastructure.bootstrap:create_app --factory --reload
"""

import logging

from azure.identity import DefaultAzureCredential
from fastapi import FastAPI

from agent.application.chat_service import ChatService
from agent.domain.errors import AgentError
from agent.domain.ports import Embedder, Judge, KnowledgeBase
from agent.infrastructure.api.routes import agent_error_handler, build_router
from agent.infrastructure.config.settings import FoundrySettings, JudgeKind, KnowledgeBaseKind, Settings
from agent.infrastructure.evaluation.decision_judge import DecisionJudge
from agent.infrastructure.evaluation.geval_judge import GEvalJudge
from agent.infrastructure.llm.credentials import build_credential
from agent.infrastructure.llm.foundry_chat_model import FoundryChatModel
from agent.infrastructure.llm.foundry_embedder import FoundryEmbedder
from agent.infrastructure.persistence.in_memory_store import InMemoryConversationStore
from agent.infrastructure.prompts.loader import load_prompt
from agent.infrastructure.search.azure_search_knowledge_base import AzureSearchKnowledgeBase
from agent.infrastructure.search.qdrant_knowledge_base import QdrantKnowledgeBase

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
log = logging.getLogger(__name__)


def _require_endpoint(foundry: FoundrySettings) -> None:
    if not foundry.endpoint:
        raise RuntimeError("Falta FOUNDRY_ENDPOINT. Copia .env.example a .env y complétalo.")
    log.info("Foundry auth provider: %s", foundry.auth_provider)


def build_chat_model(foundry: FoundrySettings, deployment: str | None = None) -> FoundryChatModel:
    _require_endpoint(foundry)
    return FoundryChatModel(
        endpoint=foundry.endpoint,
        credential=build_credential(foundry.auth_provider, foundry.api_key),
        deployment=deployment or foundry.deployment,
        timeout_s=foundry.timeout_s,
        max_retries=foundry.max_retries,
    )


def build_embedder(foundry: FoundrySettings) -> Embedder:
    _require_endpoint(foundry)
    return FoundryEmbedder(
        endpoint=foundry.endpoint,
        credential=build_credential(foundry.auth_provider, foundry.api_key),
        deployment=foundry.embedding_deployment,
        timeout_s=foundry.timeout_s,
        max_retries=foundry.max_retries,
    )


def build_knowledge_base(settings: Settings, kind: KnowledgeBaseKind | None = None) -> KnowledgeBase:
    match kind or settings.knowledge_base:
        case KnowledgeBaseKind.LOCAL:
            return QdrantKnowledgeBase(settings.ingest.data_dir / "index" / settings.domain, collection=settings.domain)
        case KnowledgeBaseKind.AZURE_SEARCH:
            search = settings.search
            if not (search.endpoint and search.index):
                raise RuntimeError("KNOWLEDGE_BASE=azure_search requiere SEARCH_ENDPOINT y SEARCH_INDEX en .env.")
            # siempre Entra ID: az login en local, Managed Identity desplegado
            return AzureSearchKnowledgeBase(search.endpoint, search.index, DefaultAzureCredential())


def build_ready_knowledge_base(settings: Settings) -> KnowledgeBase:
    """La base de KNOWLEDGE_BASE, ya publicada: con 0 chunks el agente no arranca, en vez de responder sin fuentes."""
    knowledge_base = build_knowledge_base(settings)
    chunks = knowledge_base.count()
    if not chunks:
        raise RuntimeError(
            f"La base de conocimiento ({settings.knowledge_base}: {knowledge_base}) está vacía. "
            "Publica los chunks antes de levantar el agente: uv run ingest publish"
        )
    log.info("Knowledge base: %s · %s · %d chunks", settings.knowledge_base, knowledge_base, chunks)
    return knowledge_base


def build_judge(settings: Settings, kind: JudgeKind | None = None) -> Judge:
    foundry = settings.foundry
    match kind or settings.judge:
        case JudgeKind.LOCAL:
            return GEvalJudge(build_chat_model(foundry, foundry.judge_deployment))
        case JudgeKind.AZURE_EVALUATION:
            _require_endpoint(foundry)
            credential = build_credential(foundry.auth_provider, foundry.api_key)
            return DecisionJudge(foundry.endpoint, credential, foundry.decision_deployment, foundry.timeout_s)


def build_chat_service(
    settings: Settings,
    chat_model: FoundryChatModel | None = None,  # en los tests, un fake con complete y rewrite
    embedder: Embedder | None = None,
    knowledge_base: KnowledgeBase | None = None,
) -> ChatService:
    """El agente completo. Lo usan la API y la evaluación (uv run eval): se evalúa exactamente lo que se despliega."""
    model = chat_model or build_chat_model(settings.foundry)
    return ChatService(
        model=model,
        rewriter=model,  # el mismo modelo de chat reescribe las preguntas de seguimiento
        embedder=embedder or build_embedder(settings.foundry),
        knowledge_base=knowledge_base or build_ready_knowledge_base(settings),
        store=InMemoryConversationStore(),
        system_prompt=load_prompt(settings.domain),
        max_turns=settings.max_turns,
        top_k=settings.search.top_k,
    )


def create_app(
    chat_model: FoundryChatModel | None = None,
    settings: Settings | None = None,
    embedder: Embedder | None = None,
    knowledge_base: KnowledgeBase | None = None,
) -> FastAPI:
    settings = settings or Settings()
    chat_service = build_chat_service(settings, chat_model, embedder, knowledge_base)
    app = FastAPI(title=f"agent-{settings.domain}")
    app.include_router(build_router(chat_service))
    app.add_exception_handler(AgentError, agent_error_handler)
    return app
