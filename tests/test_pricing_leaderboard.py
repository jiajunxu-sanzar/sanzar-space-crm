"""El cálculo del «más barato por producto» (§3.1) — el corazón de la app."""

from __future__ import annotations

from datetime import date

import pytest

from config.settings import (
    REL_ESTADO_CONFIRMADO,
    REL_ESTADO_DESCARTADO,
    REL_ESTADO_POTENCIAL,
)
from services.pricing_leaderboard import (
    build_leaderboards,
    headline_quote_by_supplier,
    leaderboard_for_product,
    summarize,
    winning_supplier_ids,
)
from tests.conftest import make_dataset

TODAY = date(2026, 8, 20)


def _product(product_id: str, nombre: str, estado: str = "Activo") -> dict:
    return {
        "product_id": product_id,
        "nombre_producto": nombre,
        "categoria": "Motores",
        "estado": estado,
    }


def _supplier(supplier_id: str, nombre: str, pais: str = "España") -> dict:
    return {"supplier_id": supplier_id, "nombre_suministrador": nombre, "pais": pais}


def _relation(supplier_id: str, product_id: str, estado: str = REL_ESTADO_POTENCIAL) -> dict:
    return {
        "rel_id": f"REL-{supplier_id}-{product_id}",
        "supplier_id": supplier_id,
        "product_id": product_id,
        "estado": estado,
        "razon_descarte": "Precio fuera de mercado" if estado == REL_ESTADO_DESCARTADO else "",
    }


def _quote(
    quote_id: str,
    supplier_id: str,
    product_id: str,
    precio: str,
    fecha: str,
    moneda: str = "EUR",
    validez: str = "",
) -> dict:
    return {
        "historial_precio_id": quote_id,
        "supplier_id": supplier_id,
        "product_id": product_id,
        "precio": precio,
        "moneda": moneda,
        "fecha_oferta": fecha,
        "validez_oferta_fecha": validez,
    }


def test_gana_el_precio_mas_bajo():
    dataset = make_dataset(
        productos=[_product("PRD-0001", "Motor 5kW")],
        suministradores=[_supplier("SUP-0001", "Alfa"), _supplier("SUP-0002", "Beta")],
        relaciones=[_relation("SUP-0001", "PRD-0001"), _relation("SUP-0002", "PRD-0001")],
        precios=[
            _quote("PRC-1", "SUP-0001", "PRD-0001", "1200", "01/08/2026"),
            _quote("PRC-2", "SUP-0002", "PRD-0001", "950", "02/08/2026"),
        ],
    )
    board = build_leaderboards(dataset, today=TODAY)[0]
    winner = board.winner()

    assert winner is not None
    assert winner.supplier_name == "Beta"
    assert winner.price == pytest.approx(950.0)
    assert [entry.supplier_name for entry in board.ranking()] == ["Beta", "Alfa"]


def test_solo_cuenta_la_oferta_mas_reciente_de_cada_pareja():
    """Un precio viejo y barato no debe ganarle al precio actual del proveedor."""
    dataset = make_dataset(
        productos=[_product("PRD-0001", "Motor 5kW")],
        suministradores=[_supplier("SUP-0001", "Alfa"), _supplier("SUP-0002", "Beta")],
        relaciones=[_relation("SUP-0001", "PRD-0001"), _relation("SUP-0002", "PRD-0001")],
        precios=[
            _quote("PRC-1", "SUP-0001", "PRD-0001", "500", "01/01/2026"),
            _quote("PRC-2", "SUP-0001", "PRD-0001", "1400", "01/08/2026"),
            _quote("PRC-3", "SUP-0002", "PRD-0001", "1100", "05/08/2026"),
        ],
    )
    winner = build_leaderboards(dataset, today=TODAY)[0].winner()

    assert winner is not None
    assert winner.supplier_name == "Beta"
    assert winner.price == pytest.approx(1100.0)


def test_descartado_no_entra_en_el_ranking():
    dataset = make_dataset(
        productos=[_product("PRD-0001", "Motor 5kW")],
        suministradores=[_supplier("SUP-0001", "Alfa"), _supplier("SUP-0002", "Beta")],
        relaciones=[
            _relation("SUP-0001", "PRD-0001", REL_ESTADO_DESCARTADO),
            _relation("SUP-0002", "PRD-0001", REL_ESTADO_CONFIRMADO),
        ],
        precios=[
            _quote("PRC-1", "SUP-0001", "PRD-0001", "100", "01/08/2026"),
            _quote("PRC-2", "SUP-0002", "PRD-0001", "999", "01/08/2026"),
        ],
    )
    board = build_leaderboards(dataset, today=TODAY)[0]

    assert [entry.supplier_name for entry in board.ranking()] == ["Beta"]


def test_descartado_en_un_producto_sigue_compitiendo_en_otro():
    """El estado vive en la relación, no en el proveedor (§4.2)."""
    dataset = make_dataset(
        productos=[_product("PRD-0001", "Motor"), _product("PRD-0002", "Bearing")],
        suministradores=[_supplier("SUP-0006", "Multi")],
        relaciones=[
            _relation("SUP-0006", "PRD-0001", REL_ESTADO_DESCARTADO),
            _relation("SUP-0006", "PRD-0002", REL_ESTADO_CONFIRMADO),
        ],
        precios=[
            _quote("PRC-1", "SUP-0006", "PRD-0001", "100", "01/08/2026"),
            _quote("PRC-2", "SUP-0006", "PRD-0002", "200", "01/08/2026"),
        ],
    )
    boards = {board.product_name: board for board in build_leaderboards(dataset, today=TODAY)}

    assert boards["Motor"].has_quotes is False
    assert boards["Bearing"].winner().supplier_name == "Multi"


def test_monedas_mixtas_dan_un_ganador_por_moneda():
    """Sin tipo de cambio no se elige un único ganador (§6)."""
    dataset = make_dataset(
        productos=[_product("PRD-0001", "Motor 5kW")],
        suministradores=[_supplier("SUP-0001", "Alfa"), _supplier("SUP-0002", "Beta")],
        relaciones=[_relation("SUP-0001", "PRD-0001"), _relation("SUP-0002", "PRD-0001")],
        precios=[
            _quote("PRC-1", "SUP-0001", "PRD-0001", "1000", "01/08/2026", moneda="EUR"),
            _quote("PRC-2", "SUP-0002", "PRD-0001", "900", "01/08/2026", moneda="USD"),
        ],
    )
    board = build_leaderboards(dataset, today=TODAY)[0]

    assert board.is_mixed_currency is True
    assert board.currencies == ("EUR", "USD")
    assert {entry.supplier_name for entry in board.winners()} == {"Alfa", "Beta"}
    assert board.winner("USD").price == pytest.approx(900.0)


def test_a_igual_precio_gana_el_confirmado():
    dataset = make_dataset(
        productos=[_product("PRD-0001", "Motor")],
        suministradores=[_supplier("SUP-0001", "Alfa"), _supplier("SUP-0002", "Beta")],
        relaciones=[
            _relation("SUP-0001", "PRD-0001", REL_ESTADO_POTENCIAL),
            _relation("SUP-0002", "PRD-0001", REL_ESTADO_CONFIRMADO),
        ],
        precios=[
            _quote("PRC-1", "SUP-0001", "PRD-0001", "1000", "01/08/2026"),
            _quote("PRC-2", "SUP-0002", "PRD-0001", "1000", "01/08/2026"),
        ],
    )
    assert build_leaderboards(dataset, today=TODAY)[0].winner().supplier_name == "Beta"


def test_oferta_caducada_se_marca_pero_no_desaparece():
    dataset = make_dataset(
        productos=[_product("PRD-0001", "Motor")],
        suministradores=[_supplier("SUP-0001", "Alfa")],
        relaciones=[_relation("SUP-0001", "PRD-0001")],
        precios=[
            _quote("PRC-1", "SUP-0001", "PRD-0001", "1000", "01/06/2026", validez="30/06/2026")
        ],
    )
    winner = build_leaderboards(dataset, today=TODAY)[0].winner()
    assert winner is not None and winner.is_expired is True

    sin_caducadas = build_leaderboards(dataset, include_expired=False, today=TODAY)[0]
    assert sin_caducadas.has_quotes is False


def test_precio_con_formato_espanol_se_interpreta_bien():
    """«1.250,50» son mil doscientos cincuenta, no uno con doscientos cincuenta."""
    dataset = make_dataset(
        productos=[_product("PRD-0001", "Motor")],
        suministradores=[_supplier("SUP-0001", "Alfa")],
        relaciones=[_relation("SUP-0001", "PRD-0001")],
        precios=[_quote("PRC-1", "SUP-0001", "PRD-0001", "1.250,50", "01/08/2026")],
    )
    assert build_leaderboards(dataset, today=TODAY)[0].winner().price == pytest.approx(1250.50)


def test_producto_descontinuado_se_excluye_por_defecto():
    dataset = make_dataset(
        productos=[_product("PRD-0001", "Viejo", estado="Descontinuado")],
        suministradores=[_supplier("SUP-0001", "Alfa")],
        relaciones=[_relation("SUP-0001", "PRD-0001")],
        precios=[_quote("PRC-1", "SUP-0001", "PRD-0001", "10", "01/08/2026")],
    )
    assert build_leaderboards(dataset, today=TODAY) == ()
    assert leaderboard_for_product(dataset, "PRD-0001", today=TODAY) is not None


def test_producto_sin_ofertas_aparece_vacio_y_al_final():
    dataset = make_dataset(
        productos=[_product("PRD-0001", "Sin ofertas"), _product("PRD-0002", "Con ofertas")],
        suministradores=[_supplier("SUP-0001", "Alfa")],
        relaciones=[_relation("SUP-0001", "PRD-0002")],
        precios=[_quote("PRC-1", "SUP-0001", "PRD-0002", "10", "01/08/2026")],
    )
    boards = build_leaderboards(dataset, today=TODAY)

    assert [board.product_name for board in boards] == ["Con ofertas", "Sin ofertas"]
    assert boards[1].has_quotes is False
    assert boards[1].winner() is None


def test_precio_no_numerico_se_ignora():
    dataset = make_dataset(
        productos=[_product("PRD-0001", "Motor")],
        suministradores=[_supplier("SUP-0001", "Alfa")],
        relaciones=[_relation("SUP-0001", "PRD-0001")],
        precios=[_quote("PRC-1", "SUP-0001", "PRD-0001", "pendiente", "01/08/2026")],
    )
    assert build_leaderboards(dataset, today=TODAY)[0].has_quotes is False


def test_la_oferta_destacada_es_la_ganadora_si_el_proveedor_gana_algo():
    dataset = make_dataset(
        productos=[_product("PRD-0001", "Motor"), _product("PRD-0002", "Bearing")],
        suministradores=[_supplier("SUP-0001", "Alfa"), _supplier("SUP-0002", "Beta")],
        relaciones=[
            _relation("SUP-0001", "PRD-0001"),
            _relation("SUP-0001", "PRD-0002"),
            _relation("SUP-0002", "PRD-0002"),
        ],
        precios=[
            _quote("PRC-1", "SUP-0001", "PRD-0001", "800", "01/08/2026"),
            _quote("PRC-2", "SUP-0001", "PRD-0002", "300", "05/08/2026"),
            _quote("PRC-3", "SUP-0002", "PRD-0002", "250", "05/08/2026"),
        ],
    )
    headline = headline_quote_by_supplier(dataset, today=TODAY)

    # Alfa gana Motor (es el único), así que su oferta destacada es esa.
    assert headline["SUP-0001"].product_id == "PRD-0001"
    assert headline["SUP-0002"].product_id == "PRD-0002"
    assert winning_supplier_ids(dataset, today=TODAY) == {"SUP-0001", "SUP-0002"}


def test_si_no_gana_nada_se_muestra_su_oferta_mas_reciente():
    """Nunca la «más barata»: serían de productos distintos, no comparables."""
    dataset = make_dataset(
        productos=[_product("PRD-0001", "Motor"), _product("PRD-0002", "Bearing")],
        suministradores=[_supplier("SUP-0001", "Alfa"), _supplier("SUP-0002", "Beta")],
        relaciones=[
            _relation("SUP-0001", "PRD-0001"),
            _relation("SUP-0001", "PRD-0002"),
            _relation("SUP-0002", "PRD-0001"),
            _relation("SUP-0002", "PRD-0002"),
        ],
        precios=[
            # Beta gana los dos productos.
            _quote("PRC-1", "SUP-0002", "PRD-0001", "100", "01/08/2026"),
            _quote("PRC-2", "SUP-0002", "PRD-0002", "50", "01/08/2026"),
            # Alfa pierde en ambos: su rodamiento (200) es más barato que su
            # motor (900), pero lo que interesa ver es su oferta más reciente.
            _quote("PRC-3", "SUP-0001", "PRD-0002", "200", "01/08/2026"),
            _quote("PRC-4", "SUP-0001", "PRD-0001", "900", "10/08/2026"),
        ],
    )
    headline = headline_quote_by_supplier(dataset, today=TODAY)

    assert "SUP-0001" not in winning_supplier_ids(dataset, today=TODAY)
    assert headline["SUP-0001"].product_id == "PRD-0001"
    assert headline["SUP-0001"].price == pytest.approx(900.0)


def test_summarize_cuenta_estados_y_avisa_de_monedas_mixtas():
    dataset = make_dataset(
        productos=[_product("PRD-0001", "Motor"), _product("PRD-0002", "Bearing")],
        suministradores=[_supplier("SUP-0001", "Alfa"), _supplier("SUP-0002", "Beta")],
        relaciones=[
            _relation("SUP-0001", "PRD-0001", REL_ESTADO_CONFIRMADO),
            _relation("SUP-0002", "PRD-0001", REL_ESTADO_POTENCIAL),
            _relation("SUP-0002", "PRD-0002", REL_ESTADO_DESCARTADO),
        ],
        precios=[
            _quote("PRC-1", "SUP-0001", "PRD-0001", "1000", "01/08/2026", moneda="EUR"),
            _quote("PRC-2", "SUP-0002", "PRD-0001", "900", "01/08/2026", moneda="USD"),
        ],
    )
    stats = summarize(dataset)

    assert stats.productos_activos == 2
    assert stats.productos_con_oferta == 1
    assert stats.productos_sin_oferta == 1
    assert (stats.confirmados, stats.potenciales, stats.descartados) == (1, 1, 1)
    assert stats.monedas_mixtas == ("Motor",)


def test_dataset_vacio_no_revienta():
    assert build_leaderboards(make_dataset(), today=TODAY) == ()
    assert summarize(make_dataset()).productos_activos == 0
