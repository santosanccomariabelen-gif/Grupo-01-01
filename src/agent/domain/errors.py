from enum import StrEnum


class ErrorKind(StrEnum):
    TIMEOUT = "timeout"
    RATE_LIMIT = "rate_limit"
    INVALID_OUTPUT = "invalid_output"
    UPSTREAM = "upstream"
    # T3: TOOL_ERROR, APPROVAL_REJECTED


class AgentError(Exception):
    """Falla controlada de un turno: infrastructure la produce y la API la traduce a HTTP según kind."""

    def __init__(self, kind: ErrorKind, detail: str) -> None:
        super().__init__(f"{kind}: {detail}")
        self.kind = kind
        self.detail = detail
