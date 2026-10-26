"""Ingesta offline del corpus. Arma los chunks en un archivo revisable y después los publica.

uv run ingest build      corpus → chunks + vectores → data/chunks/<dominio>.json
uv run ingest publish    data/chunks/<dominio>.json → base vectorial local (Qdrant) en data/index/<dominio>/
uv run ingest publish --target azure_search    → el índice del equipo en Azure AI Search
"""

import argparse
from collections import Counter

from agent.application.ingest_corpus import IngestCorpus
from agent.infrastructure.bootstrap import build_embedder, build_knowledge_base
from agent.infrastructure.config.settings import KnowledgeBaseKind, Settings
from agent.infrastructure.ingestion.chunks_file import read_chunks, write_chunks
from agent.infrastructure.ingestion.loaders import load_corpus


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(prog="ingest", description="Ingesta del corpus del dominio")
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("build", help="convierte, chunkea y embebe el corpus")
    publish = commands.add_parser("publish", help="publica los chunks armados en el índice")
    publish.add_argument("--target", choices=list(KnowledgeBaseKind), help="por defecto, KNOWLEDGE_BASE de .env")
    args = parser.parse_args(argv)

    settings = Settings()
    ingest = settings.ingest
    corpus_dir = ingest.corpus_dir / settings.domain
    chunks_path = ingest.data_dir / "chunks" / f"{settings.domain}.json"

    if args.command == "build":
        documents = load_corpus(corpus_dir)
        use_case = IngestCorpus(build_embedder(settings.foundry), ingest.chunk_max_chars, ingest.batch_size)
        chunks = use_case.build(documents)
        write_chunks(chunks_path, chunks)
        for source, count in sorted(Counter(chunk.source for chunk in chunks).items()):
            print(f"{count:4}  {source}")
        print(f"{len(chunks)} chunks de {len(documents)} documentos -> {chunks_path}")
    else:
        index = build_knowledge_base(settings, KnowledgeBaseKind(args.target) if args.target else None)
        index.publish(read_chunks(chunks_path))
        print(f"{index.count()} chunks en {index}")
