"""Estado de modales centralizado.

Todo el estado de "qué diálogo está abierto" vive bajo **una sola** clave de
``session_state``. Así cualquier botón de navegación puede llamar a
``close_modal()`` una vez y tener la garantía de que no reaparece un modal
obsoleto en el siguiente rerun.

Valores posibles de la clave:

    None                                          → nada abierto
    {"type": "nuevo_suministrador"}
    {"type": "nuevo_producto"}
    {"type": "editar_producto", "product_id": str}
    {"type": "nueva_conversacion", "supplier_id": str}
    {"type": "nuevo_precio",       "supplier_id": str}
    {"type": "editar_relacion",    "supplier_id": str, "rel_id": str}
    {"type": "editar_conversacion","supplier_id": str, "row_id": str}
    {"type": "editar_precio",      "supplier_id": str, "row_id": str}
"""

from __future__ import annotations

from typing import Any

import streamlit as st

_MODAL_KEY = "active_modal"


# --- Abrir ----------------------------------------------------------------


def open_modal(modal_type: str, **payload: Any) -> None:
    st.session_state[_MODAL_KEY] = {"type": str(modal_type), **payload}


def open_nuevo_suministrador() -> None:
    open_modal("nuevo_suministrador")


def open_nuevo_producto() -> None:
    open_modal("nuevo_producto")


def open_editar_producto(product_id: str) -> None:
    open_modal("editar_producto", product_id=str(product_id))


def open_nueva_conversacion(supplier_id: str) -> None:
    open_modal("nueva_conversacion", supplier_id=str(supplier_id))


def open_nuevo_precio(supplier_id: str) -> None:
    open_modal("nuevo_precio", supplier_id=str(supplier_id))


def open_editar_relacion(supplier_id: str, rel_id: str) -> None:
    open_modal("editar_relacion", supplier_id=str(supplier_id), rel_id=str(rel_id))


def open_editar_conversacion(supplier_id: str, row_id: str) -> None:
    open_modal("editar_conversacion", supplier_id=str(supplier_id), row_id=str(row_id))


def open_editar_precio(supplier_id: str, row_id: str) -> None:
    open_modal("editar_precio", supplier_id=str(supplier_id), row_id=str(row_id))


# --- Cerrar / leer --------------------------------------------------------


def close_modal() -> None:
    """Cierra cualquier modal. Seguro de llamar aunque no haya nada abierto."""
    st.session_state[_MODAL_KEY] = None


def get_active_modal() -> dict[str, Any] | None:
    modal = st.session_state.get(_MODAL_KEY)
    return modal if isinstance(modal, dict) else None


def is_open(modal_type: str, **must_match: Any) -> bool:
    """True si el modal abierto es de ese tipo y coincide en las claves dadas."""
    modal = get_active_modal()
    if not modal or modal.get("type") != modal_type:
        return False
    return all(str(modal.get(key, "")) == str(value) for key, value in must_match.items())


def field(name: str, default: str = "") -> str:
    """Lee un campo del modal activo (p. ej. ``field("rel_id")``)."""
    modal = get_active_modal() or {}
    return str(modal.get(name, default) or default)
