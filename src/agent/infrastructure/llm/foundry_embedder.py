from openai import OpenAI

from agent.infrastructure.llm.credentials import Credential
from agent.infrastructure.llm.errors import foundry_errors


class FoundryEmbedder:
    """Implementa el puerto Embedder con un deployment de embeddings de Foundry (text-embedding-3-small)."""

    def __init__(self, endpoint: str, credential: Credential, deployment: str, timeout_s: float, max_retries: int) -> None:
        self.client = OpenAI(
            base_url=f"{endpoint.rstrip('/')}/openai/v1/",
            api_key=credential,
            timeout=timeout_s,
            max_retries=max_retries,
        )
        self.deployment = deployment

    def embed(self, texts: list[str]) -> list[list[float]]:
        with foundry_errors():
            response = self.client.embeddings.create(model=self.deployment, input=texts)
        return [item.embedding for item in sorted(response.data, key=lambda item: item.index)]
