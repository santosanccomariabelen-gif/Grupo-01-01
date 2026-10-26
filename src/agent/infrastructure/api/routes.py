import json
import logging
from collections.abc import Iterator
from uuid import UUID, uuid4

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse, StreamingResponse

from agent.application.chat_service import ChatService
from agent.domain.errors import AgentError, ErrorKind
from agent.domain.models import AgentTurn, AnswerDelta, IntentDetected, TurnEvent
from agent.infrastructure.api.schemas import ChatRequest, ChatResponse, ErrorResponse

log = logging.getLogger(__name__)

ERROR_STATUS = {
    ErrorKind.TIMEOUT: 504,
    ErrorKind.RATE_LIMIT: 429,
    ErrorKind.INVALID_OUTPUT: 502,
    ErrorKind.UPSTREAM: 502,
}
ERROR_RESPONSES = {status: {"model": ErrorResponse} for status in set(ERROR_STATUS.values())}


async def agent_error_handler(request: Request, error: AgentError) -> JSONResponse:
    log.warning("%s %s falló: %s", request.method, request.url.path, error, exc_info=error.__cause__)
    body = ErrorResponse(error=error.kind, detail=error.detail)
    return JSONResponse(status_code=ERROR_STATUS[error.kind], content=body.model_dump(mode="json"))


def build_router(chat_service: ChatService) -> APIRouter:
    router = APIRouter()

    @router.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    @router.post("/chat", responses=ERROR_RESPONSES)
    def chat(chat_request: ChatRequest) -> ChatResponse:
        session_id = chat_request.session_id or uuid4()
        return _chat_response(session_id, chat_service.handle(str(session_id), chat_request.message))

    @router.post("/chat/stream", responses=ERROR_RESPONSES, response_class=StreamingResponse)
    def chat_stream(chat_request: ChatRequest) -> StreamingResponse:
        """La misma conversación que /chat, en Server-Sent Events: start, intent, delta…, y al final end o error."""
        session_id = chat_request.session_id or uuid4()
        # reescribir y buscar ocurren en esta línea: si fallan, la API responde con su código HTTP como en /chat
        events = chat_service.handle_stream(str(session_id), chat_request.message)
        return StreamingResponse(_server_sent_events(session_id, events), media_type="text/event-stream")

    return router


def _chat_response(session_id: UUID, turn: AgentTurn) -> ChatResponse:
    return ChatResponse(
        session_id=session_id,
        intent=turn.reply.intent,
        answer=turn.reply.answer,
        usage=turn.usage,
        citations=turn.citations,
    )


def _server_sent_events(session_id: UUID, events: Iterator[TurnEvent]) -> Iterator[str]:
    yield _event("start", {"session_id": str(session_id)})
    try:
        for event in events:
            match event:
                case IntentDetected(intent=intent):
                    yield _event("intent", {"intent": intent})
                case AnswerDelta(text=text):
                    yield _event("delta", {"text": text})
                case AgentTurn():
                    yield _event("end", _chat_response(session_id, event).model_dump(mode="json"))
    except AgentError as error:
        # el 200 ya se envió: la falla viaja como un evento más, y el turno no quedó guardado
        log.warning("POST /chat/stream se cortó: %s", error, exc_info=error.__cause__)
        yield _event("error", ErrorResponse(error=error.kind, detail=error.detail).model_dump(mode="json"))


def _event(name: str, data: dict) -> str:
    # formato Server-Sent Events: una línea "event:", una "data:" con JSON y una línea en blanco que lo cierra
    return f"event: {name}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"
