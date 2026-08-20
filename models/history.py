"""Modelos de los dos históricos: conversaciones y precios.

Ambos cuelgan siempre de una pareja (``supplier_id``, ``product_id``): una
conversación o una oferta se refieren a un producto concreto, nunca al
proveedor «en abstracto».
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Any, Mapping

from config.settings import (
    ESTADO_ACCION_COMPLETADA,
    ESTADO_ACCION_OPCIONES,
    ESTADO_ACCION_PENDIENTE,
    MONEDA_EUR,
    MONEDA_SIMBOLOS,
    TIPO_CONVERSACION_OPCIONES,
    TIPO_CONVERSACION_OTRO,
)
from services.locale_numbers import format_money, parse_decimal
from services.sheet_date_format import parse_sheet_date


def _text(row: Mapping[str, Any], key: str, default: str = "") -> str:
    return str(row.get(key, default) or default).strip()


def _match_option(raw: str, options: tuple[str, ...], fallback: str) -> str:
    needle = raw.casefold()
    return next((opt for opt in options if opt.casefold() == needle), fallback)


@dataclass(frozen=True, slots=True)
class Conversation:
    """Una fila de ``HistoricoConversaciones``.

    Réplica deliberada del patrón ``ACCIONES_HEADERS`` del CRM de clientes:
    ``persona_contacto`` (quién habló) y ``proxima_accion_persona`` (quién
    ejecuta lo siguiente) son campos distintos a propósito.
    """

    historial_conversacion_id: str
    supplier_id: str
    product_id: str
    tipo_conversacion: str = TIPO_CONVERSACION_OTRO
    fecha_contacto: str = ""
    hora_contacto: str = ""
    persona_contacto: str = ""
    resumen: str = ""
    proxima_accion_detalle: str = ""
    proxima_accion_fecha: str = ""
    proxima_accion_persona: str = ""
    estado_accion: str = ESTADO_ACCION_PENDIENTE
    created_at: str = ""
    updated_at: str = ""

    @property
    def is_pendiente(self) -> bool:
        return self.estado_accion.casefold() == ESTADO_ACCION_PENDIENTE.casefold()

    @property
    def fecha_contacto_date(self) -> date | None:
        return parse_sheet_date(self.fecha_contacto)

    @property
    def proxima_accion_date(self) -> date | None:
        return parse_sheet_date(self.proxima_accion_fecha)

    def has_open_action(self) -> bool:
        """Hay algo pendiente que alimente la página Acciones."""
        return self.is_pendiente and bool(
            self.proxima_accion_fecha.strip() or self.proxima_accion_detalle.strip()
        )

    @classmethod
    def from_row(cls, row: Mapping[str, Any]) -> "Conversation":
        return cls(
            historial_conversacion_id=_text(row, "historial_conversacion_id"),
            supplier_id=_text(row, "supplier_id"),
            product_id=_text(row, "product_id"),
            tipo_conversacion=_match_option(
                _text(row, "tipo_conversacion", TIPO_CONVERSACION_OTRO),
                TIPO_CONVERSACION_OPCIONES,
                TIPO_CONVERSACION_OTRO,
            ),
            fecha_contacto=_text(row, "fecha_contacto"),
            hora_contacto=_text(row, "hora_contacto"),
            persona_contacto=_text(row, "persona_contacto"),
            resumen=_text(row, "resumen"),
            proxima_accion_detalle=_text(row, "proxima_accion_detalle"),
            proxima_accion_fecha=_text(row, "proxima_accion_fecha"),
            proxima_accion_persona=_text(row, "proxima_accion_persona"),
            estado_accion=(
                ""
                if not _text(row, "estado_accion", "")
                else _match_option(
                    _text(row, "estado_accion"),
                    ESTADO_ACCION_OPCIONES,
                    ESTADO_ACCION_PENDIENTE,
                )
            ),
            created_at=_text(row, "created_at"),
            updated_at=_text(row, "updated_at"),
        )

    def to_row(self) -> dict[str, str]:
        return {
            "historial_conversacion_id": self.historial_conversacion_id,
            "supplier_id": self.supplier_id,
            "product_id": self.product_id,
            "tipo_conversacion": self.tipo_conversacion,
            "fecha_contacto": self.fecha_contacto,
            "hora_contacto": self.hora_contacto,
            "persona_contacto": self.persona_contacto,
            "resumen": self.resumen,
            "proxima_accion_detalle": self.proxima_accion_detalle,
            "proxima_accion_fecha": self.proxima_accion_fecha,
            "proxima_accion_persona": self.proxima_accion_persona,
            "estado_accion": self.estado_accion,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }


@dataclass(frozen=True, slots=True)
class PriceQuote:
    """Una fila de ``HistoricoPrecios``: una oferta recibida."""

    historial_precio_id: str
    supplier_id: str
    product_id: str
    fecha_oferta: str = ""
    precio: str = ""
    moneda: str = MONEDA_EUR
    unidad_medida: str = ""
    cantidad_minima: str = ""
    condiciones: str = ""
    validez_oferta_fecha: str = ""
    link_catalogo: str = ""
    registrado_por: str = ""
    notas: str = ""
    created_at: str = ""
    updated_at: str = ""

    @property
    def precio_value(self) -> float | None:
        """Precio numérico, tolerante a «1.234,56 €» y a «1,234.56»."""
        return parse_decimal(self.precio)

    @property
    def fecha_oferta_date(self) -> date | None:
        return parse_sheet_date(self.fecha_oferta)

    @property
    def validez_date(self) -> date | None:
        return parse_sheet_date(self.validez_oferta_fecha)

    def is_expired(self, *, today: date | None = None) -> bool:
        validez = self.validez_date
        return validez is not None and validez < (today or date.today())

    def formatted_price(self) -> str:
        """«1.250,00 €» — formato es-ES, o el texto original si no es numérico."""
        value = self.precio_value
        if value is None:
            symbol = MONEDA_SIMBOLOS.get(self.moneda, self.moneda)
            return f"{self.precio} {symbol}".strip()
        return format_money(value, self.moneda)

    @classmethod
    def from_row(cls, row: Mapping[str, Any]) -> "PriceQuote":
        moneda_raw = _text(row, "moneda", MONEDA_EUR).upper()
        return cls(
            historial_precio_id=_text(row, "historial_precio_id"),
            supplier_id=_text(row, "supplier_id"),
            product_id=_text(row, "product_id"),
            fecha_oferta=_text(row, "fecha_oferta"),
            precio=_text(row, "precio"),
            moneda=moneda_raw or MONEDA_EUR,
            unidad_medida=_text(row, "unidad_medida"),
            cantidad_minima=_text(row, "cantidad_minima"),
            condiciones=_text(row, "condiciones"),
            validez_oferta_fecha=_text(row, "validez_oferta_fecha"),
            link_catalogo=_text(row, "link_catalogo"),
            registrado_por=_text(row, "registrado_por"),
            notas=_text(row, "notas"),
            created_at=_text(row, "created_at"),
            updated_at=_text(row, "updated_at"),
        )

    def to_row(self) -> dict[str, str]:
        return {
            "historial_precio_id": self.historial_precio_id,
            "supplier_id": self.supplier_id,
            "product_id": self.product_id,
            "fecha_oferta": self.fecha_oferta,
            "precio": self.precio,
            "moneda": self.moneda,
            "unidad_medida": self.unidad_medida,
            "cantidad_minima": self.cantidad_minima,
            "condiciones": self.condiciones,
            "validez_oferta_fecha": self.validez_oferta_fecha,
            "link_catalogo": self.link_catalogo,
            "registrado_por": self.registrado_por,
            "notas": self.notas,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }
