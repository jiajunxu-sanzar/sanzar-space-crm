"""``SpaceDataset``: índices, cruces y tolerancia a hojas mal rellenadas."""

from __future__ import annotations

from datetime import date

import pandas as pd
import pytest

from config.settings import USUARIOS_HEADERS
from services.dataset import SpaceDataset
from services.sheets_service import SheetsService
from services.users_service import (
    active_users,
    person_options,
    user_names,
    users_from_frame,
)
from tests.conftest import make_dataset


def _rich_dataset():
    return make_dataset(
        productos=[
            {"product_id": "PRD-0001", "nombre_producto": "Motor", "categoria": "Motores", "estado": "Activo"},
            {"product_id": "PRD-0002", "nombre_producto": "Bearing", "categoria": "Bearing", "estado": "Descontinuado"},
        ],
        suministradores=[
            {"supplier_id": "SUP-0001", "nombre_suministrador": "Alfa", "pais": "España"},
            {"supplier_id": "SUP-0002", "nombre_suministrador": "Beta", "pais": "China"},
        ],
        relaciones=[
            {"rel_id": "REL-1", "supplier_id": "SUP-0001", "product_id": "PRD-0001", "estado": "Proveedor confirmado"},
            {"rel_id": "REL-2", "supplier_id": "SUP-0002", "product_id": "PRD-0001", "estado": "Potencial proveedor"},
        ],
        conversaciones=[
            {
                "historial_conversacion_id": "CNV-1",
                "supplier_id": "SUP-0001",
                "product_id": "PRD-0001",
                "tipo_conversacion": "Email",
                "fecha_contacto": "01/08/2026",
                "resumen": "Primer contacto",
                "estado_accion": "Pendiente",
                "proxima_accion_detalle": "Pedir precio",
                "proxima_accion_fecha": "10/08/2026",
                "proxima_accion_persona": "Marco",
            },
            {
                "historial_conversacion_id": "CNV-2",
                "supplier_id": "SUP-0001",
                "product_id": "PRD-0001",
                "tipo_conversacion": "Llamada",
                "fecha_contacto": "15/08/2026",
                "resumen": "Segundo contacto",
                "estado_accion": "Completada",
            },
        ],
        precios=[
            {"historial_precio_id": "PRC-1", "supplier_id": "SUP-0001", "product_id": "PRD-0001", "precio": "1000", "moneda": "EUR", "fecha_oferta": "01/08/2026"},
            {"historial_precio_id": "PRC-2", "supplier_id": "SUP-0001", "product_id": "PRD-0001", "precio": "900", "moneda": "EUR", "fecha_oferta": "10/08/2026"},
        ],
    )


def test_los_indices_resuelven_nombres():
    dataset = _rich_dataset()
    assert dataset.product_name("PRD-0001") == "Motor"
    assert dataset.supplier_name("SUP-0002") == "Beta"
    # Un id desconocido devuelve el propio id, no revienta ni miente.
    assert dataset.product_name("PRD-9999") == "PRD-9999"


def test_active_products_filtra_descontinuados():
    assert [p.product_id for p in _rich_dataset().active_products()] == ["PRD-0001"]


def test_las_conversaciones_salen_de_la_mas_reciente_a_la_mas_antigua():
    conversations = _rich_dataset().conversations_by_supplier["SUP-0001"]
    assert [c.historial_conversacion_id for c in conversations] == ["CNV-2", "CNV-1"]


def test_latest_quote_devuelve_la_mas_reciente():
    quote = _rich_dataset().latest_quote("SUP-0001", "PRD-0001")
    assert quote is not None and quote.historial_precio_id == "PRC-2"


def test_last_contact_date_usa_la_conversacion_mas_reciente():
    assert _rich_dataset().last_contact_date("SUP-0001") == date(2026, 8, 15)


def test_open_actions_ignora_las_completadas():
    actions = _rich_dataset().open_actions_for_supplier("SUP-0001")
    assert [a.historial_conversacion_id for a in actions] == ["CNV-1"]


def test_paises_y_categorias_se_deducen_de_los_datos():
    dataset = _rich_dataset()
    assert dataset.paises == ("China", "España")
    assert dataset.categorias == ("Bearing", "Motores")


def test_las_filas_sin_clave_primaria_se_descartan():
    dataset = make_dataset(
        productos=[{"product_id": "", "nombre_producto": "Fantasma"}, {"product_id": "PRD-1", "nombre_producto": "Real"}]
    )
    assert [p.product_id for p in dataset.products] == ["PRD-1"]


def test_dataset_vacio_es_navegable():
    dataset = SpaceDataset.empty()
    assert dataset.is_empty is True
    assert dataset.products == () and dataset.suppliers == ()
    assert dataset.products_for_supplier("SUP-0001") == ()
    assert dataset.latest_quote("SUP-0001", "PRD-0001") is None


# --- values_to_df: lo que llega de verdad desde la API --------------------


def test_values_to_df_rellena_filas_cortas():
    """La API omite las celdas vacías del final: no deben desalinear la fila."""
    values = [["a", "b", "c"], ["1", "2"], ["3"]]
    df = SheetsService.values_to_df(values, ["a", "b", "c"])
    assert df.shape == (2, 3)
    assert df.iloc[0].tolist() == ["1", "2", ""]


def test_values_to_df_garantiza_las_columnas_requeridas():
    df = SheetsService.values_to_df([["a"], ["1"]], ["a", "nueva"])
    assert "nueva" in df.columns and df["nueva"].tolist() == [""]


def test_values_to_df_con_hoja_vacia():
    df = SheetsService.values_to_df([], ["a", "b"])
    assert df.empty and list(df.columns) == ["a", "b"]


def test_values_to_df_descarta_columnas_duplicadas():
    df = SheetsService.values_to_df([["a", "a", "b"], ["1", "2", "3"]], ["a", "b"])
    assert list(df.columns) == ["a", "b"]


@pytest.mark.parametrize("index,expected", [(0, "A"), (25, "Z"), (26, "AA"), (27, "AB"), (51, "AZ")])
def test_column_letter(index, expected):
    from services.sheets_service import column_letter

    assert column_letter(index) == expected


# --- Usuarios -------------------------------------------------------------


def _users_frame(rows):
    return pd.DataFrame(rows, columns=list(USUARIOS_HEADERS)).fillna("").astype(str)


def test_usuarios_sin_nombre_o_id_se_descartan():
    users = users_from_frame(
        _users_frame(
            [
                {"employee_id": "EMP001", "nombre": "Marco", "rol": "admin", "activo": "Sí", "password": "x", "notas": ""},
                {"employee_id": "", "nombre": "Sin id", "rol": "admin", "activo": "Sí", "password": "x", "notas": ""},
            ]
        )
    )
    assert [u.employee_id for u in users] == ["EMP001"]


def test_activo_vacio_cuenta_como_activo():
    users = users_from_frame(
        _users_frame([{"employee_id": "EMP001", "nombre": "Marco", "rol": "admin", "activo": "", "password": "x", "notas": ""}])
    )
    assert active_users(users)[0].activo is True


def test_un_rol_desconocido_cae_a_comercial():
    users = users_from_frame(
        _users_frame([{"employee_id": "EMP001", "nombre": "X", "rol": "jefazo", "activo": "Sí", "password": "x", "notas": ""}])
    )
    assert users[0].role == "comercial"


def test_person_options_conserva_un_nombre_historico():
    """Editar una entrada antigua no debe borrar a quien ya no está en plantilla."""
    users = users_from_frame(
        _users_frame([{"employee_id": "EMP001", "nombre": "Marco", "rol": "admin", "activo": "Sí", "password": "x", "notas": ""}])
    )
    options = person_options(users, current="Alguien Que Se Fue")
    assert "Alguien Que Se Fue" in options and "Marco" in options
    assert user_names(users) == ["Marco"]
