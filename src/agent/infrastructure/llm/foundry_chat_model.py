from openai import OpenAI

from agent.domain.models import Message
from agent.infrastructure.llm.credentials import Credential


class FoundryChatModel:
    """Implementa el puerto ChatModel contra Microsoft Foundry (API v1 compatible con OpenAI)."""

    def __init__(
        self,
        endpoint: str,
        credential: Credential,
        deployment: str,
        timeout_s: float,
        max_retries: int,
    ) -> None:
        # el SDK reintenta con backoff timeouts, 429 y 5xx
        self.client = OpenAI(
            base_url=f"{endpoint.rstrip('/')}/openai/v1/",
            api_key=credential,
            timeout=timeout_s,
            max_retries=max_retries,
        )
        self.deployment = deployment

    def complete(self, messages: list[Message]):
        # TODO S1: self.client.chat.completions.parse(model=..., messages=..., response_format=AgentReply)
        #          y devolver message.parsed.
        # TODO S2: medir latencia y tokens; traducir timeout, 429, salida inválida y errores de Foundry
        #          a AgentError del dominio.
        raise NotImplementedError("TODO S1: FoundryChatModel.complete")
