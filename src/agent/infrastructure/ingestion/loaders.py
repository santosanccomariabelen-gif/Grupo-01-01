"""Convierte cada formato del corpus a Markdown con títulos (#, ##, ###), que es lo que entiende el chunker."""

import csv
import io
import json
import re
from html.parser import HTMLParser
from pathlib import Path

from docx import Document
from docx.table import Table
from pypdf import PdfReader

from agent.domain.knowledge import SourceDocument

# "1. Objeto" o "3.1 Plazo": número de sección seguido de un título con mayúscula
PDF_HEADING = re.compile(r"^(\d+)\.(\d+)?\s+[A-ZÁÉÍÓÚÑ¿]")


def load_corpus(corpus_dir: Path) -> list[SourceDocument]:
    manifest = json.loads((corpus_dir / "manifest.json").read_text(encoding="utf-8"))
    return [SourceDocument(markdown=to_markdown(corpus_dir / entry["source"]), **entry) for entry in manifest]


def to_markdown(path: Path) -> str:
    match path.suffix.lower():
        case ".md":
            return path.read_text(encoding="utf-8")
        case ".csv":
            return csv_to_markdown(path.stem, path.read_text(encoding="utf-8"))
        case ".html":
            return html_to_markdown(path.read_text(encoding="utf-8"))
        case ".docx":
            return docx_to_markdown(path)
        case ".pdf":
            return pdf_text_to_markdown("\n".join(page.extract_text() or "" for page in PdfReader(path).pages))
        case other:
            raise ValueError(f"formato no soportado: {other} ({path.name})")


def csv_to_markdown(title: str, text: str) -> str:
    return "\n".join([f"# {title}", "", *markdown_table(list(csv.reader(io.StringIO(text))))]) + "\n"


def markdown_table(rows: list[list[str]]) -> list[str]:
    """La primera fila es el encabezado. Una tabla en Markdown es lo que el chunker sabe partir por filas."""
    header, *body = rows
    return [_markdown_row(header), _markdown_row(["---"] * len(header)), *[_markdown_row(row) for row in body]]


def _markdown_row(cells: list[str]) -> str:
    return "| " + " | ".join(" ".join(cell.split()) for cell in cells) + " |"


class _HtmlToMarkdown(HTMLParser):
    SKIP = {"nav", "footer", "script", "style", "head"}

    def __init__(self) -> None:
        super().__init__()
        self.lines: list[str] = []
        self.prefix = ""
        self.skip_depth = 0
        self.text: list[str] = []
        self.rows: list[list[str]] = []

    def handle_starttag(self, tag: str, attrs) -> None:
        if tag in self.SKIP:
            self.skip_depth += 1
        elif re.fullmatch(r"h[1-6]", tag):
            self.prefix = "#" * int(tag[1]) + " "
        elif tag == "li":
            self.prefix = "- "
        elif tag == "tr":
            self.rows.append([])
        elif tag in {"td", "th"}:
            self.text = []

    def handle_endtag(self, tag: str) -> None:
        if tag in self.SKIP:
            self.skip_depth -= 1
        elif tag in {"h1", "h2", "h3", "h4", "h5", "h6", "p", "li"}:
            if text := " ".join("".join(self.text).split()):
                self.lines += [self.prefix + text, ""] if tag != "li" else [self.prefix + text]
            self.text, self.prefix = [], ""
        elif tag == "ul":
            self.lines.append("")
        elif tag in {"td", "th"}:
            self.rows[-1].append("".join(self.text))
            self.text = []
        elif tag == "table":
            self.lines += markdown_table(self.rows) + [""]
            self.rows = []

    def handle_data(self, data: str) -> None:
        if not self.skip_depth:
            self.text.append(data)


def html_to_markdown(html: str) -> str:
    parser = _HtmlToMarkdown()
    parser.feed(html)
    return "\n".join(parser.lines)


def docx_to_markdown(path: Path) -> str:
    lines = []
    for block in Document(path).iter_inner_content():  # párrafos y tablas, en el orden del documento
        if isinstance(block, Table):
            lines += markdown_table([[cell.text for cell in row.cells] for row in block.rows]) + [""]
            continue
        text, style = block.text.strip(), block.style.name
        if not text:
            continue
        if style == "Title":
            lines += [f"# {text}", ""]
        elif style.startswith("Heading "):
            lines += ["#" * (int(style.split()[1]) + 1) + f" {text}", ""]
        elif style.startswith("List"):
            lines.append(f"- {text}")
        else:
            lines += [text, ""]
    return "\n".join(lines)


def pdf_text_to_markdown(text: str) -> str:
    """El PDF no trae estilos: la primera línea es el título y las secciones se reconocen por su numeración."""
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    if not lines:
        return ""
    markdown_lines, paragraph = [f"# {lines[0]}", ""], []
    for line in lines[1:]:
        if heading := PDF_HEADING.match(line):
            if paragraph:
                markdown_lines += [" ".join(paragraph), ""]
                paragraph = []
            markdown_lines += [("###" if heading[2] else "##") + f" {line}", ""]
        else:
            paragraph.append(line)
    if paragraph:
        markdown_lines.append(" ".join(paragraph))
    return "\n".join(markdown_lines)
