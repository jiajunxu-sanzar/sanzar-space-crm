"""Configuración y esquema de datos — única fuente de verdad del proyecto.

Los nombres de pestaña y sus cabeceras NO son variables de entorno: van fijos
aquí como constantes (igual que ``INVENTORY_WORKSHEET_NAME`` o
``COMPRAS_WORKSHEET_NAME`` en ``sanzar-crm-web``) porque no cambian entre
entornos. Lo único que cambia por entorno es el ``GOOGLE_SHEET_ID`` y las
credenciales.

Añadir una columna nueva a una hoja = añadirla a la tupla ``*_HEADERS``. El
bootstrap de ``services/schema.py`` la creará en la hoja real la próxima vez
que arranque la app, sin migraciones manuales.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Final

from app.secrets import get_bool_secret, get_int_secret, get_secret

PROJECT_ROOT: Final[Path] = Path(__file__).resolve().parents[1]

APP_NAME: Final[str] = "Sanzar Space CRM"
APP_TAGLINE: Final[str] = "Suministradores"


def normalize_google_sheet_id(raw: str) -> str:
    """Acepta el ID pelado o el link completo de Google Sheets y devuelve el ID."""
    value = (raw or "").strip().strip('"').strip("'")
    if "docs.google.com" in value and "/d/" in value:
        start = value.index("/d/") + 3
        tail = value[start:]
        return tail.split("/")[0].split("?")[0].strip()
    return value


# ---------------------------------------------------------------------------
# Nombres de pestaña
# ---------------------------------------------------------------------------

INDICE_WORKSHEET_NAME: Final[str] = "Indice"
PRODUCTOS_WORKSHEET_NAME: Final[str] = "Productos"
PRODUCTOS_CAMPOS_SCHEMA_WORKSHEET_NAME: Final[str] = "ProductosCamposSchema"
PRODUCTOS_CAMPOS_VALORES_WORKSHEET_NAME: Final[str] = "ProductosCamposValores"
SUMINISTRADORES_WORKSHEET_NAME: Final[str] = "Suministradores"
SUMINISTRADOR_PRODUCTO_WORKSHEET_NAME: Final[str] = "SuministradorProducto"
HISTORICO_CONVERSACIONES_WORKSHEET_NAME: Final[str] = "HistoricoConversaciones"
HISTORICO_PRECIOS_WORKSHEET_NAME: Final[str] = "HistoricoPrecios"
USUARIOS_WORKSHEET_NAME: Final[str] = "Usuarios"

# Reservadas para cuando se activen las páginas placeholder (§3.4 / §3.5).
COMPRAS_WORKSHEET_NAME: Final[str] = "Compras"
OFERTAS_ENVIADAS_WORKSHEET_NAME: Final[str] = "OfertasEnviadas"


# ---------------------------------------------------------------------------
# Cabeceras por hoja (§5 de la especificación)
# ---------------------------------------------------------------------------

INDICE_HEADERS: Final[tuple[str, ...]] = (
    "hoja",
    "que_guarda",
    "tipo",
    "notas",
)

PRODUCTOS_HEADERS: Final[tuple[str, ...]] = (
    "product_id",
    "nombre_producto",
    "categoria",
    "descripcion",
    "definido_por",
    "fecha_definicion",
    "link_carpeta",
    "notas",
    "estado",
    "created_at",
    "updated_at",
)

PRODUCTOS_CAMPOS_SCHEMA_HEADERS: Final[tuple[str, ...]] = (
    "product_id",
    "field_key",
    "field_label",
    "field_type",
    "unidad",
    "orden",
    "activo",
    "notas",
)

PRODUCTOS_CAMPOS_VALORES_HEADERS: Final[tuple[str, ...]] = (
    "product_id",
    "field_key",
    "valor",
    "actualizado_por",
    "updated_at",
)

SUMINISTRADORES_HEADERS: Final[tuple[str, ...]] = (
    "supplier_id",
    "nombre_suministrador",
    "pais",
    "web",
    "contacto_principal",
    "cargo_contacto_principal",
    "telefono_principal",
    "contacto_secundario",
    "cargo_contacto_secundario",
    "telefono_secundario",
    "email",
    "direccion",
    "notas_generales",
    "created_at",
    "updated_at",
)

SUMINISTRADOR_PRODUCTO_HEADERS: Final[tuple[str, ...]] = (
    "rel_id",
    "supplier_id",
    "product_id",
    "estado",
    "razon_descarte",
    "fecha_alta",
    "responsable_relacion",
    "created_at",
    "updated_at",
)

HISTORICO_CONVERSACIONES_HEADERS: Final[tuple[str, ...]] = (
    "historial_conversacion_id",
    "supplier_id",
    "product_id",
    "tipo_conversacion",
    "fecha_contacto",
    "hora_contacto",
    "persona_contacto",
    "resumen",
    "proxima_accion_detalle",
    "proxima_accion_fecha",
    "proxima_accion_persona",
    "estado_accion",
    "created_at",
    "updated_at",
)

HISTORICO_PRECIOS_HEADERS: Final[tuple[str, ...]] = (
    "historial_precio_id",
    "supplier_id",
    "product_id",
    "fecha_oferta",
    "precio",
    "moneda",
    "unidad_medida",
    "cantidad_minima",
    "condiciones",
    "validez_oferta_fecha",
    "link_catalogo",
    "registrado_por",
    "notas",
    "created_at",
    "updated_at",
)

USUARIOS_HEADERS: Final[tuple[str, ...]] = (
    "employee_id",
    "nombre",
    "rol",
    "activo",
    "password",
    "notas",
)


# Registro pestaña -> cabeceras. Lo consume ``services/schema.py`` (bootstrap
# auto-reparable) y ``app/cache.py`` (lectura batch de todo el Excel).
WORKSHEET_HEADERS: Final[dict[str, tuple[str, ...]]] = {
    PRODUCTOS_WORKSHEET_NAME: PRODUCTOS_HEADERS,
    PRODUCTOS_CAMPOS_SCHEMA_WORKSHEET_NAME: PRODUCTOS_CAMPOS_SCHEMA_HEADERS,
    PRODUCTOS_CAMPOS_VALORES_WORKSHEET_NAME: PRODUCTOS_CAMPOS_VALORES_HEADERS,
    SUMINISTRADORES_WORKSHEET_NAME: SUMINISTRADORES_HEADERS,
    SUMINISTRADOR_PRODUCTO_WORKSHEET_NAME: SUMINISTRADOR_PRODUCTO_HEADERS,
    HISTORICO_CONVERSACIONES_WORKSHEET_NAME: HISTORICO_CONVERSACIONES_HEADERS,
    HISTORICO_PRECIOS_WORKSHEET_NAME: HISTORICO_PRECIOS_HEADERS,
    USUARIOS_WORKSHEET_NAME: USUARIOS_HEADERS,
}

# Orden de lectura en el ``values.batchGet`` (una sola llamada API por refresco).
WORKSHEET_NAMES: Final[tuple[str, ...]] = tuple(WORKSHEET_HEADERS.keys())

# Documentación embebida en la propia hoja `Indice` (§4).
INDICE_ROWS: Final[tuple[tuple[str, str, str], ...]] = (
    (PRODUCTOS_WORKSHEET_NAME, "Un producto = una fila: identidad, descripción, quién lo definió, carpeta de referencia", "Maestro"),
    (PRODUCTOS_CAMPOS_SCHEMA_WORKSHEET_NAME, "Qué campos técnicos tiene cada producto (motores → potencia_kw; bearings → diámetro)", "Esquema dinámico"),
    (PRODUCTOS_CAMPOS_VALORES_WORKSHEET_NAME, "El valor de cada campo técnico, para cada producto", "Datos (EAV)"),
    (SUMINISTRADORES_WORKSHEET_NAME, "Un suministrador = una fila: identidad y contacto, independiente del producto", "Maestro"),
    (SUMINISTRADOR_PRODUCTO_WORKSHEET_NAME, "Relación N:M — qué suministradores sirven qué producto, y en qué estado", "Relación"),
    (HISTORICO_CONVERSACIONES_WORKSHEET_NAME, "Cada contacto (email/reunión/llamada/otro) con un suministrador", "Histórico"),
    (HISTORICO_PRECIOS_WORKSHEET_NAME, "Cada precio/oferta recibida de un suministrador para un producto", "Histórico"),
    (USUARIOS_WORKSHEET_NAME, "Personas con acceso a la app y su rol", "Maestro"),
)


# ---------------------------------------------------------------------------
# Listas de valores cerradas (§5)
# ---------------------------------------------------------------------------

PRODUCTO_ESTADO_ACTIVO: Final[str] = "Activo"
PRODUCTO_ESTADO_DESCONTINUADO: Final[str] = "Descontinuado"
PRODUCTO_ESTADO_OPCIONES: Final[tuple[str, ...]] = (
    PRODUCTO_ESTADO_ACTIVO,
    PRODUCTO_ESTADO_DESCONTINUADO,
)

# Categorías conocidas hoy. Lista ABIERTA: la UI ofrece estas y permite escribir
# una nueva, y el catálogo real se recalcula desde la hoja `Productos`.
CATEGORIA_PRODUCTO_SUGERENCIAS: Final[tuple[str, ...]] = (
    "Motores",
    "Slip Ring",
    "Bearing",
)

FIELD_TYPE_TEXTO: Final[str] = "texto"
FIELD_TYPE_NUMERO: Final[str] = "numero"
FIELD_TYPE_FECHA: Final[str] = "fecha"
FIELD_TYPE_BOOLEANO: Final[str] = "booleano"
FIELD_TYPE_LISTA: Final[str] = "lista"
FIELD_TYPE_OPCIONES: Final[tuple[str, ...]] = (
    FIELD_TYPE_TEXTO,
    FIELD_TYPE_NUMERO,
    FIELD_TYPE_FECHA,
    FIELD_TYPE_BOOLEANO,
    FIELD_TYPE_LISTA,
)

SI: Final[str] = "Sí"
NO: Final[str] = "No"
SI_NO_OPCIONES: Final[tuple[str, ...]] = (SI, NO)

REL_ESTADO_POTENCIAL: Final[str] = "Potencial proveedor"
REL_ESTADO_CONFIRMADO: Final[str] = "Proveedor confirmado"
REL_ESTADO_DESCARTADO: Final[str] = "Descartado"
REL_ESTADO_OPCIONES: Final[tuple[str, ...]] = (
    REL_ESTADO_POTENCIAL,
    REL_ESTADO_CONFIRMADO,
    REL_ESTADO_DESCARTADO,
)
# Orden de "calidad" de la relación, de mejor a peor (para ordenar tablas).
REL_ESTADO_ORDER: Final[dict[str, int]] = {
    REL_ESTADO_CONFIRMADO: 0,
    REL_ESTADO_POTENCIAL: 1,
    REL_ESTADO_DESCARTADO: 2,
}

TIPO_CONVERSACION_EMAIL: Final[str] = "Email"
TIPO_CONVERSACION_REUNION: Final[str] = "Reunión"
TIPO_CONVERSACION_LLAMADA: Final[str] = "Llamada"
TIPO_CONVERSACION_OTRO: Final[str] = "Otro"
TIPO_CONVERSACION_OPCIONES: Final[tuple[str, ...]] = (
    TIPO_CONVERSACION_EMAIL,
    TIPO_CONVERSACION_REUNION,
    TIPO_CONVERSACION_LLAMADA,
    TIPO_CONVERSACION_OTRO,
)

ESTADO_ACCION_PENDIENTE: Final[str] = "Pendiente"
ESTADO_ACCION_COMPLETADA: Final[str] = "Completada"
ESTADO_ACCION_OPCIONES: Final[tuple[str, ...]] = (
    ESTADO_ACCION_PENDIENTE,
    ESTADO_ACCION_COMPLETADA,
)

MONEDA_EUR: Final[str] = "EUR"
MONEDA_USD: Final[str] = "USD"
MONEDA_OPCIONES: Final[tuple[str, ...]] = (MONEDA_EUR, MONEDA_USD)
MONEDA_SIMBOLOS: Final[dict[str, str]] = {MONEDA_EUR: "€", MONEDA_USD: "$"}

UNIDAD_MEDIDA_SUGERENCIAS: Final[tuple[str, ...]] = (
    "por unidad",
    "por lote de 10",
    "por lote de 50",
    "por lote de 100",
    "por metro",
    "por kg",
)

# Prefijos de clave primaria legible (`PRD-0001`, `SUP-0007`, …).
PRODUCT_ID_PREFIX: Final[str] = "PRD"
SUPPLIER_ID_PREFIX: Final[str] = "SUP"
REL_ID_PREFIX: Final[str] = "REL"
CONVERSACION_ID_PREFIX: Final[str] = "CNV"
PRECIO_ID_PREFIX: Final[str] = "PRC"
EMPLOYEE_ID_PREFIX: Final[str] = "EMP"

# Fuera del MVP pero ya parametrizado (§6): a los cuántos días sin conversación
# nueva se considera "estancada" una relación `Potencial proveedor`.
REL_ESTADO_STAGNATION_DAYS: Final[dict[str, int]] = {
    REL_ESTADO_POTENCIAL: 30,
    REL_ESTADO_CONFIRMADO: 90,
}


@dataclass(frozen=True)
class AppConfig:
    google_sheet_id: str = normalize_google_sheet_id(get_secret("GOOGLE_SHEET_ID", ""))
    google_service_account_path: str = get_secret(
        "GOOGLE_SERVICE_ACCOUNT_JSON",
        get_secret("GOOGLE_SERVICE_ACCOUNT_PATH", "config/credentials/service_account.json"),
    )
    data_cache_ttl_seconds: int = get_int_secret("DATA_CACHE_TTL_SECONDS", 300)
    remote_sync_poll_seconds: int = get_int_secret("REMOTE_SYNC_POLL_SECONDS", 60)
    smtp_host: str = get_secret("SMTP_HOST", "")
    smtp_port: int = get_int_secret("SMTP_PORT", 587)
    smtp_user: str = get_secret("SMTP_USER", "")
    smtp_password: str = get_secret("SMTP_PASSWORD", "")
    smtp_use_tls: bool = get_bool_secret("SMTP_USE_TLS", True)


CONFIG: Final[AppConfig] = AppConfig()
