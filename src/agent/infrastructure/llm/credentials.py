from collections.abc import Callable

from azure.identity import DefaultAzureCredential, get_bearer_token_provider
from pydantic import SecretStr

from agent.infrastructure.config.settings import AuthProvider

ENTRA_SCOPE = "https://cognitiveservices.azure.com/.default"

Credential = str | Callable[[], str]  # api key fija o proveedor de token renovable


def build_credential(provider: AuthProvider, api_key: SecretStr) -> Credential:
    match provider:
        case AuthProvider.API_KEY:
            if not api_key.get_secret_value():
                raise RuntimeError("FOUNDRY_AUTH_PROVIDER=api_key requiere FOUNDRY_API_KEY.")
            return api_key.get_secret_value()
        case AuthProvider.ENTRA_ID:
            # az login en local, Managed Identity desplegado
            return get_bearer_token_provider(DefaultAzureCredential(), ENTRA_SCOPE)
