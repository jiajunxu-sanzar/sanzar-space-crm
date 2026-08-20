"""Chips de estado — el vocabulario visual compartido por toda la app.

Un chip es un ``<span>`` con fondo/borde/texto derivados de ``ui/palette.py``.
Todo lo que se pinta pasa por ``html.escape``: el contenido viene de una hoja de
cálculo que edita gente, y una celda con ``<script>`` no debe poder ejecutarse.
"""

from __future__ import annotations

import html

import streamlit as st

from ui.palette import (
    StatusStyle,
    STATUS_NEUTRAL,
    action_due_style,
    conversation_style,
    price_style,
    supplier_state_style,
    validity_style,
)


def chip_html(text: str, style: StatusStyle = STATUS_NEUTRAL, *, icon: str = "") -> str:
    """Devuelve el HTML del chip (para componerlo dentro de otro bloque)."""
    label = html.escape(str(text or "").strip())
    if not label:
        return ""
    prefix = f"{html.escape(icon)} " if icon else ""
    return f"<span class='space-chip' style='{style.css()}'>{prefix}{label}</span>"


def chip(text: str, style: StatusStyle = STATUS_NEUTRAL, *, icon: str = "") -> None:
    markup = chip_html(text, style, icon=icon)
    if markup:
        st.markdown(markup, unsafe_allow_html=True)


def chip_row(chips: list[str]) -> None:
    """Fila de chips ya renderizados a HTML (los vacíos se descartan)."""
    visible = [markup for markup in chips if markup]
    if not visible:
        return
    st.markdown(
        f"<div class='space-chip-row'>{''.join(visible)}</div>", unsafe_allow_html=True
    )


# --- Atajos semánticos ----------------------------------------------------


def supplier_state_chip_html(estado: str) -> str:
    return chip_html(estado, supplier_state_style(estado))


def conversation_chip_html(tipo: str) -> str:
    return chip_html(tipo, conversation_style(tipo))


def price_chip_html(text: str, *, is_winner: bool = False, is_expired: bool = False) -> str:
    return chip_html(text, price_style(is_winner=is_winner, is_expired=is_expired))


def validity_chip_html(validez_fecha: str) -> str:
    if not str(validez_fecha or "").strip():
        return ""
    return chip_html(f"Válida hasta {validez_fecha}", validity_style(validez_fecha))


def action_chip_html(label: str, fecha: str, estado_accion: str = "") -> str:
    return chip_html(label, action_due_style(fecha, estado_accion))
