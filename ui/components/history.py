"""Listas de histórico: conversaciones y precios de la ficha del suministrador.

Se pintan como bloques HTML compactos (texto largo) con un botón de editar
por fila: el markdown puro no admite widgets de Streamlit.
"""

from __future__ import annotations

import html
from collections.abc import Callable

import streamlit as st

from models.history import Conversation, PriceQuote
from services.dataset import SpaceDataset
from ui.components.chips import (
    action_chip_html,
    chip_html,
    conversation_chip_html,
    price_chip_html,
    validity_chip_html,
)
from ui.palette import STATUS_NEUTRAL, STATUS_SUCCESS, conversation_icon


def _modifier(tipo: str) -> str:
    return {
        "Email": "email",
        "Reunión": "reunion",
        "Llamada": "llamada",
    }.get(tipo, "otro")


def _link_html(url: str, label: str) -> str:
    clean = str(url or "").strip()
    if not clean.startswith(("http://", "https://")):
        return ""
    return (
        f"<a href='{html.escape(clean, quote=True)}' target='_blank' rel='noopener noreferrer'>"
        f"{html.escape(label)}</a>"
    )


def _conversation_block_html(conversation: Conversation, dataset: SpaceDataset) -> str:
    chips = [
        conversation_chip_html(conversation.tipo_conversacion),
        chip_html(dataset.product_name(conversation.product_id), STATUS_NEUTRAL),
    ]
    if conversation.proxima_accion_fecha or conversation.proxima_accion_detalle:
        if conversation.is_pendiente:
            label = f"Próx.: {conversation.proxima_accion_fecha or 'sin fecha'}"
            chips.append(
                action_chip_html(
                    label, conversation.proxima_accion_fecha, conversation.estado_accion
                )
            )
        else:
            chips.append(chip_html("Acción completada", STATUS_SUCCESS))
    elif conversation.estado_accion.strip():
        if not conversation.is_pendiente:
            chips.append(chip_html("Acción completada", STATUS_SUCCESS))

    when = " ".join(
        part for part in (conversation.fecha_contacto, conversation.hora_contacto) if part
    )
    foot_bits = [
        f"Registrado por {conversation.persona_contacto}" if conversation.persona_contacto else ""
    ]
    if conversation.proxima_accion_detalle:
        responsable = conversation.proxima_accion_persona or "sin asignar"
        foot_bits.append(
            f"Próxima acción: {conversation.proxima_accion_detalle} ({responsable})"
        )
    foot = " · ".join(bit for bit in foot_bits if bit)

    return (
        f"<div class='space-history-item space-history-item--{_modifier(conversation.tipo_conversacion)}'>"
        "<div class='space-history-head'>"
        f"<div class='space-history-title'>{html.escape(when or 'Sin fecha')}</div>"
        f"<div class='space-chip-row'>{''.join(c for c in chips if c)}</div>"
        "</div>"
        f"<div class='space-history-body'>{html.escape(conversation.resumen)}</div>"
        + (f"<div class='space-history-foot'>{html.escape(foot)}</div>" if foot else "")
        + "</div>"
    )


def _quote_block_html(
    quote: PriceQuote, dataset: SpaceDataset, *, winning_ids: frozenset[str]
) -> str:
    chips = [
        price_chip_html(
            quote.formatted_price(),
            is_winner=quote.historial_precio_id in winning_ids,
            is_expired=quote.is_expired(),
        ),
        chip_html(dataset.product_name(quote.product_id), STATUS_NEUTRAL),
        validity_chip_html(quote.validez_oferta_fecha),
    ]
    if quote.cantidad_minima:
        chips.append(chip_html(f"MOQ {quote.cantidad_minima}", STATUS_NEUTRAL))

    foot_bits = []
    if quote.unidad_medida:
        foot_bits.append(quote.unidad_medida)
    if quote.registrado_por:
        foot_bits.append(f"Registrado por {quote.registrado_por}")
    catalog = _link_html(quote.link_catalogo, "Catálogo / carpeta")
    foot = " · ".join(html.escape(bit) for bit in foot_bits if bit)
    if catalog:
        foot = f"{foot} · {catalog}" if foot else catalog

    body_bits = [quote.condiciones, quote.notas]
    body = "\n".join(bit for bit in body_bits if bit)

    return (
        "<div class='space-history-item'>"
        "<div class='space-history-head'>"
        f"<div class='space-history-title'>{html.escape(quote.fecha_oferta or 'Sin fecha')}</div>"
        f"<div class='space-chip-row'>{''.join(c for c in chips if c)}</div>"
        "</div>"
        + (f"<div class='space-history-body'>{html.escape(body)}</div>" if body else "")
        + (f"<div class='space-history-foot'>{foot}</div>" if foot else "")
        + "</div>"
    )


def render_conversations(
    conversations: tuple[Conversation, ...],
    dataset: SpaceDataset,
    *,
    limit: int = 25,
    on_edit: Callable[[str], None] | None = None,
) -> None:
    """Histórico de conversaciones, de la más reciente a la más antigua."""
    if not conversations:
        st.markdown(
            "<div class='space-empty'>Todavía no hay conversaciones registradas con "
            "este suministrador.</div>",
            unsafe_allow_html=True,
        )
        return

    for conversation in conversations[:limit]:
        body_col, edit_col = st.columns([12, 0.7], vertical_alignment="top")
        with body_col:
            st.markdown(
                _conversation_block_html(conversation, dataset),
                unsafe_allow_html=True,
            )
        with edit_col:
            if on_edit is not None and st.button(
                "",
                key=f"hist_edit_conv_{conversation.historial_conversacion_id}",
                icon=":material/edit:",
                type="tertiary",
                width="stretch",
                help="Editar conversación",
            ):
                on_edit(conversation.historial_conversacion_id)
                st.rerun()

    if len(conversations) > limit:
        st.caption(f"Mostrando las {limit} más recientes de {len(conversations)}.")


def render_quotes(
    quotes: tuple[PriceQuote, ...],
    dataset: SpaceDataset,
    *,
    winning_ids: frozenset[str] = frozenset(),
    limit: int = 25,
    on_edit: Callable[[str], None] | None = None,
) -> None:
    """Histórico de precios, de la oferta más reciente a la más antigua."""
    if not quotes:
        st.markdown(
            "<div class='space-empty'>Todavía no hay precios registrados para este "
            "suministrador.</div>",
            unsafe_allow_html=True,
        )
        return

    for quote in quotes[:limit]:
        body_col, edit_col = st.columns([12, 0.7], vertical_alignment="top")
        with body_col:
            st.markdown(
                _quote_block_html(quote, dataset, winning_ids=winning_ids),
                unsafe_allow_html=True,
            )
        with edit_col:
            if on_edit is not None and st.button(
                "",
                key=f"hist_edit_quote_{quote.historial_precio_id}",
                icon=":material/edit:",
                type="tertiary",
                width="stretch",
                help="Editar precio",
            ):
                on_edit(quote.historial_precio_id)
                st.rerun()

    if len(quotes) > limit:
        st.caption(f"Mostrando las {limit} más recientes de {len(quotes)}.")


__all__ = ["render_conversations", "render_quotes", "conversation_icon"]
