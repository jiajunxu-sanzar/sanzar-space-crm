"""Validación de suministradores y de sus relaciones por producto (§4.2)."""

from __future__ import annotations

from config.settings import (
    REL_ESTADO_CONFIRMADO,
    REL_ESTADO_DESCARTADO,
    REL_ESTADO_POTENCIAL,
)
from services.conversations_service import ConversationsService
from services.pricing_service import PricingService
from services.suppliers_service import SuppliersService
from tests.conftest import make_dataset


def _dataset():
    return make_dataset(
        productos=[
            {"product_id": "PRD-0001", "nombre_producto": "Motor", "categoria": "Motores", "estado": "Activo"},
            {"product_id": "PRD-0002", "nombre_producto": "Bearing", "categoria": "Bearing", "estado": "Activo"},
        ],
        suministradores=[
            {"supplier_id": "SUP-0001", "nombre_suministrador": "Alfa", "pais": "España"},
            {"supplier_id": "SUP-0006", "nombre_suministrador": "Multi", "pais": "China"},
        ],
        relaciones=[
            {"rel_id": "REL-1", "supplier_id": "SUP-0001", "product_id": "PRD-0001", "estado": REL_ESTADO_POTENCIAL},
            {"rel_id": "REL-2", "supplier_id": "SUP-0006", "product_id": "PRD-0001", "estado": REL_ESTADO_DESCARTADO, "razon_descarte": "Plazo"},
            {"rel_id": "REL-3", "supplier_id": "SUP-0006", "product_id": "PRD-0002", "estado": REL_ESTADO_CONFIRMADO},
        ],
    )


# --- Identidad ------------------------------------------------------------


def test_nombre_obligatorio():
    errors = SuppliersService.validate_supplier(_dataset(), nombre_suministrador="  ")
    assert any("obligatorio" in error for error in errors)


def test_nombre_duplicado_se_rechaza_sin_distinguir_mayusculas():
    errors = SuppliersService.validate_supplier(_dataset(), nombre_suministrador="alfa")
    assert any("Ya existe" in error for error in errors)


def test_al_editar_no_choca_consigo_mismo():
    errors = SuppliersService.validate_supplier(
        _dataset(), nombre_suministrador="Alfa", exclude_supplier_id="SUP-0001"
    )
    assert errors == ()


def test_email_con_formato_dudoso_se_rechaza():
    errors = SuppliersService.validate_supplier(
        _dataset(), nombre_suministrador="Nuevo", email="esto no es un email"
    )
    assert any("email" in error.lower() for error in errors)


def test_email_vacio_es_valido():
    assert SuppliersService.validate_supplier(_dataset(), nombre_suministrador="Nuevo", email="") == ()


# --- Relación proveedor ↔ producto ---------------------------------------


def test_descartar_exige_razon():
    errors = SuppliersService.validate_relation(
        _dataset(), product_id="PRD-0001", estado=REL_ESTADO_DESCARTADO, razon_descarte=""
    )
    assert any("razón de descarte" in error.lower() for error in errors)


def test_descartar_con_razon_es_valido():
    errors = SuppliersService.validate_relation(
        _dataset(),
        product_id="PRD-0001",
        estado=REL_ESTADO_DESCARTADO,
        razon_descarte="Precio fuera de mercado",
    )
    assert errors == ()


def test_no_se_puede_duplicar_la_misma_relacion():
    errors = SuppliersService.validate_relation(
        _dataset(),
        product_id="PRD-0001",
        estado=REL_ESTADO_POTENCIAL,
        supplier_id="SUP-0001",
    )
    assert any("ya tiene una relación" in error for error in errors)


def test_al_editar_una_relacion_existente_no_se_marca_como_duplicada():
    errors = SuppliersService.validate_relation(
        _dataset(),
        product_id="PRD-0001",
        estado=REL_ESTADO_CONFIRMADO,
        supplier_id="SUP-0001",
        allow_existing=True,
    )
    assert errors == ()


def test_producto_inexistente_se_rechaza():
    errors = SuppliersService.validate_relation(
        _dataset(), product_id="PRD-9999", estado=REL_ESTADO_POTENCIAL
    )
    assert any("no existe" in error for error in errors)


def test_un_proveedor_puede_tener_estados_distintos_por_producto():
    dataset = _dataset()
    assert dataset.relation_state("SUP-0006", "PRD-0001") == REL_ESTADO_DESCARTADO
    assert dataset.relation_state("SUP-0006", "PRD-0002") == REL_ESTADO_CONFIRMADO


def test_las_relaciones_se_ordenan_confirmado_primero():
    estados = [rel.estado for rel in _dataset().products_for_supplier("SUP-0006")]
    assert estados[0] == REL_ESTADO_CONFIRMADO


# --- Conversaciones -------------------------------------------------------


def test_una_proxima_accion_pendiente_necesita_responsable():
    errors = ConversationsService.validate(
        _dataset(),
        supplier_id="SUP-0001",
        product_id="PRD-0001",
        tipo_conversacion="Email",
        fecha_contacto="01/08/2026",
        persona_contacto="Marco",
        resumen="Pedimos oferta",
        proxima_accion_detalle="Reclamar precio",
        proxima_accion_fecha="10/08/2026",
        proxima_accion_persona="",
    )
    assert any("quién la ejecuta" in error for error in errors)


def test_el_resumen_es_obligatorio():
    errors = ConversationsService.validate(
        _dataset(),
        supplier_id="SUP-0001",
        product_id="PRD-0001",
        tipo_conversacion="Email",
        fecha_contacto="01/08/2026",
        persona_contacto="Marco",
        resumen="",
    )
    assert any("resumen" in error.lower() for error in errors)


def test_fecha_con_formato_invalido_se_rechaza():
    errors = ConversationsService.validate(
        _dataset(),
        supplier_id="SUP-0001",
        product_id="PRD-0001",
        tipo_conversacion="Email",
        fecha_contacto="2026-08-01",
        persona_contacto="Marco",
        resumen="Algo",
    )
    assert any("DD/MM/AAAA" in error for error in errors)


def test_conversacion_valida_no_da_errores():
    assert (
        ConversationsService.validate(
            _dataset(),
            supplier_id="SUP-0001",
            product_id="PRD-0001",
            tipo_conversacion="Reunión",
            fecha_contacto="01/08/2026",
            hora_contacto="09:30",
            persona_contacto="Marco",
            resumen="Reunión de arranque",
            proxima_accion_detalle="Enviar specs",
            proxima_accion_fecha="10/08/2026",
            proxima_accion_persona="Jiajun",
        )
        == ()
    )


def test_sin_proxima_accion_permite_estado_vacio():
    assert (
        ConversationsService.validate(
            _dataset(),
            supplier_id="SUP-0001",
            product_id="PRD-0001",
            tipo_conversacion="Email",
            fecha_contacto="01/08/2026",
            persona_contacto="Marco",
            resumen="Solo informativo",
            estado_accion="",
        )
        == ()
    )


def test_proxima_accion_sin_estado_se_rechaza():
    errors = ConversationsService.validate(
        _dataset(),
        supplier_id="SUP-0001",
        product_id="PRD-0001",
        tipo_conversacion="Email",
        fecha_contacto="01/08/2026",
        persona_contacto="Marco",
        resumen="Algo",
        proxima_accion_detalle="Reclamar",
        proxima_accion_fecha="10/08/2026",
        proxima_accion_persona="Jiajun",
        estado_accion="",
    )
    assert any("Pendiente o Completada" in error for error in errors)


# --- Precios --------------------------------------------------------------


def test_no_se_puede_registrar_precio_sin_relacion_previa():
    errors = PricingService.validate(
        _dataset(),
        supplier_id="SUP-0001",
        product_id="PRD-0002",
        fecha_oferta="01/08/2026",
        precio="100",
        moneda="EUR",
    )
    assert any("no tiene ninguna relación" in error for error in errors)


def test_precio_no_numerico_se_rechaza():
    errors = PricingService.validate(
        _dataset(),
        supplier_id="SUP-0001",
        product_id="PRD-0001",
        fecha_oferta="01/08/2026",
        precio="a negociar",
        moneda="EUR",
    )
    assert any("número" in error for error in errors)


def test_la_validez_no_puede_ser_anterior_a_la_oferta():
    errors = PricingService.validate(
        _dataset(),
        supplier_id="SUP-0001",
        product_id="PRD-0001",
        fecha_oferta="01/08/2026",
        precio="100",
        moneda="EUR",
        validez_oferta_fecha="01/07/2026",
    )
    assert any("anterior" in error for error in errors)


def test_moneda_no_soportada_se_rechaza():
    errors = PricingService.validate(
        _dataset(),
        supplier_id="SUP-0001",
        product_id="PRD-0001",
        fecha_oferta="01/08/2026",
        precio="100",
        moneda="GBP",
    )
    assert any("Moneda no válida" in error for error in errors)


def test_precio_valido_no_da_errores():
    assert (
        PricingService.validate(
            _dataset(),
            supplier_id="SUP-0001",
            product_id="PRD-0001",
            fecha_oferta="01/08/2026",
            precio="1.250,00",
            moneda="EUR",
            cantidad_minima="50",
            validez_oferta_fecha="30/09/2026",
        )
        == ()
    )
