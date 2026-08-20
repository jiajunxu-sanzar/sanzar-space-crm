"""Rejilla de campos etiqueta/valor para las fichas.

Un solo bloque HTML en vez de ``st.columns`` anidadas: menos nodos, menos
reflow, y las columnas se reorganizan solas según el ancho disponible.
"""

from __future__ import annotations

import html

import streamlit as st

_EMPTY = "—"


def _value_html(value: str, *, link: bool = False) -> str:
    text = str(value or "").strip()
    if not text:
        return f"<span style='color:var(--ui-text-muted)'>{_EMPTY}</span>"
    if link and (text.startswith("http://") or text.startswith("https://")):
        safe = html.escape(text, quote=True)
        # rel=noopener: una URL que viene de una hoja de cálculo es contenido
        # externo; nunca debe recibir acceso a la ventana de la app.
        return f"<a href='{safe}' target='_blank' rel='noopener noreferrer'>{html.escape(text)}</a>"
    return html.escape(text)


def render_field_grid(fields: list[tuple[str, str]], *, links: bool = False) -> None:
    """Pinta [(etiqueta, valor)] como rejilla responsive."""
    if not fields:
        return
    cells = "".join(
        "<div>"
        f"<div class='space-field-label'>{html.escape(label)}</div>"
        f"<div class='space-field-value'>{_value_html(value, link=links)}</div>"
        "</div>"
        for label, value in fields
    )
    st.markdown(f"<div class='space-field-grid'>{cells}</div>", unsafe_allow_html=True)


def render_detail_header(
    *,
    initials: str,
    title: str,
    meta: str = "",
    chips_html: str = "",
) -> None:
    """Cabecera de la ficha del suministrador: avatar, nombre, metadatos y chips."""
    meta_block = (
        f"<div class='space-detail-meta'>{html.escape(meta)}</div>" if meta else ""
    )
    chips_block = (
        f"<div class='space-chip-row' style='margin-top:8px'>{chips_html}</div>"
        if chips_html
        else ""
    )
    st.markdown(
        "<div class='space-detail-header'>"
        f"<div class='space-detail-avatar'>{html.escape(initials)}</div>"
        "<div style='min-width:0'>"
        f"<div class='space-detail-name'>{html.escape(title)}</div>"
        f"{meta_block}{chips_block}"
        "</div></div>",
        unsafe_allow_html=True,
    )
