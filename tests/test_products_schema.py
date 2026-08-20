"""Esquema técnico dinámico (§4.1): añadir un producto no toca la estructura."""

from __future__ import annotations

from services.ids import next_sequential_id, relation_id, slugify_field_key, unique_id
from services.products_service import ProductsService, TechnicalField
from tests.conftest import make_dataset


def _dataset_con_esquema():
    return make_dataset(
        productos=[
            {"product_id": "PRD-0001", "nombre_producto": "Motor 5kW", "categoria": "Motores", "estado": "Activo"},
            {"product_id": "PRD-0002", "nombre_producto": "Bearing 6204", "categoria": "Bearing", "estado": "Activo"},
        ],
        campos_schema=[
            {"product_id": "PRD-0001", "field_key": "potencia_kw", "field_label": "Potencia", "unidad": "kW", "orden": "1", "activo": "Sí", "field_type": "numero"},
            {"product_id": "PRD-0001", "field_key": "voltaje_v", "field_label": "Voltaje", "unidad": "V", "orden": "2", "activo": "Sí", "field_type": "numero"},
            {"product_id": "PRD-0001", "field_key": "obsoleto", "field_label": "Campo retirado", "orden": "3", "activo": "No", "field_type": "texto"},
            {"product_id": "PRD-0002", "field_key": "diametro_mm", "field_label": "Diámetro", "unidad": "mm", "orden": "1", "activo": "Sí", "field_type": "numero"},
        ],
        campos_valores=[
            {"product_id": "PRD-0001", "field_key": "potencia_kw", "valor": "5"},
            {"product_id": "PRD-0001", "field_key": "voltaje_v", "valor": "400"},
            {"product_id": "PRD-0002", "field_key": "diametro_mm", "valor": "20"},
        ],
    )


def test_cada_producto_tiene_sus_propios_campos():
    """Un motor y un rodamiento no comparten especificaciones — ese es el punto."""
    dataset = _dataset_con_esquema()

    motor = [spec.field_key for spec, _ in dataset.product_specs("PRD-0001")]
    bearing = [spec.field_key for spec, _ in dataset.product_specs("PRD-0002")]

    assert motor == ["potencia_kw", "voltaje_v"]
    assert bearing == ["diametro_mm"]
    assert set(motor) & set(bearing) == set()


def test_los_campos_inactivos_no_se_muestran_pero_no_se_borran():
    dataset = _dataset_con_esquema()
    keys = [spec.field_key for spec, _ in dataset.product_specs("PRD-0001")]

    assert "obsoleto" not in keys
    # La fila sigue existiendo en la hoja: retirar no es perder histórico.
    assert any(spec.field_key == "obsoleto" for spec in dataset.field_specs)


def test_los_campos_salen_en_el_orden_declarado():
    dataset = make_dataset(
        productos=[{"product_id": "PRD-0001", "nombre_producto": "Motor", "estado": "Activo"}],
        campos_schema=[
            {"product_id": "PRD-0001", "field_key": "c", "orden": "3", "activo": "Sí"},
            {"product_id": "PRD-0001", "field_key": "a", "orden": "1", "activo": "Sí"},
            {"product_id": "PRD-0001", "field_key": "b", "orden": "2", "activo": "Sí"},
        ],
    )
    assert [spec.field_key for spec, _ in dataset.product_specs("PRD-0001")] == ["a", "b", "c"]


def test_un_campo_sin_valor_aparece_vacio_no_desaparece():
    dataset = make_dataset(
        productos=[{"product_id": "PRD-0001", "nombre_producto": "Motor", "estado": "Activo"}],
        campos_schema=[
            {"product_id": "PRD-0001", "field_key": "rpm", "field_label": "RPM", "orden": "1", "activo": "Sí"}
        ],
    )
    specs = dataset.product_specs("PRD-0001")
    assert len(specs) == 1 and specs[0][1] == ""


def test_la_etiqueta_incluye_la_unidad():
    dataset = _dataset_con_esquema()
    labels = [spec.label for spec, _ in dataset.product_specs("PRD-0001")]
    assert labels == ["Potencia (kW)", "Voltaje (V)"]


def test_activo_vacio_se_considera_activo():
    """Una celda en blanco en una hoja rellenada a mano no debe ocultar el campo."""
    dataset = make_dataset(
        productos=[{"product_id": "PRD-0001", "nombre_producto": "Motor", "estado": "Activo"}],
        campos_schema=[{"product_id": "PRD-0001", "field_key": "rpm", "orden": "1", "activo": ""}],
    )
    assert len(dataset.product_specs("PRD-0001")) == 1


# --- Validación de altas --------------------------------------------------


def test_no_se_puede_crear_un_producto_duplicado():
    dataset = _dataset_con_esquema()
    errors = ProductsService.validate(dataset, nombre_producto="motor 5kw", categoria="Motores")
    assert any("Ya existe" in error for error in errors)


def test_nombre_y_categoria_son_obligatorios():
    errors = ProductsService.validate(make_dataset(), nombre_producto="  ", categoria="")
    assert len(errors) == 2


def test_campos_tecnicos_repetidos_se_detectan():
    errors = ProductsService.validate(
        make_dataset(),
        nombre_producto="Nuevo",
        categoria="Motores",
        technical_fields=(
            TechnicalField(label="Potencia (kW)"),
            TechnicalField(label="potencia kw"),
        ),
    )
    assert any("repetido" in error for error in errors)


# --- Generación de ids ----------------------------------------------------


def test_next_sequential_id_continua_desde_el_maximo():
    assert next_sequential_id("PRD", ["PRD-0001", "PRD-0003"]) == "PRD-0004"


def test_next_sequential_id_ignora_basura_y_otros_prefijos():
    assert next_sequential_id("SUP", ["PRD-0009", "cosa rara", "", "SUP-0002"]) == "SUP-0003"


def test_next_sequential_id_desde_cero():
    assert next_sequential_id("PRD", []) == "PRD-0001"


def test_slugify_field_key_quita_acentos_y_simbolos():
    assert slugify_field_key("Potencia (kW)") == "potencia_kw"
    assert slugify_field_key("Diámetro máximo") == "diametro_maximo"
    assert slugify_field_key("  ") == "campo"


def test_relation_id_es_determinista():
    assert relation_id("SUP-0001", "PRD-0002") == relation_id("sup-0001", "prd-0002")


def test_unique_id_no_colisiona():
    assert len({unique_id("CNV") for _ in range(500)}) == 500
