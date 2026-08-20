"""Pasarela a Google Sheets — la única parte del código que habla con la API.

Optimizaciones heredadas de ``sanzar-crm-web`` (ya probadas en producción):

- **Reintentos con backoff** solo ante errores transitorios (429/5xx, red).
- **Caché de objetos ``Worksheet``**: ``spreadsheet.worksheet(name)`` dispara
  una petición de metadatos en CADA llamada de gspread; cachearlo ahorra ~1
  llamada por operación.
- **Caché de cabeceras** en memoria, con relectura forzada antes de escribir
  una fila completa (una columna añadida a mano desalinearía la escritura).
- **``values.batchGet``**: todas las pestañas en UNA sola llamada.
- **Escritura mínima**: ``append_row`` / ``update`` de una fila; nunca se
  reescribe la hoja entera salvo petición explícita.

Todos los valores se escriben con ``value_input_option="RAW"`` para que Sheets
en locale es_ES no reinterprete «1.234» como 1234 ni convierta fechas.
"""

from __future__ import annotations

import random
import time
from pathlib import Path
from typing import Any, Callable, Iterable, TypeVar

import gspread
import pandas as pd
import requests
from google.auth.transport.requests import Request as GoogleAuthRequest
from google.oauth2.service_account import Credentials

from app.secrets import service_account_info
from app.telemetry import timed
from config.settings import CONFIG, PROJECT_ROOT

_T = TypeVar("_T")

SCOPES = (
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
)

# Esperas (segundos) antes de cada reintento: 3 reintentos → 4 intentos.
_RETRY_WAITS_S: tuple[float, ...] = (1.5, 3.5, 7.0)

_TRANSIENT_HTTP_STATUSES: frozenset[int] = frozenset({429, 500, 502, 503, 504})

_TRANSIENT_QUALNAMES: frozenset[str] = frozenset(
    {
        "requests.exceptions.ConnectionError",
        "requests.exceptions.Timeout",
        "requests.exceptions.ReadTimeout",
        "urllib3.exceptions.ProtocolError",
        "urllib3.exceptions.MaxRetryError",
        "urllib3.exceptions.NewConnectionError",
        "http.client.RemoteDisconnected",
    }
)


class SheetsUnavailableError(RuntimeError):
    """La hoja no se pudo leer/escribir (config ausente o API caída)."""


def _is_transient_error(exc: BaseException) -> bool:
    """True para errores que merece la pena reintentar (red / cuota / servidor)."""
    if isinstance(exc, (ConnectionError, ConnectionResetError, OSError, TimeoutError, BrokenPipeError)):
        return True
    if isinstance(exc, (gspread.exceptions.APIError, requests.exceptions.HTTPError)):
        code = getattr(getattr(exc, "response", None), "status_code", 0)
        return int(code or 0) in _TRANSIENT_HTTP_STATUSES
    qualname = f"{type(exc).__module__}.{type(exc).__qualname__}"
    return qualname in _TRANSIENT_QUALNAMES


def column_letter(index_0based: int) -> str:
    """Índice de columna 0-based → notación A1 (0→A, 25→Z, 26→AA)."""
    number = index_0based + 1
    letters = ""
    while number > 0:
        number, remainder = divmod(number - 1, 26)
        letters = chr(65 + remainder) + letters
    return letters


class SheetsService:
    """Cliente de una única hoja de cálculo (la definida por ``GOOGLE_SHEET_ID``)."""

    def __init__(self, config=CONFIG) -> None:
        self.config = config
        self._spreadsheet: Any | None = None
        self._worksheet_cache: dict[str, Any] = {}
        self._headers_cache: dict[str, list[str]] = {}

    # ------------------------------------------------------------------
    # Reintentos
    # ------------------------------------------------------------------

    def _with_retry(self, fn: Callable[[], _T]) -> _T:
        """Ejecuta ``fn()`` reintentando ante errores transitorios.

        En cada fallo se suelta la referencia cacheada del spreadsheet para que
        el siguiente intento reautentique y abra una conexión limpia.
        """
        last_exc: BaseException | None = None
        for wait in (0.0, *_RETRY_WAITS_S):
            if wait > 0:
                # Jitter: si varias sesiones chocan con la cuota a la vez, no
                # deben reintentar todas en el mismo instante.
                time.sleep(wait + random.uniform(0.0, wait * 0.25))
            try:
                return fn()
            except BaseException as exc:  # noqa: BLE001 — se reevalúa y se relanza
                if not _is_transient_error(exc):
                    raise
                last_exc = exc
                self._spreadsheet = None
                self._worksheet_cache = {}
        raise last_exc  # type: ignore[misc]

    # ------------------------------------------------------------------
    # Conexión
    # ------------------------------------------------------------------

    def is_configured(self) -> bool:
        return bool(self.config.google_sheet_id)

    def _credentials(self) -> Credentials:
        info = service_account_info()
        if info:
            return Credentials.from_service_account_info(info, scopes=SCOPES)
        path = Path(self.config.google_service_account_path)
        if not path.is_absolute():
            path = PROJECT_ROOT / path
        if not path.exists():
            raise SheetsUnavailableError(
                f"No se encuentra el service account en «{path}». "
                "Revisa GOOGLE_SERVICE_ACCOUNT_PATH en el .env."
            )
        return Credentials.from_service_account_file(str(path), scopes=SCOPES)

    def client(self) -> gspread.Client:
        return gspread.authorize(self._credentials())

    def spreadsheet(self):
        if self._spreadsheet is None:
            if not self.is_configured():
                raise SheetsUnavailableError("GOOGLE_SHEET_ID no está configurado.")
            self._spreadsheet = self._with_retry(
                lambda: self.client().open_by_key(self.config.google_sheet_id)
            )
        return self._spreadsheet

    def get_modified_time(self) -> str:
        """``modifiedTime`` ISO del fichero en Drive.

        Llamada barata que NO consume cuota de la Sheets API: la usa
        ``app.remote_sync`` para invalidar cachés cuando alguien edita el Excel
        a mano, sin releer la hoja en cada rerun.
        """
        file_id = self.config.google_sheet_id
        if not file_id:
            raise SheetsUnavailableError("GOOGLE_SHEET_ID no está configurado.")

        def _call() -> str:
            creds = self._credentials()
            if not getattr(creds, "valid", False):
                creds.refresh(GoogleAuthRequest())
            response = requests.get(
                f"https://www.googleapis.com/drive/v3/files/{file_id}",
                headers={"Authorization": f"Bearer {creds.token}"},
                params={"fields": "modifiedTime", "supportsAllDrives": "true"},
                timeout=10,
            )
            response.raise_for_status()
            return str((response.json() or {}).get("modifiedTime", "") or "")

        with timed("sheets.get_modified_time"):
            return self._with_retry(_call)

    # ------------------------------------------------------------------
    # Pestañas y cabeceras
    # ------------------------------------------------------------------

    def worksheet(self, name: str):
        cached = self._worksheet_cache.get(name)
        if cached is not None:
            return cached
        worksheet = self._with_retry(lambda: self.spreadsheet().worksheet(name))
        self._worksheet_cache[name] = worksheet
        return worksheet

    def worksheet_or_none(self, name: str):
        """Devuelve la pestaña o ``None`` si no existe (no la crea)."""
        cached = self._worksheet_cache.get(name)
        if cached is not None:
            return cached
        try:
            worksheet = self.spreadsheet().worksheet(name)
        except gspread.WorksheetNotFound:
            return None
        self._worksheet_cache[name] = worksheet
        return worksheet

    def existing_worksheet_titles(self) -> set[str]:
        """Títulos de todas las pestañas — 1 llamada, usada por el bootstrap."""
        with timed("sheets.list_worksheets"):
            worksheets = self._with_retry(lambda: self.spreadsheet().worksheets())
        for worksheet in worksheets:
            self._worksheet_cache.setdefault(worksheet.title, worksheet)
        return {worksheet.title for worksheet in worksheets}

    def worksheet_headers(self, name: str, *, force: bool = False) -> list[str]:
        """Cabeceras (fila 1) cacheadas en memoria; ``force`` relee la fila."""
        if not force:
            cached = self._headers_cache.get(name)
            if cached:
                return list(cached)
        worksheet = self.worksheet(name)
        headers = [str(h) for h in self._with_retry(lambda: worksheet.row_values(1))]
        while headers and not headers[-1].strip():
            headers.pop()
        if headers:
            self._headers_cache[name] = list(headers)
        return headers

    def get_or_create_worksheet(self, name: str, headers: Iterable[str]):
        """Devuelve la pestaña, creándola o completando columnas que falten.

        Auto-reparable: si el admin añadió columnas a mano, se respeta el orden
        real de la hoja y solo se **anexan** las que falten; nunca se reordena
        ni se borra nada.
        """
        wanted = [str(h) for h in headers if str(h).strip()]

        # Camino rápido sin ninguna llamada API: pestaña y cabeceras conocidas.
        cached_ws = self._worksheet_cache.get(name)
        cached_headers = self._headers_cache.get(name, [])
        if cached_ws is not None and wanted and cached_headers and all(h in cached_headers for h in wanted):
            return cached_ws

        def _open() -> Any:
            spreadsheet = self.spreadsheet()
            try:
                worksheet = self._worksheet_cache.get(name) or spreadsheet.worksheet(name)
            except gspread.WorksheetNotFound:
                worksheet = spreadsheet.add_worksheet(
                    title=name, rows=1000, cols=max(1, len(wanted))
                )
                worksheet.update([wanted], "A1")
                self._headers_cache[name] = list(wanted)
                self._worksheet_cache[name] = worksheet
                return worksheet

            self._worksheet_cache[name] = worksheet
            cached = self._headers_cache.get(name, [])
            if wanted and cached and all(h in cached for h in wanted):
                return worksheet

            current = [str(h).strip() for h in worksheet.row_values(1)]
            current = [h for h in current if h]
            if not current:
                current = list(wanted)
                worksheet.update([current], "A1")
            else:
                missing = [h for h in wanted if h not in current]
                if missing:
                    current = current + missing
                    worksheet.update([current], "A1")
            self._headers_cache[name] = list(current)
            return worksheet

        return self._with_retry(_open)

    # ------------------------------------------------------------------
    # Lectura
    # ------------------------------------------------------------------

    @staticmethod
    def values_to_df(values: list[list[Any]], headers: Iterable[str] | None = None) -> pd.DataFrame:
        """Matriz de ``values.batchGet`` → DataFrame de strings.

        Fila 1 = cabecera, celdas ausentes = cadena vacía, columnas requeridas
        garantizadas aunque la hoja aún no las tenga.
        """
        required = [str(h) for h in (headers or [])]
        if not values:
            return pd.DataFrame(columns=required)

        raw_header = [str(h).strip() for h in values[0]]
        width = len(raw_header)
        rows: list[list[str]] = []
        for row in values[1:]:
            cells = [str(cell) for cell in row[:width]]
            cells.extend([""] * (width - len(cells)))
            rows.append(cells)

        df = pd.DataFrame(rows, columns=raw_header) if rows else pd.DataFrame(columns=raw_header)
        # Una hoja con columnas duplicadas rompería el acceso por nombre.
        df = df.loc[:, ~df.columns.duplicated()]
        for header in required:
            if header not in df.columns:
                df[header] = ""
        return df.astype(str)

    def read_worksheet_df(self, name: str, headers: Iterable[str] | None = None) -> pd.DataFrame:
        """Lee una pestaña completa (creándola si falta)."""
        worksheet = self.get_or_create_worksheet(name, headers or [])
        with timed("sheets.read_worksheet_df", worksheet=name):
            values = self._with_retry(lambda: worksheet.get_all_values())
        return self.values_to_df(values, headers)

    def read_worksheets_batch(
        self,
        names: Iterable[str],
        headers_by_name: dict[str, Iterable[str]] | None = None,
    ) -> dict[str, pd.DataFrame]:
        """Lee VARIAS pestañas en **una sola** llamada (``values.batchGet``).

        Es la lectura que usa la app en caliente: todo el «Excel» cuesta 1
        llamada API por refresco, no una por hoja. Si alguna pestaña no existe
        la API falla, así que el bootstrap debe haberlas creado antes.
        """
        wanted = [str(name) for name in names]
        if not wanted:
            return {}
        headers_by_name = headers_by_name or {}
        ranges = [f"'{name}'" for name in wanted]
        spreadsheet = self.spreadsheet()
        with timed("sheets.read_worksheets_batch", worksheets=len(wanted)):
            response = self._with_retry(lambda: spreadsheet.values_batch_get(ranges))
        value_ranges = (response or {}).get("valueRanges", []) or []

        out: dict[str, pd.DataFrame] = {}
        for name, value_range in zip(wanted, value_ranges):
            values = (value_range or {}).get("values", []) or []
            out[name] = self.values_to_df(values, headers_by_name.get(name))
        for name in wanted:
            if name not in out:
                out[name] = pd.DataFrame(columns=list(headers_by_name.get(name, [])))
        return out

    def row_numbers_by_id(self, name: str, id_column: str) -> dict[str, int]:
        """Mapa ``id -> nº de fila`` leyendo SOLO la columna de ids (1 llamada ligera)."""
        worksheet = self.get_or_create_worksheet(name, [id_column])
        headers = self._headers_cache.get(name) or self.worksheet_headers(name)
        index = self.column_index(headers, id_column)
        if index is None:
            return {}
        with timed("sheets.row_numbers_by_id", worksheet=name):
            column = self._with_retry(lambda: worksheet.col_values(index + 1))
        out: dict[str, int] = {}
        for row_number, value in enumerate(column[1:], start=2):
            row_id = str(value).strip()
            if row_id and row_id not in out:
                out[row_id] = row_number
        return out

    @staticmethod
    def column_index(header_row: Iterable[str], column_name: str) -> int | None:
        needle = str(column_name or "").strip().casefold()
        for index, raw in enumerate(header_row):
            if str(raw).strip().casefold() == needle:
                return index
        return None

    # ------------------------------------------------------------------
    # Escritura
    # ------------------------------------------------------------------

    def _headers_for_write(self, name: str, required: Iterable[str]) -> tuple[Any, list[str]]:
        """(worksheet, cabeceras en el orden REAL de la fila 1).

        Se relee la fila 1 antes de cada escritura de fila completa: si el admin
        insertó una columna a mano, escribir con el orden cacheado metería los
        datos en columnas equivocadas.
        """
        wanted = [str(h) for h in required if str(h).strip()]
        worksheet = self.get_or_create_worksheet(name, wanted)
        raw = [str(h) for h in self._with_retry(lambda: worksheet.row_values(1))]
        # Solo se recortan los vacíos FINALES. Un hueco intermedio (una columna
        # sin título que alguien dejó a medias) se conserva como posición: si se
        # compactara, la cabecera se desplazaría respecto a las filas de datos y
        # cada valor pasaría a leerse bajo la columna equivocada.
        while raw and not raw[-1].strip():
            raw.pop()
        current = [h.strip() for h in raw]
        if not any(current):
            current = list(wanted)
            self._with_retry(lambda: worksheet.update([current], "A1"))
        else:
            missing = [h for h in wanted if h and h not in current]
            if missing:
                current = current + missing
                self._with_retry(lambda: worksheet.update([current], "A1"))
        self._headers_cache[name] = list(current)
        return worksheet, list(current)

    @staticmethod
    def _row_number_from_append_response(response: Any) -> int:
        """Nº de fila (1-based) desde ``updates.updatedRange`` («'Hoja'!A42:R42»)."""
        try:
            rng = str(((response or {}).get("updates") or {}).get("updatedRange") or "")
        except AttributeError:
            return -1
        cell = rng.split("!")[-1].split(":")[0]
        digits = "".join(ch for ch in cell if ch.isdigit())
        return int(digits) if digits else -1

    def append_row(self, name: str, headers: Iterable[str], row: dict[str, Any]) -> int:
        """Añade una fila alineada al orden real de la fila 1. Devuelve su nº de fila."""
        worksheet, sheet_headers = self._headers_for_write(name, headers)
        values = [str(row.get(header, "") or "") for header in sheet_headers]
        with timed("sheets.append_row", worksheet=name):
            response = self._with_retry(
                lambda: worksheet.append_row(values, value_input_option="RAW")
            )
        return self._row_number_from_append_response(response)

    def append_rows(self, name: str, headers: Iterable[str], rows: list[dict[str, Any]]) -> int:
        """Añade N filas en UNA llamada. Devuelve cuántas se escribieron."""
        if not rows:
            return 0
        worksheet, sheet_headers = self._headers_for_write(name, headers)
        matrix = [[str(row.get(header, "") or "") for header in sheet_headers] for row in rows]
        with timed("sheets.append_rows", worksheet=name, rows=len(matrix)):
            self._with_retry(lambda: worksheet.append_rows(matrix, value_input_option="RAW"))
        return len(matrix)

    def update_row(
        self,
        name: str,
        headers: Iterable[str],
        row_number: int,
        row: dict[str, Any],
        *,
        preserve_unknown: bool = True,
    ) -> None:
        """Reescribe una fila por su número (1-based).

        Con ``preserve_unknown`` (por defecto) se lee antes la fila y se
        conservan las columnas que la app no conoce. Sin esto, cualquier columna
        que el equipo haya añadido a mano —una nota interna, un campo de
        seguimiento— se borraría al editar esa fila desde la app. Cuesta una
        lectura ligera extra, y las ediciones son poco frecuentes.
        """
        worksheet, sheet_headers = self._headers_for_write(name, headers)
        known = {str(h) for h in headers if str(h).strip()}

        existing: list[str] = []
        if preserve_unknown:
            with timed("sheets.update_row_read", worksheet=name):
                existing = [
                    str(cell) for cell in self._with_retry(lambda: worksheet.row_values(row_number))
                ]

        values: list[str] = []
        for index, header in enumerate(sheet_headers):
            if header in known:
                values.append(str(row.get(header, "") or ""))
            elif header in row:
                values.append(str(row.get(header, "") or ""))
            else:
                # Columna desconocida (o sin título): se deja tal cual estaba.
                values.append(existing[index] if index < len(existing) else "")

        with timed("sheets.update_row", worksheet=name):
            self._with_retry(
                lambda: worksheet.update([values], f"A{row_number}", value_input_option="RAW")
            )

    def update_row_by_id(
        self,
        name: str,
        headers: Iterable[str],
        id_column: str,
        row_id: str,
        row: dict[str, Any],
    ) -> bool:
        """Reescribe la fila cuyo ``id_column`` vale ``row_id``. False si no existe."""
        row_number = self.row_numbers_by_id(name, id_column).get(str(row_id).strip())
        if not row_number:
            return False
        self.update_row(name, headers, row_number, row)
        return True

    def update_cell_by_id(
        self,
        name: str,
        id_column: str,
        row_id: str,
        column: str,
        value: str,
    ) -> bool:
        """Actualiza UNA celda sin reescribir la fila (1 lectura ligera + 1 escritura)."""
        headers = self.worksheet_headers(name, force=True)
        column_idx = self.column_index(headers, column)
        if column_idx is None:
            return False
        row_number = self.row_numbers_by_id(name, id_column).get(str(row_id).strip())
        if not row_number:
            return False
        worksheet = self.worksheet(name)
        cell = f"{column_letter(column_idx)}{row_number}"
        with timed("sheets.update_cell", worksheet=name):
            self._with_retry(
                lambda: worksheet.update([[str(value)]], cell, value_input_option="RAW")
            )
        return True

    def delete_rows_where(self, name: str, column: str, value: str) -> int:
        """Borra las filas donde ``column == value``. Devuelve cuántas se borraron.

        Un único ``batchUpdate`` con ``deleteDimension`` de abajo a arriba (borrar
        de arriba abajo desplazaría los índices restantes).
        """
        worksheet = self.worksheet_or_none(name)
        if worksheet is None:
            return 0
        target = str(value).strip()
        with timed("sheets.delete_rows_read", worksheet=name):
            values = self._with_retry(lambda: worksheet.get_all_values())
        if len(values) < 2:
            return 0
        column_idx = self.column_index([str(h) for h in values[0]], column)
        if column_idx is None:
            return 0

        to_delete = [
            row_number
            for row_number in range(2, len(values) + 1)
            for row in [values[row_number - 1]]
            if str(row[column_idx] if column_idx < len(row) else "").strip() == target
        ]
        if not to_delete:
            return 0

        sheet_id = worksheet.id
        requests_payload = [
            {
                "deleteDimension": {
                    "range": {
                        "sheetId": sheet_id,
                        "dimension": "ROWS",
                        "startIndex": row - 1,
                        "endIndex": row,
                    }
                }
            }
            for row in sorted(set(to_delete), reverse=True)
        ]
        spreadsheet = self.spreadsheet()
        with timed("sheets.delete_rows", worksheet=name, rows=len(requests_payload)):
            self._with_retry(lambda: spreadsheet.batch_update({"requests": requests_payload}))
        return len(requests_payload)

    def write_worksheet_df(self, name: str, df: pd.DataFrame, headers: Iterable[str]) -> None:
        """Reescribe una pestaña entera. Caro: reservado para el bootstrap."""
        wanted = [str(h) for h in headers]
        worksheet = self.get_or_create_worksheet(name, wanted)
        frame = df.fillna("").astype(str)
        for header in wanted:
            if header not in frame.columns:
                frame[header] = ""
        rows = [wanted] + frame[wanted].values.tolist()
        with timed("sheets.write_worksheet_df", worksheet=name, rows=max(0, len(rows) - 1)):
            self._with_retry(lambda: (worksheet.clear(), worksheet.update(rows, "A1")))
        self._headers_cache[name] = list(wanted)

    def invalidate_caches(self) -> None:
        """Suelta las referencias cacheadas (tras un cambio de esquema)."""
        self._spreadsheet = None
        self._worksheet_cache = {}
        self._headers_cache = {}
