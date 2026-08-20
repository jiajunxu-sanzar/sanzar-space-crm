"""Bootstrap del esquema: crea/repara las pestañas del Excel al arrancar.

Se ejecuta **una vez por proceso** (``@st.cache_resource`` en ``streamlit_app``),
no en cada rerun: en el CRM de clientes esa fue una fuga silenciosa de cuota de
la API que costó detectar.

Qué hace y qué NO hace:

- Crea las pestañas que falten con sus cabeceras.
- Anexa columnas nuevas a las pestañas existentes (respetando el orden real).
- Reescribe la hoja `Indice` con la documentación del modelo de datos.
- **Nunca borra, reordena ni sobrescribe datos** de usuario.
"""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from app.telemetry import timed
from config.settings import (
    INDICE_HEADERS,
    INDICE_ROWS,
    INDICE_WORKSHEET_NAME,
    WORKSHEET_HEADERS,
    WORKSHEET_NAMES,
)
from services.sheets_service import SheetsService


@dataclass(frozen=True, slots=True)
class SchemaReport:
    """Qué tocó el bootstrap — se muestra en Usuarios → Diagnóstico."""

    created_worksheets: tuple[str, ...] = ()
    repaired_worksheets: tuple[str, ...] = ()
    ok: bool = True
    error: str = ""

    @property
    def changed(self) -> bool:
        return bool(self.created_worksheets or self.repaired_worksheets)

    def summary(self) -> str:
        if not self.ok:
            return f"Error preparando el esquema: {self.error}"
        if not self.changed:
            return "Esquema correcto: todas las pestañas y columnas existen."
        parts: list[str] = []
        if self.created_worksheets:
            parts.append(f"pestañas creadas: {', '.join(self.created_worksheets)}")
        if self.repaired_worksheets:
            parts.append(f"columnas añadidas en: {', '.join(self.repaired_worksheets)}")
        return "Esquema actualizado — " + "; ".join(parts) + "."


def ensure_schema(sheets: SheetsService, *, write_index: bool = True) -> SchemaReport:
    """Garantiza que existen todas las pestañas y columnas de ``WORKSHEET_HEADERS``."""
    if not sheets.is_configured():
        return SchemaReport(ok=False, error="GOOGLE_SHEET_ID no está configurado.")

    created: list[str] = []
    repaired: list[str] = []

    try:
        with timed("schema.ensure"):
            existing = sheets.existing_worksheet_titles()

            for name in WORKSHEET_NAMES:
                headers = list(WORKSHEET_HEADERS[name])
                if name not in existing:
                    sheets.get_or_create_worksheet(name, headers)
                    created.append(name)
                    continue
                before = set(sheets.worksheet_headers(name, force=True))
                missing = [header for header in headers if header not in before]
                if missing:
                    sheets.get_or_create_worksheet(name, headers)
                    repaired.append(name)

            if write_index:
                _ensure_index_sheet(sheets, existing)
    except Exception as exc:  # noqa: BLE001 — el arranque nunca debe tumbar la app
        return SchemaReport(
            created_worksheets=tuple(created),
            repaired_worksheets=tuple(repaired),
            ok=False,
            error=str(exc),
        )

    return SchemaReport(tuple(created), tuple(repaired), ok=True)


def _ensure_index_sheet(sheets: SheetsService, existing: set[str]) -> None:
    """Mantiene la hoja `Indice` como documentación viva del modelo de datos.

    Es la única hoja que se reescribe entera, porque su contenido es generado:
    no hay datos de usuario que perder.
    """
    rows = [
        {
            "hoja": hoja,
            "que_guarda": que_guarda,
            "tipo": tipo,
            "notas": f"Columnas: {', '.join(WORKSHEET_HEADERS.get(hoja, ()))}",
        }
        for hoja, que_guarda, tipo in INDICE_ROWS
    ]
    rows.append(
        {
            "hoja": INDICE_WORKSHEET_NAME,
            "que_guarda": "Documentación de cada hoja (esta misma tabla)",
            "tipo": "Meta",
            "notas": "Generada automáticamente por services/schema.py al arrancar la app.",
        }
    )
    del existing  # el bootstrap crea la hoja si falta; no hace falta comprobar
    sheets.write_worksheet_df(
        INDICE_WORKSHEET_NAME, pd.DataFrame(rows), list(INDICE_HEADERS)
    )
