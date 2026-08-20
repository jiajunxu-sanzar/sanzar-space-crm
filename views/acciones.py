"""Acciones — bandeja de trabajo personal (§3.2).

Todas las entradas de `HistoricoConversaciones` cuya ``proxima_accion_persona``
sea el usuario logueado, ordenadas por fecha con las **vencidas primero**. Un
admin puede quitar el filtro de persona y ver el trabajo de todo el equipo.

Cada fila enlaza a la ficha del suministrador; completar la acción se hace
editando la conversación desde esa ficha.
"""

from __future__ import annotations

import html

import streamlit as st

from app.navigation import ROLE_ADMIN, normalize_role
from app.state import select_supplier
from services.actions_stats import (
    ActionItem,
    BUCKET_LABELS,
    group_by_bucket,
    pending_actions,
    people_with_actions,
    summarize_actions,
)
from services.dataset import SpaceDataset
from services.users_service import AppUser
from ui.components.chips import chip_html
from ui.components.kpi import Kpi, render_kpi_row
from ui.components.page_header import render_empty_state, render_page_header
from ui.palette import STATUS_NEUTRAL, action_bucket_style

_TODOS = "— Todo el equipo —"


def render(dataset: SpaceDataset, user: AppUser) -> None:
    render_page_header("Acciones")

    is_admin = normalize_role(user.role) == ROLE_ADMIN
    persona = _render_person_filter(dataset, user, is_admin=is_admin)

    items = pending_actions(dataset, persona=persona)
    stats = summarize_actions(items)

    render_kpi_row(
        [
            Kpi("Vencidas", stats.vencidas, "Lo primero de la lista", tone="danger" if stats.vencidas else "success"),
            Kpi("Hoy", stats.hoy, tone="warning" if stats.hoy else "neutral"),
            Kpi("Próximos 7 días", stats.proximos_7, tone="info"),
            Kpi("Sin fecha", stats.sin_fecha, "Pendientes sin plazo asignado"),
        ]
    )

    if not items:
        who = "nadie del equipo" if not persona else f"«{persona}»"
        render_empty_state(f"No hay ninguna acción pendiente asignada a {who}. Todo al día.")
        return

    for bucket, rows in group_by_bucket(items):
        style = action_bucket_style(bucket.value)
        st.markdown(
            f"<div style='margin:18px 0 8px'>"
            f"<span class='space-chip' style='{style.css()}'>"
            f"{html.escape(BUCKET_LABELS[bucket])} · {len(rows)}</span></div>",
            unsafe_allow_html=True,
        )
        for position, item in enumerate(rows):
            _render_action_row(item, show_person=not persona, slot=f"{bucket.value}_{position}")


def _render_person_filter(dataset: SpaceDataset, user: AppUser, *, is_admin: bool) -> str:
    """Devuelve el nombre por el que filtrar («» = todo el equipo).

    Un no-admin ve siempre solo lo suyo: su bandeja no debe convertirse en la
    lista de tareas de otro.
    """
    if not is_admin:
        return user.nombre

    roster = list(people_with_actions(dataset))
    options = [_TODOS] + roster
    default = user.nombre if user.nombre in roster else _TODOS
    choice = st.selectbox(
        "Ver acciones de",
        options,
        index=options.index(default),
        key="acciones_persona",
    )
    return "" if choice == _TODOS else choice


def _render_action_row(item: ActionItem, *, show_person: bool, slot: str) -> None:
    """Pinta una fila de la bandeja.

    ``slot`` (cubo + posición) es lo que hace únicas las keys de los botones:
    una conversación antigua rellenada a mano puede no tener id, y dos widgets
    con la misma key lanzan excepción en Streamlit.
    """
    detail_column, actions_column = st.columns([5, 1.4], gap="small", vertical_alignment="center")

    with detail_column:
        chips = [
            chip_html(item.due_label(), action_bucket_style(item.bucket.value)),
            chip_html(item.product_name, STATUS_NEUTRAL),
        ]
        if show_person and item.persona:
            chips.append(chip_html(item.persona, STATUS_NEUTRAL))

        detalle = item.detalle or "(sin detalle de la próxima acción)"
        st.markdown(
            "<div class='space-history-item'>"
            "<div class='space-history-head'>"
            f"<div class='space-history-title'>{html.escape(item.supplier_name)}</div>"
            f"<div class='space-chip-row'>{''.join(c for c in chips if c)}</div>"
            "</div>"
            f"<div class='space-history-body'>{html.escape(detalle)}</div>"
            + (
                f"<div class='space-history-foot'>Último contacto: "
                f"{html.escape(item.tipo_conversacion)} — {html.escape(item.resumen[:180])}"
                f"{'…' if len(item.resumen) > 180 else ''}</div>"
                if item.resumen
                else ""
            )
            + "</div>",
            unsafe_allow_html=True,
        )

    with actions_column:
        if st.button(
            "Ver ficha",
            key=f"action_row_open_{slot}",
            icon=":material/arrow_forward:",
            type="tertiary",
            width="stretch",
        ):
            select_supplier(item.supplier_id, product_id=item.product_id)
            st.rerun()
