"""Sanzar Space CRM — punto de entrada.

Responsabilidades de este fichero, y solo estas:

1. Configurar la página y aplicar el tema.
2. Preparar el esquema del Excel **una vez por proceso** (no en cada rerun: en
   el CRM de clientes eso fue una fuga silenciosa de cuota de la API).
3. Autenticar contra la hoja `Usuarios` y pintar la navegación por rol.
4. Cargar el dataset (una sola llamada a la API) y delegar en la página activa.

Toda la lógica vive en ``services/``; toda la presentación, en ``views/`` y
``ui/``.
"""

from __future__ import annotations

import html

import streamlit as st

from app import auth
from app.cache import (
    clear_dataset_error,
    dataset_error,
    load_dataset,
    load_users_frame_cached,
    sheets_service,
)
from app.navigation import (
    ACCIONES_PAGE,
    COMPRAS_PAGE,
    HOME_PAGE,
    OFERTAS_PAGE,
    PAGE_ICONS,
    PAGES_REQUIRING_DATA,
    ROLE_ADMIN,
    ROLE_LABELS,
    SUMINISTRADORES_PAGE,
    USUARIOS_PAGE,
    can_view,
    nav_sections_for_role,
    normalize_role,
    pages_for_role,
)
from app.remote_sync import check_remote_changes, reset_remote_sync_state
from app.state import (
    PENDING_NAV_KEY,
    clear_selected_supplier,
    data_version,
    hard_refresh_preserving_auth,
    init_state,
    soft_reload_data,
)
from config.settings import APP_NAME, APP_TAGLINE, CONFIG
from services.actions_stats import pending_actions, summarize_actions
from services.dataset import SpaceDataset
from services.schema import ensure_schema
from services.users_service import AppUser, active_users, seed_users_if_empty, users_from_frame
from ui import modal_state
from ui.theme import apply_theme
from views import acciones, compras, home, ofertas, suministradores, users as users_page

st.set_page_config(page_title=APP_NAME, page_icon="🏭", layout="wide")
apply_theme()
init_state()


# ---------------------------------------------------------------------------
# Esquema — una vez por proceso
# ---------------------------------------------------------------------------


@st.cache_resource(show_spinner=False)
def _ensure_schema_once() -> str:
    """Crea/repara pestañas y columnas. Devuelve el resumen para Diagnóstico."""
    return ensure_schema(sheets_service()).summary()


if CONFIG.google_sheet_id:
    try:
        st.session_state["_schema_report_summary"] = _ensure_schema_once()
    except Exception as exc:  # noqa: BLE001 — nunca bloquear el arranque
        st.session_state["_schema_report_summary"] = f"No se pudo preparar el esquema: {exc}"


def _page_key_slug(page: str) -> str:
    """Clave estable y segura para widgets/CSS a partir del nombre de página."""
    return "".join(char if char.isalnum() else "_" for char in page).lower()


# Prefijos de las keys de los formularios modales. Se limpian al cambiar de
# página para que un formulario a medio rellenar no reaparezca en otra pestaña.
_FORM_KEY_PREFIXES = ("ns_", "np_", "nc_", "nq_", "ar_", "er_", "es_", "ep_", "ec_", "eq_", "eu_", "nu_")


def _close_all_overlays() -> None:
    """Cierra cualquier overlay al cambiar de página: nada debe sobrevivir al salto."""
    modal_state.close_modal()
    for key in list(st.session_state.keys()):
        if key.startswith(_FORM_KEY_PREFIXES):
            st.session_state.pop(key, None)


def _load_users() -> tuple[tuple[AppUser, ...], str]:
    """(usuarios, error) desde la hoja `Usuarios`, sembrando un admin si está vacía.

    Devuelve el error en vez de pintarlo: quien llama decide dónde mostrarlo, y
    así un fallo de la API no se confunde con «la hoja no tiene usuarios».

    Va por la caché versionada: si no, cada clic de cualquier usuario costaría
    una lectura extra a la Sheets API solo para repintar la barra lateral.
    """
    try:
        frame = load_users_frame_cached(data_version())
    except Exception as exc:  # noqa: BLE001
        return (), str(exc)
    return (seed_users_if_empty(sheets_service(), frame) or users_from_frame(frame)), ""


# ---------------------------------------------------------------------------
# Arranque: marca, comprobaciones bloqueantes y login
#
# Todo esto se pinta en el ÁREA PRINCIPAL, no en la barra lateral. Un login (o
# peor, un error de configuración) escondido en el sidebar deja el lienzo en
# blanco, y una pantalla en blanco no se lee como «falta iniciar sesión»: se lee
# como «esto está roto».
# ---------------------------------------------------------------------------

_BRAND_HTML = (
    "<div class='space-brand'>"
    "<div class='space-brand-mark'>S</div>"
    f"<div><div class='space-brand-name'>{APP_NAME}</div>"
    f"<div class='space-brand-sub'>{APP_TAGLINE}</div></div>"
    "</div>"
)


def _centered_card(key: str):
    """Columna central estrecha con la tarjeta de arranque."""
    _, middle, _ = st.columns([1, 1.25, 1])
    return middle, key


def _boot_screen(title: str, body_html: str, *, detail: str = "") -> None:
    """Pantalla de arranque bloqueante (error de configuración). Termina el script."""
    middle, key = _centered_card("space_boot_card")
    with middle:
        with st.container(key=key):
            st.markdown(_BRAND_HTML, unsafe_allow_html=True)
            st.markdown(
                f"<h1 class='space-login-heading'>{html.escape(title)}</h1>"
                f"<p class='space-login-help'>{body_html}</p>",
                unsafe_allow_html=True,
            )
            if detail:
                st.code(detail, language=None)
    st.stop()


def _render_login(user_by_id: dict[str, AppUser]) -> None:
    """Pantalla de login centrada. Termina el script si no se autentica."""
    middle, key = _centered_card("space_login_card")
    with middle:
        with st.container(key=key):
            st.markdown(_BRAND_HTML, unsafe_allow_html=True)
            st.markdown(
                "<h1 class='space-login-heading'>Inicia sesión</h1>"
                "<p class='space-login-help'>Selecciona tu usuario e introduce "
                "la contraseña.</p>",
                unsafe_allow_html=True,
            )
            with st.form("login_form", clear_on_submit=False):
                # Clave DISTINTA de la de auth: así la maquinaria de widgets de
                # Streamlit no puede sobrescribir quién está logueado.
                login_user = st.selectbox(
                    "Usuario",
                    list(user_by_id.keys()),
                    format_func=lambda uid: user_by_id[uid].nombre,
                    key="_login_user_select",
                )
                password = st.text_input(
                    "Contraseña", type="password", key="_login_password_input"
                )
                submitted = st.form_submit_button(
                    "Entrar", width="stretch", type="primary"
                )

            if submitted:
                candidate = user_by_id.get(login_user)
                if candidate and password == candidate.password:
                    auth.login(login_user)
                    st.rerun()
                st.session_state["login_error"] = "Contraseña incorrecta."

            if st.session_state.get("login_error"):
                st.error(st.session_state["login_error"])
    st.stop()


with st.sidebar:
    st.markdown(_BRAND_HTML, unsafe_allow_html=True)

if not CONFIG.google_sheet_id:
    _boot_screen(
        "Falta configurar la hoja",
        "No hay <code>GOOGLE_SHEET_ID</code>. Copia <code>.env.example</code> a "
        "<code>.env</code> y pega ahí el link de tu hoja de Google Sheets.",
    )

app_users, users_error = _load_users()
app_users = active_users(app_users)

if users_error:
    _boot_screen(
        "No se pudo leer la hoja",
        "La app no ha podido abrir la pestaña <b>Usuarios</b> del Google Sheet. "
        "Comprueba que la hoja está compartida como <b>Editor</b> con el "
        "<code>client_email</code> del service account y que el ID del "
        "<code>.env</code> es el correcto.",
        detail=users_error,
    )

if not app_users:
    _boot_screen(
        "No hay usuarios con acceso",
        "La pestaña <b>Usuarios</b> no tiene ninguna fila activa. Añade una con "
        "rol <code>admin</code>, o deja la pestaña vacía y reinicia la app para "
        "que cree el usuario inicial.",
    )

user_by_id = {item.employee_id: item for item in app_users}

# --- Guardia de autenticación ---
# Se comprueba el flag Y que el id siga existiendo: si la hoja cambió bajo
# nuestros pies, cerramos sesión limpiamente en vez de cambiar de usuario en
# silencio.
authenticated_id = auth.get_authenticated_user_id()
if not auth.is_authenticated() or authenticated_id not in user_by_id:
    if authenticated_id and authenticated_id not in user_by_id:
        auth.logout()
    _render_login(user_by_id)

# --- Autenticado a partir de aquí ---
current_user = user_by_id[auth.get_authenticated_user_id()]
role = normalize_role(current_user.role)


# ---------------------------------------------------------------------------
# Sidebar: usuario, navegación por rol y utilidades
# ---------------------------------------------------------------------------

with st.sidebar:
    st.markdown(
        "<div class='space-user-chip'>"
        f"<div class='space-user-avatar'>{current_user.initials}</div>"
        f"<div style='min-width:0'><div class='space-user-name'>{current_user.nombre}</div>"
        f"<div class='space-user-role'>{ROLE_LABELS.get(role, role)}</div></div>"
        "</div>",
        unsafe_allow_html=True,
    )

    available_pages = pages_for_role(role)

    pending_nav = str(st.session_state.get(PENDING_NAV_KEY, "") or "")
    if pending_nav in available_pages:
        st.session_state["active_page"] = pending_nav
    st.session_state[PENDING_NAV_KEY] = ""

    active_page = st.session_state.get("active_page", available_pages[0])
    if active_page not in available_pages:
        active_page = available_pages[0]

    with st.container(key="space_nav"):
        for section_title, section_pages in nav_sections_for_role(role):
            st.markdown(
                f"<p class='space-nav-section'>{section_title}</p>", unsafe_allow_html=True
            )
            for nav_page in section_pages:
                is_active = nav_page == active_page
                if (
                    st.button(
                        nav_page,
                        key=f"nav_btn_{_page_key_slug(nav_page)}",
                        icon=PAGE_ICONS.get(nav_page),
                        type="primary" if is_active else "tertiary",
                        width="stretch",
                    )
                    and not is_active
                ):
                    st.session_state["active_page"] = nav_page
                    st.rerun()

    page = active_page
    if st.session_state.get("_last_page", page) != page:
        _close_all_overlays()
        # Si el salto lo pidió la propia app (p. ej. «Ver ficha» desde Home),
        # la selección ES el motivo del salto y no debe limpiarse; solo se
        # limpia cuando el usuario cambia de pestaña por su cuenta.
        if pending_nav != page:
            clear_selected_supplier()
    st.session_state["_last_page"] = page
    st.session_state["active_page"] = page

    st.markdown("<hr class='space-sidebar-divider'/>", unsafe_allow_html=True)

    reload_col, reset_col = st.columns(2, gap="small")
    if reload_col.button(
        "Recargar",
        key="nav_util_reload",
        icon=":material/refresh:",
        width="stretch",
        help="Vuelve a leer desde Google Sheets sin perder filtros ni selección.",
    ):
        soft_reload_data()
        reset_remote_sync_state()
        clear_dataset_error()
        st.toast("Datos recargados", icon="✅")
        st.rerun()

    if reset_col.button(
        "Reiniciar",
        key="nav_util_reset",
        icon=":material/mop:",
        width="stretch",
        help="Limpia toda la sesión (filtros, selección, diálogos) manteniendo el login.",
    ):
        _close_all_overlays()
        hard_refresh_preserving_auth()
        reset_remote_sync_state()
        st.toast("Sesión reiniciada", icon="🧹")
        st.rerun()

    if st.button("Cerrar sesión", key="nav_util_logout", icon=":material/logout:", width="stretch"):
        auth.logout()
        st.rerun()


# ---------------------------------------------------------------------------
# Datos y despacho de página
# ---------------------------------------------------------------------------

if check_remote_changes():
    st.toast("Datos actualizados desde el Excel", icon="🔄")

if page in PAGES_REQUIRING_DATA:
    version = data_version()
    seen_key = "_dataset_seen_version"
    is_cache_miss = st.session_state.get(seen_key) != version
    # El spinner solo aparece si la lectura va a tocar Sheets de verdad: en un
    # acierto de caché la operación es instantánea y el parpadeo se percibe
    # como lentitud.
    if is_cache_miss:
        with st.spinner("Cargando datos…"):
            dataset = load_dataset(version)
    else:
        dataset = load_dataset(version)
    st.session_state[seen_key] = version

    error = dataset_error()
    if error:
        st.error(f"No se pudieron cargar los datos de Google Sheets: {error}")
else:
    dataset = SpaceDataset.empty()

# Defensa en profundidad: la navegación ya oculta lo que no toca, pero una
# página nunca debe fiarse solo de que el menú la haya escondido.
if not can_view(role, page):
    st.error("No tienes permisos para ver esta sección.")
    st.stop()

if page == HOME_PAGE:
    home.render(dataset, current_user)
elif page == ACCIONES_PAGE:
    acciones.render(dataset, current_user)
elif page == SUMINISTRADORES_PAGE:
    suministradores.render(dataset, current_user, app_users)
elif page == COMPRAS_PAGE:
    compras.render(dataset, current_user)
elif page == OFERTAS_PAGE:
    ofertas.render(dataset, current_user)
elif page == USUARIOS_PAGE:
    if role != ROLE_ADMIN:
        st.error("La sección Usuarios solo está disponible para administradores.")
        st.stop()
    users_page.render(dataset, current_user, app_users)

# Aviso discreto en la portada si el usuario tiene trabajo vencido.
if page == HOME_PAGE and not dataset.is_empty:
    overdue = summarize_actions(pending_actions(dataset, persona=current_user.nombre)).vencidas
    if overdue:
        st.toast(f"Tienes {overdue} acción(es) vencida(s).", icon="⏰")
