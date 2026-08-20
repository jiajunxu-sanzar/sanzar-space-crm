"""Altas y edición de productos y de su esquema técnico dinámico (§4.1).

Dar de alta un producto con especificaciones que nadie había visto antes es
solo escribir filas en tres hojas: `Productos`, `ProductosCamposSchema` y
`ProductosCamposValores`. Ni una migración de esquema ni un cambio de código.
"""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from config.settings import (
    FIELD_TYPE_OPCIONES,
    FIELD_TYPE_TEXTO,
    PRODUCT_ID_PREFIX,
    PRODUCTO_ESTADO_ACTIVO,
    PRODUCTO_ESTADO_OPCIONES,
    PRODUCTOS_CAMPOS_SCHEMA_HEADERS,
    PRODUCTOS_CAMPOS_SCHEMA_WORKSHEET_NAME,
    PRODUCTOS_CAMPOS_VALORES_HEADERS,
    PRODUCTOS_CAMPOS_VALORES_WORKSHEET_NAME,
    PRODUCTOS_HEADERS,
    PRODUCTOS_WORKSHEET_NAME,
)
from models.product import Product, ProductFieldSpec, ProductFieldValue
from services.dataset import SpaceDataset
from services.ids import next_sequential_id, slugify_field_key
from services.result import WriteResult
from services.sheet_date_format import (
    is_valid_dd_mm_yyyy,
    normalize_dd_mm_yyyy,
    timestamp_now,
    today_str,
    DD_MM_YYYY_HINT,
)
from services.sheets_service import SheetsService


@dataclass(frozen=True, slots=True)
class TechnicalField:
    """Campo técnico tal y como lo introduce el usuario en el formulario."""

    label: str
    valor: str = ""
    field_type: str = FIELD_TYPE_TEXTO
    unidad: str = ""
    field_key: str = ""

    def resolved_key(self) -> str:
        return (self.field_key or slugify_field_key(self.label)).strip()


class ProductsService:
    def __init__(self, sheets: SheetsService) -> None:
        self.sheets = sheets

    # ------------------------------------------------------------------
    # Validación
    # ------------------------------------------------------------------

    @staticmethod
    def validate(
        dataset: SpaceDataset,
        *,
        nombre_producto: str,
        categoria: str,
        fecha_definicion: str = "",
        estado: str = PRODUCTO_ESTADO_ACTIVO,
        exclude_product_id: str = "",
        technical_fields: tuple[TechnicalField, ...] = (),
    ) -> tuple[str, ...]:
        errors: list[str] = []

        nombre = (nombre_producto or "").strip()
        if not nombre:
            errors.append("El nombre del producto es obligatorio.")
        else:
            duplicate = any(
                product.nombre_producto.casefold() == nombre.casefold()
                and product.product_id != exclude_product_id
                for product in dataset.products
            )
            if duplicate:
                errors.append(f"Ya existe un producto llamado «{nombre}».")

        if not (categoria or "").strip():
            errors.append("La categoría es obligatoria.")

        if not is_valid_dd_mm_yyyy(fecha_definicion):
            errors.append(f"Fecha de definición inválida. {DD_MM_YYYY_HINT}")

        if estado and estado not in PRODUCTO_ESTADO_OPCIONES:
            errors.append(f"Estado no válido: {estado}.")

        seen_keys: set[str] = set()
        for spec in technical_fields:
            if not spec.label.strip():
                continue
            if spec.field_type not in FIELD_TYPE_OPCIONES:
                errors.append(f"Tipo de campo no válido en «{spec.label}»: {spec.field_type}.")
            key = spec.resolved_key()
            if key in seen_keys:
                errors.append(f"El campo técnico «{key}» está repetido.")
            seen_keys.add(key)

        return tuple(errors)

    # ------------------------------------------------------------------
    # Altas
    # ------------------------------------------------------------------

    def create_product(
        self,
        dataset: SpaceDataset,
        *,
        nombre_producto: str,
        categoria: str,
        descripcion: str = "",
        definido_por: str = "",
        fecha_definicion: str = "",
        link_carpeta: str = "",
        notas: str = "",
        estado: str = PRODUCTO_ESTADO_ACTIVO,
        technical_fields: tuple[TechnicalField, ...] = (),
    ) -> WriteResult:
        """Crea el producto y, en dos llamadas más, todo su esquema técnico."""
        errors = self.validate(
            dataset,
            nombre_producto=nombre_producto,
            categoria=categoria,
            fecha_definicion=fecha_definicion,
            estado=estado,
            technical_fields=technical_fields,
        )
        if errors:
            return WriteResult.failure(*errors)

        now = timestamp_now()
        product = Product(
            product_id=next_sequential_id(
                PRODUCT_ID_PREFIX, (p.product_id for p in dataset.products)
            ),
            nombre_producto=nombre_producto.strip(),
            categoria=categoria.strip(),
            descripcion=(descripcion or "").strip(),
            definido_por=(definido_por or "").strip(),
            fecha_definicion=normalize_dd_mm_yyyy(fecha_definicion) or today_str(),
            link_carpeta=(link_carpeta or "").strip(),
            notas=(notas or "").strip(),
            estado=estado or PRODUCTO_ESTADO_ACTIVO,
            created_at=now,
            updated_at=now,
        )

        try:
            self.sheets.append_row(
                PRODUCTOS_WORKSHEET_NAME, PRODUCTOS_HEADERS, product.to_row()
            )
            self._write_technical_fields(
                product.product_id,
                technical_fields,
                actualizado_por=definido_por,
                start_order=0,
            )
        except Exception as exc:  # noqa: BLE001
            return WriteResult.from_exception(exc, action="crear el producto")

        return WriteResult.success(
            f"Producto «{product.nombre_producto}» creado ({product.product_id}).",
            entity_id=product.product_id,
        )

    def add_technical_fields(
        self,
        dataset: SpaceDataset,
        product_id: str,
        technical_fields: tuple[TechnicalField, ...],
        *,
        actualizado_por: str = "",
    ) -> WriteResult:
        """Añade campos técnicos a un producto ya existente."""
        product = dataset.product_by_id.get(str(product_id).strip())
        if product is None:
            return WriteResult.failure(f"No existe el producto {product_id}.")

        existing = {spec.field_key for spec in dataset.specs_by_product.get(product.product_id, ())}
        fresh = tuple(
            spec
            for spec in technical_fields
            if spec.label.strip() and spec.resolved_key() not in existing
        )
        if not fresh:
            return WriteResult.failure("No hay campos técnicos nuevos que añadir.")

        start_order = max(
            (spec.orden for spec in dataset.specs_by_product.get(product.product_id, ())),
            default=0,
        )
        try:
            self._write_technical_fields(
                product.product_id, fresh, actualizado_por=actualizado_por, start_order=start_order
            )
        except Exception as exc:  # noqa: BLE001
            return WriteResult.from_exception(exc, action="añadir los campos técnicos")

        return WriteResult.success(
            f"{len(fresh)} campo(s) técnico(s) añadidos a «{product.display_name}».",
            entity_id=product.product_id,
        )

    def set_field_value(
        self,
        product_id: str,
        field_key: str,
        valor: str,
        *,
        actualizado_por: str = "",
    ) -> WriteResult:
        """Actualiza el valor de un campo técnico (o lo crea si aún no existía)."""
        value = ProductFieldValue(
            product_id=str(product_id).strip(),
            field_key=str(field_key).strip(),
            valor=str(valor or "").strip(),
            actualizado_por=(actualizado_por or "").strip(),
            updated_at=timestamp_now(),
        )
        if not value.product_id or not value.field_key:
            return WriteResult.failure("Faltan el producto o la clave del campo.")

        try:
            # La pareja (product_id, field_key) es la clave real, pero Sheets no
            # tiene claves compuestas: borramos las filas del producto para esa
            # clave y volvemos a escribir una sola. Barato porque estas hojas
            # son pequeñas y evita duplicados históricos.
            self._replace_field_value(value)
        except Exception as exc:  # noqa: BLE001
            return WriteResult.from_exception(exc, action="guardar el campo técnico")

        return WriteResult.success("Campo técnico actualizado.", entity_id=value.field_key)

    def update_product(
        self,
        dataset: SpaceDataset,
        product_id: str,
        changes: dict[str, str],
    ) -> WriteResult:
        """Reescribe la ficha de un producto conservando ``created_at``."""
        product = dataset.product_by_id.get(str(product_id).strip())
        if product is None:
            return WriteResult.failure(f"No existe el producto {product_id}.")

        merged = product.to_row() | {
            key: str(value or "").strip() for key, value in changes.items() if key in PRODUCTOS_HEADERS
        }
        merged["product_id"] = product.product_id
        merged["created_at"] = product.created_at
        merged["fecha_definicion"] = normalize_dd_mm_yyyy(merged.get("fecha_definicion", ""))
        merged["updated_at"] = timestamp_now()

        errors = self.validate(
            dataset,
            nombre_producto=merged.get("nombre_producto", ""),
            categoria=merged.get("categoria", ""),
            fecha_definicion=merged.get("fecha_definicion", ""),
            estado=merged.get("estado", PRODUCTO_ESTADO_ACTIVO),
            exclude_product_id=product.product_id,
        )
        if errors:
            return WriteResult.failure(*errors)

        try:
            written = self.sheets.update_row_by_id(
                PRODUCTOS_WORKSHEET_NAME,
                PRODUCTOS_HEADERS,
                "product_id",
                product.product_id,
                merged,
            )
        except Exception as exc:  # noqa: BLE001
            return WriteResult.from_exception(exc, action="actualizar el producto")

        if not written:
            return WriteResult.failure(
                f"No se encontró la fila de {product.product_id} en la hoja Productos."
            )
        return WriteResult.success("Producto actualizado.", entity_id=product.product_id)

    # ------------------------------------------------------------------
    # Internos
    # ------------------------------------------------------------------

    def _write_technical_fields(
        self,
        product_id: str,
        technical_fields: tuple[TechnicalField, ...],
        *,
        actualizado_por: str,
        start_order: int,
    ) -> None:
        """Escribe definiciones y valores en 2 llamadas (una por hoja), no 2×N."""
        specs: list[dict[str, str]] = []
        values: list[dict[str, str]] = []
        now = timestamp_now()

        for offset, spec in enumerate(
            (field for field in technical_fields if field.label.strip()), start=1
        ):
            key = spec.resolved_key()
            specs.append(
                ProductFieldSpec(
                    product_id=product_id,
                    field_key=key,
                    field_label=spec.label.strip(),
                    field_type=spec.field_type,
                    unidad=spec.unidad.strip(),
                    orden=start_order + offset,
                    activo=True,
                ).to_row()
            )
            if spec.valor.strip():
                values.append(
                    ProductFieldValue(
                        product_id=product_id,
                        field_key=key,
                        valor=spec.valor.strip(),
                        actualizado_por=(actualizado_por or "").strip(),
                        updated_at=now,
                    ).to_row()
                )

        if specs:
            self.sheets.append_rows(
                PRODUCTOS_CAMPOS_SCHEMA_WORKSHEET_NAME,
                PRODUCTOS_CAMPOS_SCHEMA_HEADERS,
                specs,
            )
        if values:
            self.sheets.append_rows(
                PRODUCTOS_CAMPOS_VALORES_WORKSHEET_NAME,
                PRODUCTOS_CAMPOS_VALORES_HEADERS,
                values,
            )

    def _replace_field_value(self, value: ProductFieldValue) -> None:
        """Deja exactamente una fila para la pareja (product_id, field_key).

        Sheets no tiene claves compuestas, así que si ya hay valor para ese
        campo se reescribe la hoja sin las filas viejas más la nueva. Es la hoja
        más pequeña del modelo (un puñado de filas por producto), y evita que el
        histórico acumule valores contradictorios del mismo campo.
        """
        current = self.sheets.read_worksheet_df(
            PRODUCTOS_CAMPOS_VALORES_WORKSHEET_NAME, PRODUCTOS_CAMPOS_VALORES_HEADERS
        )
        if not current.empty:
            mask = (current["product_id"].str.strip() == value.product_id) & (
                current["field_key"].str.strip() == value.field_key
            )
            if bool(mask.any()):
                updated = pd.concat(
                    [current[~mask], pd.DataFrame([value.to_row()])],
                    ignore_index=True,
                )
                self.sheets.write_worksheet_df(
                    PRODUCTOS_CAMPOS_VALORES_WORKSHEET_NAME,
                    updated,
                    list(PRODUCTOS_CAMPOS_VALORES_HEADERS),
                )
                return
        self.sheets.append_row(
            PRODUCTOS_CAMPOS_VALORES_WORKSHEET_NAME,
            PRODUCTOS_CAMPOS_VALORES_HEADERS,
            value.to_row(),
        )
