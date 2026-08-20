"""Histórico de precios ofertados por los suministradores (§5, `HistoricoPrecios`).

Nunca se sobrescribe una oferta: cada precio recibido es una fila nueva, con su
fecha. El «precio actual» de una pareja (proveedor, producto) es simplemente la
fila más reciente — así queda registrado cómo ha ido evolucionando la
negociación, que es justo lo que se pierde cuando esto vive en correos.
"""

from __future__ import annotations

from config.settings import (
    HISTORICO_PRECIOS_HEADERS,
    HISTORICO_PRECIOS_WORKSHEET_NAME,
    MONEDA_EUR,
    MONEDA_OPCIONES,
    PRECIO_ID_PREFIX,
    REL_ESTADO_DESCARTADO,
)
from models.history import PriceQuote
from services.dataset import SpaceDataset
from services.ids import unique_id
from services.locale_numbers import parse_decimal, parse_int
from services.result import WriteResult
from services.sheet_date_format import (
    DD_MM_YYYY_HINT,
    is_valid_dd_mm_yyyy,
    normalize_dd_mm_yyyy,
    parse_sheet_date,
    timestamp_now,
    today_str,
)
from services.sheets_service import SheetsService


class PricingService:
    def __init__(self, sheets: SheetsService) -> None:
        self.sheets = sheets

    # ------------------------------------------------------------------
    # Validación
    # ------------------------------------------------------------------

    @staticmethod
    def validate(
        dataset: SpaceDataset,
        *,
        supplier_id: str,
        product_id: str,
        fecha_oferta: str,
        precio: str,
        moneda: str,
        cantidad_minima: str = "",
        validez_oferta_fecha: str = "",
    ) -> tuple[str, ...]:
        errors: list[str] = []

        supplier = str(supplier_id or "").strip()
        product = str(product_id or "").strip()
        if supplier not in dataset.supplier_by_id:
            errors.append("Selecciona un suministrador válido.")
        if product not in dataset.product_by_id:
            errors.append("Selecciona el producto ofertado.")
        if supplier and product and (supplier, product) not in dataset.relation_by_pair:
            name = dataset.product_name(product)
            errors.append(
                f"Este suministrador no tiene ninguna relación con «{name}». "
                "Asocia primero el producto en Datos generales."
            )

        if not (fecha_oferta or "").strip():
            errors.append("La fecha de la oferta es obligatoria.")
        elif not is_valid_dd_mm_yyyy(fecha_oferta):
            errors.append(f"Fecha de oferta inválida. {DD_MM_YYYY_HINT}")

        value = parse_decimal(precio)
        if value is None:
            errors.append("El precio debe ser un número (por ejemplo 1.250,00).")
        elif value < 0:
            errors.append("El precio no puede ser negativo.")

        if str(moneda or "").upper() not in MONEDA_OPCIONES:
            errors.append(f"Moneda no válida: {moneda}. Usa {' o '.join(MONEDA_OPCIONES)}.")

        if (cantidad_minima or "").strip():
            minimum = parse_int(cantidad_minima)
            if minimum is None or minimum < 0:
                errors.append("La cantidad mínima (MOQ) debe ser un número entero positivo.")

        if not is_valid_dd_mm_yyyy(validez_oferta_fecha):
            errors.append(f"Fecha de validez inválida. {DD_MM_YYYY_HINT}")
        else:
            offer_date = parse_sheet_date(fecha_oferta)
            valid_until = parse_sheet_date(validez_oferta_fecha)
            if offer_date and valid_until and valid_until < offer_date:
                errors.append("La validez de la oferta no puede ser anterior a su fecha.")

        return tuple(errors)

    # ------------------------------------------------------------------
    # Altas
    # ------------------------------------------------------------------

    def add_quote(
        self,
        dataset: SpaceDataset,
        *,
        supplier_id: str,
        product_id: str,
        precio: str,
        moneda: str = MONEDA_EUR,
        fecha_oferta: str = "",
        unidad_medida: str = "",
        cantidad_minima: str = "",
        condiciones: str = "",
        validez_oferta_fecha: str = "",
        link_catalogo: str = "",
        registrado_por: str = "",
        notas: str = "",
    ) -> WriteResult:
        fecha = normalize_dd_mm_yyyy(fecha_oferta) or today_str()
        errors = self.validate(
            dataset,
            supplier_id=supplier_id,
            product_id=product_id,
            fecha_oferta=fecha,
            precio=precio,
            moneda=moneda,
            cantidad_minima=cantidad_minima,
            validez_oferta_fecha=validez_oferta_fecha,
        )
        if errors:
            return WriteResult.failure(*errors)

        value = parse_decimal(precio)
        quote = PriceQuote(
            historial_precio_id=unique_id(PRECIO_ID_PREFIX),
            supplier_id=str(supplier_id).strip(),
            product_id=str(product_id).strip(),
            fecha_oferta=fecha,
            # Se guarda con punto decimal: es el formato que `parse_decimal`
            # reinterpreta sin ambigüedad venga de donde venga la hoja.
            precio=f"{value:.4f}".rstrip("0").rstrip(".") if value is not None else "",
            moneda=str(moneda).upper(),
            unidad_medida=(unidad_medida or "").strip(),
            cantidad_minima=(cantidad_minima or "").strip(),
            condiciones=(condiciones or "").strip(),
            validez_oferta_fecha=normalize_dd_mm_yyyy(validez_oferta_fecha),
            link_catalogo=(link_catalogo or "").strip(),
            registrado_por=(registrado_por or "").strip(),
            notas=(notas or "").strip(),
            created_at=timestamp_now(),
            updated_at=timestamp_now(),
        )

        try:
            self.sheets.append_row(
                HISTORICO_PRECIOS_WORKSHEET_NAME, HISTORICO_PRECIOS_HEADERS, quote.to_row()
            )
        except Exception as exc:  # noqa: BLE001
            return WriteResult.from_exception(exc, action="registrar el precio")

        warnings: list[str] = []
        if dataset.relation_state(quote.supplier_id, quote.product_id) == REL_ESTADO_DESCARTADO:
            # No bloquea (a veces se registra una oferta de un descartado para
            # dejar constancia), pero sí se avisa: no entrará en el ranking.
            warnings.append(
                "Ojo: esta relación está descartada, así que la oferta no entra en el ranking de Home."
            )

        message = f"Precio registrado: {quote.formatted_price()}."
        if warnings:
            message = f"{message} {' '.join(warnings)}"
        return WriteResult.success(message, entity_id=quote.historial_precio_id)

    def update_quote(
        self,
        dataset: SpaceDataset,
        quote_id: str,
        changes: dict[str, str],
    ) -> WriteResult:
        quote = next(
            (item for item in dataset.quotes if item.historial_precio_id == str(quote_id).strip()),
            None,
        )
        if quote is None:
            return WriteResult.failure(f"No existe la oferta {quote_id}.")

        merged = quote.to_row() | {
            key: str(value or "").strip()
            for key, value in changes.items()
            if key in HISTORICO_PRECIOS_HEADERS
        }
        merged["historial_precio_id"] = quote.historial_precio_id
        merged["created_at"] = quote.created_at
        merged["fecha_oferta"] = normalize_dd_mm_yyyy(merged.get("fecha_oferta", ""))
        merged["validez_oferta_fecha"] = normalize_dd_mm_yyyy(merged.get("validez_oferta_fecha", ""))
        merged["moneda"] = str(merged.get("moneda", MONEDA_EUR)).upper()
        merged["updated_at"] = timestamp_now()

        errors = self.validate(
            dataset,
            supplier_id=merged.get("supplier_id", ""),
            product_id=merged.get("product_id", ""),
            fecha_oferta=merged.get("fecha_oferta", ""),
            precio=merged.get("precio", ""),
            moneda=merged.get("moneda", ""),
            cantidad_minima=merged.get("cantidad_minima", ""),
            validez_oferta_fecha=merged.get("validez_oferta_fecha", ""),
        )
        if errors:
            return WriteResult.failure(*errors)

        try:
            written = self.sheets.update_row_by_id(
                HISTORICO_PRECIOS_WORKSHEET_NAME,
                HISTORICO_PRECIOS_HEADERS,
                "historial_precio_id",
                quote.historial_precio_id,
                merged,
            )
        except Exception as exc:  # noqa: BLE001
            return WriteResult.from_exception(exc, action="actualizar la oferta")

        if not written:
            return WriteResult.failure("No se encontró la fila en HistoricoPrecios.")
        return WriteResult.success("Oferta actualizada.", entity_id=quote.historial_precio_id)
