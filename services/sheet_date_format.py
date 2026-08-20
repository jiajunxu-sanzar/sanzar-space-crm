"""Fechas y horas de/para Google Sheets — formato canónico ``DD/MM/AAAA``.

Mismo contrato que ``services/sheet_date_format.py`` en ``sanzar-crm-web``:
la hoja guarda texto en ``DD/MM/AAAA``, pero la lectura es tolerante (ISO,
``DD-MM-AAAA``, fecha-hora) porque una hoja editada a mano siempre acaba
teniendo de todo.
"""

from __future__ import annotations

import re
from datetime import date, datetime
from zoneinfo import ZoneInfo

DATE_FMT = "%d/%m/%Y"
DATETIME_FMT = "%d/%m/%Y %H:%M:%S"
TIME_FMT = "%H:%M"

MADRID_TZ = ZoneInfo("Europe/Madrid")

_DATE_RE = re.compile(r"^\d{2}/\d{2}/\d{4}$")
_TIME_RE = re.compile(r"^(\d{1,2}):(\d{2})(?::\d{2})?$")

DD_MM_YYYY_HINT = (
    "Las fechas deben ir en formato DD/MM/AAAA. "
    "Ejemplos válidos: 05/04/2026, 31/12/2025."
)
HH_MM_HINT = "Las horas deben ir en formato HH:MM (24h). Ejemplo: 09:30."


# --- Ahora (siempre hora de Madrid, no la del servidor) --------------------


def now_madrid() -> datetime:
    return datetime.now(MADRID_TZ)


def today_madrid() -> date:
    return now_madrid().date()


def timestamp_now() -> str:
    """Marca de tiempo para ``created_at`` / ``updated_at``."""
    return now_madrid().strftime(DATETIME_FMT)


def today_str() -> str:
    return today_madrid().strftime(DATE_FMT)


# --- Validación -----------------------------------------------------------


def is_valid_dd_mm_yyyy(value: str) -> bool:
    """Vacío se considera válido: hay campos de fecha opcionales."""
    raw = (value or "").strip()
    if not raw:
        return True
    if not _DATE_RE.match(raw):
        return False
    try:
        datetime.strptime(raw, DATE_FMT)
    except ValueError:
        return False
    return True


def is_valid_hh_mm(value: str) -> bool:
    raw = (value or "").strip()
    if not raw:
        return True
    match = _TIME_RE.match(raw)
    if not match:
        return False
    hours, minutes = int(match.group(1)), int(match.group(2))
    return 0 <= hours <= 23 and 0 <= minutes <= 59


# --- Parseo ---------------------------------------------------------------


def parse_sheet_date(value: object) -> date | None:
    """Fecha desde la hoja: ``DD/MM/AAAA``, ISO, ``DD-MM-AAAA`` o fecha-hora."""
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value

    raw = str(value or "").strip()
    if not raw:
        return None
    if " " in raw:
        raw = raw.split(" ", 1)[0].strip()
    for fmt in (DATE_FMT, "%Y-%m-%d", "%d-%m-%Y", "%Y/%m/%d"):
        try:
            return datetime.strptime(raw, fmt).date()
        except ValueError:
            continue
    return None


def parse_sheet_datetime(value: object) -> datetime | None:
    raw = str(value or "").strip()
    if not raw:
        return None
    for fmt in (DATETIME_FMT, "%d/%m/%Y %H:%M", "%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M:%S"):
        try:
            return datetime.strptime(raw, fmt)
        except ValueError:
            continue
    parsed_date = parse_sheet_date(raw)
    return datetime.combine(parsed_date, datetime.min.time()) if parsed_date else None


def normalize_dd_mm_yyyy(value: object) -> str:
    """Devuelve ``DD/MM/AAAA`` canónico, o cadena vacía si no se puede parsear."""
    parsed = parse_sheet_date(value)
    return parsed.strftime(DATE_FMT) if parsed else ""


def normalize_hh_mm(value: object) -> str:
    raw = str(value or "").strip()
    match = _TIME_RE.match(raw)
    if not match:
        return ""
    return f"{int(match.group(1)):02d}:{match.group(2)}"


def format_date(value: date | None) -> str:
    return value.strftime(DATE_FMT) if value else ""


# --- Validación de formularios -------------------------------------------


def validate_dd_mm_yyyy_fields(labels_and_values: list[tuple[str, str]]) -> str | None:
    """Mensaje de error si alguna fecha con etiqueta tiene formato inválido."""
    bad = [label for label, value in labels_and_values if not is_valid_dd_mm_yyyy(value)]
    if not bad:
        return None
    return f"Revisa el formato de fecha en: {', '.join(bad)}.\n\n{DD_MM_YYYY_HINT}"


def days_until(value: object, *, today: date | None = None) -> int | None:
    """Días desde hoy hasta la fecha dada (negativo = vencida)."""
    parsed = parse_sheet_date(value)
    if parsed is None:
        return None
    return (parsed - (today or today_madrid())).days
