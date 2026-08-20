"""Los tokens de diseño se resuelven y el tema no deja hex sin resolver."""

from __future__ import annotations

import re

import pytest

from ui.design_tokens import color, css_variables, load_design_tokens, mix_hex, motion, rounded
from ui.palette import (
    STATUS_NEUTRAL,
    price_style,
    supplier_state_modifier,
    supplier_state_style,
    validity_style,
)
from config.settings import (
    REL_ESTADO_CONFIRMADO,
    REL_ESTADO_DESCARTADO,
    REL_ESTADO_POTENCIAL,
)

_HEX = re.compile(r"^#[0-9a-fA-F]{6}$")


def test_la_capa_space_sobreescribe_a_cal():
    """El acento es el verde Sanzar, no el azul de Cal."""
    assert color("brand-accent") == "#2D6A4F"


def test_los_neutros_se_heredan_de_cal():
    assert color("canvas") == "#ffffff"
    assert color("ink") == "#111111"
    assert rounded("lg") == "12px"


def test_las_referencias_entre_tokens_se_resuelven():
    """`{colors.brand-accent}` no debe llegar literal al CSS."""
    components = load_design_tokens().get("components", {})
    value = components.get("button-primary", {}).get("backgroundColor", "")
    assert value == "#2D6A4F"
    assert "{" not in value


def test_css_variables_no_deja_placeholders():
    css = css_variables()
    assert "{colors." not in css
    assert "{rounded." not in css
    assert css.strip().startswith(":root {")
    assert css.strip().endswith("}")


@pytest.mark.parametrize(
    "variable",
    [
        "--ui-accent",
        "--ui-supplier-confirmado",
        "--ui-supplier-potencial",
        "--ui-supplier-descartado",
        "--ui-price-winner",
        "--ui-price-expired",
        "--ui-duration-base",
        "--ui-ease-out",
        "--ui-stagger-step",
    ],
)
def test_las_variables_clave_estan_presentes(variable):
    assert variable in css_variables()


def test_ninguna_animacion_supera_300ms():
    """Regla dura del sistema de movimiento."""
    for token in ("duration-instant", "duration-fast", "duration-base", "duration-slow"):
        value = motion(token)
        assert value.endswith("ms")
        assert int(value.removesuffix("ms")) <= 300


def test_nunca_se_usa_ease_in_como_curva_de_entrada():
    """`ease-in` retrasa el arranque y se percibe como lag."""
    assert not motion("ease-out").startswith("ease-in")
    assert motion("ease-out").startswith("cubic-bezier")


def test_el_tema_no_usa_transition_all_ni_propiedades_de_layout():
    from ui.theme import _stylesheet

    # Se comprueban las reglas reales, no los comentarios: la documentación del
    # fichero cita justamente lo que está prohibido.
    css = re.sub(r"/\*.*?\*/", "", _stylesheet(), flags=re.DOTALL)
    assert "transition: all" not in css
    # Animar width/height/margin/padding fuerza layout en cada fotograma.
    for prohibited in ("transition: width", "transition: height", "transition: margin", "transition: padding"):
        assert prohibited not in css
    # Nada entra desde scale(0).
    assert "scale(0)" not in css
    # El hover va tras la media query de puntero fino.
    assert "@media (hover: hover) and (pointer: fine)" in css
    assert "@media (prefers-reduced-motion: reduce)" in css


@pytest.mark.parametrize(
    "estado,modifier",
    [
        (REL_ESTADO_CONFIRMADO, "confirmado"),
        (REL_ESTADO_POTENCIAL, "potencial"),
        (REL_ESTADO_DESCARTADO, "descartado"),
        ("lo que sea", "neutral"),
    ],
)
def test_cada_estado_tiene_su_modificador(estado, modifier):
    assert supplier_state_modifier(estado) == modifier


def test_los_estados_tienen_colores_distintos():
    confirmado = supplier_state_style(REL_ESTADO_CONFIRMADO)
    potencial = supplier_state_style(REL_ESTADO_POTENCIAL)
    descartado = supplier_state_style(REL_ESTADO_DESCARTADO)
    assert len({confirmado.fg, potencial.fg, descartado.fg}) == 3


def test_los_estilos_producen_hex_validos():
    for style in (STATUS_NEUTRAL, supplier_state_style(REL_ESTADO_CONFIRMADO)):
        assert _HEX.match(style.bg) and _HEX.match(style.border) and _HEX.match(style.fg)
        assert "background:" in style.css()


def test_una_oferta_caducada_manda_sobre_ser_ganadora():
    caducada = price_style(is_winner=True, is_expired=True)
    ganadora = price_style(is_winner=True, is_expired=False)
    assert caducada.fg != ganadora.fg


def test_validity_style_avisa_antes_de_caducar():
    from datetime import date

    today = date(2026, 8, 20)
    assert validity_style("15/08/2026", today=today).fg != validity_style("31/12/2026", today=today).fg
    assert validity_style("", today=today) == STATUS_NEUTRAL


def test_mix_hex_interpola():
    assert mix_hex("#000000", "#ffffff", 0.0) == "#000000"
    assert mix_hex("#000000", "#ffffff", 1.0) == "#ffffff"
