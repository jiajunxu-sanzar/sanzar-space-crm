"""Home — «¿quién es hoy el suministrador más barato de cada producto?» (§3.1).

KPIs arriba y, como pieza central, una tarjeta por producto con el suministrador
confirmado o potencial más barato, su precio, la fecha de la oferta y un botón
que abre su ficha.

Nada de esto está guardado en el Excel: se calcula en tiempo real en
``services/pricing_leaderboard.py``.
"""

from __future__ import annotations

import streamlit as st

from app.state import select_supplier
from services.actions_stats import pending_actions, summarize_actions
from services.dataset import SpaceDataset
from services.pricing_leaderboard import build_leaderboards, summarize
from services.users_service import AppUser
from ui.components.cards import render_product_card, render_ranking_table
from ui.components.kpi import Kpi, render_kpi_row
from ui.components.page_header import render_empty_state, render_page_header

_CARDS_PER_ROW = 3


def render(dataset: SpaceDataset, user: AppUser) -> None:
    render_page_header("Home")

    if dataset.is_empty:
        render_empty_state(
            "Todavía no hay productos ni suministradores en la hoja. "
            "Empieza dando de alta un producto y su primer suministrador desde "
            "la pestaña Suministradores."
        )
        return

    boards = build_leaderboards(dataset)
    stats = summarize(dataset, boards)
    my_actions = summarize_actions(pending_actions(dataset, persona=user.nombre))

    render_kpi_row(
        [
            Kpi("Productos activos", stats.productos_activos, f"{stats.productos_sin_oferta} sin oferta"),
            Kpi("Suministradores", stats.suministradores, f"{stats.confirmados} confirmados"),
            Kpi(
                "Potenciales",
                stats.potenciales,
                f"{stats.descartados} descartados",
                tone="info",
            ),
            Kpi(
                "Tus acciones",
                my_actions.needs_attention,
                f"{my_actions.vencidas} vencidas · {my_actions.total} en total",
                tone="danger" if my_actions.vencidas else ("warning" if my_actions.total else "success"),
            ),
        ]
    )

    if stats.monedas_mixtas:
        st.info(
            "Estos productos tienen ofertas en más de una moneda. En la tarjeta se "
            "muestra el importe unitario más bajo sin convertir; el ranking completo "
            f"detalla el resto: {', '.join(stats.monedas_mixtas)}.",
            icon=":material/currency_exchange:",
        )

    st.markdown("##### El más barato de cada producto")

    with_quotes = [board for board in boards if board.has_quotes]
    without_quotes = [board for board in boards if not board.has_quotes]

    _render_card_grid(boards)

    if without_quotes:
        st.caption(
            f"{len(without_quotes)} producto(s) todavía sin ninguna oferta registrada."
        )

    if with_quotes:
        st.markdown("---")
        _render_ranking_explorer(with_quotes)


def _render_card_grid(boards) -> None:
    """Parrilla de tarjetas. La navegación se resuelve fuera del bucle."""
    target_supplier = ""
    for start in range(0, len(boards), _CARDS_PER_ROW):
        row = boards[start : start + _CARDS_PER_ROW]
        columns = st.columns(_CARDS_PER_ROW, gap="medium")
        for column, board in zip(columns, row):
            with column:
                clicked = render_product_card(
                    board, on_open_key=f"home_open_{board.product_id}"
                )
                if clicked:
                    target_supplier = clicked
        # Rellenar la fila incompleta mantiene el ancho de tarjeta constante.
        for column in columns[len(row) :]:
            with column:
                st.empty()

    if target_supplier:
        select_supplier(target_supplier)
        st.rerun()


def _render_ranking_explorer(boards) -> None:
    """Ranking completo del producto elegido — el «por qué» detrás de la tarjeta."""
    st.markdown("##### Ranking completo por producto")
    options = {board.product_name: board for board in boards}
    selected_name = st.selectbox(
        "Producto",
        list(options.keys()),
        key="home_ranking_product",
        label_visibility="collapsed",
    )
    board = options.get(selected_name)
    if board is None:
        return

    if board.is_mixed_currency:
        tabs = st.tabs([f"{currency}" for currency in board.currencies])
        for tab, currency in zip(tabs, board.currencies):
            with tab:
                render_ranking_table(
                    type(board)(
                        product_id=board.product_id,
                        product_name=board.product_name,
                        categoria=board.categoria,
                        by_currency={currency: board.by_currency[currency]},
                    )
                )
    else:
        render_ranking_table(board)
