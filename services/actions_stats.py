"""Bandeja de próximas acciones (§3.2) — módulo puro, sin Streamlit ni red.

Equivalente a ``overdue_actions()`` / ``upcoming_actions()`` del CRM de
clientes, pero sobre `HistoricoConversaciones`: cada entrada con
``estado_accion = Pendiente`` y una próxima acción es una tarea de alguien.

El orden es siempre **vencidas primero**: lo que ya se pasó de fecha es lo que
cuesta dinero, y debe estar arriba aunque sea de hace tres semanas.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from datetime import date, timedelta
from enum import Enum

from models.history import Conversation
from services.dataset import SpaceDataset
from services.sheet_date_format import today_madrid


class Bucket(str, Enum):
    """Cubos temporales de la bandeja."""

    VENCIDA = "vencida"
    HOY = "hoy"
    MANANA = "manana"
    PROXIMOS = "proximos"
    FUTURO = "futuro"
    SIN_FECHA = "sin_fecha"


BUCKET_LABELS: dict[Bucket, str] = {
    Bucket.VENCIDA: "Vencidas",
    Bucket.HOY: "Hoy",
    Bucket.MANANA: "Mañana",
    Bucket.PROXIMOS: "Próximos 7 días",
    Bucket.FUTURO: "Más adelante",
    Bucket.SIN_FECHA: "Sin fecha",
}

# Orden de presentación: lo urgente arriba, lo indefinido al final.
BUCKET_ORDER: tuple[Bucket, ...] = (
    Bucket.VENCIDA,
    Bucket.HOY,
    Bucket.MANANA,
    Bucket.PROXIMOS,
    Bucket.FUTURO,
    Bucket.SIN_FECHA,
)

_BUCKET_RANK: dict[Bucket, int] = {bucket: index for index, bucket in enumerate(BUCKET_ORDER)}


def classify(due: date | None, *, today: date | None = None) -> Bucket:
    reference = today or today_madrid()
    if due is None:
        return Bucket.SIN_FECHA
    if due < reference:
        return Bucket.VENCIDA
    if due == reference:
        return Bucket.HOY
    if due == reference + timedelta(days=1):
        return Bucket.MANANA
    if due <= reference + timedelta(days=7):
        return Bucket.PROXIMOS
    return Bucket.FUTURO


@dataclass(frozen=True, slots=True)
class ActionItem:
    """Una fila de la bandeja, con todo lo necesario para pintarla y navegar."""

    conversation_id: str
    supplier_id: str
    supplier_name: str
    product_id: str
    product_name: str
    detalle: str
    fecha: str
    due: date | None
    persona: str
    tipo_conversacion: str
    resumen: str
    bucket: Bucket

    @property
    def is_overdue(self) -> bool:
        return self.bucket is Bucket.VENCIDA

    def days_late(self, *, today: date | None = None) -> int:
        if self.due is None:
            return 0
        return max(0, ((today or today_madrid()) - self.due).days)

    def due_label(self, *, today: date | None = None) -> str:
        """«Vencida hace 3 días», «Hoy», «En 5 días», «Sin fecha»."""
        if self.due is None:
            return "Sin fecha"
        delta = (self.due - (today or today_madrid())).days
        if delta < 0:
            days = abs(delta)
            return f"Vencida hace {days} día{'s' if days != 1 else ''}"
        if delta == 0:
            return "Hoy"
        if delta == 1:
            return "Mañana"
        return f"En {delta} días"


def _to_item(dataset: SpaceDataset, conversation: Conversation, today: date | None) -> ActionItem:
    due = conversation.proxima_accion_date
    return ActionItem(
        conversation_id=conversation.historial_conversacion_id,
        supplier_id=conversation.supplier_id,
        supplier_name=dataset.supplier_name(conversation.supplier_id),
        product_id=conversation.product_id,
        product_name=dataset.product_name(conversation.product_id),
        detalle=conversation.proxima_accion_detalle,
        fecha=conversation.proxima_accion_fecha,
        due=due,
        persona=conversation.proxima_accion_persona,
        tipo_conversacion=conversation.tipo_conversacion,
        resumen=conversation.resumen,
        bucket=classify(due, today=today),
    )


def _sort_key(item: ActionItem) -> tuple[int, date, str]:
    # Dentro de cada cubo, lo más antiguo primero (lo que más lleva esperando).
    return (_BUCKET_RANK[item.bucket], item.due or date.max, item.supplier_name.casefold())


def pending_actions(
    dataset: SpaceDataset,
    *,
    persona: str = "",
    today: date | None = None,
    include_undated: bool = True,
) -> tuple[ActionItem, ...]:
    """Acciones pendientes, vencidas primero.

    Args:
        persona: filtra por ``proxima_accion_persona`` (comparación sin
            distinguir mayúsculas ni espacios). Vacío = todo el equipo, que es
            lo que ve un admin al quitar el filtro.
        include_undated: incluir pendientes sin fecha. Se muestran al final
            porque «pendiente sin fecha» sigue siendo trabajo por hacer.
    """
    needle = str(persona or "").strip().casefold()
    items: list[ActionItem] = []

    for conversation in dataset.conversations:
        if not conversation.has_open_action():
            continue
        if needle and conversation.proxima_accion_persona.strip().casefold() != needle:
            continue
        item = _to_item(dataset, conversation, today)
        if item.bucket is Bucket.SIN_FECHA and not include_undated:
            continue
        items.append(item)

    return tuple(sorted(items, key=_sort_key))


def bucket_counts(items: tuple[ActionItem, ...]) -> dict[Bucket, int]:
    """Cuántas acciones hay en cada cubo (todos presentes, aunque valgan 0)."""
    counter = Counter(item.bucket for item in items)
    return {bucket: int(counter.get(bucket, 0)) for bucket in BUCKET_ORDER}


def group_by_bucket(items: tuple[ActionItem, ...]) -> list[tuple[Bucket, tuple[ActionItem, ...]]]:
    """[(cubo, acciones)] en orden de urgencia, sin cubos vacíos."""
    grouped: dict[Bucket, list[ActionItem]] = {bucket: [] for bucket in BUCKET_ORDER}
    for item in items:
        grouped[item.bucket].append(item)
    return [(bucket, tuple(rows)) for bucket, rows in grouped.items() if rows]


def people_with_actions(dataset: SpaceDataset) -> tuple[str, ...]:
    """Personas que tienen alguna acción pendiente asignada."""
    return tuple(
        sorted(
            {
                conversation.proxima_accion_persona.strip()
                for conversation in dataset.conversations
                if conversation.has_open_action() and conversation.proxima_accion_persona.strip()
            },
            key=str.casefold,
        )
    )


@dataclass(frozen=True, slots=True)
class ActionsSummary:
    total: int = 0
    vencidas: int = 0
    hoy: int = 0
    proximos_7: int = 0
    sin_fecha: int = 0

    @property
    def needs_attention(self) -> int:
        """Lo que hay que mirar hoy sí o sí."""
        return self.vencidas + self.hoy


def summarize_actions(items: tuple[ActionItem, ...]) -> ActionsSummary:
    counts = bucket_counts(items)
    return ActionsSummary(
        total=len(items),
        vencidas=counts[Bucket.VENCIDA],
        hoy=counts[Bucket.HOY],
        proximos_7=counts[Bucket.MANANA] + counts[Bucket.PROXIMOS],
        sin_fecha=counts[Bucket.SIN_FECHA],
    )


# ---------------------------------------------------------------------------
# Estancamiento (§6) — fuera del MVP, pero encaja natural aquí
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class StagnantRelation:
    supplier_id: str
    supplier_name: str
    product_id: str
    product_name: str
    estado: str
    days_since_contact: int | None


def stagnant_relations(
    dataset: SpaceDataset,
    *,
    today: date | None = None,
) -> tuple[StagnantRelation, ...]:
    """Relaciones sin conversación nueva desde hace más de lo tolerable.

    Usa ``REL_ESTADO_STAGNATION_DAYS``, mismo patrón que
    ``CONTACT_ESTADO_STAGNATION_DAYS`` en el CRM de clientes. Una relación sin
    ninguna conversación registrada cuenta como estancada: nadie ha hablado con
    ese proveedor todavía.

    La antigüedad se mide **por relación**, no por proveedor: hablar de motores
    con alguien no significa que su negociación de rodamientos siga viva.
    """
    from config.settings import REL_ESTADO_STAGNATION_DAYS

    reference = today or today_madrid()
    out: list[StagnantRelation] = []

    for relation in dataset.relations:
        threshold = REL_ESTADO_STAGNATION_DAYS.get(relation.estado)
        if threshold is None:
            continue
        last = dataset.last_contact_date(relation.supplier_id, relation.product_id)
        days = (reference - last).days if last else None
        if days is not None and days <= threshold:
            continue
        out.append(
            StagnantRelation(
                supplier_id=relation.supplier_id,
                supplier_name=dataset.supplier_name(relation.supplier_id),
                product_id=relation.product_id,
                product_name=dataset.product_name(relation.product_id),
                estado=relation.estado,
                days_since_contact=days,
            )
        )

    # Sin contacto nunca (None) es lo más grave: va primero.
    return tuple(
        sorted(out, key=lambda row: (row.days_since_contact is not None, -(row.days_since_contact or 0)))
    )
