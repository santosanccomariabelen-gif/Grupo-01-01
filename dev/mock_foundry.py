"""Mock local de Foundry (API v1 compatible con OpenAI) para desarrollar sin cuenta de Azure.

Uso:  uv run python dev/mock_foundry.py
.env: FOUNDRY_ENDPOINT=http://127.0.0.1:8100  y  FOUNDRY_API_KEY=<cualquier valor>

Chat: responde {"intent", "answer", "sources"} detectando la intención por palabras clave; en product_question
cita el fragmento [1] del contexto y repite su comienzo. Con stream=true responde en pedazos, como Foundry.
El rewrite devuelve la pregunta tal cual. El juez G-Eval y Microsoft-Decision-1 ponen notas fijas (S5).
Embeddings: vectores determinísticos por bolsa de palabras; textos con palabras en común quedan cerca.
"""

import asyncio
import base64
import hashlib
import json
import math
import os
import re
import struct
import time
from uuid import uuid4

import uvicorn
from fastapi import FastAPI, Header, HTTPException, Request
from fastapi.responses import StreamingResponse

# ponytail: heurística naive por palabras clave, suficiente para probar el flujo
RULES = [
    ("sensitive_action", ("bloque", "robaron", "robo", "perdí", "registrar reclamo")),
    ("data_query", ("mis movimientos", "estado de mi reclamo", "estado del reclamo")),
    ("product_question", ("fraude", "contracargo", "plazo", "reclamo", "no reconozco")),
    ("greeting", ("hola", "buenos", "buenas", "gracias", "adiós")),
]

DIM = 1536  # igual que text-embedding-3-small

app = FastAPI(title="mock-foundry")


def _authorize(authorization: str) -> None:
    if not authorization.removeprefix("Bearer ").strip():
        raise HTTPException(401, {"error": {"code": "401", "message": "Falta la API key"}})


@app.post("/openai/v1/chat/completions", response_model=None)  # responde JSON normal o en streaming
async def chat_completions(request: Request, authorization: str = Header(default="")) -> dict | StreamingResponse:
    _authorize(authorization)

    body = await request.json()
    question = body["messages"][-1]["content"]
    # el SDK manda el nombre del modelo Pydantic que espera como respuesta
    schema = body.get("response_format", {}).get("json_schema", {}).get("name")
    if schema == "SearchQuery":
        data = {"query": question}  # ponytail: no reescribe de verdad; alcanza para probar el flujo
    elif schema == "GEvalScores":  # el juez de la S5: una nota fija, con su razonamiento
        data = {"reasoning": "[mock] la respuesta repite el fragmento [1].", "groundedness": 4, "relevance": 4, "citation_correct": 4}
    else:
        text = question.lower()
        intent = next((name for name, words in RULES if any(word in text for word in words)), "out_of_scope")
        answer = f"[mock] intención detectada: {intent}."
        sources = []
        if intent == "product_question" and (fragment := _first_fragment(body["messages"])):
            answer, sources = f"{answer} El fragmento [1] dice: {fragment}", [1]
        data = {"intent": intent, "answer": answer, "sources": sources}
    content = json.dumps(data, ensure_ascii=False)
    prompt_tokens = sum(len(str(message["content"]).split()) for message in body["messages"])
    completion_tokens = len(content.split())
    usage = {"prompt_tokens": prompt_tokens, "completion_tokens": completion_tokens, "total_tokens": prompt_tokens + completion_tokens}
    if body.get("stream"):
        return StreamingResponse(_stream_chunks(body["model"], content, usage), media_type="text/event-stream")
    return {
        "id": f"mock-{uuid4().hex[:8]}",
        "object": "chat.completion",
        "created": int(time.time()),
        "model": body["model"],
        "choices": [
            {
                "index": 0,
                "finish_reason": "stop",
                "message": {"role": "assistant", "content": content, "refusal": None},
            }
        ],
        "usage": usage,
    }


def _first_fragment(messages: list[dict]) -> str:
    """El comienzo del fragmento [1] del contexto, si lo hay."""
    for message in messages:
        if message["role"] == "system" and "\n[1] " in message["content"]:
            block = message["content"].split("\n[1] ", 1)[1].split("\n\n[2] ", 1)[0]
            text = block.split("\n", 1)[-1]  # la primera línea es el nombre del documento
            return " ".join(text.split())[:200]
    return ""


async def _stream_chunks(model: str, content: str, usage: dict):
    """Igual que Foundry con stream=true: la respuesta en pedazos chat.completion.chunk y al final el consumo."""
    chunk_id, created = f"mock-{uuid4().hex[:8]}", int(time.time())

    def chunk(choices: list, usage: dict | None = None) -> str:
        data = {"id": chunk_id, "object": "chat.completion.chunk", "created": created, "model": model, "choices": choices}
        return f"data: {json.dumps({**data, 'usage': usage}, ensure_ascii=False)}\n\n"

    yield chunk([{"index": 0, "delta": {"role": "assistant", "content": ""}, "finish_reason": None}])
    for start in range(0, len(content), 8):
        await asyncio.sleep(0.02)  # una pausa corta, para que en el chat se vea cómo va apareciendo
        yield chunk([{"index": 0, "delta": {"content": content[start : start + 8]}, "finish_reason": None}])
    yield chunk([{"index": 0, "delta": {}, "finish_reason": "stop"}])
    yield chunk([], usage)
    yield "data: [DONE]\n\n"


@app.post("/openai/v1/embeddings")
async def embeddings(request: Request, authorization: str = Header(default="")) -> dict:
    _authorize(authorization)
    body = await request.json()
    texts = body["input"] if isinstance(body["input"], list) else [body["input"]]
    # el SDK de openai pide base64 por defecto y lo decodifica solo
    as_base64 = body.get("encoding_format") == "base64"
    data = [
        {"object": "embedding", "index": position, "embedding": _encode(_embed(text), as_base64)}
        for position, text in enumerate(texts)
    ]
    tokens = sum(len(text.split()) for text in texts)
    return {"object": "list", "data": data, "model": body["model"], "usage": {"prompt_tokens": tokens, "total_tokens": tokens}}


def _embed(text: str) -> list[float]:
    # ponytail: bolsa de palabras con hash, sin semántica real; alcanza para probar el flujo sin Azure
    vector = [0.0] * DIM
    for word in re.findall(r"\w+", text.lower()):
        vector[int(hashlib.md5(word.encode()).hexdigest(), 16) % DIM] += 1.0
    magnitude = math.sqrt(sum(value * value for value in vector)) or 1.0
    return [value / magnitude for value in vector]


def _encode(vector: list[float], as_base64: bool) -> str | list[float]:
    return base64.b64encode(struct.pack(f"<{len(vector)}f", *vector)).decode() if as_base64 else vector



@app.post("/providers/microsoft/v1/systemone")
async def decision(request: Request, authorization: str = Header(default=""), api_key: str = Header(default="", alias="api-key")) -> dict:
    """Microsoft-Decision-1 de mentira: puntajes fijos, más altos si la respuesta citó fuentes."""
    if not (authorization.removeprefix("Bearer ").strip() or api_key):
        raise HTTPException(401, {"error": {"code": "401", "message": "Falta la credencial"}})
    body = await request.json()
    supported = bool(body["state"]["fragments"]) and bool(body["state"]["cited_sources"])
    answers = {
        name: {"type": "score", "score": 3.5 if supported else 1.0} if question["type"] == "score"
        else {"type": "noul", "probability": 0.9 if supported else 0.2}
        for name, question in body["questions"].items()
    }
    return {"model": "microsoft-decision-1", "answers": answers, "usage": {"input_tokens": len(json.dumps(body).split())}}

if __name__ == "__main__":
    uvicorn.run(app, host=os.environ.get("MOCK_HOST", "127.0.0.1"), port=8100)
