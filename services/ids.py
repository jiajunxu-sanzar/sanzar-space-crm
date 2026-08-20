"""Generación de claves primarias legibles (`PRD-0001`, `SUP-0007`, …).

Se generan **a partir de los ids ya existentes en memoria**, no leyendo la hoja:
el dataset completo ya está cargado en caché, así que calcular el siguiente
número no cuesta ni una llamada a la API.

Para los históricos (conversaciones, precios), donde dos personas pueden dar de
alta a la vez y un contador secuencial colisionaría, se usa un id con sufijo
aleatorio corto en vez de `N+1`.
"""

from __future__ import annotations

import re
import uuid
from typing import Iterable

_NUMERIC_SUFFIX_RE = re.compile(r"^(?P<prefix>[A-Za-z]+)[-_]?(?P<number>\d+)$")


def next_sequential_id(prefix: str, existing_ids: Iterable[str], *, width: int = 4) -> str:
    """Siguiente id secuencial del tipo ``PRD-0004`` sin colisionar con los ya usados.

    Ignora ids con otro prefijo y los que no siguen el patrón (una hoja editada
    a mano puede tener cualquier cosa); nunca reutiliza un hueco intermedio,
    porque un id liberado puede seguir referenciado en un histórico.
    """
    clean_prefix = str(prefix or "").strip().upper()
    highest = 0
    used: set[str] = set()
    for raw in existing_ids:
        value = str(raw or "").strip()
        if not value:
            continue
        used.add(value.upper())
        match = _NUMERIC_SUFFIX_RE.match(value)
        if not match or match.group("prefix").upper() != clean_prefix:
            continue
        highest = max(highest, int(match.group("number")))

    candidate_number = highest + 1
    while True:
        candidate = f"{clean_prefix}-{candidate_number:0{width}d}"
        if candidate.upper() not in used:
            return candidate
        candidate_number += 1


def unique_id(prefix: str) -> str:
    """Id único sin coordinación: ``CNV-3f9a2b7c``.

    Para históricos de alta frecuencia y multiusuario, donde un contador
    secuencial provocaría que dos altas simultáneas escriban el mismo id.
    """
    clean_prefix = str(prefix or "").strip().upper()
    suffix = uuid.uuid4().hex[:8]
    return f"{clean_prefix}-{suffix}" if clean_prefix else suffix


def relation_id(supplier_id: str, product_id: str) -> str:
    """Id determinista de una relación proveedor–producto.

    Al derivarse de la pareja, dar de alta dos veces la misma relación produce
    el mismo ``rel_id`` — lo que convierte los duplicados en detectables en vez
    de en dos filas silenciosamente distintas.
    """
    supplier = str(supplier_id or "").strip().upper()
    product = str(product_id or "").strip().upper()
    return f"REL-{supplier}-{product}"


def slugify_field_key(label: str) -> str:
    """Convierte «Potencia (kW)» en ``potencia_kw`` para usar como ``field_key``."""
    import unicodedata

    text = unicodedata.normalize("NFD", str(label or "").strip().lower())
    text = "".join(char for char in text if unicodedata.category(char) != "Mn")
    text = re.sub(r"[^a-z0-9]+", "_", text).strip("_")
    return text or "campo"
