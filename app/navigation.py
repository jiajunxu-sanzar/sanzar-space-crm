"""Navegación lateral por rol — única fuente de verdad de las pestañas visibles.

Mismo patrón que ``app/navigation.py`` en ``sanzar-crm-web``: un único módulo
declara ``PAGES``, sus etiquetas/iconos/descripciones, las secciones del menú y
las **exclusiones explícitas por rol**. Nunca se duplican listas de páginas:
``pages_for_role()`` deriva todo por diferencia sobre ``PAGES``.

Roles (§3):

- ``admin``      → todas las páginas, incluida «Usuarios».
- ``comprador``  → Home, Acciones, Suministradores, Compras.
- ``comercial``  → Home, Ofertas.

Cualquier rol desconocido cae a ``comercial`` (el de menor privilegio), nunca a
admin: un typo en la hoja `Usuarios` no puede escalar permisos.
"""

from __future__ import annotations

from typing import Final

HOME_PAGE: Final[str] = "Home"
ACCIONES_PAGE: Final[str] = "Acciones"
SUMINISTRADORES_PAGE: Final[str] = "Suministradores"
COMPRAS_PAGE: Final[str] = "Compras"
OFERTAS_PAGE: Final[str] = "Ofertas"
USUARIOS_PAGE: Final[str] = "Usuarios"

PAGES: Final[tuple[str, ...]] = (
    HOME_PAGE,
    ACCIONES_PAGE,
    SUMINISTRADORES_PAGE,
    COMPRAS_PAGE,
    OFERTAS_PAGE,
    USUARIOS_PAGE,
)

_PAGES_SET: Final[frozenset[str]] = frozenset(PAGES)

PAGE_MENU_LABELS: Final[dict[str, str]] = {
    HOME_PAGE: "🏠 Home",
    ACCIONES_PAGE: "⚡ Acciones",
    SUMINISTRADORES_PAGE: "🏭 Suministradores",
    COMPRAS_PAGE: "🛒 Compras",
    OFERTAS_PAGE: "📤 Ofertas",
    USUARIOS_PAGE: "🔐 Usuarios",
}

PAGE_ICONS: Final[dict[str, str]] = {
    HOME_PAGE: ":material/space_dashboard:",
    ACCIONES_PAGE: ":material/bolt:",
    SUMINISTRADORES_PAGE: ":material/factory:",
    COMPRAS_PAGE: ":material/shopping_cart:",
    OFERTAS_PAGE: ":material/outgoing_mail:",
    USUARIOS_PAGE: ":material/admin_panel_settings:",
}

PAGE_DESCRIPTIONS: Final[dict[str, str]] = {
    HOME_PAGE: "El suministrador más barato de cada producto, ahora mismo",
    ACCIONES_PAGE: "Tu bandeja: próximas acciones con suministradores",
    SUMINISTRADORES_PAGE: "Fichas, conversaciones y precios por producto",
    COMPRAS_PAGE: "Pedidos de compra a suministradores",
    OFERTAS_PAGE: "Ofertas enviadas a potenciales clientes",
    USUARIOS_PAGE: "Gestión de usuarios y roles de la app",
}

NAV_SECTIONS: Final[tuple[tuple[str, tuple[str, ...]], ...]] = (
    ("Suministro", (HOME_PAGE, ACCIONES_PAGE, SUMINISTRADORES_PAGE, COMPRAS_PAGE)),
    ("Comercial", (OFERTAS_PAGE,)),
    ("Administración", (USUARIOS_PAGE,)),
)

# Páginas reservadas: se muestran en el menú, pero solo pintan un aviso
# "Próximamente" (§3.4 y §3.5). Vivir aquí evita que la navegación y las
# páginas se desincronicen.
PLACEHOLDER_PAGES: Final[frozenset[str]] = frozenset({COMPRAS_PAGE, OFERTAS_PAGE})

ROLE_ADMIN: Final[str] = "admin"
ROLE_COMPRADOR: Final[str] = "comprador"
ROLE_COMERCIAL: Final[str] = "comercial"

KNOWN_APP_ROLES: Final[frozenset[str]] = frozenset({ROLE_ADMIN, ROLE_COMPRADOR, ROLE_COMERCIAL})

ROLE_LABELS: Final[dict[str, str]] = {
    ROLE_ADMIN: "Administrador",
    ROLE_COMPRADOR: "Compras",
    ROLE_COMERCIAL: "Comercial",
}

# Alias tolerantes: si alguien escribe "compras" o "procurement" en la hoja,
# lo entendemos en vez de degradar silenciosamente a comercial.
ROLE_ALIASES: Final[dict[str, str]] = {
    "administrador": ROLE_ADMIN,
    "compras": ROLE_COMPRADOR,
    "procurement": ROLE_COMPRADOR,
    "purchasing": ROLE_COMPRADOR,
    "ventas": ROLE_COMERCIAL,
    "sales": ROLE_COMERCIAL,
}

# Exclusiones por rol — ÚNICO sitio donde se decide quién ve qué.
_PAGES_EXCLUSIVE_TO_ADMIN: Final[frozenset[str]] = frozenset({USUARIOS_PAGE})
COMPRADOR_DENIED_PAGES: Final[frozenset[str]] = _PAGES_EXCLUSIVE_TO_ADMIN | {OFERTAS_PAGE}
COMERCIAL_DENIED_PAGES: Final[frozenset[str]] = _PAGES_EXCLUSIVE_TO_ADMIN | {
    ACCIONES_PAGE,
    SUMINISTRADORES_PAGE,
    COMPRAS_PAGE,
}

# Páginas que necesitan leer el dataset completo de Google Sheets. Las demás
# (placeholders) se pintan sin tocar la API: cuota que no se gasta.
PAGES_REQUIRING_DATA: Final[frozenset[str]] = frozenset(
    {HOME_PAGE, ACCIONES_PAGE, SUMINISTRADORES_PAGE, USUARIOS_PAGE}
)


def normalize_role(role: str) -> str:
    """Devuelve un rol conocido; desconocido → ``comercial`` (menor privilegio)."""
    slug = (role or "").strip().lower()
    if slug in KNOWN_APP_ROLES:
        return slug
    return ROLE_ALIASES.get(slug, ROLE_COMERCIAL)


def page_menu_title(canonical_page: str) -> str:
    """Etiqueta del menú (emoji + nombre) para una clave de ``PAGES``."""
    return PAGE_MENU_LABELS[canonical_page]


def pages_for_role(role: str) -> tuple[str, ...]:
    slug = normalize_role(role)
    if slug == ROLE_ADMIN:
        return PAGES
    denied = COMPRADOR_DENIED_PAGES if slug == ROLE_COMPRADOR else COMERCIAL_DENIED_PAGES
    return tuple(page for page in PAGES if page not in denied)


def can_view(role: str, page: str) -> bool:
    return page in pages_for_role(role)


def unavailable_pages_for_role(role: str) -> tuple[str, ...]:
    allowed = frozenset(pages_for_role(role))
    return tuple(page for page in PAGES if page not in allowed)


def nav_sections_for_role(role: str) -> tuple[tuple[str, tuple[str, ...]], ...]:
    """Secciones del menú con solo las páginas visibles (las vacías se ocultan)."""
    allowed = frozenset(pages_for_role(role))
    out: list[tuple[str, tuple[str, ...]]] = []
    for section_title, section_pages in NAV_SECTIONS:
        visible = tuple(page for page in section_pages if page in allowed)
        if visible:
            out.append((section_title, visible))
    return tuple(out)


# ---------------------------------------------------------------------------
# Contrato de integridad — falla al importar si alguien deja el menú incoherente
# ---------------------------------------------------------------------------


def _assert_navigation_contract() -> None:
    for name, mapping in (
        ("PAGE_MENU_LABELS", PAGE_MENU_LABELS),
        ("PAGE_ICONS", PAGE_ICONS),
        ("PAGE_DESCRIPTIONS", PAGE_DESCRIPTIONS),
    ):
        if frozenset(mapping.keys()) != _PAGES_SET:
            raise AssertionError(f"{name} keys must match PAGES exactly")

    section_pages_flat = [page for _, pages in NAV_SECTIONS for page in pages]
    if len(section_pages_flat) != len(set(section_pages_flat)):
        raise AssertionError("NAV_SECTIONS must not repeat pages")
    if frozenset(section_pages_flat) != _PAGES_SET:
        raise AssertionError("NAV_SECTIONS must cover PAGES exactly")

    if not PLACEHOLDER_PAGES.issubset(_PAGES_SET):
        raise AssertionError("PLACEHOLDER_PAGES must reference only PAGES identifiers")
    if not PAGES_REQUIRING_DATA.issubset(_PAGES_SET):
        raise AssertionError("PAGES_REQUIRING_DATA must reference only PAGES identifiers")
    if PAGES_REQUIRING_DATA & PLACEHOLDER_PAGES:
        raise AssertionError("Una página placeholder no debe cargar datos de Sheets")

    for role in KNOWN_APP_ROLES:
        visible = pages_for_role(role)
        if not visible:
            raise AssertionError(f"El rol {role} se quedaría sin ninguna página")
        if HOME_PAGE not in visible:
            raise AssertionError("Todos los roles deben ver Home")
        if not frozenset(visible).issubset(_PAGES_SET):
            raise AssertionError(f"pages_for_role({role}) devolvió páginas fuera de PAGES")

    admin_pages = frozenset(pages_for_role(ROLE_ADMIN))
    for role in (ROLE_COMPRADOR, ROLE_COMERCIAL):
        if not frozenset(pages_for_role(role)).issubset(admin_pages):
            raise AssertionError("Admin debe ver, como mínimo, todo lo que ve cualquier otro rol")
    if USUARIOS_PAGE in pages_for_role(ROLE_COMPRADOR) or USUARIOS_PAGE in pages_for_role(ROLE_COMERCIAL):
        raise AssertionError("Usuarios es exclusiva de admin")


_assert_navigation_contract()
