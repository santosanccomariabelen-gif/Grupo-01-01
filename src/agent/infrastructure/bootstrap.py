"""Composition root: conecta cada puerto del dominio con su implementación.

Arranque: uv run uvicorn agent.infrastructure.bootstrap:create_app --factory --reload
"""

import logging

from fastapi import FastAPI

from agent.infrastructure.api.routes import build_router
from agent.infrastructure.config.settings import Settings

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or Settings()
    # TODO S1: crear FoundryChatModel (con build_credential), InMemoryConversationStore y el prompt
    #          del dominio (load_prompt); armar ChatService y pasarlo a build_router.
    app = FastAPI(title=f"agent-{settings.domain}")
    app.include_router(build_router())
    return app
