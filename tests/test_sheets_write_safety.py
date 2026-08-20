"""Escrituras en Sheets: no perder datos del usuario ni desalinear columnas.

La hoja la editan personas. Estas pruebas fijan las dos garantías que más caro
salen si se rompen: que una columna añadida a mano no se borre al editar una
fila, y que un hueco de cabecera no desplace todos los valores.
"""

from __future__ import annotations

from typing import Any

import pytest

from services.sheets_service import SheetsService


class FakeWorksheet:
    """Doble mínimo de ``gspread.Worksheet``: solo lo que usa el servicio."""

    def __init__(self, rows: list[list[str]]) -> None:
        self.rows = [list(row) for row in rows]
        self.updates: list[tuple[str, list[list[str]]]] = []

    def row_values(self, row_number: int) -> list[str]:
        index = row_number - 1
        return list(self.rows[index]) if 0 <= index < len(self.rows) else []

    def get_all_values(self) -> list[list[str]]:
        return [list(row) for row in self.rows]

    def update(self, values: list[list[str]], rng: str = "A1", **_: Any) -> None:
        self.updates.append((rng, values))
        row_number = int("".join(ch for ch in rng if ch.isdigit()) or 1)
        while len(self.rows) < row_number:
            self.rows.append([])
        self.rows[row_number - 1] = list(values[0])

    def append_row(self, values: list[str], **_: Any) -> dict:
        self.rows.append(list(values))
        return {"updates": {"updatedRange": f"'X'!A{len(self.rows)}:Z{len(self.rows)}"}}


@pytest.fixture
def service(monkeypatch):
    sheets = SheetsService()
    monkeypatch.setattr(SheetsService, "is_configured", lambda self: True)
    return sheets


def _bind(monkeypatch, sheets: SheetsService, worksheet: FakeWorksheet) -> None:
    monkeypatch.setattr(SheetsService, "get_or_create_worksheet", lambda self, name, headers: worksheet)
    monkeypatch.setattr(SheetsService, "worksheet", lambda self, name: worksheet)


def test_update_row_conserva_las_columnas_que_la_app_no_conoce(service, monkeypatch):
    """Una nota interna añadida a mano no puede desaparecer al editar la ficha."""
    worksheet = FakeWorksheet(
        [
            ["supplier_id", "nombre_suministrador", "mi_nota_interna"],
            ["SUP-0001", "Alfa", "OJO: pagan a 90 días"],
        ]
    )
    _bind(monkeypatch, service, worksheet)

    service.update_row(
        "Suministradores",
        ["supplier_id", "nombre_suministrador"],
        2,
        {"supplier_id": "SUP-0001", "nombre_suministrador": "Alfa Ibérica"},
    )

    assert worksheet.rows[1] == ["SUP-0001", "Alfa Ibérica", "OJO: pagan a 90 días"]


def test_update_row_sin_preservar_si_se_pide_explicitamente(service, monkeypatch):
    worksheet = FakeWorksheet([["a", "b", "extra"], ["1", "2", "conservar"]])
    _bind(monkeypatch, service, worksheet)

    service.update_row("H", ["a", "b"], 2, {"a": "9", "b": "8"}, preserve_unknown=False)

    assert worksheet.rows[1] == ["9", "8", ""]


def test_una_cabecera_vacia_en_medio_no_desplaza_las_columnas(service, monkeypatch):
    """Compactar la cabecera desalinearía todas las filas ya escritas."""
    worksheet = FakeWorksheet(
        [
            ["supplier_id", "", "pais"],
            ["SUP-0001", "nota suelta", "España"],
        ]
    )
    _bind(monkeypatch, service, worksheet)

    _, headers = service._headers_for_write("Suministradores", ["supplier_id", "pais"])

    assert headers[:3] == ["supplier_id", "", "pais"]
    assert worksheet.rows[0][:3] == ["supplier_id", "", "pais"]


def test_las_columnas_que_faltan_se_anaden_al_final(service, monkeypatch):
    worksheet = FakeWorksheet([["supplier_id", "pais"], ["SUP-0001", "España"]])
    _bind(monkeypatch, service, worksheet)

    _, headers = service._headers_for_write("Suministradores", ["supplier_id", "pais", "email"])

    # Se anexa; nunca se reordena lo que ya existía.
    assert headers == ["supplier_id", "pais", "email"]


def test_append_row_se_alinea_al_orden_real_de_la_hoja(service, monkeypatch):
    """Si el admin reordenó las columnas, la fila nueva debe seguir SU orden."""
    worksheet = FakeWorksheet([["pais", "supplier_id", "nombre_suministrador"]])
    _bind(monkeypatch, service, worksheet)

    service.append_row(
        "Suministradores",
        ["supplier_id", "nombre_suministrador", "pais"],
        {"supplier_id": "SUP-0002", "nombre_suministrador": "Beta", "pais": "China"},
    )

    assert worksheet.rows[-1] == ["China", "SUP-0002", "Beta"]


def test_una_hoja_con_cabecera_vacia_se_inicializa(service, monkeypatch):
    worksheet = FakeWorksheet([[]])
    _bind(monkeypatch, service, worksheet)

    _, headers = service._headers_for_write("Nueva", ["a", "b"])

    assert headers == ["a", "b"]
