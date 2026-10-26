"""Agrega a manifest.json los documentos nuevos del corpus del dominio, para no escribir sus entradas a mano.

uv run python dev/update_manifest.py

Las entradas que ya están no se tocan: solo se agregan las de archivos que todavía no aparecen, con valores por defecto que hay
que revisar (doc_type, product y vigencia). Si una entrada apunta a un archivo que ya no existe, avisa sin borrarla.
"""

import json
import sys
from datetime import date

from agent.infrastructure.config.settings import Settings

FORMATS = {".md", ".csv", ".html", ".docx", ".pdf"}  # los que convierte loaders.to_markdown

settings = Settings()
corpus_dir = settings.ingest.corpus_dir / settings.domain
manifest_path = corpus_dir / "manifest.json"
if not corpus_dir.is_dir():
    sys.exit(f"No existe {corpus_dir}. Trae primero el corpus de tu dominio (sesión 3, paso 1).")

manifest = json.loads(manifest_path.read_text(encoding="utf-8")) if manifest_path.exists() else []
listed = {entry["source"] for entry in manifest}
new_files = sorted(path.name for path in corpus_dir.iterdir() if path.suffix.lower() in FORMATS and path.name not in listed)

for name in new_files:
    entry = {"source": name, "doc_type": "guide", "product": None, "valid_from": date.today().isoformat(), "valid_until": None}
    manifest.append(entry)
    print(f"+ {name:40} doc_type=guide  product=null  valid_from={entry['valid_from']}  valid_until=null")
for name in sorted(listed):
    if not (corpus_dir / name).exists():
        print(f"! {name:40} está en el manifest, pero el archivo no existe: ingest build va a fallar")

if new_files:
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"\nRevisa esas entradas en {manifest_path} (doc_type, product y vigencia) y corre: uv run ingest build")
else:
    print(f"Nada que agregar: todos los documentos de {corpus_dir} están en el manifest.")
