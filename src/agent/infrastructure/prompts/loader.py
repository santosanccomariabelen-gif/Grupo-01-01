from pathlib import Path

PROMPTS_DIR = Path(__file__).parent


def load_prompt(domain: str) -> str:
    path = PROMPTS_DIR / f"{domain}.md"
    if not path.is_file():
        available = sorted(prompt.stem for prompt in PROMPTS_DIR.glob("*.md"))
        raise ValueError(f"DOMAIN '{domain}' no existe. Disponibles: {available}")
    return path.read_text(encoding="utf-8")
