"""Parseo y formato de números tolerante al locale español.

Google Sheets en locale `es_ES` escribe «1.234,56». Un `float()` directo sobre
eso falla o —peor— interpreta «1.234» como 1,234. Este módulo normaliza ambas
convenciones antes de convertir, y es la única puerta de entrada a números que
vienen de la hoja.
"""

from __future__ import annotations

import re

_CLEAN_RE = re.compile(r"[^0-9,.\-]")


def parse_decimal(value: object) -> float | None:
    """Convierte texto de hoja de cálculo a ``float``; ``None`` si no es un número.

    Acepta «1.234,56», «1,234.56», «1234.56», «1234,56», «1 234,56 €», «-12».
    """
    if value is None:
        return None
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return float(value)

    raw = _CLEAN_RE.sub("", str(value).strip())
    if not raw or raw in {"-", ",", "."}:
        return None

    has_comma = "," in raw
    has_dot = "." in raw
    if has_comma and has_dot:
        # El separador decimal es el que aparece MÁS a la derecha.
        if raw.rfind(",") > raw.rfind("."):
            raw = raw.replace(".", "").replace(",", ".")
        else:
            raw = raw.replace(",", "")
    elif has_comma:
        # Una sola coma → decimal (es-ES). Varias → separador de miles.
        raw = raw.replace(",", ".") if raw.count(",") == 1 else raw.replace(",", "")
    elif has_dot and raw.count(".") > 1:
        raw = raw.replace(".", "")

    try:
        return float(raw)
    except ValueError:
        return None


def parse_int(value: object) -> int | None:
    parsed = parse_decimal(value)
    return None if parsed is None else int(parsed)


def format_decimal(value: float | None, *, decimals: int = 2) -> str:
    """Formatea en es-ES: miles con punto, decimales con coma.

    Se parte por el separador decimal en lugar de encadenar ``replace`` con un
    carácter intermedio: ese truco es frágil y difícil de leer.
    """
    if value is None:
        return ""
    thousands, _, fraction = f"{value:,.{decimals}f}".partition(".")
    thousands = thousands.replace(",", ".")
    return f"{thousands},{fraction}" if fraction else thousands


def format_money(value: float | None, moneda: str = "EUR", *, decimals: int = 2) -> str:
    from config.settings import MONEDA_SIMBOLOS

    if value is None:
        return "—"
    symbol = MONEDA_SIMBOLOS.get(str(moneda).upper(), str(moneda))
    return f"{format_decimal(value, decimals=decimals)} {symbol}".strip()
