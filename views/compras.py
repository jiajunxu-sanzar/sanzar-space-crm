"""Compras — página reservada (§3.4).

Sin lógica todavía. Cuando se active, puede reutilizar directamente el patrón
``COMPRAS_HEADERS`` que ya existe en el CRM de clientes (referencia, contacto
del proveedor, estado, fechas, importe, líneas de pedido) apuntando a
`Suministradores` en vez de a proveedores sueltos.

Se deja como página real —y no oculta— a propósito: el equipo de compras ve que
está en camino y no pregunta si se ha olvidado.
"""

from __future__ import annotations

from services.dataset import SpaceDataset
from services.users_service import AppUser
from ui.components.page_header import render_coming_soon, render_page_header


def render(dataset: SpaceDataset, user: AppUser) -> None:
    del dataset, user  # la página aún no lee datos: no gasta cuota de la API

    render_page_header("Compras")
    render_coming_soon(
        "Próximamente",
        "Aquí vivirán los pedidos de compra a suministradores: referencia, proveedor, "
        "estado, fechas, importe y líneas de pedido. Reutilizará el mismo modelo de "
        "Compras que ya funciona en el CRM de clientes, pero apuntando a la hoja "
        "Suministradores de este proyecto.",
    )
