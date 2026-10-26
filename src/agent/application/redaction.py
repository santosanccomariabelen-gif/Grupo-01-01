"""Datos personales: se enmascaran antes de indexar. Lo que no está en el índice no puede aparecer en una respuesta."""

import re

CARD_NUMBER = re.compile(r"\b(?:\d[ -]?){12,18}\d\b")  # de 13 a 19 dígitos, con o sin espacios o guiones
DNI = re.compile(r"\b\d{8}\b")  # documento nacional de identidad: 8 dígitos seguidos


def redact_personal_data(text: str) -> str:
    # primero las tarjetas: dentro de un número de tarjeta podría haber 8 dígitos seguidos que parecen un DNI
    return DNI.sub("[DNI]", CARD_NUMBER.sub("[TARJETA]", text))


def contains_personal_data(text: str) -> bool:
    return bool(CARD_NUMBER.search(text) or DNI.search(text))
