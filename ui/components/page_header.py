"""Cabecera de página consistente (título + descripción) para todas las pestañas.

Patrón único estilo Linear/Attio: título limpio sin emoji, subtítulo muted y
separación regular. El icono vive solo en la navegación lateral.
"""

from __future__ import annotations

import html

import streamlit as st

from app.navigation import PAGE_DESCRIPTIONS


def render_page_header(page: str, *, description: str | None = None) -> None:
    """Pinta la cabecera estándar.

    Args:
        page: clave canónica de ``app.navigation.PAGES``.
        description: subtítulo alternativo; por defecto el de ``PAGE_DESCRIPTIONS``.
    """
    desc = description if description is not None else PAGE_DESCRIPTIONS.get(page, "")
    desc_html = f"<p class='space-page-desc'>{html.escape(desc)}</p>" if desc else ""
    st.markdown(
        "<div class='space-page-header'>"
        f"<h1 class='space-page-title'>{html.escape(page)}</h1>"
        f"{desc_html}"
        "</div>",
        unsafe_allow_html=True,
    )


def render_coming_soon(title: str, body: str) -> None:
    """Aviso «Próximamente» de las páginas reservadas (§3.4 y §3.5)."""
    st.markdown(
        "<div class='space-soon'>"
        f"<div class='space-soon-title'>{html.escape(title)}</div>"
        f"<p class='space-soon-text'>{html.escape(body)}</p>"
        "</div>",
        unsafe_allow_html=True,
    )


def render_empty_state(message: str) -> None:
    st.markdown(
        f"<div class='space-empty'>{html.escape(message)}</div>", unsafe_allow_html=True
    )
