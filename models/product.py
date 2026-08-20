"""Modelo de producto y de su esquema técnico dinámico (§4.1).

Un motor y un rodamiento no comparten especificaciones. En vez de una hoja
`Productos` ancha con todas las columnas posibles, el esquema vive en dos hojas
(patrón EAV, igual que ``InventarioCamposModelo`` en ``sanzar-crm-web``):

- ``ProductosCamposSchema``  → *qué* campos tiene cada producto.
- ``ProductosCamposValores`` → *cuánto vale* cada campo para cada producto.

Así, dar de alta un producto con especificaciones nunca vistas es añadir filas,
nunca migrar la hoja ni tocar código.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping

from config.settings import (
    FIELD_TYPE_OPCIONES,
    FIELD_TYPE_TEXTO,
    PRODUCTO_ESTADO_ACTIVO,
    SI,
)


def _text(row: Mapping[str, Any], key: str, default: str = "") -> str:
    return str(row.get(key, default) or default).strip()


@dataclass(frozen=True, slots=True)
class Product:
    product_id: str
    nombre_producto: str = ""
    categoria: str = ""
    descripcion: str = ""
    definido_por: str = ""
    fecha_definicion: str = ""
    link_carpeta: str = ""
    notas: str = ""
    estado: str = PRODUCTO_ESTADO_ACTIVO
    created_at: str = ""
    updated_at: str = ""

    @property
    def is_activo(self) -> bool:
        return self.estado.strip().casefold() == PRODUCTO_ESTADO_ACTIVO.casefold()

    @property
    def display_name(self) -> str:
        """Nombre para selectores: cae al id si la fila no tiene nombre."""
        return self.nombre_producto or self.product_id

    @classmethod
    def from_row(cls, row: Mapping[str, Any]) -> "Product":
        return cls(
            product_id=_text(row, "product_id"),
            nombre_producto=_text(row, "nombre_producto"),
            categoria=_text(row, "categoria"),
            descripcion=_text(row, "descripcion"),
            definido_por=_text(row, "definido_por"),
            fecha_definicion=_text(row, "fecha_definicion"),
            link_carpeta=_text(row, "link_carpeta"),
            notas=_text(row, "notas"),
            estado=_text(row, "estado", PRODUCTO_ESTADO_ACTIVO),
            created_at=_text(row, "created_at"),
            updated_at=_text(row, "updated_at"),
        )

    def to_row(self) -> dict[str, str]:
        return {
            "product_id": self.product_id,
            "nombre_producto": self.nombre_producto,
            "categoria": self.categoria,
            "descripcion": self.descripcion,
            "definido_por": self.definido_por,
            "fecha_definicion": self.fecha_definicion,
            "link_carpeta": self.link_carpeta,
            "notas": self.notas,
            "estado": self.estado,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }


@dataclass(frozen=True, slots=True)
class ProductFieldSpec:
    """Una fila de ``ProductosCamposSchema``: la definición de un campo técnico."""

    product_id: str
    field_key: str
    field_label: str = ""
    field_type: str = FIELD_TYPE_TEXTO
    unidad: str = ""
    orden: int = 0
    activo: bool = True
    notas: str = ""

    @property
    def label(self) -> str:
        base = self.field_label or self.field_key
        return f"{base} ({self.unidad})" if self.unidad else base

    @classmethod
    def from_row(cls, row: Mapping[str, Any]) -> "ProductFieldSpec":
        raw_type = _text(row, "field_type", FIELD_TYPE_TEXTO).casefold()
        field_type = next(
            (opt for opt in FIELD_TYPE_OPCIONES if opt.casefold() == raw_type),
            FIELD_TYPE_TEXTO,
        )
        try:
            orden = int(float(_text(row, "orden", "0") or 0))
        except ValueError:
            orden = 0
        activo_raw = _text(row, "activo", SI).casefold()
        return cls(
            product_id=_text(row, "product_id"),
            field_key=_text(row, "field_key"),
            field_label=_text(row, "field_label"),
            field_type=field_type,
            unidad=_text(row, "unidad"),
            orden=orden,
            # Solo un "No" explícito desactiva: una celda vacía en una hoja
            # rellenada a mano no debe esconder el campo.
            activo=activo_raw not in {"no", "false", "0"},
            notas=_text(row, "notas"),
        )

    def to_row(self) -> dict[str, str]:
        return {
            "product_id": self.product_id,
            "field_key": self.field_key,
            "field_label": self.field_label,
            "field_type": self.field_type,
            "unidad": self.unidad,
            "orden": str(self.orden),
            "activo": SI if self.activo else "No",
            "notas": self.notas,
        }


@dataclass(frozen=True, slots=True)
class ProductFieldValue:
    """Una fila de ``ProductosCamposValores``."""

    product_id: str
    field_key: str
    valor: str = ""
    actualizado_por: str = ""
    updated_at: str = ""

    @classmethod
    def from_row(cls, row: Mapping[str, Any]) -> "ProductFieldValue":
        return cls(
            product_id=_text(row, "product_id"),
            field_key=_text(row, "field_key"),
            valor=_text(row, "valor"),
            actualizado_por=_text(row, "actualizado_por"),
            updated_at=_text(row, "updated_at"),
        )

    def to_row(self) -> dict[str, str]:
        return {
            "product_id": self.product_id,
            "field_key": self.field_key,
            "valor": self.valor,
            "actualizado_por": self.actualizado_por,
            "updated_at": self.updated_at,
        }


@dataclass(frozen=True, slots=True)
class ProductSpecSheet:
    """Producto + sus campos técnicos resueltos, listo para pintar la ficha."""

    product: Product
    specs: tuple[tuple[ProductFieldSpec, str], ...] = field(default=())

    def as_pairs(self) -> list[tuple[str, str]]:
        """[(etiqueta, valor)] en el orden declarado por el esquema."""
        return [(spec.label, value) for spec, value in self.specs if value]
