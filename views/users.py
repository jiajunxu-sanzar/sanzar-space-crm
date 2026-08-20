"""Usuarios — alta, baja y roles (solo admin).

También expone un diagnóstico del esquema y de la telemetría: cuando algo va
lento o una pestaña no aparece, aquí se ve por qué sin abrir los logs.
"""

from __future__ import annotations

import streamlit as st

from app.cache import users_service
from app.navigation import KNOWN_APP_ROLES, ROLE_LABELS, normalize_role
from app.state import bump_data_cache
from app.telemetry import recent_events
from config.settings import CONFIG
from services.dataset import SpaceDataset
from services.users_service import AppUser
from ui.components.kpi import Kpi, render_kpi_row
from ui.components.page_header import render_page_header

_ROLE_OPTIONS = sorted(KNOWN_APP_ROLES)


def render(dataset: SpaceDataset, user: AppUser, users: tuple[AppUser, ...]) -> None:
    render_page_header("Usuarios")

    active = [item for item in users if item.activo]
    render_kpi_row(
        [
            Kpi("Usuarios activos", len(active), f"de {len(users)} en la hoja"),
            Kpi("Administradores", sum(1 for item in active if item.role == "admin")),
            Kpi("Compras", sum(1 for item in active if item.role == "comprador")),
            Kpi("Comercial", sum(1 for item in active if item.role == "comercial")),
        ]
    )

    tab_manage, tab_new, tab_diag = st.tabs(["Gestionar", "Nuevo usuario", "Diagnóstico"])

    with tab_manage:
        _render_manage(users, user)
    with tab_new:
        _render_new(users)
    with tab_diag:
        _render_diagnostics(dataset)


def _render_manage(users: tuple[AppUser, ...], current: AppUser) -> None:
    if not users:
        st.info("La hoja «Usuarios» está vacía.")
        return

    labels = {f"{item.nombre} ({item.employee_id})": item for item in users}
    choice = st.selectbox("Usuario", list(labels.keys()), key="users_pick")
    target = labels[choice]

    if target.employee_id == current.employee_id:
        st.caption("Estás editando tu propio usuario.")

    # Las keys llevan el id del usuario: con keys fijas, Streamlit ignora el
    # `value=` en cuanto el widget ya existe y el formulario seguiría mostrando
    # —y guardando— los datos del usuario anterior. Ese bug escribiría el rol de
    # uno sobre otro sin ningún aviso.
    suffix = target.employee_id
    with st.form(f"edit_user_form_{suffix}"):
        c1, c2 = st.columns(2)
        nombre = c1.text_input("Nombre *", value=target.nombre, key=f"eu_nombre_{suffix}")
        rol = c2.selectbox(
            "Rol *",
            _ROLE_OPTIONS,
            index=_ROLE_OPTIONS.index(normalize_role(target.role)),
            format_func=lambda value: f"{ROLE_LABELS.get(value, value)} ({value})",
            key=f"eu_rol_{suffix}",
        )
        c3, c4 = st.columns(2)
        password = c3.text_input("Contraseña *", value=target.password, key=f"eu_password_{suffix}")
        activo = c4.toggle("Activo", value=target.activo, key=f"eu_activo_{suffix}")
        notas = st.text_input("Notas", value=target.notas, key=f"eu_notas_{suffix}")
        submitted = st.form_submit_button("Guardar cambios", type="primary", width="stretch")

    if not submitted:
        return

    result = users_service().update_user(
        users,
        target.employee_id,
        nombre=nombre,
        rol=rol,
        password=password,
        activo=activo,
        notas=notas,
    )
    if not result.ok:
        st.error(result.message)
        return

    bump_data_cache()
    st.toast(result.message, icon="✅")
    st.rerun()


def _render_new(users: tuple[AppUser, ...]) -> None:
    with st.form("new_user_form", clear_on_submit=True):
        c1, c2 = st.columns(2)
        nombre = c1.text_input("Nombre *", key="nu_nombre")
        rol = c2.selectbox(
            "Rol *",
            _ROLE_OPTIONS,
            index=_ROLE_OPTIONS.index("comprador"),
            format_func=lambda value: f"{ROLE_LABELS.get(value, value)} ({value})",
            key="nu_rol",
        )
        c3, c4 = st.columns(2)
        password = c3.text_input("Contraseña *", key="nu_password")
        activo = c4.toggle("Activo", value=True, key="nu_activo")
        notas = st.text_input("Notas", key="nu_notas")
        submitted = st.form_submit_button("Crear usuario", type="primary", width="stretch")

    if not submitted:
        return

    result = users_service().create_user(
        users, nombre=nombre, rol=rol, password=password, activo=activo, notas=notas
    )
    if not result.ok:
        st.error(result.message)
        return

    bump_data_cache()
    st.toast(result.message, icon="✅")
    st.rerun()


def _render_diagnostics(dataset: SpaceDataset) -> None:
    report = st.session_state.get("_schema_report_summary", "")
    if report:
        st.info(report, icon=":material/table_chart:")

    st.markdown("###### Conexión")
    sheet_id = CONFIG.google_sheet_id
    st.markdown(
        f"- Hoja de cálculo: `{sheet_id or 'sin configurar'}`\n"
        f"- Credenciales: `{CONFIG.google_service_account_path}`\n"
        f"- TTL de caché: {CONFIG.data_cache_ttl_seconds}s · "
        f"poll de cambios: {CONFIG.remote_sync_poll_seconds}s"
    )

    st.markdown("###### Volumen de datos")
    st.markdown(
        f"- Productos: {len(dataset.products)} ({len(dataset.active_products())} activos)\n"
        f"- Suministradores: {len(dataset.suppliers)}\n"
        f"- Relaciones: {len(dataset.relations)}\n"
        f"- Conversaciones: {len(dataset.conversations)}\n"
        f"- Precios: {len(dataset.quotes)}"
    )

    st.markdown("###### Últimas operaciones (latencia real)")
    events = recent_events(15)
    if not events:
        st.caption("Todavía no hay eventos en esta sesión.")
        return
    st.dataframe(
        [
            {
                "operación": event["name"],
                "ms": event["duration_ms"],
                "ok": event["success"],
            }
            for event in reversed(events)
        ],
        hide_index=True,
        width="stretch",
    )
