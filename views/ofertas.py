"""Ofertas — página reservada (§3.5).

Es el flujo **inverso** al resto de la app: ofertas que Sanzar envía a
potenciales clientes de sus propios productos y servicios. Cuando se desarrolle
necesitará su propia hoja (`OfertasEnviadas`), con una forma muy parecida a
`HistoricoPrecios` pero en sentido saliente: destinatario, producto/servicio
ofertado, importe, estado de la oferta y próxima acción.
"""

from __future__ import annotations

from services.dataset import SpaceDataset
from services.users_service import AppUser
from ui.components.page_header import render_coming_soon, render_page_header


def render(dataset: SpaceDataset, user: AppUser) -> None:
    del dataset, user  # la página aún no lee datos: no gasta cuota de la API

    render_page_header("Ofertas")
    render_coming_soon(
        "Próximamente",
        "Aquí se registrarán las ofertas que Sanzar envía a potenciales clientes: "
        "destinatario, producto o servicio ofertado, importe, estado de la oferta y "
        "próxima acción. Es el sentido contrario al de Suministradores, y por eso "
        "tendrá su propia hoja (OfertasEnviadas) en lugar de reutilizar HistoricoPrecios.",
    )
