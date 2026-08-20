"""Tarjetas de la portada: «el más barato de cada producto» (§3.1).

Cada tarjeta muestra **un** suministrador ganador (precio unitario más bajo),
la fecha de la oferta y un botón «Ver ficha». El ranking completo bajo la
portada sirve para comparar el resto.
"""

from __future__ import annotations

import html

import streamlit as st

from services.pricing_leaderboard import LeaderboardEntry, ProductLeaderboard, _sort_key
from ui.components.chips import (
    chip_html,
    price_chip_html,
    supplier_state_chip_html,
)
from ui.palette import STATUS_NEUTRAL, STATUS_WARNING


def _winner_block(entry: LeaderboardEntry) -> str:
    chips = [supplier_state_chip_html(entry.estado_relacion)]
    if entry.is_expired:
        chips.append(chip_html("Oferta caducada", STATUS_WARNING))
    if entry.cantidad_minima:
        chips.append(chip_html(f"MOQ {entry.cantidad_minima}", STATUS_NEUTRAL))

    meta_bits = [f"Oferta del {entry.fecha_oferta}" if entry.fecha_oferta else ""]
    if entry.unidad_medida:
        meta_bits.append(entry.unidad_medida)
    meta = " · ".join(bit for bit in meta_bits if bit)

    return (
        f"<div class='space-card-price'>{html.escape(entry.formatted_price())}</div>"
        f"<div class='space-card-supplier'>{html.escape(entry.supplier_name)}</div>"
        f"<div class='space-card-meta'>{html.escape(meta)}</div>"
        f"<div class='space-chip-row' style='margin-top:10px'>{''.join(c for c in chips if c)}</div>"
    )


def _card_winner(board: ProductLeaderboard) -> LeaderboardEntry | None:
    """Oferta de menor precio unitario entre todas las monedas (sin FX)."""
    entries = board.ranking()
    if not entries:
        return None
    # Mismo desempate que el ranking (confirmado → reciente), pero cruzando monedas.
    return min(entries, key=_sort_key)


def render_product_card(board: ProductLeaderboard, *, on_open_key: str = "") -> str | None:
    """Pinta la tarjeta de un producto. Devuelve el ``supplier_id`` si se pulsó «Ver ficha».

    Siempre un solo ganador en la tarjeta (importe unitario más bajo). Con
    monedas mixtas se avisa: no hay tipo de cambio; el ranking completo detalla
    el resto.
    """
    with st.container(border=False):
        header = (
            "<div class='space-card-head'>"
            f"<div class='space-card-title'>{html.escape(board.product_name)}</div>"
            f"<div class='space-card-eyebrow'>{html.escape(board.categoria or '—')}</div>"
            "</div>"
        )

        if not board.has_quotes:
            body = (
                "<div class='space-card-empty'>Todavía no hay ninguna oferta registrada "
                "para este producto.</div>"
            )
            st.markdown(f"<div class='space-card'>{header}{body}</div>", unsafe_allow_html=True)
            return None

        winner = _card_winner(board)
        body = _winner_block(winner) if winner else ""
        if board.is_mixed_currency:
            body += (
                "<div class='space-card-meta' style='margin-top:10px'>"
                "Hay ofertas en varias monedas: se muestra el importe unitario más bajo "
                "sin convertir. Compara el resto en el ranking completo."
                "</div>"
            )

        footer = (
            f"<div class='space-card-meta' style='margin-top:10px'>"
            f"{board.supplier_count()} suministrador(es) en juego</div>"
        )
        st.markdown(
            f"<div class='space-card'>{header}{body}{footer}</div>", unsafe_allow_html=True
        )

        if winner and on_open_key:
            if st.button(
                "Ver ficha",
                key=on_open_key,
                icon=":material/arrow_forward:",
                type="tertiary",
                width="stretch",
            ):
                return winner.supplier_id
    return None


def render_ranking_table(board: ProductLeaderboard, *, limit: int = 8) -> None:
    """Ranking completo de un producto, para el detalle del Home."""
    entries = board.ranking()
    if not entries:
        return
    rows = []
    for position, entry in enumerate(entries[:limit], start=1):
        chips = [
            price_chip_html(
                entry.formatted_price(), is_winner=position == 1, is_expired=entry.is_expired
            ),
            supplier_state_chip_html(entry.estado_relacion),
        ]
        rows.append(
            "<div class='space-history-item'>"
            "<div class='space-history-head'>"
            f"<div class='space-history-title'>{position}. {html.escape(entry.supplier_name)}</div>"
            f"<div class='space-chip-row'>{''.join(c for c in chips if c)}</div>"
            "</div>"
            f"<div class='space-history-foot'>Oferta del {html.escape(entry.fecha_oferta or '—')}"
            f"{' · ' + html.escape(entry.unidad_medida) if entry.unidad_medida else ''}</div>"
            "</div>"
        )
    st.markdown("".join(rows), unsafe_allow_html=True)
    if len(entries) > limit:
        st.caption(f"…y {len(entries) - limit} oferta(s) más.")
