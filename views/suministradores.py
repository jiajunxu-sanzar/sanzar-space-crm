"""Suministradores — la página núcleo (§3.3).

Dos pestañas bajo el mismo header:

- **Productos**: catálogo maestro (nombre, categoría, descripción, estado) y
  alta de producto.
- **Suministradores**: lista operativa (filtros, tabla) y ficha con datos
  generales, conversaciones y precios.
"""

from __future__ import annotations

import html
from datetime import date

import streamlit as st

from app.state import (
    clear_selected_product,
    clear_selected_supplier,
    pop_write_status,
    select_product,
    select_supplier,
    selected_product_id,
    selected_supplier_id,
)
from config.settings import REL_ESTADO_DESCARTADO
from models.product import Product
from models.supplier import Supplier, SupplierProduct
from services.dataset import SpaceDataset
from services.pricing_leaderboard import (
    LeaderboardEntry,
    build_leaderboards,
    headline_quote_by_supplier,
    winning_supplier_ids,
)
from services.users_service import AppUser
from ui import modal_state
from ui.components.chips import chip_html, price_chip_html, supplier_state_chip_html
from ui.components.fields import render_detail_header, render_field_grid
from ui.components.history import render_conversations, render_quotes
from ui.components.kpi import Kpi, render_kpi_row
from ui.components.page_header import render_empty_state, render_page_header
from ui.palette import STATUS_NEUTRAL, STATUS_WARNING, product_state_style, supplier_state_style
from views import suministradores_forms as forms

# Cuántos chips de producto caben en una fila de la tabla antes de resumir.
_MAX_PRODUCT_CHIPS = 3


def render(dataset: SpaceDataset, user: AppUser, users: tuple[AppUser, ...]) -> None:
    status = pop_write_status()
    if status["status"] == "success" and status["message"]:
        st.toast(status["message"], icon="✅")

    forms.render_active_dialog(dataset, user, users)

    supplier = dataset.supplier_by_id.get(selected_supplier_id())
    if supplier is not None:
        _render_detail(dataset, supplier, user, users)
        return

    product = dataset.product_by_id.get(selected_product_id())
    if product is not None:
        _render_product_detail(dataset, product, user)
        return

    _render_list(dataset, user, users)


# ---------------------------------------------------------------------------
# Lista (pestañas Productos | Suministradores)
# ---------------------------------------------------------------------------


def _render_list(dataset: SpaceDataset, user: AppUser, users: tuple[AppUser, ...]) -> None:
    render_page_header("Suministradores")

    tab_products, tab_suppliers = st.tabs(["Productos", "Suministradores"])
    with tab_products:
        _render_products_tab(dataset, user)
    with tab_suppliers:
        _render_suppliers_tab(dataset, user, users)


def _render_products_tab(dataset: SpaceDataset, _user: AppUser) -> None:
    toolbar_left, new_product_col = st.columns([3, 1.3], vertical_alignment="bottom")
    with toolbar_left:
        query = st.text_input(
            "Buscar productos",
            key="prod_busqueda",
            placeholder="Nombre, categoría, descripción…",
            label_visibility="collapsed",
        )
    if new_product_col.button(
        "+ Nuevo producto", key="sup_new_product", type="primary", width="stretch"
    ):
        modal_state.open_nuevo_producto()
        st.rerun()

    products = _filter_products(dataset.products, query=query)
    if not dataset.products:
        render_empty_state(
            "Todavía no hay ningún producto. Pulsa «+ Nuevo producto» para dar de "
            "alta el primero."
        )
        return
    if not products:
        render_empty_state("Ningún producto coincide con esta búsqueda.")
        return

    render_kpi_row(
        [
            Kpi("Mostrando", len(products), f"de {len(dataset.products)} productos"),
            Kpi("Activos", len([p for p in products if p.is_activo]), tone="success"),
        ]
    )

    header_cols = st.columns([2.0, 1.3, 2.8, 1.1, 0.6], vertical_alignment="center")
    for column, label in zip(
        header_cols, ("Producto", "Categoría", "Descripción", "Estado", "")
    ):
        column.markdown(
            f"<div class='space-field-label' style='padding:0 0 4px 2px'>{label}</div>",
            unsafe_allow_html=True,
        )

    for product in products:
        _render_product_row(product)


def _filter_products(products: tuple[Product, ...], *, query: str) -> list[Product]:
    needle = str(query or "").strip().casefold()
    out: list[Product] = []
    for product in products:
        if needle:
            haystack = " ".join(
                (
                    product.nombre_producto,
                    product.categoria,
                    product.descripcion,
                    product.notas,
                    product.estado,
                )
            ).casefold()
            if needle not in haystack:
                continue
        out.append(product)
    return sorted(out, key=lambda item: item.display_name.casefold())


def _render_product_row(product: Product) -> None:
    with st.container(border=True):
        name_col, cat_col, desc_col, state_col, open_col = st.columns(
            [2.0, 1.3, 2.8, 1.1, 0.6], vertical_alignment="center"
        )
        name_col.markdown(
            f"<div class='space-field-value'>{html.escape(product.display_name)}</div>",
            unsafe_allow_html=True,
        )
        cat_col.markdown(
            f"<div class='space-field-value'>{html.escape(product.categoria or '—')}</div>",
            unsafe_allow_html=True,
        )
        desc = product.descripcion.strip() or "—"
        desc_col.markdown(
            f"<div class='space-field-value' style='font-size:0.8125rem;"
            f"color:var(--ui-text-muted)'>{html.escape(desc)}</div>",
            unsafe_allow_html=True,
        )
        state_col.markdown(
            chip_html(product.estado or "—", product_state_style(product.estado)),
            unsafe_allow_html=True,
        )
        if open_col.button(
            "+",
            key=f"prod_open_{product.product_id}",
            type="tertiary",
            width="stretch",
            help="Ver ficha del producto",
        ):
            select_product(product.product_id)
            st.rerun()


def _render_suppliers_tab(
    dataset: SpaceDataset, _user: AppUser, _users: tuple[AppUser, ...]
) -> None:
    toolbar_left, new_supplier_col = st.columns([3, 1.6], vertical_alignment="bottom")
    with toolbar_left:
        query = st.text_input(
            "Buscar",
            key="sup_busqueda",
            placeholder="Nombre, contacto, país…",
            label_visibility="collapsed",
        )
    if new_supplier_col.button(
        "+ Nuevo suministrador", key="sup_new_supplier", type="primary", width="stretch"
    ):
        modal_state.open_nuevo_suministrador()
        st.rerun()

    if not dataset.suppliers:
        render_empty_state(
            "Todavía no hay ningún suministrador. Pulsa «+ Nuevo suministrador» para "
            "dar de alta el primero."
        )
        return

    filter_products, filter_countries, show_discarded = _render_filters(dataset)

    rows = _filter_suppliers(
        dataset,
        query=query,
        product_ids=filter_products,
        countries=filter_countries,
        show_discarded=show_discarded,
    )

    winner_ids = winning_supplier_ids(dataset)
    headline_quotes = headline_quote_by_supplier(dataset)

    render_kpi_row(
        [
            Kpi("Mostrando", len(rows), f"de {len(dataset.suppliers)} suministradores"),
            Kpi(
                "Mejores del ranking",
                len(winner_ids),
                "los más baratos por producto",
                tone="success",
            ),
            Kpi("Productos activos", len(dataset.active_products())),
        ]
    )

    if not rows:
        render_empty_state("Ningún suministrador coincide con estos filtros.")
        return

    _render_table_header()
    for supplier in rows:
        _render_supplier_row(dataset, supplier, headline_quotes, winner_ids)


def _render_filters(dataset: SpaceDataset) -> tuple[list[str], list[str], bool]:
    product_labels = {product.display_name: product.product_id for product in dataset.products}
    left, middle, right = st.columns([2, 2, 1.4], vertical_alignment="bottom")

    selected_products = left.multiselect(
        "Producto",
        list(product_labels.keys()),
        key="sup_filtro_productos",
        placeholder="Todos los productos",
    )
    selected_countries = middle.multiselect(
        "País",
        list(dataset.paises),
        key="sup_filtro_paises",
        placeholder="Todos los países",
    )
    show_discarded = right.toggle(
        "Mostrar descartados",
        key="sup_mostrar_descartados",
        help="Por defecto se ocultan los suministradores cuya única relación está descartada.",
    )
    return (
        [product_labels[label] for label in selected_products],
        selected_countries,
        bool(show_discarded),
    )


def _filter_suppliers(
    dataset: SpaceDataset,
    *,
    query: str,
    product_ids: list[str],
    countries: list[str],
    show_discarded: bool,
) -> list[Supplier]:
    needle = str(query or "").strip().casefold()
    wanted_products = set(product_ids)
    wanted_countries = set(countries)
    out: list[Supplier] = []

    for supplier in dataset.suppliers:
        relations = dataset.products_for_supplier(supplier.supplier_id)

        if wanted_products and not any(rel.product_id in wanted_products for rel in relations):
            continue
        if wanted_countries and supplier.pais not in wanted_countries:
            continue

        # Se oculta solo a quien está descartado en TODAS sus relaciones: un
        # proveedor descartado para bearings pero confirmado para motores sigue
        # siendo relevante.
        if not show_discarded and relations and all(rel.is_descartado for rel in relations):
            continue

        if needle:
            haystack = " ".join(
                (
                    supplier.nombre_suministrador,
                    supplier.pais,
                    supplier.contacto_principal,
                    supplier.contacto_secundario,
                    supplier.email,
                    supplier.notas_generales,
                )
            ).casefold()
            if needle not in haystack:
                continue

        out.append(supplier)

    return sorted(out, key=lambda item: item.display_name.casefold())


def _render_table_header() -> None:
    columns = st.columns([2.4, 1, 2.2, 1.6, 1.6], vertical_alignment="center")
    for column, label in zip(
        columns, ("Suministrador", "País", "Productos y estado", "Mejor precio", "Próxima acción")
    ):
        column.markdown(
            f"<div class='space-field-label' style='padding:0 0 4px 2px'>{label}</div>",
            unsafe_allow_html=True,
        )


def _render_supplier_row(
    dataset: SpaceDataset,
    supplier: Supplier,
    headline_quotes: dict[str, LeaderboardEntry],
    winner_ids: set[str],
) -> None:
    with st.container(border=True):
        name_col, country_col, products_col, price_col, action_col = st.columns(
            [2.4, 1, 2.2, 1.6, 1.6], vertical_alignment="center"
        )

        with name_col:
            if st.button(
                supplier.display_name,
                key=f"supplier_row_{supplier.supplier_id}",
                width="stretch",
                type="tertiary",
            ):
                select_supplier(supplier.supplier_id, navigate=False)
                st.rerun()

        country_col.markdown(
            f"<div class='space-field-value'>{html.escape(supplier.pais or '—')}</div>",
            unsafe_allow_html=True,
        )

        relations = dataset.products_for_supplier(supplier.supplier_id)
        chips = [
            chip_html(dataset.product_name(rel.product_id), supplier_state_style(rel.estado))
            for rel in relations[:_MAX_PRODUCT_CHIPS]
        ]
        if len(relations) > _MAX_PRODUCT_CHIPS:
            chips.append(chip_html(f"+{len(relations) - _MAX_PRODUCT_CHIPS}", STATUS_NEUTRAL))
        products_col.markdown(
            f"<div class='space-chip-row'>{''.join(c for c in chips if c) or '—'}</div>",
            unsafe_allow_html=True,
        )

        # El chip verde solo aparece si la oferta MOSTRADA es la ganadora de su
        # producto; marcar como ganador un precio de otro producto sería engañoso.
        entry = headline_quotes.get(supplier.supplier_id)
        if entry is not None:
            price_col.markdown(
                price_chip_html(
                    f"{entry.formatted_price()} · {dataset.product_name(entry.product_id)}",
                    is_winner=supplier.supplier_id in winner_ids,
                    is_expired=entry.is_expired,
                ),
                unsafe_allow_html=True,
            )
        else:
            price_col.markdown(
                "<span class='space-field-value' style='color:var(--ui-text-muted)'>—</span>",
                unsafe_allow_html=True,
            )

        open_actions = dataset.open_actions_for_supplier(supplier.supplier_id)
        if open_actions:
            # La más próxima manda: es la que dice si hay algo que hacer ya.
            soonest = min(open_actions, key=lambda item: item.proxima_accion_date or date.max)
            label = soonest.proxima_accion_fecha or "sin fecha"
            action_col.markdown(chip_html(label, STATUS_WARNING), unsafe_allow_html=True)
        else:
            action_col.markdown(
                "<span class='space-field-value' style='color:var(--ui-text-muted)'>—</span>",
                unsafe_allow_html=True,
            )


# ---------------------------------------------------------------------------
# Ficha de producto
# ---------------------------------------------------------------------------


def _render_product_detail(dataset: SpaceDataset, product: Product, _user: AppUser) -> None:
    back_col, spacer, edit_col = st.columns([0.7, 4.7, 1.6], vertical_alignment="center")
    if back_col.button(
        "",
        key="prod_back",
        icon=":material/arrow_back:",
        type="tertiary",
        width="stretch",
        help="Volver al listado",
    ):
        clear_selected_product()
        st.rerun()
    del spacer
    if edit_col.button(
        "Editar producto",
        key="prod_edit",
        icon=":material/edit:",
        type="secondary",
        width="stretch",
    ):
        modal_state.open_editar_producto(product.product_id)
        st.rerun()

    render_detail_header(
        initials=(product.display_name[:2] or "?").upper(),
        title=product.display_name,
        meta=" · ".join(bit for bit in (product.categoria, product.product_id) if bit),
        chips_html=chip_html(product.estado or "—", product_state_style(product.estado)),
    )

    render_field_grid(
        [
            ("Descripción", product.descripcion),
            ("Definido por", product.definido_por),
            ("Fecha de definición", product.fecha_definicion),
            ("Carpeta / documento", product.link_carpeta),
            ("Notas", product.notas),
            ("Estado", product.estado),
            ("Creado", product.created_at),
            ("Actualizado", product.updated_at),
        ],
        links=True,
    )

    st.markdown("---")
    st.markdown("###### Campos técnicos")
    specs = dataset.product_specs(product.product_id)
    if not specs:
        render_empty_state(
            "Este producto aún no tiene campos técnicos. Pulsa «Editar producto» "
            "para añadir potencia, voltaje, diámetro…"
        )
    else:
        filled = [(spec.label, value or "—") for spec, value in specs]
        render_field_grid(filled)


# ---------------------------------------------------------------------------
# Ficha de suministrador
# ---------------------------------------------------------------------------


def _render_detail(
    dataset: SpaceDataset, supplier: Supplier, user: AppUser, users: tuple[AppUser, ...]
) -> None:
    back_col, spacer, edit_col = st.columns([0.7, 4.7, 1.4], vertical_alignment="center")
    if back_col.button(
        "",
        key="sup_back",
        icon=":material/arrow_back:",
        type="tertiary",
        width="stretch",
        help="Volver al listado",
    ):
        clear_selected_supplier()
        st.rerun()
    del spacer
    if edit_col.button("Editar ficha", key="sup_edit", icon=":material/edit:", type="secondary", width="stretch"):
        modal_state.open_modal("editar_suministrador", supplier_id=supplier.supplier_id)
        st.rerun()

    relations = dataset.products_for_supplier(supplier.supplier_id)
    meta_bits = [supplier.pais, supplier.contacto_principal, supplier.email]
    render_detail_header(
        initials=supplier.initials,
        title=supplier.display_name,
        meta=" · ".join(bit for bit in meta_bits if bit),
        chips_html="".join(
            supplier_state_chip_html(f"{dataset.product_name(rel.product_id)}: {rel.estado}")
            for rel in relations
        ),
    )

    tab_general, tab_conversations, tab_prices = st.tabs(
        ["Datos generales", "Conversaciones", "Precios"]
    )

    with tab_general:
        _render_general_block(dataset, supplier, relations)
    with tab_conversations:
        _render_conversations_block(dataset, supplier)
    with tab_prices:
        _render_prices_block(dataset, supplier)


def _render_general_block(
    dataset: SpaceDataset, supplier: Supplier, relations: tuple[SupplierProduct, ...]
) -> None:
    render_field_grid(
        [
            ("País", supplier.pais),
            ("Web", supplier.web),
            ("Email", supplier.email),
            ("Dirección", supplier.direccion),
            ("Contacto principal", supplier.contacto_principal),
            ("Cargo", supplier.cargo_contacto_principal),
            ("Teléfono", supplier.telefono_principal),
            ("Contacto secundario", supplier.contacto_secundario),
            ("Cargo", supplier.cargo_contacto_secundario),
            ("Teléfono", supplier.telefono_secundario),
        ],
        links=True,
    )
    if supplier.notas_generales:
        st.markdown("###### Notas")
        st.markdown(
            f"<div class='space-history-body'>{html.escape(supplier.notas_generales)}</div>",
            unsafe_allow_html=True,
        )

    st.markdown("---")
    head_col, add_col = st.columns([4, 1.4], vertical_alignment="center")
    head_col.markdown("###### Productos asociados")
    if add_col.button(
        "Asociar producto", key="sup_add_relation", icon=":material/add:", type="secondary", width="stretch"
    ):
        modal_state.open_modal("nueva_relacion", supplier_id=supplier.supplier_id)
        st.rerun()

    if not relations:
        render_empty_state("Este suministrador todavía no está asociado a ningún producto.")
        return

    for relation in relations:
        product_col, state_col, extra_col, edit_col = st.columns(
            [2.2, 1.6, 2.4, 1.2], vertical_alignment="center"
        )
        product = dataset.product_by_id.get(relation.product_id)
        product_col.markdown(
            f"<div class='space-field-value'>{html.escape(dataset.product_name(relation.product_id))}</div>"
            f"<div class='space-field-label'>{html.escape(product.categoria if product else '')}</div>",
            unsafe_allow_html=True,
        )
        state_col.markdown(supplier_state_chip_html(relation.estado), unsafe_allow_html=True)

        extra_bits = []
        if relation.responsable_relacion:
            extra_bits.append(f"Responsable: {relation.responsable_relacion}")
        if relation.fecha_alta:
            extra_bits.append(f"Alta: {relation.fecha_alta}")
        if relation.estado == REL_ESTADO_DESCARTADO and relation.razon_descarte:
            extra_bits.append(f"Razón: {relation.razon_descarte}")
        extra_col.markdown(
            f"<div class='space-field-value' style='font-size:0.8125rem'>"
            f"{html.escape(' · '.join(extra_bits)) or '—'}</div>",
            unsafe_allow_html=True,
        )

        # La key va por la pareja (proveedor, producto), que el dataset ya
        # garantiza única, y no por ``rel_id``, que en una hoja editada a mano
        # puede venir vacío o repetido.
        if edit_col.button(
            "Estado",
            key=f"rel_edit_{relation.supplier_id}_{relation.product_id}",
            type="tertiary",
            width="stretch",
        ):
            modal_state.open_editar_relacion(supplier.supplier_id, relation.rel_id)
            st.rerun()

        specs = dataset.product_specs(relation.product_id)
        filled = [(spec.label, value) for spec, value in specs if value]
        if filled:
            with st.expander(f"Especificaciones técnicas de {dataset.product_name(relation.product_id)}"):
                render_field_grid(filled)


def _render_conversations_block(dataset: SpaceDataset, supplier: Supplier) -> None:
    head_col, add_col = st.columns([4, 1.6], vertical_alignment="center")
    conversations = dataset.conversations_by_supplier.get(supplier.supplier_id, ())
    head_col.markdown(f"###### {len(conversations)} conversación(es) registradas")
    if add_col.button(
        "Registrar conversación",
        key="sup_add_conversation",
        icon=":material/add:",
        type="primary",
        width="stretch",
    ):
        modal_state.open_nueva_conversacion(supplier.supplier_id)
        st.rerun()

    render_conversations(
        conversations,
        dataset,
        on_edit=lambda row_id: modal_state.open_editar_conversacion(
            supplier.supplier_id, row_id
        ),
    )


def _render_prices_block(dataset: SpaceDataset, supplier: Supplier) -> None:
    head_col, add_col = st.columns([4, 1.6], vertical_alignment="center")
    quotes = dataset.quotes_by_supplier.get(supplier.supplier_id, ())
    head_col.markdown(f"###### {len(quotes)} oferta(s) registradas")
    if add_col.button(
        "Registrar precio",
        key="sup_add_quote",
        icon=":material/add:",
        type="primary",
        width="stretch",
    ):
        modal_state.open_nuevo_precio(supplier.supplier_id)
        st.rerun()

    # Qué ofertas de este proveedor son, hoy, las ganadoras de su producto:
    # se marcan en verde para que la ficha cuente lo mismo que la portada.
    winning_ids: set[str] = set()
    for board in build_leaderboards(dataset, only_active_products=False):
        for entry in board.winners():
            if entry.supplier_id != supplier.supplier_id:
                continue
            quote = dataset.latest_quote(entry.supplier_id, entry.product_id)
            if quote is not None:
                winning_ids.add(quote.historial_precio_id)

    render_quotes(
        quotes,
        dataset,
        winning_ids=frozenset(winning_ids),
        on_edit=lambda row_id: modal_state.open_editar_precio(supplier.supplier_id, row_id),
    )


__all__ = ["render"]
