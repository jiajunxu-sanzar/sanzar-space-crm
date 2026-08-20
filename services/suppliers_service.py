"""Altas y edición de suministradores y de sus relaciones por producto (§4.2).

El alta de un suministrador nuevo escribe en dos hojas: su identidad en
`Suministradores` y su primera relación en `SuministradorProducto`. El estado
(potencial / confirmado / descartado) vive **siempre** en la relación, nunca en
la ficha, porque un mismo proveedor puede estar confirmado para un producto y
descartado para otro.
"""

from __future__ import annotations

from config.settings import (
    REL_ESTADO_DESCARTADO,
    REL_ESTADO_OPCIONES,
    REL_ESTADO_POTENCIAL,
    SUMINISTRADOR_PRODUCTO_HEADERS,
    SUMINISTRADOR_PRODUCTO_WORKSHEET_NAME,
    SUMINISTRADORES_HEADERS,
    SUMINISTRADORES_WORKSHEET_NAME,
    SUPPLIER_ID_PREFIX,
)
from models.supplier import Supplier, SupplierProduct
from services.dataset import SpaceDataset
from services.ids import next_sequential_id, relation_id
from services.result import WriteResult
from services.sheet_date_format import (
    DD_MM_YYYY_HINT,
    is_valid_dd_mm_yyyy,
    normalize_dd_mm_yyyy,
    timestamp_now,
    today_str,
)
from services.sheets_service import SheetsService

_EMAIL_HINT = "Revisa el email: debe tener la forma nombre@dominio.com."


def _looks_like_email(value: str) -> bool:
    raw = (value or "").strip()
    if not raw:
        return True  # opcional
    return "@" in raw and "." in raw.rsplit("@", 1)[-1] and " " not in raw


class SuppliersService:
    def __init__(self, sheets: SheetsService) -> None:
        self.sheets = sheets

    # ------------------------------------------------------------------
    # Validación
    # ------------------------------------------------------------------

    @staticmethod
    def validate_supplier(
        dataset: SpaceDataset,
        *,
        nombre_suministrador: str,
        email: str = "",
        exclude_supplier_id: str = "",
    ) -> tuple[str, ...]:
        errors: list[str] = []
        nombre = (nombre_suministrador or "").strip()
        if not nombre:
            errors.append("El nombre del suministrador es obligatorio.")
        else:
            duplicate = any(
                supplier.nombre_suministrador.casefold() == nombre.casefold()
                and supplier.supplier_id != exclude_supplier_id
                for supplier in dataset.suppliers
            )
            if duplicate:
                errors.append(f"Ya existe un suministrador llamado «{nombre}».")
        if not _looks_like_email(email):
            errors.append(_EMAIL_HINT)
        return tuple(errors)

    @staticmethod
    def validate_relation(
        dataset: SpaceDataset,
        *,
        product_id: str,
        estado: str,
        razon_descarte: str = "",
        fecha_alta: str = "",
        supplier_id: str = "",
        allow_existing: bool = False,
    ) -> tuple[str, ...]:
        errors: list[str] = []

        product = str(product_id or "").strip()
        if not product:
            errors.append("Selecciona el producto de la relación.")
        elif product not in dataset.product_by_id:
            errors.append(f"El producto {product} no existe en la hoja Productos.")

        if estado not in REL_ESTADO_OPCIONES:
            errors.append(f"Estado de relación no válido: {estado}.")
        # Regla del modelo (§5): descartar exige explicar por qué. Sin esto, en
        # seis meses nadie recuerda si se descartó por precio o por plazo.
        if estado == REL_ESTADO_DESCARTADO and not (razon_descarte or "").strip():
            errors.append("Si el estado es «Descartado», la razón de descarte es obligatoria.")

        if not is_valid_dd_mm_yyyy(fecha_alta):
            errors.append(f"Fecha de alta inválida. {DD_MM_YYYY_HINT}")

        supplier = str(supplier_id or "").strip()
        if supplier and product and not allow_existing:
            if (supplier, product) in dataset.relation_by_pair:
                name = dataset.product_name(product)
                errors.append(f"Este suministrador ya tiene una relación con «{name}».")

        return tuple(errors)

    # ------------------------------------------------------------------
    # Altas
    # ------------------------------------------------------------------

    def create_supplier(
        self,
        dataset: SpaceDataset,
        *,
        nombre_suministrador: str,
        pais: str = "",
        web: str = "",
        contacto_principal: str = "",
        cargo_contacto_principal: str = "",
        telefono_principal: str = "",
        contacto_secundario: str = "",
        cargo_contacto_secundario: str = "",
        telefono_secundario: str = "",
        email: str = "",
        direccion: str = "",
        notas_generales: str = "",
        # Primera relación producto ↔ suministrador
        product_id: str = "",
        estado: str = REL_ESTADO_POTENCIAL,
        razon_descarte: str = "",
        responsable_relacion: str = "",
        fecha_alta: str = "",
    ) -> WriteResult:
        """Crea el suministrador y su primera relación con un producto."""
        errors = list(
            self.validate_supplier(
                dataset, nombre_suministrador=nombre_suministrador, email=email
            )
        )
        errors += list(
            self.validate_relation(
                dataset,
                product_id=product_id,
                estado=estado,
                razon_descarte=razon_descarte,
                fecha_alta=fecha_alta,
            )
        )
        if errors:
            return WriteResult.failure(*errors)

        now = timestamp_now()
        supplier = Supplier(
            supplier_id=next_sequential_id(
                SUPPLIER_ID_PREFIX, (s.supplier_id for s in dataset.suppliers)
            ),
            nombre_suministrador=nombre_suministrador.strip(),
            pais=(pais or "").strip(),
            web=(web or "").strip(),
            contacto_principal=(contacto_principal or "").strip(),
            cargo_contacto_principal=(cargo_contacto_principal or "").strip(),
            telefono_principal=(telefono_principal or "").strip(),
            contacto_secundario=(contacto_secundario or "").strip(),
            cargo_contacto_secundario=(cargo_contacto_secundario or "").strip(),
            telefono_secundario=(telefono_secundario or "").strip(),
            email=(email or "").strip(),
            direccion=(direccion or "").strip(),
            notas_generales=(notas_generales or "").strip(),
            created_at=now,
            updated_at=now,
        )
        relation = SupplierProduct(
            rel_id=relation_id(supplier.supplier_id, product_id),
            supplier_id=supplier.supplier_id,
            product_id=str(product_id).strip(),
            estado=estado,
            razon_descarte=(razon_descarte or "").strip(),
            fecha_alta=normalize_dd_mm_yyyy(fecha_alta) or today_str(),
            responsable_relacion=(responsable_relacion or "").strip(),
            created_at=now,
            updated_at=now,
        )

        try:
            self.sheets.append_row(
                SUMINISTRADORES_WORKSHEET_NAME, SUMINISTRADORES_HEADERS, supplier.to_row()
            )
            self.sheets.append_row(
                SUMINISTRADOR_PRODUCTO_WORKSHEET_NAME,
                SUMINISTRADOR_PRODUCTO_HEADERS,
                relation.to_row(),
            )
        except Exception as exc:  # noqa: BLE001
            return WriteResult.from_exception(exc, action="crear el suministrador")

        return WriteResult.success(
            f"Suministrador «{supplier.nombre_suministrador}» creado ({supplier.supplier_id}).",
            entity_id=supplier.supplier_id,
        )

    def update_supplier(
        self,
        dataset: SpaceDataset,
        supplier_id: str,
        changes: dict[str, str],
    ) -> WriteResult:
        """Reescribe la ficha de identidad conservando ``created_at``."""
        supplier = dataset.supplier_by_id.get(str(supplier_id).strip())
        if supplier is None:
            return WriteResult.failure(f"No existe el suministrador {supplier_id}.")

        merged = supplier.to_row() | {
            key: str(value or "").strip()
            for key, value in changes.items()
            if key in SUMINISTRADORES_HEADERS
        }
        merged["supplier_id"] = supplier.supplier_id
        merged["created_at"] = supplier.created_at
        merged["updated_at"] = timestamp_now()

        errors = self.validate_supplier(
            dataset,
            nombre_suministrador=merged.get("nombre_suministrador", ""),
            email=merged.get("email", ""),
            exclude_supplier_id=supplier.supplier_id,
        )
        if errors:
            return WriteResult.failure(*errors)

        try:
            written = self.sheets.update_row_by_id(
                SUMINISTRADORES_WORKSHEET_NAME,
                SUMINISTRADORES_HEADERS,
                "supplier_id",
                supplier.supplier_id,
                merged,
            )
        except Exception as exc:  # noqa: BLE001
            return WriteResult.from_exception(exc, action="actualizar el suministrador")

        if not written:
            return WriteResult.failure(
                f"No se encontró la fila de {supplier.supplier_id} en la hoja Suministradores."
            )
        return WriteResult.success("Ficha actualizada.", entity_id=supplier.supplier_id)

    # ------------------------------------------------------------------
    # Relaciones proveedor ↔ producto
    # ------------------------------------------------------------------

    def add_relation(
        self,
        dataset: SpaceDataset,
        *,
        supplier_id: str,
        product_id: str,
        estado: str = REL_ESTADO_POTENCIAL,
        razon_descarte: str = "",
        responsable_relacion: str = "",
        fecha_alta: str = "",
    ) -> WriteResult:
        """Asocia un producto más a un suministrador ya existente."""
        supplier = dataset.supplier_by_id.get(str(supplier_id).strip())
        if supplier is None:
            return WriteResult.failure(f"No existe el suministrador {supplier_id}.")

        errors = self.validate_relation(
            dataset,
            product_id=product_id,
            estado=estado,
            razon_descarte=razon_descarte,
            fecha_alta=fecha_alta,
            supplier_id=supplier.supplier_id,
        )
        if errors:
            return WriteResult.failure(*errors)

        now = timestamp_now()
        relation = SupplierProduct(
            rel_id=relation_id(supplier.supplier_id, product_id),
            supplier_id=supplier.supplier_id,
            product_id=str(product_id).strip(),
            estado=estado,
            razon_descarte=(razon_descarte or "").strip(),
            fecha_alta=normalize_dd_mm_yyyy(fecha_alta) or today_str(),
            responsable_relacion=(responsable_relacion or "").strip(),
            created_at=now,
            updated_at=now,
        )
        try:
            self.sheets.append_row(
                SUMINISTRADOR_PRODUCTO_WORKSHEET_NAME,
                SUMINISTRADOR_PRODUCTO_HEADERS,
                relation.to_row(),
            )
        except Exception as exc:  # noqa: BLE001
            return WriteResult.from_exception(exc, action="asociar el producto")

        name = dataset.product_name(relation.product_id)
        return WriteResult.success(
            f"«{name}» asociado a {supplier.display_name}.", entity_id=relation.rel_id
        )

    def update_relation(
        self,
        dataset: SpaceDataset,
        rel_id: str,
        *,
        estado: str,
        razon_descarte: str = "",
        responsable_relacion: str | None = None,
        fecha_alta: str | None = None,
    ) -> WriteResult:
        """Cambia el estado de una relación (p. ej. potencial → confirmado)."""
        relation = next((rel for rel in dataset.relations if rel.rel_id == str(rel_id).strip()), None)
        if relation is None:
            return WriteResult.failure(f"No existe la relación {rel_id}.")

        errors = self.validate_relation(
            dataset,
            product_id=relation.product_id,
            estado=estado,
            razon_descarte=razon_descarte,
            fecha_alta=fecha_alta or relation.fecha_alta,
            supplier_id=relation.supplier_id,
            allow_existing=True,
        )
        if errors:
            return WriteResult.failure(*errors)

        updated = relation.to_row() | {
            "estado": estado,
            # Al dejar de estar descartado, la razón deja de tener sentido.
            "razon_descarte": (razon_descarte or "").strip()
            if estado == REL_ESTADO_DESCARTADO
            else "",
            "responsable_relacion": (
                relation.responsable_relacion
                if responsable_relacion is None
                else str(responsable_relacion).strip()
            ),
            "fecha_alta": normalize_dd_mm_yyyy(
                relation.fecha_alta if fecha_alta is None else fecha_alta
            ),
            "updated_at": timestamp_now(),
        }

        try:
            written = self.sheets.update_row_by_id(
                SUMINISTRADOR_PRODUCTO_WORKSHEET_NAME,
                SUMINISTRADOR_PRODUCTO_HEADERS,
                "rel_id",
                relation.rel_id,
                updated,
            )
        except Exception as exc:  # noqa: BLE001
            return WriteResult.from_exception(exc, action="actualizar la relación")

        if not written:
            return WriteResult.failure(
                f"No se encontró la fila {relation.rel_id} en SuministradorProducto."
            )
        return WriteResult.success(
            f"Estado actualizado a «{estado}».", entity_id=relation.rel_id
        )
