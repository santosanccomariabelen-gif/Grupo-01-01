"""Muestra los chunks que armó `uv run ingest build`, para revisarlos antes de publicar.

uv run python dev/show_chunks.py                          resumen: fuente, largo y sección de cada chunk
uv run python dev/show_chunks.py response-times.csv   texto completo de los chunks de una fuente
"""

import sys

from agent.infrastructure.config.settings import Settings
from agent.infrastructure.ingestion.chunks_file import read_chunks

settings = Settings()
path = settings.ingest.data_dir / "chunks" / f"{settings.domain}.json"
chunks = read_chunks(path)
if not chunks:
    sys.exit(f"No hay chunks en {path}. Corre primero: uv run ingest build")

if len(sys.argv) > 1:
    for chunk in (candidate for candidate in chunks if candidate.source == sys.argv[1]):
        print(f"--- {chunk.section}  ({len(chunk.content)} caracteres, vector de {len(chunk.content_vector)})\n{chunk.content}\n")
else:
    for chunk in chunks:
        print(f"{chunk.source:40} {len(chunk.content):5}  {chunk.section}")
    print(f"\n{len(chunks)} chunks en {path}")
