"""«¿Quién es hoy el suministrador más barato de cada producto?» (§3.1).

Este cálculo **no se materializa en ninguna hoja**: se computa en tiempo real
a partir de `HistoricoPrecios` + `SuministradorProducto`, exactamente igual que
``services/proxima_accion_stats.py`` en el CRM de clientes calcula sus buckets a
partir de `Contacts`. Una tabla de "ganadores" guardada en el Excel se quedaría
obsoleta en cuanto alguien registre una oferta nueva.

Algoritmo (§3.1):

1. Quedarse con el registro más reciente (``fecha_oferta``) por cada pareja
   (``supplier_id``, ``product_id``).
2. Descartar las parejas cuyo estado en `SuministradorProducto` sea
   ``Descartado``.
3. Agrupar por producto y quedarse con el precio mínimo **dentro de cada
   moneda** (§6: sin tipo de cambio, comparar EUR con USD sería inventarse un
   ganador).
4. Devolver el ganador de cada producto para pintar su tarjeta.

Módulo puro: recibe un ``SpaceDataset`` y devuelve datos. Sin Streamlit, sin
red — por eso es directamente testeable.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date

from config.settings import REL_ESTADO_CONFIRMADO, REL_ESTADO_DESCARTADO
from models.history import PriceQuote
from services.dataset import SpaceDataset
from services.locale_numbers import format_money


@dataclass(frozen=True, slots=True)
class LeaderboardEntry:
    """Una oferta candidata dentro del ranking de un producto."""

    supplier_id: str
    supplier_name: str
    product_id: str
    price: float
    moneda: str
    fecha_oferta: str
    unidad_medida: str = ""
    cantidad_minima: str = ""
    estado_relacion: str = ""
    link_catalogo: str = ""
    condiciones: str = ""
    is_expired: bool = False

    @property
    def is_confirmed(self) -> bool:
        return self.estado_relacion == REL_ESTADO_CONFIRMADO

    def formatted_price(self) -> str:
        return format_money(self.price, self.moneda)

    def price_caption(self) -> str:
        """«1.250,00 € · por unidad · MOQ 50»."""
        parts = [self.formatted_price()]
        if self.unidad_medida:
            parts.append(self.unidad_medida)
        if self.cantidad_minima:
            parts.append(f"MOQ {self.cantidad_minima}")
        return " · ".join(parts)


@dataclass(frozen=True, slots=True)
class ProductLeaderboard:
    """Ranking completo de un producto, agrupado por moneda.

    Se agrupa por moneda a propósito (§6): sin tipo de cambio de referencia,
    decir que 900 USD «gana» a 950 EUR sería inventarse el resultado.
    """

    product_id: str
    product_name: str
    categoria: str = ""
    by_currency: dict[str, tuple[LeaderboardEntry, ...]] = field(default_factory=dict)

    @property
    def has_quotes(self) -> bool:
        return any(self.by_currency.values())

    @property
    def currencies(self) -> tuple[str, ...]:
        return tuple(sorted(currency for currency, rows in self.by_currency.items() if rows))

    @property
    def is_mixed_currency(self) -> bool:
        """Hay ofertas vivas en más de una moneda: no existe un único ganador."""
        return len(self.currencies) > 1

    def winner(self, moneda: str | None = None) -> LeaderboardEntry | None:
        """Oferta más barata; sin moneda, la de la primera moneda disponible."""
        if moneda:
            rows = self.by_currency.get(moneda, ())
            return rows[0] if rows else None
        for currency in self.currencies:
            rows = self.by_currency.get(currency, ())
            if rows:
                return rows[0]
        return None

    def winners(self) -> tuple[LeaderboardEntry, ...]:
        """Un ganador por moneda (uno solo salvo cotizaciones mixtas)."""
        return tuple(
            entry
            for entry in (self.winner(currency) for currency in self.currencies)
            if entry is not None
        )

    def ranking(self, moneda: str | None = None) -> tuple[LeaderboardEntry, ...]:
        if moneda:
            return self.by_currency.get(moneda, ())
        return tuple(
            entry for currency in self.currencies for entry in self.by_currency.get(currency, ())
        )

    def supplier_count(self) -> int:
        return len({entry.supplier_id for entry in self.ranking()})


def _candidate_entries(
    dataset: SpaceDataset,
    *,
    include_expired: bool,
    today: date | None,
) -> list[LeaderboardEntry]:
    """Paso 1 + 2: última oferta por pareja, sin las relaciones descartadas."""
    reference = today
    entries: list[LeaderboardEntry] = []

    for (supplier_id, product_id), quote in dataset.latest_quote_by_pair.items():
        estado = dataset.relation_state(supplier_id, product_id)
        # Paso 2 — un proveedor descartado para ESTE producto no compite, aunque
        # siga confirmado para otro.
        if estado == REL_ESTADO_DESCARTADO:
            continue

        price = quote.precio_value
        if price is None or price < 0:
            continue

        expired = quote.is_expired(today=reference) if reference else quote.is_expired()
        if expired and not include_expired:
            continue

        entries.append(_entry_from_quote(dataset, quote, price, estado, expired))

    return entries


def _entry_from_quote(
    dataset: SpaceDataset,
    quote: PriceQuote,
    price: float,
    estado: str,
    expired: bool,
) -> LeaderboardEntry:
    return LeaderboardEntry(
        supplier_id=quote.supplier_id,
        supplier_name=dataset.supplier_name(quote.supplier_id),
        product_id=quote.product_id,
        price=price,
        moneda=quote.moneda,
        fecha_oferta=quote.fecha_oferta,
        unidad_medida=quote.unidad_medida,
        cantidad_minima=quote.cantidad_minima,
        estado_relacion=estado,
        link_catalogo=quote.link_catalogo,
        condiciones=quote.condiciones,
        is_expired=expired,
    )


def _sort_key(entry: LeaderboardEntry) -> tuple[float, int, int, str]:
    """Orden del ranking: barato → confirmado → reciente → id (estable)."""
    return (
        entry.price,
        # A igual precio gana el proveedor ya confirmado: menos riesgo.
        0 if entry.is_confirmed else 1,
        # Negativo para que la fecha MÁS reciente ordene antes.
        -_date_ordinal(entry.fecha_oferta),
        # Desempate determinista: el orden no puede depender del orden de las
        # filas en la hoja, o la UI "bailaría" entre reruns.
        entry.supplier_id,
    )


def _date_ordinal(value: str) -> int:
    from services.sheet_date_format import parse_sheet_date

    parsed = parse_sheet_date(value)
    return parsed.toordinal() if parsed else 0


def build_leaderboards(
    dataset: SpaceDataset,
    *,
    include_expired: bool = True,
    only_active_products: bool = True,
    today: date | None = None,
) -> tuple[ProductLeaderboard, ...]:
    """Ranking de todos los productos, ordenado por nombre de producto.

    Args:
        include_expired: incluir ofertas cuya ``validez_oferta_fecha`` ya pasó.
            Por defecto sí, marcadas como caducadas: es más útil ver «el mejor
            precio conocido, caducado» que no ver nada.
        only_active_products: ignorar los productos ``Descontinuado``.
        today: fecha de referencia (los tests la fijan).
    """
    entries = _candidate_entries(dataset, include_expired=include_expired, today=today)

    grouped: dict[str, dict[str, list[LeaderboardEntry]]] = {}
    for entry in entries:
        grouped.setdefault(entry.product_id, {}).setdefault(entry.moneda, []).append(entry)

    products = dataset.active_products() if only_active_products else dataset.products
    boards: list[ProductLeaderboard] = []
    for product in products:
        by_currency = {
            currency: tuple(sorted(rows, key=_sort_key))
            for currency, rows in grouped.get(product.product_id, {}).items()
        }
        boards.append(
            ProductLeaderboard(
                product_id=product.product_id,
                product_name=product.display_name,
                categoria=product.categoria,
                by_currency=by_currency,
            )
        )

    # Primero los productos que ya tienen ofertas: la portada debe abrir con
    # información, no con tarjetas vacías.
    return tuple(
        sorted(boards, key=lambda board: (not board.has_quotes, board.product_name.casefold()))
    )


def leaderboard_for_product(
    dataset: SpaceDataset,
    product_id: str,
    *,
    include_expired: bool = True,
    today: date | None = None,
) -> ProductLeaderboard | None:
    target = str(product_id or "").strip()
    for board in build_leaderboards(
        dataset, include_expired=include_expired, only_active_products=False, today=today
    ):
        if board.product_id == target:
            return board
    return None


def headline_quote_by_supplier(
    dataset: SpaceDataset,
    *,
    today: date | None = None,
) -> dict[str, LeaderboardEntry]:
    """Oferta que representa a cada suministrador en la columna «precio».

    Comparar por precio las ofertas de un mismo proveedor **no** funciona: son
    de productos distintos y a veces de monedas distintas, así que «la más
    barata» acabaría diciendo que 1.100 $ de rodamientos es mejor que 1.250 €
    de motores. En su lugar:

    1. Si el proveedor gana el ranking de algún producto, se muestra esa oferta
       (y el chip de «ganador» se refiere entonces a lo que se está viendo).
    2. Si no gana ninguna, se muestra su oferta **más reciente**: es su precio
       actual, que es lo que interesa de un vistazo.
    """
    winners: dict[str, LeaderboardEntry] = {}
    for board in build_leaderboards(dataset, only_active_products=False, today=today):
        for entry in board.winners():
            winners.setdefault(entry.supplier_id, entry)

    headline: dict[str, LeaderboardEntry] = {}
    for entry in _candidate_entries(dataset, include_expired=True, today=today):
        supplier_id = entry.supplier_id
        if supplier_id in winners:
            headline[supplier_id] = winners[supplier_id]
            continue
        current = headline.get(supplier_id)
        if current is None or _date_ordinal(entry.fecha_oferta) > _date_ordinal(current.fecha_oferta):
            headline[supplier_id] = entry
    return headline


def winning_supplier_ids(
    dataset: SpaceDataset,
    *,
    today: date | None = None,
) -> set[str]:
    """Suministradores que hoy ganan el ranking de al menos un producto."""
    return {
        entry.supplier_id
        for board in build_leaderboards(dataset, only_active_products=False, today=today)
        for entry in board.winners()
    }


@dataclass(frozen=True, slots=True)
class LeaderboardSummary:
    """KPIs de la portada."""

    productos_activos: int = 0
    productos_con_oferta: int = 0
    suministradores: int = 0
    confirmados: int = 0
    potenciales: int = 0
    descartados: int = 0
    monedas_mixtas: tuple[str, ...] = ()

    @property
    def productos_sin_oferta(self) -> int:
        return max(0, self.productos_activos - self.productos_con_oferta)


def summarize(
    dataset: SpaceDataset,
    boards: tuple[ProductLeaderboard, ...] | None = None,
) -> LeaderboardSummary:
    boards = boards if boards is not None else build_leaderboards(dataset)
    from config.settings import REL_ESTADO_POTENCIAL

    estados = [relation.estado for relation in dataset.relations]
    return LeaderboardSummary(
        productos_activos=len(dataset.active_products()),
        productos_con_oferta=sum(1 for board in boards if board.has_quotes),
        suministradores=len(dataset.suppliers),
        confirmados=sum(1 for estado in estados if estado == REL_ESTADO_CONFIRMADO),
        potenciales=sum(1 for estado in estados if estado == REL_ESTADO_POTENCIAL),
        descartados=sum(1 for estado in estados if estado == REL_ESTADO_DESCARTADO),
        monedas_mixtas=tuple(
            board.product_name for board in boards if board.is_mixed_currency
        ),
    )
