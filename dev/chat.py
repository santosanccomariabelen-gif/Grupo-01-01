"""Cliente de consola para conversar con el agente, sin pelear con las comillas ni las tildes de PowerShell.

uv run python dev/chat.py            conversación: escribe tus mensajes; "nueva" empieza otra sesión, "salir" termina
uv run python dev/chat.py "Hola"     un solo mensaje y termina

La respuesta aparece mientras el agente la escribe (POST /chat/stream, Server-Sent Events).
AGENT_URL cambia la dirección del agente (por defecto http://127.0.0.1:8000).
"""

import json
import os
import sys
import time
import urllib.error
import urllib.request
from collections.abc import Iterator
from http.client import HTTPResponse

URL = os.environ.get("AGENT_URL", "http://127.0.0.1:8000").rstrip("/") + "/chat/stream"


def send(message: str, session_id: str | None) -> str | None:
    """Envía el mensaje, muestra la respuesta mientras llega y devuelve el session_id para el siguiente turno."""
    body = json.dumps({"message": message, "session_id": session_id}).encode("utf-8")
    request = urllib.request.Request(URL, data=body, headers={"Content-Type": "application/json"})
    sent_at = time.perf_counter()
    try:
        response = urllib.request.urlopen(request, timeout=120)
    except urllib.error.HTTPError as error:  # falló antes de empezar a responder: llega como HTTP normal
        show_error(error.code, json.loads(error.read().decode("utf-8")))
        return None
    except urllib.error.URLError:
        sys.exit(f"No hay agente en {URL}. ¿Lo levantaste con uvicorn en otra terminal?")

    first_text_ms = None
    with response:
        for name, data in read_events(response):
            match name:
                case "intent":
                    print(f"  Agente [{data['intent']}]: ", end="", flush=True)
                case "delta":
                    first_text_ms = first_text_ms or milliseconds_since(sent_at)
                    print(data["text"], end="", flush=True)
                case "end":
                    print()
                    show_end(data, first_text_ms, milliseconds_since(sent_at))
                    return data["session_id"]
                case "error":
                    print()
                    show_error(200, data)
    return None


def read_events(response: HTTPResponse) -> Iterator[tuple[str, dict]]:
    """Lee los eventos a medida que llegan: cada uno es una línea "event: <nombre>" y una "data: <json>"."""
    name = ""
    for raw_line in response:
        line = raw_line.decode("utf-8").rstrip("\r\n")
        if line.startswith("event: "):
            name = line.removeprefix("event: ")
        elif line.startswith("data: "):
            yield name, json.loads(line.removeprefix("data: "))


def show_end(reply: dict, first_text_ms: int | None, total_ms: int) -> None:
    if citations := reply.get("citations"):
        print("  Fuentes:")
        for number, citation in enumerate(citations, start=1):
            print(f"   [{number}] {citation['source']} · {citation['section']}")
    usage = reply["usage"]
    first_text = f"primer texto en {first_text_ms} ms, " if first_text_ms else ""
    print(f"  ({first_text}respuesta completa en {total_ms} ms, "
          f"{usage['prompt_tokens']} tokens de entrada, {usage['completion_tokens']} de salida)")


def show_error(status: int, reply: dict) -> None:
    detail = reply.get("detail")
    if isinstance(detail, list):  # 422: FastAPI explica qué campo no pasó la validación
        detail = "; ".join(problem.get("msg", str(problem)) for problem in detail)
    kind = f" ({reply['error']})" if reply.get("error") else ""
    where = "a mitad de la respuesta" if status == 200 else str(status)
    print(f"  Error {where}{kind}: {detail}")


def milliseconds_since(start: float) -> int:
    return int((time.perf_counter() - start) * 1000)


def main() -> None:
    if len(sys.argv) > 1:
        send(" ".join(sys.argv[1:]), None)
        return
    print('Conversación con el agente. Escribe "nueva" para otra sesión o "salir" para terminar.')
    session_id = None
    while True:
        try:
            message = input("Tú: ")
        except (EOFError, KeyboardInterrupt):
            break
        if message.strip().lower() == "salir":
            break
        if message.strip().lower() == "nueva":
            session_id = None
            print("  (sesión nueva)")
            continue
        session_id = send(message, session_id) or session_id


if __name__ == "__main__":
    main()
