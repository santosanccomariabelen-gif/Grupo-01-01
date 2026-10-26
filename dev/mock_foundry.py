"""Mock local de Foundry (API v1 compatible con OpenAI) para desarrollar sin cuenta de Azure.

Uso:  uv run python dev/mock_foundry.py
.env: FOUNDRY_ENDPOINT=http://127.0.0.1:8100  y  FOUNDRY_API_KEY=<cualquier valor>

Responde {"intent", "answer"} detectando la intención por palabras clave.
"""

import json
import os
import time
from uuid import uuid4

import uvicorn
from fastapi import FastAPI, Header, HTTPException, Request

# ponytail: heurística naive por palabras clave, suficiente para probar el flujo
RULES = [
    ("sensitive_action", ("bloque", "robaron", "robo", "perdí", "registrar reclamo")),
    ("data_query", ("mis movimientos", "estado de mi reclamo", "estado del reclamo")),
    ("product_question", ("fraude", "contracargo", "plazo", "reclamo", "no reconozco")),
    ("greeting", ("hola", "buenos", "buenas", "gracias", "adiós")),
]

app = FastAPI(title="mock-foundry")


@app.post("/openai/v1/chat/completions")
async def chat_completions(request: Request, authorization: str = Header(default="")) -> dict:
    if not authorization.removeprefix("Bearer ").strip():
        raise HTTPException(401, {"error": {"code": "401", "message": "Falta la API key"}})

    body = await request.json()
    text = body["messages"][-1]["content"].lower()
    intent = next((name for name, words in RULES if any(word in text for word in words)), "out_of_scope")
    content = json.dumps({"intent": intent, "answer": f"[mock] intención detectada: {intent}"}, ensure_ascii=False)
    prompt_tokens = sum(len(str(message["content"]).split()) for message in body["messages"])
    completion_tokens = len(content.split())
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
        "usage": {
            "prompt_tokens": prompt_tokens,
            "completion_tokens": completion_tokens,
            "total_tokens": prompt_tokens + completion_tokens,
        },
    }


if __name__ == "__main__":
    uvicorn.run(app, host=os.environ.get("MOCK_HOST", "127.0.0.1"), port=8100)
