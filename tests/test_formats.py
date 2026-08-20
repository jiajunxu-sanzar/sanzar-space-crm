"""Fechas y números: lo que entra desde una hoja de cálculo editada a mano."""

from __future__ import annotations

from datetime import date

import pytest

from services.locale_numbers import format_decimal, format_money, parse_decimal, parse_int
from services.sheet_date_format import (
    days_until,
    is_valid_dd_mm_yyyy,
    is_valid_hh_mm,
    normalize_dd_mm_yyyy,
    normalize_hh_mm,
    parse_sheet_date,
    validate_dd_mm_yyyy_fields,
)


# --- Números --------------------------------------------------------------


@pytest.mark.parametrize(
    "raw,expected",
    [
        ("1.250,50", 1250.50),   # es-ES
        ("1,250.50", 1250.50),   # en-US
        ("1250.50", 1250.50),
        ("1250,50", 1250.50),
        ("1.250.000", 1250000.0),
        ("1 234,56 €", 1234.56),
        ("-12", -12.0),
        (1500, 1500.0),
        (99.5, 99.5),
    ],
)
def test_parse_decimal_tolera_ambos_locales(raw, expected):
    assert parse_decimal(raw) == pytest.approx(expected)


@pytest.mark.parametrize("raw", ["", "   ", None, "a negociar", "-", ","])
def test_parse_decimal_devuelve_none_si_no_es_numero(raw):
    assert parse_decimal(raw) is None


def test_parse_decimal_no_confunde_booleanos_con_numeros():
    assert parse_decimal(True) is None


def test_parse_int_trunca():
    assert parse_int("50,9") == 50
    assert parse_int("no") is None


def test_format_decimal_usa_convencion_espanola():
    assert format_decimal(1250.5) == "1.250,50"
    assert format_decimal(None) == ""


def test_format_money_anade_el_simbolo():
    assert format_money(1250.5, "EUR") == "1.250,50 €"
    assert format_money(900, "USD") == "900,00 $"
    assert format_money(None) == "—"


# --- Fechas ---------------------------------------------------------------


@pytest.mark.parametrize("raw", ["05/04/2026", "31/12/2025", ""])
def test_fechas_validas(raw):
    assert is_valid_dd_mm_yyyy(raw) is True


@pytest.mark.parametrize("raw", ["2026-04-05", "5/4/2026", "31/13/2025", "32/01/2026", "hoy"])
def test_fechas_invalidas(raw):
    assert is_valid_dd_mm_yyyy(raw) is False


@pytest.mark.parametrize(
    "raw,expected",
    [
        ("05/04/2026", date(2026, 4, 5)),
        ("2026-04-05", date(2026, 4, 5)),
        ("05-04-2026", date(2026, 4, 5)),
        ("05/04/2026 09:30:00", date(2026, 4, 5)),
        (date(2026, 4, 5), date(2026, 4, 5)),
    ],
)
def test_parse_sheet_date_es_tolerante_al_leer(raw, expected):
    assert parse_sheet_date(raw) == expected


@pytest.mark.parametrize("raw", ["", None, "no es fecha"])
def test_parse_sheet_date_devuelve_none(raw):
    assert parse_sheet_date(raw) is None


def test_normalize_dd_mm_yyyy_canoniza_o_vacia():
    assert normalize_dd_mm_yyyy("2026-04-05") == "05/04/2026"
    assert normalize_dd_mm_yyyy("basura") == ""


def test_dia_y_mes_no_se_confunden():
    """dayfirst: 05/04 es 5 de abril, nunca 4 de mayo."""
    assert parse_sheet_date("05/04/2026") == date(2026, 4, 5)


@pytest.mark.parametrize("raw,expected", [("09:30", True), ("9:30", True), ("24:00", False), ("09:60", False), ("", True)])
def test_horas(raw, expected):
    assert is_valid_hh_mm(raw) is expected


def test_normalize_hh_mm_rellena_con_cero():
    assert normalize_hh_mm("9:05") == "09:05"
    assert normalize_hh_mm("nope") == ""


def test_validate_dd_mm_yyyy_fields_lista_las_etiquetas_malas():
    message = validate_dd_mm_yyyy_fields(
        [("Fecha de oferta", "2026-01-01"), ("Validez", "31/12/2026")]
    )
    assert message is not None and "Fecha de oferta" in message and "Validez" not in message


def test_validate_dd_mm_yyyy_fields_sin_errores_devuelve_none():
    assert validate_dd_mm_yyyy_fields([("Validez", "31/12/2026"), ("Alta", "")]) is None


def test_days_until():
    assert days_until("22/08/2026", today=date(2026, 8, 20)) == 2
    assert days_until("15/08/2026", today=date(2026, 8, 20)) == -5
    assert days_until("", today=date(2026, 8, 20)) is None
