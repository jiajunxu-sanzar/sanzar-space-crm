"""Fila de KPIs — la primera línea de cualquier página con datos.

Se pinta como una única parrilla CSS (``grid``), no como ``st.columns``: así el
número de tarjetas por fila se adapta al ancho real de la ventana en vez de
quedar fijado desde Python, y la animación de entrada escalonada es coherente.
"""

from __future__ import annotations

import html
from dataclasses import dataclass
from typing import Literal

import streamlit as st

Tone = Literal["neutral", "success", "warning", "danger", "info"]


@dataclass(frozen=True, slots=True)
class Kpi:
    label: str
    value: str | int
    hint: str = ""
    tone: Tone = "neutral"

    def to_html(self) -> str:
        modifier = f" space-kpi--{self.tone}" if self.tone != "neutral" else ""
        hint = (
            f"<div class='space-kpi-hint'>{html.escape(self.hint)}</div>" if self.hint else ""
        )
        return (
            f"<div class='space-kpi{modifier}'>"
            f"<div class='space-kpi-label'>{html.escape(self.label)}</div>"
            f"<div class='space-kpi-value'>{html.escape(str(self.value))}</div>"
            f"{hint}"
            "</div>"
        )


def render_kpi_row(kpis: list[Kpi]) -> None:
    if not kpis:
        return
    st.markdown(
        f"<div class='space-kpi-row'>{''.join(kpi.to_html() for kpi in kpis)}</div>",
        unsafe_allow_html=True,
    )


def tone_for_pending(count: int) -> Tone:
    """Rojo si hay algo vencido, ámbar si hay trabajo, neutro si está limpio."""
    if count <= 0:
        return "success"
    return "danger" if count > 0 else "neutral"
