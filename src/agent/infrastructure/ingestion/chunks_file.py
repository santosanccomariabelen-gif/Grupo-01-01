"""El archivo que arma `ingest build`: los chunks con sus vectores, para revisarlos antes de publicar."""

import json
from pathlib import Path

from pydantic import TypeAdapter

from agent.domain.knowledge import Chunk

_CHUNKS = TypeAdapter(list[Chunk])


def read_chunks(path: Path) -> list[Chunk]:
    return _CHUNKS.validate_json(path.read_bytes()) if path.is_file() else []


def write_chunks(path: Path, chunks: list[Chunk]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(_CHUNKS.dump_python(chunks, mode="json"), ensure_ascii=False, indent=1), encoding="utf-8")
