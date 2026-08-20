"""API de estado de autenticación.

Toda la sesión del usuario logueado se gestiona aquí. La clave
``_authenticated_user_id`` NUNCA se usa como ``key`` de un widget de Streamlit,
para que la maquinaria de widgets no pueda sobrescribir quién está logueado
(mismo blindaje que en ``sanzar-crm-web``).
"""

from __future__ import annotations

import streamlit as st

_AUTH_KEY = "_authenticated_user_id"

# Estado efímero de UI que jamás debe sobrevivir a un login/logout.
_TRANSIENT_UI_KEYS = (
    "selected_supplier_id",
    "selected_product_id",
    "write_status",
    "pending_nav_page",
)


def _clear_transient_ui_state() -> None:
    for key in _TRANSIENT_UI_KEYS:
        st.session_state.pop(key, None)
    try:
        from ui import modal_state

        modal_state.close_modal()
    except Exception:
        # El reset de auth debe ser resiliente aunque la UI no esté disponible.
        pass


def login(user_id: str) -> None:
    """Marca un usuario como autenticado. Llamar antes de ``st.rerun()``."""
    _clear_transient_ui_state()
    st.session_state[_AUTH_KEY] = str(user_id)
    st.session_state["auth_ok"] = True
    st.session_state["login_error"] = ""


def logout() -> None:
    """Limpia el estado de auth. Llamar antes de ``st.rerun()``."""
    _clear_transient_ui_state()
    st.session_state[_AUTH_KEY] = ""
    st.session_state["auth_ok"] = False
    st.session_state["login_error"] = ""


def get_authenticated_user_id() -> str:
    return str(st.session_state.get(_AUTH_KEY, "") or "")


def is_authenticated() -> bool:
    """True solo si el flag está activo Y hay un ``employee_id`` guardado."""
    return bool(st.session_state.get("auth_ok", False)) and bool(get_authenticated_user_id())
