"""Modelo de suministrador y de su relación N:M con productos (§4.2).

`Suministradores` guarda la **identidad** (una fila por empresa) y
`SuministradorProducto` la **relación por producto** con su estado. Van
separados porque un mismo proveedor puede estar «confirmado» para slip-rings y
«descartado» para rodamientos a la vez.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

from config.settings import (
    REL_ESTADO_DESCARTADO,
    REL_ESTADO_OPCIONES,
    REL_ESTADO_ORDER,
    REL_ESTADO_POTENCIAL,
)


def _text(row: Mapping[str, Any], key: str, default: str = "") -> str:
    return str(row.get(key, default) or default).strip()


@dataclass(frozen=True, slots=True)
class Supplier:
    supplier_id: str
    nombre_suministrador: str = ""
    pais: str = ""
    web: str = ""
    contacto_principal: str = ""
    cargo_contacto_principal: str = ""
    telefono_principal: str = ""
    contacto_secundario: str = ""
    cargo_contacto_secundario: str = ""
    telefono_secundario: str = ""
    email: str = ""
    direccion: str = ""
    notas_generales: str = ""
    created_at: str = ""
    updated_at: str = ""

    @property
    def display_name(self) -> str:
        return self.nombre_suministrador or self.supplier_id

    @property
    def initials(self) -> str:
        parts = [p for p in self.display_name.replace("-", " ").split() if p]
        if not parts:
            return "?"
        if len(parts) == 1:
            return parts[0][:2].upper()
        return (parts[0][0] + parts[1][0]).upper()

    @classmethod
    def from_row(cls, row: Mapping[str, Any]) -> "Supplier":
        return cls(
            supplier_id=_text(row, "supplier_id"),
            nombre_suministrador=_text(row, "nombre_suministrador"),
            pais=_text(row, "pais"),
            web=_text(row, "web"),
            contacto_principal=_text(row, "contacto_principal"),
            cargo_contacto_principal=_text(row, "cargo_contacto_principal"),
            telefono_principal=_text(row, "telefono_principal"),
            contacto_secundario=_text(row, "contacto_secundario"),
            cargo_contacto_secundario=_text(row, "cargo_contacto_secundario"),
            telefono_secundario=_text(row, "telefono_secundario"),
            email=_text(row, "email"),
            direccion=_text(row, "direccion"),
            notas_generales=_text(row, "notas_generales"),
            created_at=_text(row, "created_at"),
            updated_at=_text(row, "updated_at"),
        )

    def to_row(self) -> dict[str, str]:
        return {
            "supplier_id": self.supplier_id,
            "nombre_suministrador": self.nombre_suministrador,
            "pais": self.pais,
            "web": self.web,
            "contacto_principal": self.contacto_principal,
            "cargo_contacto_principal": self.cargo_contacto_principal,
            "telefono_principal": self.telefono_principal,
            "contacto_secundario": self.contacto_secundario,
            "cargo_contacto_secundario": self.cargo_contacto_secundario,
            "telefono_secundario": self.telefono_secundario,
            "email": self.email,
            "direccion": self.direccion,
            "notas_generales": self.notas_generales,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }


@dataclass(frozen=True, slots=True)
class SupplierProduct:
    """Una fila de ``SuministradorProducto``: el estado de una pareja (proveedor, producto)."""

    rel_id: str
    supplier_id: str
    product_id: str
    estado: str = REL_ESTADO_POTENCIAL
    razon_descarte: str = ""
    fecha_alta: str = ""
    responsable_relacion: str = ""
    created_at: str = ""
    updated_at: str = ""

    @property
    def is_descartado(self) -> bool:
        return self.estado.casefold() == REL_ESTADO_DESCARTADO.casefold()

    @property
    def sort_key(self) -> int:
        return REL_ESTADO_ORDER.get(self.estado, len(REL_ESTADO_ORDER))

    @classmethod
    def from_row(cls, row: Mapping[str, Any]) -> "SupplierProduct":
        raw_estado = _text(row, "estado", REL_ESTADO_POTENCIAL).casefold()
        estado = next(
            (opt for opt in REL_ESTADO_OPCIONES if opt.casefold() == raw_estado),
            _text(row, "estado", REL_ESTADO_POTENCIAL),
        )
        return cls(
            rel_id=_text(row, "rel_id"),
            supplier_id=_text(row, "supplier_id"),
            product_id=_text(row, "product_id"),
            estado=estado,
            razon_descarte=_text(row, "razon_descarte"),
            fecha_alta=_text(row, "fecha_alta"),
            responsable_relacion=_text(row, "responsable_relacion"),
            created_at=_text(row, "created_at"),
            updated_at=_text(row, "updated_at"),
        )

    def to_row(self) -> dict[str, str]:
        return {
            "rel_id": self.rel_id,
            "supplier_id": self.supplier_id,
            "product_id": self.product_id,
            "estado": self.estado,
            "razon_descarte": self.razon_descarte,
            "fecha_alta": self.fecha_alta,
            "responsable_relacion": self.responsable_relacion,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }
