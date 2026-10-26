from fastapi import APIRouter


def build_router() -> APIRouter:
    router = APIRouter()

    @router.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    # TODO S1: POST /chat que reciba ChatRequest, llame a ChatService.handle y devuelva ChatResponse.
    # TODO S2: handler de AgentError → HTTP: timeout 504, rate limit 429, salida inválida 502.

    return router
