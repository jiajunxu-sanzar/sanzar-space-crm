"""La bandeja de acciones (§3.2): filtro por persona, cubos y orden."""

from __future__ import annotations

from datetime import date

from services.actions_stats import (
    Bucket,
    bucket_counts,
    classify,
    group_by_bucket,
    pending_actions,
    people_with_actions,
    stagnant_relations,
    summarize_actions,
)
from tests.conftest import make_dataset

TODAY = date(2026, 8, 20)


def _conversation(
    conv_id: str,
    *,
    persona: str,
    fecha_accion: str = "",
    detalle: str = "Llamar",
    estado: str = "Pendiente",
    supplier_id: str = "SUP-0001",
    product_id: str = "PRD-0001",
    fecha_contacto: str = "01/08/2026",
) -> dict:
    return {
        "historial_conversacion_id": conv_id,
        "supplier_id": supplier_id,
        "product_id": product_id,
        "tipo_conversacion": "Email",
        "fecha_contacto": fecha_contacto,
        "persona_contacto": "Marco",
        "resumen": "Pedimos oferta",
        "proxima_accion_detalle": detalle,
        "proxima_accion_fecha": fecha_accion,
        "proxima_accion_persona": persona,
        "estado_accion": estado,
    }


def _base_dataset(conversaciones: list[dict]):
    return make_dataset(
        productos=[{"product_id": "PRD-0001", "nombre_producto": "Motor", "estado": "Activo"}],
        suministradores=[{"supplier_id": "SUP-0001", "nombre_suministrador": "Alfa"}],
        relaciones=[
            {
                "rel_id": "REL-1",
                "supplier_id": "SUP-0001",
                "product_id": "PRD-0001",
                "estado": "Potencial proveedor",
            }
        ],
        conversaciones=conversaciones,
    )


def test_classify_cubre_todos_los_cubos():
    assert classify(date(2026, 8, 19), today=TODAY) is Bucket.VENCIDA
    assert classify(date(2026, 8, 20), today=TODAY) is Bucket.HOY
    assert classify(date(2026, 8, 21), today=TODAY) is Bucket.MANANA
    assert classify(date(2026, 8, 26), today=TODAY) is Bucket.PROXIMOS
    assert classify(date(2026, 9, 30), today=TODAY) is Bucket.FUTURO
    assert classify(None, today=TODAY) is Bucket.SIN_FECHA


def test_filtra_por_persona_de_la_proxima_accion():
    dataset = _base_dataset(
        [
            _conversation("CNV-1", persona="Marco", fecha_accion="25/08/2026"),
            _conversation("CNV-2", persona="Jiajun", fecha_accion="25/08/2026"),
        ]
    )
    mias = pending_actions(dataset, persona="Marco", today=TODAY)
    todas = pending_actions(dataset, today=TODAY)

    assert [item.conversation_id for item in mias] == ["CNV-1"]
    assert len(todas) == 2


def test_el_filtro_ignora_mayusculas_y_espacios():
    dataset = _base_dataset([_conversation("CNV-1", persona="  Marco Ruano ", fecha_accion="25/08/2026")])
    assert len(pending_actions(dataset, persona="marco ruano", today=TODAY)) == 1


def test_vencidas_van_primero_y_las_mas_antiguas_arriba():
    dataset = _base_dataset(
        [
            _conversation("CNV-futura", persona="Marco", fecha_accion="30/09/2026"),
            _conversation("CNV-vieja", persona="Marco", fecha_accion="01/07/2026"),
            _conversation("CNV-hoy", persona="Marco", fecha_accion="20/08/2026"),
            _conversation("CNV-vencida", persona="Marco", fecha_accion="15/08/2026"),
        ]
    )
    order = [item.conversation_id for item in pending_actions(dataset, persona="Marco", today=TODAY)]

    assert order == ["CNV-vieja", "CNV-vencida", "CNV-hoy", "CNV-futura"]


def test_las_completadas_no_aparecen():
    dataset = _base_dataset(
        [
            _conversation("CNV-1", persona="Marco", fecha_accion="15/08/2026", estado="Completada"),
            _conversation("CNV-2", persona="Marco", fecha_accion="15/08/2026", estado="Pendiente"),
        ]
    )
    assert [item.conversation_id for item in pending_actions(dataset, today=TODAY)] == ["CNV-2"]


def test_una_conversacion_sin_proxima_accion_no_es_una_tarea():
    dataset = _base_dataset([_conversation("CNV-1", persona="Marco", detalle="", fecha_accion="")])
    assert pending_actions(dataset, today=TODAY) == ()


def test_pendiente_sin_fecha_sigue_siendo_trabajo_y_va_al_final():
    dataset = _base_dataset(
        [
            _conversation("CNV-sin", persona="Marco", fecha_accion=""),
            _conversation("CNV-con", persona="Marco", fecha_accion="15/08/2026"),
        ]
    )
    items = pending_actions(dataset, today=TODAY)

    assert [item.conversation_id for item in items] == ["CNV-con", "CNV-sin"]
    assert items[-1].bucket is Bucket.SIN_FECHA
    assert pending_actions(dataset, today=TODAY, include_undated=False) == (items[0],)


def test_due_label_es_legible():
    dataset = _base_dataset(
        [
            _conversation("CNV-1", persona="Marco", fecha_accion="17/08/2026"),
            _conversation("CNV-2", persona="Marco", fecha_accion="20/08/2026"),
            _conversation("CNV-3", persona="Marco", fecha_accion="21/08/2026"),
        ]
    )
    labels = [item.due_label(today=TODAY) for item in pending_actions(dataset, today=TODAY)]
    assert labels == ["Vencida hace 3 días", "Hoy", "Mañana"]


def test_summary_y_conteo_por_cubo():
    dataset = _base_dataset(
        [
            _conversation("CNV-1", persona="Marco", fecha_accion="15/08/2026"),
            _conversation("CNV-2", persona="Marco", fecha_accion="20/08/2026"),
            _conversation("CNV-3", persona="Marco", fecha_accion="22/08/2026"),
            _conversation("CNV-4", persona="Marco", fecha_accion=""),
        ]
    )
    items = pending_actions(dataset, today=TODAY)
    stats = summarize_actions(items)
    counts = bucket_counts(items)

    assert (stats.total, stats.vencidas, stats.hoy, stats.proximos_7, stats.sin_fecha) == (4, 1, 1, 1, 1)
    assert stats.needs_attention == 2
    assert counts[Bucket.FUTURO] == 0
    assert [bucket for bucket, _ in group_by_bucket(items)] == [
        Bucket.VENCIDA,
        Bucket.HOY,
        Bucket.PROXIMOS,
        Bucket.SIN_FECHA,
    ]


def test_people_with_actions_solo_lista_a_quien_tiene_pendientes():
    dataset = _base_dataset(
        [
            _conversation("CNV-1", persona="Marco", fecha_accion="25/08/2026"),
            _conversation("CNV-2", persona="Jiajun", fecha_accion="25/08/2026", estado="Completada"),
        ]
    )
    assert people_with_actions(dataset) == ("Marco",)


def test_relacion_sin_ninguna_conversacion_cuenta_como_estancada():
    dataset = make_dataset(
        productos=[{"product_id": "PRD-0001", "nombre_producto": "Motor", "estado": "Activo"}],
        suministradores=[{"supplier_id": "SUP-0001", "nombre_suministrador": "Alfa"}],
        relaciones=[
            {
                "rel_id": "REL-1",
                "supplier_id": "SUP-0001",
                "product_id": "PRD-0001",
                "estado": "Potencial proveedor",
            }
        ],
    )
    stale = stagnant_relations(dataset, today=TODAY)

    assert len(stale) == 1
    assert stale[0].days_since_contact is None


def test_una_conversacion_reciente_evita_el_estancamiento():
    dataset = _base_dataset([_conversation("CNV-1", persona="Marco", fecha_contacto="18/08/2026")])
    assert stagnant_relations(dataset, today=TODAY) == ()


def test_el_estancamiento_se_mide_por_relacion_no_por_proveedor():
    """Hablar de motores no mantiene viva la negociación de rodamientos."""
    dataset = make_dataset(
        productos=[
            {"product_id": "PRD-0001", "nombre_producto": "Motor", "estado": "Activo"},
            {"product_id": "PRD-0002", "nombre_producto": "Bearing", "estado": "Activo"},
        ],
        suministradores=[{"supplier_id": "SUP-0001", "nombre_suministrador": "Alfa"}],
        relaciones=[
            {"rel_id": "REL-1", "supplier_id": "SUP-0001", "product_id": "PRD-0001", "estado": "Potencial proveedor"},
            {"rel_id": "REL-2", "supplier_id": "SUP-0001", "product_id": "PRD-0002", "estado": "Potencial proveedor"},
        ],
        conversaciones=[
            _conversation("CNV-1", persona="Marco", fecha_contacto="18/08/2026", product_id="PRD-0001")
        ],
    )
    stale = stagnant_relations(dataset, today=TODAY)

    assert [row.product_id for row in stale] == ["PRD-0002"]
