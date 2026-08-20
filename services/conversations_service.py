"""Histórico de conversaciones con suministradores (§5, `HistoricoConversaciones`).

Cada entrada registra quién habló (``persona_contacto``) y quién ejecuta lo
siguiente (``proxima_accion_persona``) — son campos distintos a propósito, igual
que en ``ACCIONES_HEADERS`` del CRM de clientes. De ahí se alimenta la página
Acciones.
"""

from __future__ import annotations

from config.settings import (
    CONVERSACION_ID_PREFIX,
    ESTADO_ACCION_COMPLETADA,
    ESTADO_ACCION_OPCIONES,
    ESTADO_ACCION_PENDIENTE,
    HISTORICO_CONVERSACIONES_HEADERS,
    HISTORICO_CONVERSACIONES_WORKSHEET_NAME,
    TIPO_CONVERSACION_OPCIONES,
)
from models.history import Conversation
from services.dataset import SpaceDataset
from services.ids import unique_id
from services.result import WriteResult
from services.sheet_date_format import (
    DD_MM_YYYY_HINT,
    HH_MM_HINT,
    is_valid_dd_mm_yyyy,
    is_valid_hh_mm,
    normalize_dd_mm_yyyy,
    normalize_hh_mm,
    timestamp_now,
    today_str,
)
from services.sheets_service import SheetsService


class ConversationsService:
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
        tipo_conversacion: str,
        fecha_contacto: str,
        hora_contacto: str = "",
        persona_contacto: str = "",
        resumen: str = "",
        proxima_accion_detalle: str = "",
        proxima_accion_fecha: str = "",
        proxima_accion_persona: str = "",
        estado_accion: str = ESTADO_ACCION_PENDIENTE,
    ) -> tuple[str, ...]:
        errors: list[str] = []

        if str(supplier_id or "").strip() not in dataset.supplier_by_id:
            errors.append("Selecciona un suministrador válido.")
        if str(product_id or "").strip() not in dataset.product_by_id:
            errors.append("Selecciona el producto sobre el que va la conversación.")
        if tipo_conversacion not in TIPO_CONVERSACION_OPCIONES:
            errors.append(f"Tipo de conversación no válido: {tipo_conversacion}.")

        if not (fecha_contacto or "").strip():
            errors.append("La fecha de contacto es obligatoria.")
        elif not is_valid_dd_mm_yyyy(fecha_contacto):
            errors.append(f"Fecha de contacto inválida. {DD_MM_YYYY_HINT}")

        if not is_valid_hh_mm(hora_contacto):
            errors.append(f"Hora de contacto inválida. {HH_MM_HINT}")
        if not (persona_contacto or "").strip():
            errors.append("Indica quién ha hablado con el suministrador.")
        if not (resumen or "").strip():
            errors.append("El resumen de lo hablado es obligatorio: es el valor de este histórico.")

        if not is_valid_dd_mm_yyyy(proxima_accion_fecha):
            errors.append(f"Fecha de próxima acción inválida. {DD_MM_YYYY_HINT}")

        # Vacío = sin próxima acción (válido). Si hay acción, el estado debe
        # ser Pendiente o Completada.
        has_next = bool(
            (proxima_accion_detalle or "").strip() or (proxima_accion_fecha or "").strip()
        )
        estado = (estado_accion or "").strip()
        if estado and estado not in ESTADO_ACCION_OPCIONES:
            errors.append(f"Estado de acción no válido: {estado_accion}.")
        if has_next and not estado:
            errors.append("Si hay próxima acción, elige Pendiente o Completada.")

        # Una próxima acción sin responsable no llega nunca a la bandeja de
        # nadie: es peor que no tener acción, porque parece que está cubierta.
        if (
            has_next
            and estado == ESTADO_ACCION_PENDIENTE
            and not (proxima_accion_persona or "").strip()
        ):
            errors.append("Si hay próxima acción pendiente, indica quién la ejecuta.")

        return tuple(errors)

    # ------------------------------------------------------------------
    # Altas y ediciones
    # ------------------------------------------------------------------

    def add_conversation(
        self,
        dataset: SpaceDataset,
        *,
        supplier_id: str,
        product_id: str,
        tipo_conversacion: str,
        fecha_contacto: str = "",
        hora_contacto: str = "",
        persona_contacto: str = "",
        resumen: str = "",
        proxima_accion_detalle: str = "",
        proxima_accion_fecha: str = "",
        proxima_accion_persona: str = "",
        estado_accion: str = ESTADO_ACCION_PENDIENTE,
    ) -> WriteResult:
        fecha = normalize_dd_mm_yyyy(fecha_contacto) or today_str()
        errors = self.validate(
            dataset,
            supplier_id=supplier_id,
            product_id=product_id,
            tipo_conversacion=tipo_conversacion,
            fecha_contacto=fecha,
            hora_contacto=hora_contacto,
            persona_contacto=persona_contacto,
            resumen=resumen,
            proxima_accion_detalle=proxima_accion_detalle,
            proxima_accion_fecha=proxima_accion_fecha,
            proxima_accion_persona=proxima_accion_persona,
            estado_accion=estado_accion,
        )
        if errors:
            return WriteResult.failure(*errors)

        now = timestamp_now()
        conversation = Conversation(
            historial_conversacion_id=unique_id(CONVERSACION_ID_PREFIX),
            supplier_id=str(supplier_id).strip(),
            product_id=str(product_id).strip(),
            tipo_conversacion=tipo_conversacion,
            fecha_contacto=fecha,
            hora_contacto=normalize_hh_mm(hora_contacto),
            persona_contacto=(persona_contacto or "").strip(),
            resumen=(resumen or "").strip(),
            proxima_accion_detalle=(proxima_accion_detalle or "").strip(),
            proxima_accion_fecha=normalize_dd_mm_yyyy(proxima_accion_fecha),
            proxima_accion_persona=(proxima_accion_persona or "").strip(),
            estado_accion=estado_accion,
            created_at=now,
            updated_at=now,
        )

        try:
            self.sheets.append_row(
                HISTORICO_CONVERSACIONES_WORKSHEET_NAME,
                HISTORICO_CONVERSACIONES_HEADERS,
                conversation.to_row(),
            )
        except Exception as exc:  # noqa: BLE001
            return WriteResult.from_exception(exc, action="registrar la conversación")

        return WriteResult.success(
            "Conversación registrada.", entity_id=conversation.historial_conversacion_id
        )

    def update_conversation(
        self,
        dataset: SpaceDataset,
        conversation_id: str,
        changes: dict[str, str],
    ) -> WriteResult:
        conversation = next(
            (
                item
                for item in dataset.conversations
                if item.historial_conversacion_id == str(conversation_id).strip()
            ),
            None,
        )
        if conversation is None:
            return WriteResult.failure(f"No existe la conversación {conversation_id}.")

        merged = conversation.to_row() | {
            key: str(value or "").strip()
            for key, value in changes.items()
            if key in HISTORICO_CONVERSACIONES_HEADERS
        }
        merged["historial_conversacion_id"] = conversation.historial_conversacion_id
        merged["created_at"] = conversation.created_at
        merged["fecha_contacto"] = normalize_dd_mm_yyyy(merged.get("fecha_contacto", ""))
        merged["hora_contacto"] = normalize_hh_mm(merged.get("hora_contacto", ""))
        merged["proxima_accion_fecha"] = normalize_dd_mm_yyyy(merged.get("proxima_accion_fecha", ""))
        merged["updated_at"] = timestamp_now()

        errors = self.validate(
            dataset,
            supplier_id=merged.get("supplier_id", ""),
            product_id=merged.get("product_id", ""),
            tipo_conversacion=merged.get("tipo_conversacion", ""),
            fecha_contacto=merged.get("fecha_contacto", ""),
            hora_contacto=merged.get("hora_contacto", ""),
            persona_contacto=merged.get("persona_contacto", ""),
            resumen=merged.get("resumen", ""),
            proxima_accion_detalle=merged.get("proxima_accion_detalle", ""),
            proxima_accion_fecha=merged.get("proxima_accion_fecha", ""),
            proxima_accion_persona=merged.get("proxima_accion_persona", ""),
            estado_accion=merged.get("estado_accion", ESTADO_ACCION_PENDIENTE),
        )
        if errors:
            return WriteResult.failure(*errors)

        try:
            written = self.sheets.update_row_by_id(
                HISTORICO_CONVERSACIONES_WORKSHEET_NAME,
                HISTORICO_CONVERSACIONES_HEADERS,
                "historial_conversacion_id",
                conversation.historial_conversacion_id,
                merged,
            )
        except Exception as exc:  # noqa: BLE001
            return WriteResult.from_exception(exc, action="actualizar la conversación")

        if not written:
            return WriteResult.failure("No se encontró la fila en HistoricoConversaciones.")
        return WriteResult.success(
            "Conversación actualizada.", entity_id=conversation.historial_conversacion_id
        )

    def mark_action_done(self, conversation_id: str) -> WriteResult:
        """Cierra la próxima acción de una conversación — 1 celda, no la fila entera."""
        target = str(conversation_id or "").strip()
        if not target:
            return WriteResult.failure("Falta el identificador de la conversación.")
        try:
            written = self.sheets.update_cell_by_id(
                HISTORICO_CONVERSACIONES_WORKSHEET_NAME,
                "historial_conversacion_id",
                target,
                "estado_accion",
                ESTADO_ACCION_COMPLETADA,
            )
        except Exception as exc:  # noqa: BLE001
            return WriteResult.from_exception(exc, action="cerrar la acción")

        if not written:
            return WriteResult.failure("No se encontró esa conversación en la hoja.")
        return WriteResult.success("Acción marcada como completada.", entity_id=target)
