from collections.abc import Iterator
from contextlib import contextmanager

from azure.core.exceptions import ClientAuthenticationError
from openai import (
    APIError,
    APITimeoutError,
    ContentFilterFinishReasonError,
    LengthFinishReasonError,
    RateLimitError,
)
from pydantic import ValidationError

from agent.domain.errors import AgentError, ErrorKind


@contextmanager
def foundry_errors() -> Iterator[None]:
    """Traduce las fallas del SDK de openai y de Entra ID a AgentError, que la API convierte en HTTP."""
    # el SDK reintenta con backoff timeouts, 429 y 5xx; AgentError llega tras agotar reintentos
    try:
        yield
    except APITimeoutError as error:
        raise AgentError(ErrorKind.TIMEOUT, "Foundry no respondió a tiempo") from error
    except RateLimitError as error:
        raise AgentError(ErrorKind.RATE_LIMIT, "Foundry limitó las solicitudes (429)") from error
    except LengthFinishReasonError as error:
        raise AgentError(ErrorKind.INVALID_OUTPUT, "respuesta cortada por límite de tokens") from error
    except ContentFilterFinishReasonError as error:
        raise AgentError(ErrorKind.INVALID_OUTPUT, "respuesta bloqueada por el filtro de contenido") from error
    except ValidationError as error:
        raise AgentError(ErrorKind.INVALID_OUTPUT, "el modelo no devolvió el contrato esperado") from error
    except ClientAuthenticationError as error:
        raise AgentError(ErrorKind.UPSTREAM, "no se pudo obtener token de Entra ID (¿hiciste az login?)") from error
    except APIError as error:
        raise AgentError(ErrorKind.UPSTREAM, f"error de Foundry: {type(error).__name__}") from error
