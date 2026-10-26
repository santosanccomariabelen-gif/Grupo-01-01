from collections.abc import Callable

from pydantic import SecretStr

from agent.infrastructure.config.settings import AuthProvider

ENTRA_SCOPE = "https://cognitiveservices.azure.com/.default"

Credential = str | Callable[[], str]  # api key fija o proveedor de token renovable


def build_credential(provider: AuthProvider, api_key: SecretStr) -> Credential:
    # TODO S1: según el provider elegido en FOUNDRY_AUTH_PROVIDER
    #   - api_key:  devolver la key (fallar con un mensaje claro si está vacía)
    #   - entra_id: azure.identity.get_bearer_token_provider(DefaultAzureCredential(), ENTRA_SCOPE)
    raise NotImplementedError("TODO S1: build_credential")
