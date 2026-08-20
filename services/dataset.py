"""``SpaceDataset``: todo el «Excel» en memoria, leído en UNA llamada API.

En vez de que cada página lea su pestaña (8 llamadas por refresco, y la cuota de
Sheets se agota rápido con varios usuarios), la app hace un único
``values.batchGet`` y construye este objeto. A partir de ahí, todos los cruces
—qué productos sirve un proveedor, cuál es su último precio, qué acciones tiene
pendientes— son operaciones en memoria sobre índices ya construidos.

El objeto es de solo lectura y se cachea con ``@st.cache_data``; las escrituras
van directas a Sheets y luego invalidan la versión de caché.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from datetime import date
from functools import cached_property

import pandas as pd

from config.settings import (
    HISTORICO_CONVERSACIONES_HEADERS,
    HISTORICO_CONVERSACIONES_WORKSHEET_NAME,
    HISTORICO_PRECIOS_HEADERS,
    HISTORICO_PRECIOS_WORKSHEET_NAME,
    PRODUCTOS_CAMPOS_SCHEMA_HEADERS,
    PRODUCTOS_CAMPOS_SCHEMA_WORKSHEET_NAME,
    PRODUCTOS_CAMPOS_VALORES_HEADERS,
    PRODUCTOS_CAMPOS_VALORES_WORKSHEET_NAME,
    PRODUCTOS_HEADERS,
    PRODUCTOS_WORKSHEET_NAME,
    SUMINISTRADOR_PRODUCTO_HEADERS,
    SUMINISTRADOR_PRODUCTO_WORKSHEET_NAME,
    SUMINISTRADORES_HEADERS,
    SUMINISTRADORES_WORKSHEET_NAME,
    USUARIOS_HEADERS,
    USUARIOS_WORKSHEET_NAME,
    WORKSHEET_HEADERS,
    WORKSHEET_NAMES,
)
from models.history import Conversation, PriceQuote
from models.product import Product, ProductFieldSpec, ProductFieldValue
from models.supplier import Supplier, SupplierProduct
from services.sheet_date_format import parse_sheet_date
from services.sheets_service import SheetsService

_SHEET_TO_ATTR: dict[str, str] = {
    PRODUCTOS_WORKSHEET_NAME: "productos",
    PRODUCTOS_CAMPOS_SCHEMA_WORKSHEET_NAME: "campos_schema",
    PRODUCTOS_CAMPOS_VALORES_WORKSHEET_NAME: "campos_valores",
    SUMINISTRADORES_WORKSHEET_NAME: "suministradores",
    SUMINISTRADOR_PRODUCTO_WORKSHEET_NAME: "relaciones",
    HISTORICO_CONVERSACIONES_WORKSHEET_NAME: "conversaciones",
    HISTORICO_PRECIOS_WORKSHEET_NAME: "precios",
    USUARIOS_WORKSHEET_NAME: "usuarios",
}

_ATTR_HEADERS: dict[str, tuple[str, ...]] = {
    "productos": PRODUCTOS_HEADERS,
    "campos_schema": PRODUCTOS_CAMPOS_SCHEMA_HEADERS,
    "campos_valores": PRODUCTOS_CAMPOS_VALORES_HEADERS,
    "suministradores": SUMINISTRADORES_HEADERS,
    "relaciones": SUMINISTRADOR_PRODUCTO_HEADERS,
    "conversaciones": HISTORICO_CONVERSACIONES_HEADERS,
    "precios": HISTORICO_PRECIOS_HEADERS,
    "usuarios": USUARIOS_HEADERS,
}


def _empty(headers: tuple[str, ...]) -> pd.DataFrame:
    return pd.DataFrame(columns=list(headers))


def _records(df: pd.DataFrame) -> list[dict[str, str]]:
    if df is None or df.empty:
        return []
    return df.fillna("").astype(str).to_dict("records")


def _dedupe(rows: list, key) -> tuple:
    """Deja una sola entidad por clave primaria, conservando la primera fila.

    La hoja la editan personas: duplicar una fila con copiar/pegar es trivial y
    no debe tumbar la app (dos widgets con la misma key lanzan excepción en
    Streamlit) ni contar dos veces el mismo proveedor en un KPI.
    """
    seen: set[str] = set()
    out: list = []
    for row in rows:
        identifier = str(key(row)).strip()
        # Una fila SIN id (histórico rellenado a mano antes de existir la app)
        # no se deduplica: colapsarlas todas en una sola perdería datos reales.
        if identifier and identifier in seen:
            continue
        if identifier:
            seen.add(identifier)
        out.append(row)
    return tuple(out)


@dataclass
class SpaceDataset:
    """Instantánea inmutable de todas las pestañas + índices derivados."""

    productos: pd.DataFrame = field(default_factory=lambda: _empty(PRODUCTOS_HEADERS))
    campos_schema: pd.DataFrame = field(default_factory=lambda: _empty(PRODUCTOS_CAMPOS_SCHEMA_HEADERS))
    campos_valores: pd.DataFrame = field(default_factory=lambda: _empty(PRODUCTOS_CAMPOS_VALORES_HEADERS))
    suministradores: pd.DataFrame = field(default_factory=lambda: _empty(SUMINISTRADORES_HEADERS))
    relaciones: pd.DataFrame = field(default_factory=lambda: _empty(SUMINISTRADOR_PRODUCTO_HEADERS))
    conversaciones: pd.DataFrame = field(default_factory=lambda: _empty(HISTORICO_CONVERSACIONES_HEADERS))
    precios: pd.DataFrame = field(default_factory=lambda: _empty(HISTORICO_PRECIOS_HEADERS))
    usuarios: pd.DataFrame = field(default_factory=lambda: _empty(USUARIOS_HEADERS))

    # ------------------------------------------------------------------
    # Construcción
    # ------------------------------------------------------------------

    @classmethod
    def load(cls, sheets: SheetsService) -> "SpaceDataset":
        """Lee TODAS las pestañas en una sola llamada a la API."""
        frames = sheets.read_worksheets_batch(
            WORKSHEET_NAMES, {name: WORKSHEET_HEADERS[name] for name in WORKSHEET_NAMES}
        )
        kwargs = {
            attr: frames.get(sheet_name, _empty(_ATTR_HEADERS[attr]))
            for sheet_name, attr in _SHEET_TO_ATTR.items()
        }
        return cls(**kwargs)

    @classmethod
    def empty(cls) -> "SpaceDataset":
        return cls()

    @property
    def is_empty(self) -> bool:
        return self.productos.empty and self.suministradores.empty

    # ------------------------------------------------------------------
    # Entidades (materializadas una sola vez por instancia)
    # ------------------------------------------------------------------

    @cached_property
    def products(self) -> tuple[Product, ...]:
        rows = [Product.from_row(row) for row in _records(self.productos)]
        return _dedupe([row for row in rows if row.product_id], lambda row: row.product_id)

    @cached_property
    def suppliers(self) -> tuple[Supplier, ...]:
        rows = [Supplier.from_row(row) for row in _records(self.suministradores)]
        return _dedupe([row for row in rows if row.supplier_id], lambda row: row.supplier_id)

    @cached_property
    def relations(self) -> tuple[SupplierProduct, ...]:
        rows = [SupplierProduct.from_row(row) for row in _records(self.relaciones)]
        # La clave real es la pareja, no ``rel_id``: dos filas para el mismo
        # proveedor y producto son el mismo hecho escrito dos veces.
        return _dedupe(
            [row for row in rows if row.supplier_id and row.product_id],
            lambda row: (row.supplier_id, row.product_id),
        )

    @cached_property
    def conversations(self) -> tuple[Conversation, ...]:
        rows = [Conversation.from_row(row) for row in _records(self.conversaciones)]
        return _dedupe(
            [row for row in rows if row.supplier_id],
            lambda row: row.historial_conversacion_id,
        )

    @cached_property
    def quotes(self) -> tuple[PriceQuote, ...]:
        rows = [PriceQuote.from_row(row) for row in _records(self.precios)]
        return _dedupe(
            [row for row in rows if row.supplier_id and row.product_id],
            lambda row: row.historial_precio_id,
        )

    @cached_property
    def field_specs(self) -> tuple[ProductFieldSpec, ...]:
        rows = [ProductFieldSpec.from_row(row) for row in _records(self.campos_schema)]
        return tuple(row for row in rows if row.product_id and row.field_key)

    @cached_property
    def field_values(self) -> tuple[ProductFieldValue, ...]:
        rows = [ProductFieldValue.from_row(row) for row in _records(self.campos_valores)]
        return tuple(row for row in rows if row.product_id and row.field_key)

    # ------------------------------------------------------------------
    # Índices — construidos una vez, consultados muchas
    # ------------------------------------------------------------------

    @cached_property
    def product_by_id(self) -> dict[str, Product]:
        return {product.product_id: product for product in self.products}

    @cached_property
    def supplier_by_id(self) -> dict[str, Supplier]:
        return {supplier.supplier_id: supplier for supplier in self.suppliers}

    @cached_property
    def relations_by_supplier(self) -> dict[str, tuple[SupplierProduct, ...]]:
        grouped: dict[str, list[SupplierProduct]] = defaultdict(list)
        for relation in self.relations:
            grouped[relation.supplier_id].append(relation)
        return {
            supplier_id: tuple(sorted(items, key=lambda rel: (rel.sort_key, rel.product_id)))
            for supplier_id, items in grouped.items()
        }

    @cached_property
    def relations_by_product(self) -> dict[str, tuple[SupplierProduct, ...]]:
        grouped: dict[str, list[SupplierProduct]] = defaultdict(list)
        for relation in self.relations:
            grouped[relation.product_id].append(relation)
        return {product_id: tuple(items) for product_id, items in grouped.items()}

    @cached_property
    def relation_by_pair(self) -> dict[tuple[str, str], SupplierProduct]:
        return {(rel.supplier_id, rel.product_id): rel for rel in self.relations}

    @cached_property
    def conversations_by_supplier(self) -> dict[str, tuple[Conversation, ...]]:
        grouped: dict[str, list[Conversation]] = defaultdict(list)
        for conversation in self.conversations:
            grouped[conversation.supplier_id].append(conversation)
        return {
            supplier_id: tuple(sorted(items, key=_conversation_sort_key, reverse=True))
            for supplier_id, items in grouped.items()
        }

    @cached_property
    def quotes_by_supplier(self) -> dict[str, tuple[PriceQuote, ...]]:
        grouped: dict[str, list[PriceQuote]] = defaultdict(list)
        for quote in self.quotes:
            grouped[quote.supplier_id].append(quote)
        return {
            supplier_id: tuple(sorted(items, key=_quote_sort_key, reverse=True))
            for supplier_id, items in grouped.items()
        }

    @cached_property
    def latest_quote_by_pair(self) -> dict[tuple[str, str], PriceQuote]:
        """Oferta más reciente por pareja (proveedor, producto) — base del ranking."""
        best: dict[tuple[str, str], PriceQuote] = {}
        for quote in self.quotes:
            key = (quote.supplier_id, quote.product_id)
            current = best.get(key)
            if current is None or _quote_sort_key(quote) > _quote_sort_key(current):
                best[key] = quote
        return best

    @cached_property
    def specs_by_product(self) -> dict[str, tuple[ProductFieldSpec, ...]]:
        grouped: dict[str, list[ProductFieldSpec]] = defaultdict(list)
        for spec in self.field_specs:
            if spec.activo:
                grouped[spec.product_id].append(spec)
        return {
            product_id: tuple(sorted(items, key=lambda spec: (spec.orden, spec.field_key)))
            for product_id, items in grouped.items()
        }

    @cached_property
    def spec_values_by_product(self) -> dict[str, dict[str, str]]:
        grouped: dict[str, dict[str, str]] = defaultdict(dict)
        for value in self.field_values:
            grouped[value.product_id][value.field_key] = value.valor
        return dict(grouped)

    @cached_property
    def paises(self) -> tuple[str, ...]:
        return tuple(sorted({s.pais for s in self.suppliers if s.pais}, key=str.casefold))

    @cached_property
    def categorias(self) -> tuple[str, ...]:
        return tuple(sorted({p.categoria for p in self.products if p.categoria}, key=str.casefold))

    # ------------------------------------------------------------------
    # Consultas de conveniencia
    # ------------------------------------------------------------------

    def product_name(self, product_id: str) -> str:
        product = self.product_by_id.get(str(product_id).strip())
        return product.display_name if product else str(product_id or "")

    def supplier_name(self, supplier_id: str) -> str:
        supplier = self.supplier_by_id.get(str(supplier_id).strip())
        return supplier.display_name if supplier else str(supplier_id or "")

    def active_products(self) -> tuple[Product, ...]:
        return tuple(product for product in self.products if product.is_activo)

    def products_for_supplier(self, supplier_id: str) -> tuple[SupplierProduct, ...]:
        return self.relations_by_supplier.get(str(supplier_id).strip(), ())

    def suppliers_for_product(self, product_id: str) -> tuple[SupplierProduct, ...]:
        return self.relations_by_product.get(str(product_id).strip(), ())

    def relation_state(self, supplier_id: str, product_id: str) -> str:
        relation = self.relation_by_pair.get((str(supplier_id).strip(), str(product_id).strip()))
        return relation.estado if relation else ""

    def latest_quote(self, supplier_id: str, product_id: str) -> PriceQuote | None:
        return self.latest_quote_by_pair.get((str(supplier_id).strip(), str(product_id).strip()))

    def latest_quote_for_supplier(self, supplier_id: str) -> PriceQuote | None:
        quotes = self.quotes_by_supplier.get(str(supplier_id).strip(), ())
        return quotes[0] if quotes else None

    def last_contact_date(self, supplier_id: str, product_id: str = "") -> date | None:
        """Fecha del último contacto con un proveedor.

        Con ``product_id`` se acota a las conversaciones sobre ESE producto: una
        charla sobre motores no debe hacer parecer viva la relación de
        rodamientos con el mismo proveedor.
        """
        wanted_product = str(product_id or "").strip()
        for conversation in self.conversations_by_supplier.get(str(supplier_id).strip(), ()):
            if wanted_product and conversation.product_id != wanted_product:
                continue
            parsed = conversation.fecha_contacto_date
            if parsed:
                return parsed
        return None

    def open_actions_for_supplier(self, supplier_id: str) -> tuple[Conversation, ...]:
        return tuple(
            conversation
            for conversation in self.conversations_by_supplier.get(str(supplier_id).strip(), ())
            if conversation.has_open_action()
        )

    def product_specs(self, product_id: str) -> list[tuple[ProductFieldSpec, str]]:
        """[(definición del campo, valor)] en el orden declarado por el esquema."""
        key = str(product_id).strip()
        values = self.spec_values_by_product.get(key, {})
        return [(spec, values.get(spec.field_key, "")) for spec in self.specs_by_product.get(key, ())]


# ---------------------------------------------------------------------------
# Claves de ordenación — «más reciente primero» con fallback estable
# ---------------------------------------------------------------------------


def _conversation_sort_key(conversation: Conversation) -> tuple:
    parsed = conversation.fecha_contacto_date
    return (
        parsed or date.min,
        conversation.hora_contacto or "",
        conversation.historial_conversacion_id,
    )


def _quote_sort_key(quote: PriceQuote) -> tuple:
    parsed = quote.fecha_oferta_date
    # Ante misma fecha, desempata el id: el orden nunca depende del orden de
    # llegada de las filas, así que la UI no "baila" entre reruns.
    return (parsed or date.min, quote.historial_precio_id)


def parse_date(value: object) -> date | None:
    """Reexport para que las páginas no importen el módulo de fechas por su cuenta."""
    return parse_sheet_date(value)
