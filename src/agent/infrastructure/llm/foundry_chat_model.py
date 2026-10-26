import logging
import time
from collections.abc import Iterator
from typing import Any

from jiter import from_json
from openai import OpenAI
from openai.types.chat import ParsedChatCompletion
from pydantic import BaseModel

from agent.domain.errors import AgentError, ErrorKind
from agent.domain.models import (
    AgentReply,
    AnswerDelta,
    IntentDetected,
    Message,
    ModelEvent,
    ModelResult,
    RewriteResult,
    SearchQuery,
    Usage,
)
from agent.infrastructure.llm.credentials import Credential
from agent.infrastructure.llm.errors import foundry_errors

log = logging.getLogger(__name__)


class FoundryChatModel:
    """Implementa los puertos ChatModel y QueryRewriter contra Microsoft Foundry (API v1 compatible con OpenAI)."""

    def __init__(
        self,
        endpoint: str,
        credential: Credential,
        deployment: str,
        timeout_s: float,
        max_retries: int,
    ) -> None:
        self.client = OpenAI(
            base_url=f"{endpoint.rstrip('/')}/openai/v1/",
            api_key=credential,
            timeout=timeout_s,
            max_retries=max_retries,
        )
        self.deployment = deployment

    def complete(self, messages: list[Message]) -> ModelResult:
        reply, usage = self.parse(messages, AgentReply)
        return ModelResult(reply=reply, usage=usage)

    def rewrite(self, messages: list[Message]) -> RewriteResult:
        search, usage = self.parse(messages, SearchQuery)
        return RewriteResult(query=search.query, usage=usage)

    def stream(self, messages: list[Message]) -> Iterator[ModelEvent]:
        start = time.perf_counter()
        intent_sent, answer_sent = False, ""
        with foundry_errors(), self.client.chat.completions.stream(
            model=self.deployment,
            messages=messages,
            response_format=AgentReply,
            stream_options={"include_usage": True},  # sin esto, el consumo no llega en modo streaming
        ) as stream:
            for event in stream:
                if event.type != "content.delta":
                    continue
                reply_so_far = partial_reply(event.snapshot)
                # los campos llegan en el orden del schema: si ya empezó answer, intent está completo
                if not intent_sent and "answer" in reply_so_far:
                    yield IntentDetected(intent=reply_so_far["intent"])
                    intent_sent = True
                answer_so_far = reply_so_far.get("answer", "")
                if len(answer_so_far) > len(answer_sent):
                    yield AnswerDelta(text=answer_so_far[len(answer_sent) :])
                    answer_sent = answer_so_far
            completion = stream.get_final_completion()
        reply, usage = self._parsed_and_usage(completion, start, AgentReply)
        yield ModelResult(reply=reply, usage=usage)

    def parse[Output: BaseModel](self, messages: list[Message], schema: type[Output]) -> tuple[Output, Usage]:
        """Cualquier structured output: lo usan complete, rewrite y el juez G-Eval (S5)."""
        start = time.perf_counter()
        with foundry_errors():
            completion = self.client.chat.completions.parse(
                model=self.deployment, messages=messages, response_format=schema
            )
        return self._parsed_and_usage(completion, start, schema)

    def _parsed_and_usage[Output: BaseModel](
        self, completion: ParsedChatCompletion[Output], start: float, schema: type[Output]
    ) -> tuple[Output, Usage]:
        message = completion.choices[0].message
        if message.parsed is None:
            raise AgentError(ErrorKind.INVALID_OUTPUT, f"el modelo no devolvió el contrato: {message.refusal or 'vacío'}")

        tokens = completion.usage
        usage = Usage(
            models=[completion.model or self.deployment],
            llm_calls=1,
            latency_ms=int((time.perf_counter() - start) * 1000),
            prompt_tokens=tokens.prompt_tokens if tokens else 0,
            completion_tokens=tokens.completion_tokens if tokens else 0,
        )
        log.info("llm %s %s", schema.__name__, usage.model_dump())
        return message.parsed, usage


def partial_reply(snapshot: str) -> dict[str, Any]:
    """El JSON a medio escribir, incluido el texto que todavía no se cerró: '{"answer": "Ho' → {"answer": "Ho"}."""
    try:
        reply = from_json(snapshot.encode(), partial_mode="trailing-strings")
    except ValueError:  # todavía no llegó ni la primera llave
        return {}
    return reply if isinstance(reply, dict) else {}
