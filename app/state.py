"""Estado de sesión: valores por defecto, invalidación de caché y navegación.

La caché de datos se invalida con un **contador de versión** en
``session_state`` que se pasa como argumento a los loaders cacheados
(``load_dataset_cached(version)``). Incrementar el contador invalida la entrada
de ``@st.cache_data`` sin borrar toda la caché ni tocar el estado de UI.
"""

from __future__ import annotations

from typing import Any, Final

import streamlit as st

from app.navigation import HOME_PAGE

DATA_CACHE_VERSION_KEY: Final[str] = "data_cache_version"

SELECTED_SUPPLIER_KEY: Final[str] = "selected_supplier_id"
SELECTED_PRODUCT_KEY: Final[str] = "selected_product_id"
PENDING_NAV_KEY: Final[str] = "pending_nav_page"
WRITE_STATUS_KEY: Final[str] = "write_status"

DEFAULT_STATE: Final[dict[str, Any]] = {
    "active_page": HOME_PAGE,
    PENDING_NAV_KEY: "",
    SELECTED_SUPPLIER_KEY: "",
    SELECTED_PRODUCT_KEY: "",
    DATA_CACHE_VERSION_KEY: 0,
    "sup_filtro_productos": [],
    "sup_filtro_paises": [],
    "sup_mostrar_descartados": False,
    "sup_busqueda": "",
    # Claves de auth — gestionadas solo vía ``app.auth``, nunca como key de widget.
    "_authenticated_user_id": "",
    "auth_ok": False,
    "login_error": "",
    "active_modal": None,
}


def init_state() -> None:
    for key, value in DEFAULT_STATE.items():
        if key not in st.session_state:
            st.session_state[key] = list(value) if isinstance(value, list) else value


# --- Invalidación de caché ------------------------------------------------


def data_version() -> int:
    return int(st.session_state.get(DATA_CACHE_VERSION_KEY, 0))


def bump_data_cache() -> None:
    """Marca los datos como obsoletos: la próxima lectura vuelve a Sheets."""
    st.session_state[DATA_CACHE_VERSION_KEY] = data_version() + 1


def soft_reload_data() -> None:
    """Vacía la caché de datos conservando filtros, selección y diálogos."""
    from app.cache import clear_data_cache

    clear_data_cache()
    bump_data_cache()


def hard_refresh_preserving_auth(*, extra_keep: dict[str, object] | None = None) -> None:
    """Limpia toda la sesión manteniendo el login (botón «Reiniciar»)."""
    from app.cache import clear_data_cache

    keep: dict[str, object] = {
        "_authenticated_user_id": str(st.session_state.get("_authenticated_user_id", "")),
        "auth_ok": bool(st.session_state.get("auth_ok", False)),
        "login_error": "",
    }
    if extra_keep:
        keep.update(extra_keep)
    for key in list(st.session_state.keys()):
        st.session_state.pop(key, None)
    for key, value in keep.items():
        st.session_state[key] = value
    clear_data_cache()
    init_state()


# --- Navegación y selección ----------------------------------------------


def go_to(page: str) -> None:
    """Pide navegar a otra página en el próximo rerun."""
    st.session_state[PENDING_NAV_KEY] = str(page or "")


def select_supplier(supplier_id: str, *, product_id: str = "", navigate: bool = True) -> None:
    """Abre la ficha de un suministrador (opcionalmente enfocando un producto)."""
    from app.navigation import SUMINISTRADORES_PAGE

    st.session_state[SELECTED_SUPPLIER_KEY] = str(supplier_id or "")
    if product_id:
        st.session_state[SELECTED_PRODUCT_KEY] = str(product_id)
    if navigate:
        go_to(SUMINISTRADORES_PAGE)


def select_product(product_id: str) -> None:
    """Abre la ficha de un producto; limpia el suministrador para no mezclar fichas."""
    st.session_state[SELECTED_PRODUCT_KEY] = str(product_id or "")
    st.session_state[SELECTED_SUPPLIER_KEY] = ""


def selected_supplier_id() -> str:
    return str(st.session_state.get(SELECTED_SUPPLIER_KEY, "") or "")


def selected_product_id() -> str:
    return str(st.session_state.get(SELECTED_PRODUCT_KEY, "") or "")


def clear_selected_supplier() -> None:
    st.session_state[SELECTED_SUPPLIER_KEY] = ""
    st.session_state[SELECTED_PRODUCT_KEY] = ""


def clear_selected_product() -> None:
    st.session_state[SELECTED_PRODUCT_KEY] = ""


# --- Feedback de escritura ------------------------------------------------


def set_write_status(status: str, message: str = "") -> None:
    st.session_state[WRITE_STATUS_KEY] = {"status": str(status or ""), "message": str(message or "")}


def pop_write_status() -> dict[str, str]:
    raw = st.session_state.pop(WRITE_STATUS_KEY, {})
    if isinstance(raw, dict):
        return {"status": str(raw.get("status", "")), "message": str(raw.get("message", ""))}
    return {"status": "", "message": ""}
