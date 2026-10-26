"""Búsqueda híbrida en Python: puntaje por palabras (BM25) y fusión de rankings (Reciprocal Rank Fusion)."""

import math
import re
import unicodedata
from collections import Counter

# los valores clásicos de BM25 y de Reciprocal Rank Fusion; casi todos los buscadores usan estos
REPETITION_LIMIT = 1.5  # hasta dónde suma repetir una palabra: la décima vez vale mucho menos que la primera
LENGTH_PENALTY = 0.75  # cuánto se le exige a un chunk largo, que tiene más palabras por azar
RANK_SMOOTHING = 60  # suaviza la distancia entre el primer y el segundo puesto de cada ranking


def split_into_words(text: str) -> list[str]:
    # sin tildes ni mayúsculas: "Débito" y "debito" cuentan como la misma palabra
    without_accents = unicodedata.normalize("NFKD", text.lower()).encode("ascii", "ignore").decode()
    return re.findall(r"\w+", without_accents)


def keyword_scores(question: str, chunk_texts: list[str]) -> list[float]:
    """Puntaje BM25 de cada chunk: sube por cada palabra de la pregunta que contiene, y más si esa palabra es rara."""
    word_counts = [Counter(split_into_words(text)) for text in chunk_texts]
    lengths = [sum(counts.values()) for counts in word_counts]
    average_length = sum(lengths) / len(lengths) if lengths else 0.0
    scores = [0.0] * len(chunk_texts)
    for word in set(split_into_words(question)):
        chunks_with_word = sum(1 for counts in word_counts if word in counts)
        if not chunks_with_word:
            continue
        rarity = math.log(1 + (len(chunk_texts) - chunks_with_word + 0.5) / (chunks_with_word + 0.5))
        for position, counts in enumerate(word_counts):
            if times_in_chunk := counts[word]:
                length_ratio = lengths[position] / average_length
                saturation = REPETITION_LIMIT * (1 - LENGTH_PENALTY + LENGTH_PENALTY * length_ratio)
                scores[position] += rarity * times_in_chunk * (REPETITION_LIMIT + 1) / (times_in_chunk + saturation)
    return scores


def fuse_rankings(rankings: list[list[str]]) -> list[tuple[str, float]]:
    """Reciprocal Rank Fusion: cada ranking le da 1 / (60 + puesto) a cada id. Gana lo que sale arriba en varios rankings."""
    fused_scores: dict[str, float] = {}
    for ranking in rankings:
        for place, item_id in enumerate(ranking, start=1):
            fused_scores[item_id] = fused_scores.get(item_id, 0.0) + 1 / (RANK_SMOOTHING + place)
    return sorted(fused_scores.items(), key=lambda id_and_score: id_and_score[1], reverse=True)
