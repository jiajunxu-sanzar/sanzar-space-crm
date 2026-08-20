"""Smoke test de la app completa contra una hoja de cálculo simulada.

Ejecuta ``streamlit_app.py`` de verdad con ``AppTest``, sustituyendo únicamente
la capa que habla con Google (``SheetsService``) por datos en memoria. Así se
verifica lo que ninguna prueba unitaria cubre: que las páginas se pintan sin
excepciones, que el login funciona y que los permisos por rol se respetan
también en el despacho de páginas, no solo en el menú.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest

st_testing = pytest.importorskip("streamlit.testing.v1")
AppTest = st_testing.AppTest

from config.settings import (  # noqa: E402
    HISTORICO_CONVERSACIONES_HEADERS,
    HISTORICO_CONVERSACIONES_WORKSHEET_NAME,
    HISTORICO_PRECIOS_HEADERS,
    HISTORICO_PRECIOS_WORKSHEET_NAME,
    PRODUCTOS_CAMPOS_SCHEMA_HEADERS,
    PRODUCTOS_CAMPOS_SCHEMA_WORKSHEET_NAME,
    PRODUCTOS_CAMPOS_VALORES_HEADERS,
    PRODUCTOS_CAMPOS_VALORES_WORKSHEET_NAME,
    PRODUCTOS_HEADERS,
    PRODUCTOS_WORKSHEET_NAME,
    SUMINISTRADOR_PRODUCTO_HEADERS,
    SUMINISTRADOR_PRODUCTO_WORKSHEET_NAME,
    SUMINISTRADORES_HEADERS,
    SUMINISTRADORES_WORKSHEET_NAME,
    USUARIOS_HEADERS,
    USUARIOS_WORKSHEET_NAME,
    WORKSHEET_HEADERS,
)
from services.sheets_service import SheetsService  # noqa: E402

APP_PATH = str(Path(__file__).resolve().parents[1] / "streamlit_app.py")

_ROWS: dict[str, list[dict]] = {
    USUARIOS_WORKSHEET_NAME: [
        {"employee_id": "EMP001", "nombre": "Marco Ruano", "rol": "admin", "activo": "Sí", "password": "2026", "notas": ""},
        {"employee_id": "EMP002", "nombre": "Jiajun Xu", "rol": "comprador", "activo": "Sí", "password": "1234", "notas": ""},
        {"employee_id": "EMP003", "nombre": "Carla Moreno", "rol": "comercial", "activo": "Sí", "password": "1234", "notas": ""},
    ],
    PRODUCTOS_WORKSHEET_NAME: [
        {"product_id": "PRD-0001", "nombre_producto": "Motor 5kW", "categoria": "Motores", "estado": "Activo", "descripcion": "Motor trifásico"},
        {"product_id": "PRD-0002", "nombre_producto": "Slip Ring 12 vías", "categoria": "Slip Ring", "estado": "Activo"},
        {"product_id": "PRD-0003", "nombre_producto": "Bearing 6204", "categoria": "Bearing", "estado": "Activo"},
    ],
    PRODUCTOS_CAMPOS_SCHEMA_WORKSHEET_NAME: [
        {"product_id": "PRD-0001", "field_key": "potencia_kw", "field_label": "Potencia", "field_type": "numero", "unidad": "kW", "orden": "1", "activo": "Sí"},
        {"product_id": "PRD-0003", "field_key": "diametro_mm", "field_label": "Diámetro", "field_type": "numero", "unidad": "mm", "orden": "1", "activo": "Sí"},
    ],
    PRODUCTOS_CAMPOS_VALORES_WORKSHEET_NAME: [
        {"product_id": "PRD-0001", "field_key": "potencia_kw", "valor": "5"},
        {"product_id": "PRD-0003", "field_key": "diametro_mm", "valor": "20"},
    ],
    SUMINISTRADORES_WORKSHEET_NAME: [
        {"supplier_id": "SUP-0001", "nombre_suministrador": "SUPPLIER - EXAMPLE 1", "pais": "España", "email": "a@example.com", "contacto_principal": "Ana"},
        {"supplier_id": "SUP-0002", "nombre_suministrador": "SUPPLIER - EXAMPLE 2", "pais": "China", "email": "b@example.com"},
        {"supplier_id": "SUP-0006", "nombre_suministrador": "SUPPLIER - EXAMPLE 6", "pais": "Alemania"},
    ],
    SUMINISTRADOR_PRODUCTO_WORKSHEET_NAME: [
        {"rel_id": "REL-1", "supplier_id": "SUP-0001", "product_id": "PRD-0001", "estado": "Proveedor confirmado", "responsable_relacion": "Marco Ruano", "fecha_alta": "01/07/2026"},
        {"rel_id": "REL-2", "supplier_id": "SUP-0002", "product_id": "PRD-0001", "estado": "Potencial proveedor"},
        {"rel_id": "REL-3", "supplier_id": "SUP-0006", "product_id": "PRD-0002", "estado": "Potencial proveedor"},
        {"rel_id": "REL-4", "supplier_id": "SUP-0006", "product_id": "PRD-0003", "estado": "Descartado", "razon_descarte": "Plazo de entrega inasumible"},
    ],
    HISTORICO_CONVERSACIONES_WORKSHEET_NAME: [
        {
            "historial_conversacion_id": "CNV-1", "supplier_id": "SUP-0001", "product_id": "PRD-0001",
            "tipo_conversacion": "Email", "fecha_contacto": "01/08/2026", "hora_contacto": "09:30",
            "persona_contacto": "Marco Ruano", "resumen": "Pedimos oferta del motor de 5 kW",
            "proxima_accion_detalle": "Reclamar precio", "proxima_accion_fecha": "05/08/2026",
            "proxima_accion_persona": "Marco Ruano", "estado_accion": "Pendiente",
        },
        {
            "historial_conversacion_id": "CNV-2", "supplier_id": "SUP-0002", "product_id": "PRD-0001",
            "tipo_conversacion": "Llamada", "fecha_contacto": "10/08/2026",
            "persona_contacto": "Jiajun Xu", "resumen": "Nos pasan catálogo",
            "estado_accion": "Completada",
        },
    ],
    HISTORICO_PRECIOS_WORKSHEET_NAME: [
        {"historial_precio_id": "PRC-1", "supplier_id": "SUP-0001", "product_id": "PRD-0001", "fecha_oferta": "02/08/2026", "precio": "1250.5", "moneda": "EUR", "unidad_medida": "por unidad", "cantidad_minima": "10"},
        {"historial_precio_id": "PRC-2", "supplier_id": "SUP-0002", "product_id": "PRD-0001", "fecha_oferta": "11/08/2026", "precio": "1100", "moneda": "USD"},
        {"historial_precio_id": "PRC-3", "supplier_id": "SUP-0006", "product_id": "PRD-0002", "fecha_oferta": "05/08/2026", "precio": "300", "moneda": "EUR", "validez_oferta_fecha": "31/12/2026"},
    ],
}


def _frame(name: str) -> pd.DataFrame:
    headers = list(WORKSHEET_HEADERS.get(name, ()))
    frame = pd.DataFrame(_ROWS.get(name, []), columns=headers or None)
    for header in headers:
        if header not in frame.columns:
            frame[header] = ""
    return frame.fillna("").astype(str)


@pytest.fixture(autouse=True)
def fake_sheets(monkeypatch):
    """Sustituye toda la E/S de Google por datos en memoria."""
    writes: list[tuple[str, dict]] = []

    monkeypatch.setattr(SheetsService, "is_configured", lambda self: True)
    monkeypatch.setattr(
        SheetsService, "existing_worksheet_titles", lambda self: set(WORKSHEET_HEADERS)
    )
    monkeypatch.setattr(
        SheetsService, "worksheet_headers", lambda self, name, force=False: list(WORKSHEET_HEADERS.get(name, ()))
    )
    monkeypatch.setattr(
        SheetsService,
        "read_worksheets_batch",
        lambda self, names, headers_by_name=None: {name: _frame(name) for name in names},
    )
    monkeypatch.setattr(
        SheetsService, "read_worksheet_df", lambda self, name, headers=None: _frame(name)
    )
    monkeypatch.setattr(
        SheetsService,
        "append_row",
        lambda self, name, headers, row: (writes.append((name, row)), 2)[1],
    )
    monkeypatch.setattr(SheetsService, "write_worksheet_df", lambda self, name, df, headers: None)
    monkeypatch.setattr(SheetsService, "get_modified_time", lambda self: "2026-08-20T00:00:00Z")
    monkeypatch.setattr(SheetsService, "get_or_create_worksheet", lambda self, name, headers: object())
    return writes


def _login(app: AppTest, *, user_index: int = 0, password: str = "2026") -> AppTest:
    app.run()
    app.selectbox(key="_login_user_select").set_value(
        app.selectbox(key="_login_user_select").options[user_index]
    )
    app.text_input(key="_login_password_input").set_value(password)
    # El formulario de login está en el área principal, no en la barra lateral.
    next(button for button in app.main.button if button.label == "Entrar").click().run()
    return app


def _fresh_app() -> AppTest:
    app = AppTest.from_file(APP_PATH, default_timeout=30)
    # ``cache_resource`` sobrevive entre tests del mismo proceso: limpiarlo evita
    # que un test arrastre la conexión simulada de otro.
    import streamlit as st

    st.cache_data.clear()
    st.cache_resource.clear()
    return app


def test_la_app_arranca_y_pide_login_en_el_area_principal():
    """El login vive en el lienzo, no en el sidebar: una pantalla en blanco con
    un formulario escondido a la izquierda se lee como «esto está roto»."""
    app = _fresh_app().run()
    assert not app.exception

    assert any("Inicia sesión" in str(md.value) for md in app.main.markdown)
    assert not any("Inicia sesión" in str(md.value) for md in app.sidebar.markdown)
    # El sidebar solo lleva la marca; ni un botón hasta que se entra.
    assert not app.sidebar.button


def test_contrasena_incorrecta_no_deja_entrar():
    app = _login(_fresh_app(), password="mal")
    assert not app.exception
    assert any("incorrecta" in str(error.value) for error in app.main.error)


def test_admin_entra_y_ve_la_portada_con_el_mas_barato():
    app = _login(_fresh_app())
    assert not app.exception

    body = " ".join(str(md.value) for md in app.markdown)
    assert "Home" in body
    # El ganador en EUR del motor es EXAMPLE 1 (1.250,50 €); en USD, EXAMPLE 2.
    assert "1.250,50 €" in body
    assert "SUPPLIER - EXAMPLE 1" in body


def test_el_admin_ve_las_seis_paginas():
    app = _login(_fresh_app())
    labels = {button.label for button in app.sidebar.button}
    assert {"Home", "Acciones", "Suministradores", "Compras", "Ofertas", "Usuarios"} <= labels


def test_el_comercial_no_ve_suministradores_ni_usuarios():
    app = _login(_fresh_app(), user_index=2, password="1234")
    assert not app.exception
    labels = {button.label for button in app.sidebar.button}
    assert "Home" in labels and "Ofertas" in labels
    assert "Suministradores" not in labels
    assert "Usuarios" not in labels


def test_navegar_a_suministradores_pinta_la_lista():
    app = _login(_fresh_app())
    next(b for b in app.sidebar.button if b.label == "Suministradores").click().run()
    assert not app.exception

    # Cada fila de la lista es un botón: pinchar el nombre abre la ficha.
    row_labels = {button.label for button in app.main.button}
    assert {"SUPPLIER - EXAMPLE 1", "SUPPLIER - EXAMPLE 2", "SUPPLIER - EXAMPLE 6"} <= row_labels
    assert "+ Nuevo suministrador" in row_labels
    assert "+ Nuevo producto" in row_labels

    # Pestaña Productos: catálogo con nombre y descripción visibles.
    body = " ".join(str(md.value) for md in app.main.markdown)
    assert "Motor 5kW" in body


def test_abrir_ficha_de_producto_muestra_detalle_y_editar():
    app = _login(_fresh_app())
    next(b for b in app.sidebar.button if b.label == "Suministradores").click().run()
    app.button(key="prod_open_PRD-0001").click().run()
    assert not app.exception

    assert app.session_state["selected_product_id"] == "PRD-0001"
    assert app.session_state["selected_supplier_id"] == ""
    body = " ".join(str(md.value) for md in app.main.markdown)
    assert "Motor 5kW" in body
    assert "Motor trifásico" in body
    assert "Editar producto" in {button.label for button in app.main.button}
    # Volver es solo la flecha (sin texto «Volver»).
    assert "Volver" not in {button.label for button in app.main.button}
    assert app.button(key="prod_back")


def test_abrir_una_ficha_muestra_sus_tres_bloques():
    app = _login(_fresh_app())
    next(b for b in app.sidebar.button if b.label == "Suministradores").click().run()
    next(b for b in app.main.button if b.label == "SUPPLIER - EXAMPLE 1").click().run()
    assert not app.exception

    body = " ".join(str(md.value) for md in app.markdown)
    assert "SUPPLIER - EXAMPLE 1" in body
    assert "Motor 5kW" in body
    # Bloque de conversaciones y bloque de precios, con su contenido real.
    assert "Pedimos oferta del motor de 5 kW" in body
    assert "1.250,50 €" in body
    # Lápices de edición del histórico.
    assert app.button(key="hist_edit_conv_CNV-1")
    assert app.button(key="hist_edit_quote_PRC-1")


def test_el_toggle_de_descartados_no_esconde_a_quien_sigue_activo_en_otro_producto():
    """EXAMPLE 6 está descartado en bearings pero es potencial en slip rings."""
    app = _login(_fresh_app())
    next(b for b in app.sidebar.button if b.label == "Suministradores").click().run()
    assert "SUPPLIER - EXAMPLE 6" in {button.label for button in app.main.button}


def test_la_bandeja_de_acciones_muestra_lo_vencido():
    app = _login(_fresh_app())
    next(b for b in app.sidebar.button if b.label == "Acciones").click().run()
    assert not app.exception

    body = " ".join(str(md.value) for md in app.markdown)
    assert "Reclamar precio" in body
    assert "SUPPLIER - EXAMPLE 1" in body
    labels = {button.label for button in app.main.button}
    assert "Ver ficha" in labels
    assert "Completar" not in labels


@pytest.mark.parametrize("page", ["Compras", "Ofertas"])
def test_los_placeholders_avisan_de_proximamente(page):
    app = _login(_fresh_app())
    next(b for b in app.sidebar.button if b.label == page).click().run()
    assert not app.exception
    assert "Próximamente" in " ".join(str(md.value) for md in app.markdown)


def test_usuarios_lista_al_equipo():
    app = _login(_fresh_app())
    next(b for b in app.sidebar.button if b.label == "Usuarios").click().run()
    assert not app.exception
    assert app.selectbox(key="users_pick").options


# --- Regresiones ----------------------------------------------------------


def test_ver_ficha_desde_home_abre_la_ficha():
    """El salto lo pide la app: cambiar de página no debe borrar la selección.

    Con monedas mixtas la tarjeta elige el precio unitario más bajo (1100 USD
    de SUP-0002 frente a 1250,50 EUR de SUP-0001).
    """
    app = _login(_fresh_app())
    next(b for b in app.main.button if b.label == "Ver ficha").click().run()
    assert not app.exception

    assert app.session_state["active_page"] == "Suministradores"
    assert app.session_state["selected_supplier_id"] == "SUP-0002"
    assert "Nos pasan catálogo" in " ".join(str(md.value) for md in app.markdown)


def test_cambiar_de_pestana_a_mano_si_limpia_la_seleccion():
    app = _login(_fresh_app())
    next(b for b in app.main.button if b.label == "Ver ficha").click().run()
    next(b for b in app.sidebar.button if b.label == "Home").click().run()
    next(b for b in app.sidebar.button if b.label == "Suministradores").click().run()

    assert app.session_state["selected_supplier_id"] == ""
    assert "+ Nuevo suministrador" in {button.label for button in app.main.button}


def test_editar_un_usuario_no_arrastra_los_datos_del_anterior():
    """Con keys fijas, cambiar de usuario guardaría el rol del anterior."""
    app = _login(_fresh_app())
    next(b for b in app.sidebar.button if b.label == "Usuarios").click().run()

    picker = app.selectbox(key="users_pick")
    picker.set_value(picker.options[0]).run()  # Marco Ruano (admin)
    picker.set_value(picker.options[2]).run()  # Carla Moreno (comercial)
    assert not app.exception

    # El formulario de Carla muestra SU rol, no el de Marco.
    assert app.selectbox(key="eu_rol_EMP003").value == "comercial"
    assert app.text_input(key="eu_nombre_EMP003").value == "Carla Moreno"


def test_ids_duplicados_en_la_hoja_no_tumban_la_app(monkeypatch):
    """Copiar y pegar una fila en el Excel no puede romper la aplicación."""
    duplicated = dict(_ROWS[SUMINISTRADORES_WORKSHEET_NAME][0])
    monkeypatch.setitem(
        _ROWS, SUMINISTRADORES_WORKSHEET_NAME, _ROWS[SUMINISTRADORES_WORKSHEET_NAME] + [duplicated]
    )
    monkeypatch.setitem(
        _ROWS,
        PRODUCTOS_WORKSHEET_NAME,
        _ROWS[PRODUCTOS_WORKSHEET_NAME] + [dict(_ROWS[PRODUCTOS_WORKSHEET_NAME][0])],
    )

    app = _login(_fresh_app())
    assert not app.exception

    next(b for b in app.sidebar.button if b.label == "Suministradores").click().run()
    assert not app.exception
    labels = [b.label for b in app.main.button if b.label.startswith("SUPPLIER")]
    assert labels.count("SUPPLIER - EXAMPLE 1") == 1


def test_un_fallo_al_leer_la_hoja_se_explica_en_pantalla(monkeypatch):
    """Un error de configuración no puede quedarse en un lienzo en blanco."""

    def _boom(self, name, headers=None):
        raise RuntimeError("403 caller does not have permission")

    monkeypatch.setattr(SheetsService, "read_worksheet_df", _boom)

    app = _fresh_app().run()
    assert not app.exception

    body = " ".join(str(md.value) for md in app.main.markdown)
    assert "No se pudo leer la hoja" in body
    assert "client_email" in body
    # Y el detalle técnico, para poder actuar sin abrir los logs.
    assert any("403" in str(block.value) for block in app.main.code)
