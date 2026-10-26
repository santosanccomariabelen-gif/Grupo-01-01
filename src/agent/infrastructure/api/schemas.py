"""Contrato HTTP del agente. Solo crece con campos opcionales: T2 citations, T3 pending_action, T4 trace_id."""

from typing import Annotated
from uuid import UUID

from pydantic import BaseModel, StringConstraints

from agent.domain.errors import ErrorKind
from agent.domain.knowledge import Citation
from agent.domain.models import Intent, Usage

UserMessage = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=2000)]


class ChatRequest(BaseModel):
    session_id: UUID | None = None
    message: UserMessage


class ChatResponse(BaseModel):
    session_id: UUID
    intent: Intent
    answer: str
    usage: Usage
    citations: list[Citation] = []


class ErrorResponse(BaseModel):
    error: ErrorKind
    detail: str
