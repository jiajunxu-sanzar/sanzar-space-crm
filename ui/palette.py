"""Estilos semánticos: de un valor de negocio a un chip con color.

Toda decisión de "qué color tiene este estado" vive aquí, derivada de los
tokens de ``DESIGN-space.md``. Las páginas nunca escriben hex a mano: piden
``supplier_state_style("Descartado")`` y reciben fondo, borde y texto
coherentes. Añadir un estado nuevo es añadir un token y una rama, no repintar
media app.
"""

from __future__ import annotations

import unicodedata
from dataclasses import dataclass
from datetime import date

from config.settings import (
    ESTADO_ACCION_COMPLETADA,
    PRODUCTO_ESTADO_DESCONTINUADO,
    REL_ESTADO_CONFIRMADO,
    REL_ESTADO_DESCARTADO,
    REL_ESTADO_POTENCIAL,
)
from services.sheet_date_format import parse_sheet_date, today_madrid
from ui.design_tokens import color, load_design_tokens, pastel_triplet


@dataclass(frozen=True, slots=True)
class StatusStyle:
    bg: str
    border: str
    fg: str

    def css(self) -> str:
        return f"background:{self.bg};border:1px solid {self.border};color:{self.fg};"


def _from_token(token: str) -> StatusStyle:
    bg, border, fg = pastel_triplet(color(token))
    return StatusStyle(bg, border, fg)


def _neutral() -> StatusStyle:
    tokens = load_design_tokens().get("colors", {})
    return StatusStyle(
        str(tokens.get("surface-card", "#f5f5f5")),
        str(tokens.get("hairline", "#e5e7eb")),
        str(tokens.get("muted", "#6b7280")),
    )


STATUS_NEUTRAL = _neutral()
STATUS_INFO = _from_token("semantic-info")
STATUS_SUCCESS = _from_token("semantic-success")
STATUS_WARNING = _from_token("semantic-warning")
STATUS_DANGER = _from_token("semantic-error")
STATUS_PURPLE = _from_token("semantic-purple")

ACCENT = color("brand-accent")
ACCENT_SOFT = color("brand-accent-soft")
ACCENT_HOVER = color("brand-accent-hover")


def _normalize(value: object) -> str:
    """Minúsculas sin acentos: «Reunión» y «reunion» deben caer en la misma rama."""
    text = ("" if value is None else str(value)).strip().lower()
    return "".join(
        char for char in unicodedata.normalize("NFD", text) if unicodedata.category(char) != "Mn"
    )


# --- Relación proveedor ↔ producto ---------------------------------------


def supplier_state_style(estado: str) -> StatusStyle:
    text = _normalize(estado)
    if text == _normalize(REL_ESTADO_CONFIRMADO):
        return _from_token("supplier-confirmado")
    if text == _normalize(REL_ESTADO_POTENCIAL):
        return _from_token("supplier-potencial")
    if text == _normalize(REL_ESTADO_DESCARTADO):
        return _from_token("supplier-descartado")
    return STATUS_NEUTRAL


def supplier_state_modifier(estado: str) -> str:
    """Sufijo de clase CSS para tarjetas: ``confirmado`` | ``potencial`` | ``descartado``."""
    text = _normalize(estado)
    if text == _normalize(REL_ESTADO_CONFIRMADO):
        return "confirmado"
    if text == _normalize(REL_ESTADO_POTENCIAL):
        return "potencial"
    if text == _normalize(REL_ESTADO_DESCARTADO):
        return "descartado"
    return "neutral"


# --- Producto -------------------------------------------------------------


def product_state_style(estado: str) -> StatusStyle:
    if _normalize(estado) == _normalize(PRODUCTO_ESTADO_DESCONTINUADO):
        return STATUS_NEUTRAL
    return STATUS_SUCCESS


# --- Precios --------------------------------------------------------------


def price_style(*, is_winner: bool, is_expired: bool) -> StatusStyle:
    """El ganador manda sobre el resto; la caducidad se avisa, no se oculta."""
    if is_expired:
        return _from_token("price-expired")
    if is_winner:
        return _from_token("price-winner")
    return STATUS_NEUTRAL


def validity_style(validez_fecha: str, *, today: date | None = None) -> StatusStyle:
    """Caducada = rojo; caduca en ≤ 14 días = ámbar; el resto, neutro."""
    parsed = parse_sheet_date(validez_fecha)
    if parsed is None:
        return STATUS_NEUTRAL
    reference = today or today_madrid()
    days = (parsed - reference).days
    if days < 0:
        return STATUS_DANGER
    if days <= 14:
        return STATUS_WARNING
    return STATUS_SUCCESS


# --- Acciones -------------------------------------------------------------


def action_due_style(proxima_fecha: str, estado_accion: str = "", *, today: date | None = None) -> StatusStyle:
    if _normalize(estado_accion) == _normalize(ESTADO_ACCION_COMPLETADA):
        return STATUS_SUCCESS
    parsed = parse_sheet_date(proxima_fecha)
    if parsed is None:
        return STATUS_NEUTRAL
    reference = today or today_madrid()
    if parsed < reference:
        return STATUS_DANGER
    if parsed == reference:
        return STATUS_WARNING
    return STATUS_INFO


def action_bucket_style(bucket_value: str) -> StatusStyle:
    """Color del encabezado de cada grupo de la bandeja."""
    return {
        "vencida": STATUS_DANGER,
        "hoy": STATUS_WARNING,
        "manana": STATUS_INFO,
        "proximos": STATUS_INFO,
        "futuro": STATUS_NEUTRAL,
        "sin_fecha": STATUS_NEUTRAL,
    }.get(_normalize(bucket_value), STATUS_NEUTRAL)


# --- Conversaciones -------------------------------------------------------

_CONVERSATION_ICONS: dict[str, str] = {
    "email": "mail",
    "reunion": "groups",
    "llamada": "call",
    "otro": "more_horiz",
}


def conversation_icon(tipo: str) -> str:
    """Nombre de Material Symbol para el tipo de conversación."""
    return _CONVERSATION_ICONS.get(_normalize(tipo), "chat")


def conversation_style(tipo: str) -> StatusStyle:
    text = _normalize(tipo)
    if text == "email":
        return STATUS_INFO
    if text == "reunion":
        return STATUS_PURPLE
    if text == "llamada":
        return STATUS_SUCCESS
    return STATUS_NEUTRAL
