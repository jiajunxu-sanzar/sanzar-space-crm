"""Contrato de navegación: quién ve qué, y que el menú no se desincronice."""

from __future__ import annotations

import pytest

from app.navigation import (
    ACCIONES_PAGE,
    COMPRAS_PAGE,
    HOME_PAGE,
    KNOWN_APP_ROLES,
    OFERTAS_PAGE,
    PAGES,
    PLACEHOLDER_PAGES,
    ROLE_ADMIN,
    ROLE_COMERCIAL,
    ROLE_COMPRADOR,
    SUMINISTRADORES_PAGE,
    USUARIOS_PAGE,
    can_view,
    nav_sections_for_role,
    normalize_role,
    page_menu_title,
    pages_for_role,
    unavailable_pages_for_role,
)


def test_admin_ve_todas_las_paginas():
    assert pages_for_role(ROLE_ADMIN) == PAGES


def test_comprador_ve_suministro_pero_no_usuarios_ni_ofertas():
    visible = pages_for_role(ROLE_COMPRADOR)
    assert visible == (HOME_PAGE, ACCIONES_PAGE, SUMINISTRADORES_PAGE, COMPRAS_PAGE)
    assert USUARIOS_PAGE not in visible
    assert OFERTAS_PAGE not in visible


def test_comercial_solo_ve_home_y_ofertas():
    assert pages_for_role(ROLE_COMERCIAL) == (HOME_PAGE, OFERTAS_PAGE)


@pytest.mark.parametrize("raw", ["", "   ", "root", "superadmin", "desconocido", None])
def test_un_rol_desconocido_cae_al_menor_privilegio(raw):
    """Un typo en la hoja Usuarios nunca puede escalar permisos."""
    assert normalize_role(raw) == ROLE_COMERCIAL
    assert USUARIOS_PAGE not in pages_for_role(raw)


@pytest.mark.parametrize(
    "alias,expected",
    [
        ("ADMIN", ROLE_ADMIN),
        ("Administrador", ROLE_ADMIN),
        ("compras", ROLE_COMPRADOR),
        ("Procurement", ROLE_COMPRADOR),
        ("sales", ROLE_COMERCIAL),
    ],
)
def test_alias_de_rol_reconocidos(alias, expected):
    assert normalize_role(alias) == expected


def test_can_view_coincide_con_pages_for_role():
    for role in KNOWN_APP_ROLES:
        for page in PAGES:
            assert can_view(role, page) == (page in pages_for_role(role))


def test_unavailable_es_el_complemento_exacto():
    for role in KNOWN_APP_ROLES:
        visible = set(pages_for_role(role))
        hidden = set(unavailable_pages_for_role(role))
        assert visible | hidden == set(PAGES)
        assert visible & hidden == set()


def test_las_secciones_solo_muestran_paginas_permitidas():
    for role in KNOWN_APP_ROLES:
        allowed = set(pages_for_role(role))
        for _, section_pages in nav_sections_for_role(role):
            assert section_pages, "una sección vacía no debe aparecer"
            assert set(section_pages).issubset(allowed)


def test_todos_los_roles_tienen_al_menos_home():
    for role in KNOWN_APP_ROLES:
        assert HOME_PAGE in pages_for_role(role)


def test_los_placeholders_son_paginas_reales():
    assert PLACEHOLDER_PAGES == {COMPRAS_PAGE, OFERTAS_PAGE}
    assert PLACEHOLDER_PAGES.issubset(set(PAGES))


def test_cada_pagina_tiene_etiqueta_de_menu():
    for page in PAGES:
        assert page_menu_title(page).endswith(page)
