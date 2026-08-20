"""Formularios modales de la página Suministradores.

Todos siguen el mismo contrato:

1. Se abren desde ``ui/modal_state``, nunca desde un flag suelto — así cualquier
   navegación puede cerrarlos todos con una llamada.
2. Validan con el servicio correspondiente **antes** de tocar Sheets y muestran
   todos los errores juntos, no de uno en uno.
3. Al guardar bien: invalidan la caché de datos, dejan un toast y cierran.
"""

from __future__ import annotations

import streamlit as st

from app.cache import (
    conversations_service,
    pricing_service,
    products_service,
    suppliers_service,
)
from app.state import bump_data_cache, select_supplier, set_write_status
from config.settings import (
    CATEGORIA_PRODUCTO_SUGERENCIAS,
    ESTADO_ACCION_COMPLETADA,
    ESTADO_ACCION_PENDIENTE,
    FIELD_TYPE_OPCIONES,
    FIELD_TYPE_TEXTO,
    MONEDA_EUR,
    MONEDA_OPCIONES,
    PRODUCTO_ESTADO_ACTIVO,
    PRODUCTO_ESTADO_OPCIONES,
    REL_ESTADO_DESCARTADO,
    REL_ESTADO_OPCIONES,
    REL_ESTADO_POTENCIAL,
    TIPO_CONVERSACION_OPCIONES,
    UNIDAD_MEDIDA_SUGERENCIAS,
)
from models.history import Conversation, PriceQuote
from models.product import Product
from models.supplier import Supplier
from services.dataset import SpaceDataset
from services.products_service import TechnicalField
from services.result import WriteResult
from services.sheet_date_format import format_date, now_madrid, parse_sheet_date, today_madrid
from services.users_service import AppUser, person_options
from ui import modal_state

# Cuántas filas de campos técnicos ofrece el alta de producto. Cinco cubre los
# casos reales (potencia, voltaje, rpm, diámetro, carga) sin volver el
# formulario intimidante; añadir más se hace luego desde la ficha.
_TECH_FIELD_SLOTS = 5

_SIN_PROXIMA_ACCION = "— Sin próxima acción —"
_ACCION_ESTADO_UI = (_SIN_PROXIMA_ACCION, ESTADO_ACCION_PENDIENTE, ESTADO_ACCION_COMPLETADA)


def _slug(value: str) -> str:
    """Sufijo seguro para keys de widget a partir de un id."""
    return "".join(char if char.isalnum() else "_" for char in str(value or "")).lower()


def _normalize_proxima_accion(
    estado_label: str,
    detalle: str,
    fecha_str: str,
    persona: str,
) -> tuple[str, str, str, str]:
    """Si el usuario elige «sin próxima acción», vacía estado y campos asociados."""
    if estado_label == _SIN_PROXIMA_ACCION:
        return "", "", "", ""
    return (
        str(estado_label or "").strip(),
        str(detalle or "").strip(),
        str(fecha_str or "").strip(),
        str(persona or "").strip(),
    )


def _accion_estado_index(estado: str) -> int:
    if not (estado or "").strip():
        return 0  # Sin próxima acción
    if estado in _ACCION_ESTADO_UI:
        return _ACCION_ESTADO_UI.index(estado)
    return _ACCION_ESTADO_UI.index(ESTADO_ACCION_PENDIENTE)


def _show_errors(result: WriteResult) -> None:
    if len(result.errors) <= 1:
        st.error(result.message)
        return
    st.error("Revisa estos puntos antes de guardar:")
    for error in result.errors:
        st.markdown(f"- {error}")


def _product_options(dataset: SpaceDataset, *, only_active: bool = True) -> dict[str, str]:
    """{etiqueta visible: product_id} para los selectores."""
    products = dataset.active_products() if only_active else dataset.products
    return {product.display_name: product.product_id for product in products}


# ---------------------------------------------------------------------------
# Nuevo suministrador
# ---------------------------------------------------------------------------


@st.dialog("Nuevo suministrador", width="large", on_dismiss=modal_state.close_modal)
def new_supplier_dialog(dataset: SpaceDataset, user: AppUser, users: tuple[AppUser, ...]) -> None:
    products = _product_options(dataset)
    if not products:
        st.warning(
            "Antes de dar de alta un suministrador tiene que existir al menos un producto "
            "activo. Usa «+ Nuevo producto».",
            icon=":material/info:",
        )
        if st.button("Cerrar", key="new_supplier_close_empty"):
            modal_state.close_modal()
            st.rerun()
        return

    with st.form("new_supplier_form", clear_on_submit=False):
        st.markdown("###### Identidad")
        left, right = st.columns(2)
        nombre = left.text_input("Nombre del suministrador *", key="ns_nombre")
        pais = right.text_input("País", key="ns_pais")
        web = left.text_input("Web", key="ns_web", placeholder="https://…")
        email = right.text_input("Email", key="ns_email")
        direccion = st.text_input("Dirección", key="ns_direccion")

        st.markdown("###### Contacto principal")
        c1, c2, c3 = st.columns(3)
        contacto = c1.text_input("Nombre", key="ns_contacto")
        cargo = c2.text_input("Cargo", key="ns_cargo")
        telefono = c3.text_input("Teléfono", key="ns_telefono")

        with st.expander("Contacto secundario (opcional)"):
            s1, s2, s3 = st.columns(3)
            contacto2 = s1.text_input("Nombre", key="ns_contacto2")
            cargo2 = s2.text_input("Cargo", key="ns_cargo2")
            telefono2 = s3.text_input("Teléfono", key="ns_telefono2")

        st.markdown("###### Primer producto y estado")
        p1, p2 = st.columns(2)
        product_label = p1.selectbox("Producto *", list(products.keys()), key="ns_producto")
        estado = p2.selectbox(
            "Estado *",
            REL_ESTADO_OPCIONES,
            index=REL_ESTADO_OPCIONES.index(REL_ESTADO_POTENCIAL),
            key="ns_estado",
        )
        roster = person_options(users, current=user.nombre)
        r1, r2 = st.columns(2)
        responsable = r1.selectbox(
            "Responsable de la relación",
            roster,
            # Por defecto, quien está dando de alta: es quien va a gestionarlo.
            index=roster.index(user.nombre) if user.nombre in roster else 0,
            key="ns_responsable",
        )
        fecha_alta = r2.date_input("Fecha de alta", value=today_madrid(), key="ns_fecha_alta", format="DD/MM/YYYY")
        razon_descarte = st.text_input(
            "Razón de descarte",
            key="ns_razon",
            help="Obligatoria solo si el estado es «Descartado».",
        )

        notas = st.text_area("Notas generales", key="ns_notas", height=80)

        submitted = st.form_submit_button("Crear suministrador", type="primary", width="stretch")

    if not submitted:
        if st.button("Cancelar", key="new_supplier_cancel", type="tertiary"):
            modal_state.close_modal()
            st.rerun()
        return

    result = suppliers_service().create_supplier(
        dataset,
        nombre_suministrador=nombre,
        pais=pais,
        web=web,
        contacto_principal=contacto,
        cargo_contacto_principal=cargo,
        telefono_principal=telefono,
        contacto_secundario=contacto2,
        cargo_contacto_secundario=cargo2,
        telefono_secundario=telefono2,
        email=email,
        direccion=direccion,
        notas_generales=notas,
        product_id=products[product_label],
        estado=estado,
        razon_descarte=razon_descarte,
        responsable_relacion=responsable,
        fecha_alta=format_date(fecha_alta),
    )
    if not result.ok:
        _show_errors(result)
        return

    bump_data_cache()
    set_write_status("success", result.message)
    modal_state.close_modal()
    select_supplier(result.entity_id, navigate=False)
    st.rerun()


# ---------------------------------------------------------------------------
# Nuevo producto (con esquema técnico dinámico)
# ---------------------------------------------------------------------------


@st.dialog("Nuevo producto", width="large", on_dismiss=modal_state.close_modal)
def new_product_dialog(dataset: SpaceDataset, user: AppUser) -> None:
    st.caption(
        "Los campos técnicos son libres: cada producto define los suyos. No hace falta "
        "tocar la estructura de la hoja ni el código para añadir uno nuevo."
    )

    known = list(dict.fromkeys(list(dataset.categorias) + list(CATEGORIA_PRODUCTO_SUGERENCIAS)))

    with st.form("new_product_form", clear_on_submit=False):
        left, right = st.columns(2)
        nombre = left.text_input("Nombre del producto *", key="np_nombre")
        categoria = right.selectbox(
            "Categoría *",
            known + ["➕ Otra…"],
            key="np_categoria",
            accept_new_options=False,
        )
        categoria_nueva = right.text_input(
            "Nueva categoría",
            key="np_categoria_nueva",
            help="Solo si has elegido «Otra…».",
        )

        descripcion = st.text_area("Descripción", key="np_descripcion", height=80)

        m1, m2, m3 = st.columns(3)
        estado = m1.selectbox(
            "Estado",
            PRODUCTO_ESTADO_OPCIONES,
            index=PRODUCTO_ESTADO_OPCIONES.index(PRODUCTO_ESTADO_ACTIVO),
            key="np_estado",
        )
        fecha = m2.date_input(
            "Fecha de definición", value=today_madrid(), key="np_fecha", format="DD/MM/YYYY"
        )
        definido_por = m3.text_input("Definido por", value=user.nombre, key="np_definido_por")

        link = st.text_input(
            "Carpeta / documento de referencia",
            key="np_link",
            placeholder="https://drive.google.com/…",
        )

        st.markdown("###### Campos técnicos")
        technical: list[TechnicalField] = []
        for index in range(_TECH_FIELD_SLOTS):
            f1, f2, f3, f4 = st.columns([2.2, 1.2, 1, 2.2])
            label = f1.text_input(
                "Campo", key=f"np_field_label_{index}", placeholder="Potencia", label_visibility="collapsed" if index else "visible"
            )
            field_type = f2.selectbox(
                "Tipo",
                FIELD_TYPE_OPCIONES,
                index=FIELD_TYPE_OPCIONES.index(FIELD_TYPE_TEXTO),
                key=f"np_field_type_{index}",
                label_visibility="collapsed" if index else "visible",
            )
            unidad = f3.text_input(
                "Unidad", key=f"np_field_unit_{index}", placeholder="kW", label_visibility="collapsed" if index else "visible"
            )
            valor = f4.text_input(
                "Valor", key=f"np_field_value_{index}", placeholder="7,5", label_visibility="collapsed" if index else "visible"
            )
            if label.strip():
                technical.append(
                    TechnicalField(label=label, valor=valor, field_type=field_type, unidad=unidad)
                )

        notas = st.text_area("Notas", key="np_notas", height=70)
        submitted = st.form_submit_button("Crear producto", type="primary", width="stretch")

    if not submitted:
        if st.button("Cancelar", key="new_product_cancel", type="tertiary"):
            modal_state.close_modal()
            st.rerun()
        return

    final_categoria = categoria_nueva.strip() if categoria == "➕ Otra…" else categoria
    result = products_service().create_product(
        dataset,
        nombre_producto=nombre,
        categoria=final_categoria,
        descripcion=descripcion,
        definido_por=definido_por,
        fecha_definicion=format_date(fecha),
        link_carpeta=link,
        notas=notas,
        estado=estado,
        technical_fields=tuple(technical),
    )
    if not result.ok:
        _show_errors(result)
        return

    bump_data_cache()
    set_write_status("success", result.message)
    modal_state.close_modal()
    st.rerun()


# ---------------------------------------------------------------------------
# Editar producto (ficha + nuevos campos técnicos)
# ---------------------------------------------------------------------------


@st.dialog("Editar producto", width="large", on_dismiss=modal_state.close_modal)
def edit_product_dialog(dataset: SpaceDataset, product: Product, user: AppUser) -> None:
    suffix = _slug(product.product_id)
    known = list(dict.fromkeys(list(dataset.categorias) + list(CATEGORIA_PRODUCTO_SUGERENCIAS)))
    if product.categoria and product.categoria not in known:
        known = [product.categoria] + known

    cat_options = known + ["➕ Otra…"]
    cat_index = (
        cat_options.index(product.categoria)
        if product.categoria in cat_options
        else 0
    )
    estado_index = (
        PRODUCTO_ESTADO_OPCIONES.index(product.estado)
        if product.estado in PRODUCTO_ESTADO_OPCIONES
        else PRODUCTO_ESTADO_OPCIONES.index(PRODUCTO_ESTADO_ACTIVO)
    )
    fecha_valor = parse_sheet_date(product.fecha_definicion) or today_madrid()

    existing_specs = dataset.product_specs(product.product_id)
    if existing_specs:
        st.markdown("###### Campos técnicos actuales")
        for spec, value in existing_specs:
            st.caption(f"{spec.label}: {value or '—'}")

    with st.form(f"edit_product_form_{suffix}", clear_on_submit=False):
        left, right = st.columns(2)
        nombre = left.text_input(
            "Nombre del producto *", value=product.nombre_producto, key=f"ep_nombre_{suffix}"
        )
        categoria = right.selectbox(
            "Categoría *",
            cat_options,
            index=cat_index,
            key=f"ep_categoria_{suffix}",
            accept_new_options=False,
        )
        categoria_nueva = right.text_input(
            "Nueva categoría",
            key=f"ep_categoria_nueva_{suffix}",
            help="Solo si has elegido «Otra…».",
        )

        descripcion = st.text_area(
            "Descripción", value=product.descripcion, key=f"ep_descripcion_{suffix}", height=80
        )

        m1, m2, m3 = st.columns(3)
        estado = m1.selectbox(
            "Estado",
            PRODUCTO_ESTADO_OPCIONES,
            index=estado_index,
            key=f"ep_estado_{suffix}",
        )
        fecha = m2.date_input(
            "Fecha de definición",
            value=fecha_valor,
            key=f"ep_fecha_{suffix}",
            format="DD/MM/YYYY",
        )
        definido_por = m3.text_input(
            "Definido por",
            value=product.definido_por or user.nombre,
            key=f"ep_definido_por_{suffix}",
        )

        link = st.text_input(
            "Carpeta / documento de referencia",
            value=product.link_carpeta,
            key=f"ep_link_{suffix}",
            placeholder="https://drive.google.com/…",
        )
        notas = st.text_area(
            "Notas", value=product.notas, key=f"ep_notas_{suffix}", height=70
        )

        st.markdown("###### Añadir campos técnicos")
        st.caption("Solo se crean las filas con etiqueta rellenada. Los existentes no se tocan aquí.")
        technical: list[TechnicalField] = []
        for index in range(_TECH_FIELD_SLOTS):
            f1, f2, f3, f4 = st.columns([2.2, 1.2, 1, 2.2])
            label = f1.text_input(
                "Campo",
                key=f"ep_field_label_{suffix}_{index}",
                placeholder="Potencia",
                label_visibility="collapsed" if index else "visible",
            )
            field_type = f2.selectbox(
                "Tipo",
                FIELD_TYPE_OPCIONES,
                index=FIELD_TYPE_OPCIONES.index(FIELD_TYPE_TEXTO),
                key=f"ep_field_type_{suffix}_{index}",
                label_visibility="collapsed" if index else "visible",
            )
            unidad = f3.text_input(
                "Unidad",
                key=f"ep_field_unit_{suffix}_{index}",
                placeholder="kW",
                label_visibility="collapsed" if index else "visible",
            )
            valor = f4.text_input(
                "Valor",
                key=f"ep_field_value_{suffix}_{index}",
                placeholder="7,5",
                label_visibility="collapsed" if index else "visible",
            )
            if label.strip():
                technical.append(
                    TechnicalField(label=label, valor=valor, field_type=field_type, unidad=unidad)
                )

        submitted = st.form_submit_button("Guardar cambios", type="primary", width="stretch")

    if not submitted:
        if st.button("Cancelar", key=f"edit_product_cancel_{suffix}", type="tertiary"):
            modal_state.close_modal()
            st.rerun()
        return

    final_categoria = categoria_nueva.strip() if categoria == "➕ Otra…" else categoria
    result = products_service().update_product(
        dataset,
        product.product_id,
        {
            "nombre_producto": nombre,
            "categoria": final_categoria,
            "descripcion": descripcion,
            "definido_por": definido_por,
            "fecha_definicion": format_date(fecha),
            "link_carpeta": link,
            "notas": notas,
            "estado": estado,
        },
    )
    if not result.ok:
        _show_errors(result)
        return

    tech_message = ""
    if technical:
        tech_result = products_service().add_technical_fields(
            dataset,
            product.product_id,
            tuple(technical),
            actualizado_por=definido_por or user.nombre,
        )
        if not tech_result.ok:
            # La ficha ya se guardó; avisamos del fallo de campos sin revertir.
            _show_errors(tech_result)
            bump_data_cache()
            return
        tech_message = f" {tech_result.message}"

    bump_data_cache()
    set_write_status("success", f"{result.message}{tech_message}".strip())
    modal_state.close_modal()
    st.rerun()


# ---------------------------------------------------------------------------
# Nueva conversación
# ---------------------------------------------------------------------------


@st.dialog("Registrar conversación", width="large", on_dismiss=modal_state.close_modal)
def new_conversation_dialog(
    dataset: SpaceDataset, supplier: Supplier, user: AppUser, users: tuple[AppUser, ...]
) -> None:
    relations = dataset.products_for_supplier(supplier.supplier_id)
    if not relations:
        st.warning(
            "Este suministrador no tiene ningún producto asociado. Asócialo primero en "
            "«Datos generales».",
            icon=":material/info:",
        )
        if st.button("Cerrar", key="new_conv_close_empty"):
            modal_state.close_modal()
            st.rerun()
        return

    options = {dataset.product_name(rel.product_id): rel.product_id for rel in relations}
    roster = person_options(users, current=user.nombre, include_blank=False)
    default_person = roster.index(user.nombre) if user.nombre in roster else 0

    with st.form("new_conversation_form", clear_on_submit=False):
        c1, c2 = st.columns(2)
        product_label = c1.selectbox("Producto *", list(options.keys()), key="nc_producto")
        tipo = c2.selectbox("Tipo *", TIPO_CONVERSACION_OPCIONES, key="nc_tipo")

        d1, d2, d3 = st.columns(3)
        fecha = d1.date_input("Fecha *", value=today_madrid(), key="nc_fecha", format="DD/MM/YYYY")
        hora = d2.time_input("Hora", value=now_madrid().time().replace(second=0, microsecond=0), key="nc_hora")
        persona = d3.selectbox("Quién ha hablado *", roster, index=default_person, key="nc_persona")

        resumen = st.text_area(
            "Resumen de lo hablado *",
            key="nc_resumen",
            height=120,
            placeholder="Qué se ha tratado, qué han ofrecido, qué queda abierto…",
        )

        st.markdown("###### Próxima acción")
        a1, a2, a3 = st.columns([2.4, 1.1, 1.5])
        detalle = a1.text_input("Qué hay que hacer", key="nc_accion_detalle")
        accion_fecha = a2.date_input(
            "Fecha", value=None, key="nc_accion_fecha", format="DD/MM/YYYY"
        )
        accion_persona = a3.selectbox(
            "Quién la ejecuta",
            person_options(users, current=user.nombre),
            key="nc_accion_persona",
        )
        estado_accion = st.selectbox(
            "Estado de la acción",
            _ACCION_ESTADO_UI,
            index=_ACCION_ESTADO_UI.index(ESTADO_ACCION_PENDIENTE),
            key="nc_estado_accion",
            help="Elige «Sin próxima acción» si esta conversación no deja trabajo pendiente.",
        )

        submitted = st.form_submit_button("Guardar conversación", type="primary", width="stretch")

    if not submitted:
        if st.button("Cancelar", key="new_conv_cancel", type="tertiary"):
            modal_state.close_modal()
            st.rerun()
        return

    estado, detalle, accion_fecha_str, accion_persona = _normalize_proxima_accion(
        estado_accion,
        detalle,
        format_date(accion_fecha),
        accion_persona,
    )

    result = conversations_service().add_conversation(
        dataset,
        supplier_id=supplier.supplier_id,
        product_id=options[product_label],
        tipo_conversacion=tipo,
        fecha_contacto=format_date(fecha),
        hora_contacto=hora.strftime("%H:%M") if hora else "",
        persona_contacto=persona,
        resumen=resumen,
        proxima_accion_detalle=detalle,
        proxima_accion_fecha=accion_fecha_str,
        proxima_accion_persona=accion_persona,
        estado_accion=estado,
    )
    if not result.ok:
        _show_errors(result)
        return

    bump_data_cache()
    set_write_status("success", result.message)
    modal_state.close_modal()
    st.rerun()


# ---------------------------------------------------------------------------
# Nuevo precio
# ---------------------------------------------------------------------------


@st.dialog("Registrar precio", width="large", on_dismiss=modal_state.close_modal)
def new_quote_dialog(
    dataset: SpaceDataset, supplier: Supplier, user: AppUser, users: tuple[AppUser, ...]
) -> None:
    relations = dataset.products_for_supplier(supplier.supplier_id)
    if not relations:
        st.warning(
            "Este suministrador no tiene ningún producto asociado. Asócialo primero en "
            "«Datos generales».",
            icon=":material/info:",
        )
        if st.button("Cerrar", key="new_quote_close_empty"):
            modal_state.close_modal()
            st.rerun()
        return

    options = {dataset.product_name(rel.product_id): rel.product_id for rel in relations}
    roster = person_options(users, current=user.nombre, include_blank=False)

    with st.form("new_quote_form", clear_on_submit=False):
        p1, p2, p3 = st.columns([2, 1.2, 1])
        product_label = p1.selectbox("Producto *", list(options.keys()), key="nq_producto")
        precio = p2.text_input("Precio *", key="nq_precio", placeholder="1.250,00")
        moneda = p3.selectbox(
            "Moneda *", MONEDA_OPCIONES, index=MONEDA_OPCIONES.index(MONEDA_EUR), key="nq_moneda"
        )

        u1, u2, u3 = st.columns(3)
        unidad = u1.selectbox(
            "Unidad de medida",
            [""] + list(UNIDAD_MEDIDA_SUGERENCIAS),
            key="nq_unidad",
            accept_new_options=True,
        )
        moq = u2.text_input("Cantidad mínima (MOQ)", key="nq_moq", placeholder="50")
        fecha = u3.date_input("Fecha de la oferta *", value=today_madrid(), key="nq_fecha", format="DD/MM/YYYY")

        v1, v2 = st.columns(2)
        validez = v1.date_input(
            "Válida hasta", value=None, key="nq_validez", format="DD/MM/YYYY"
        )
        registrado_por = v2.selectbox(
            "Registrado por",
            roster,
            index=roster.index(user.nombre) if user.nombre in roster else 0,
            key="nq_registrado",
        )

        condiciones = st.text_area(
            "Condiciones",
            key="nq_condiciones",
            height=80,
            placeholder="Plazo de entrega, incoterm, forma de pago…",
        )
        link = st.text_input(
            "Catálogo / carpeta de referencia", key="nq_link", placeholder="https://…"
        )
        notas = st.text_area("Notas", key="nq_notas", height=70)

        submitted = st.form_submit_button("Guardar precio", type="primary", width="stretch")

    if not submitted:
        if st.button("Cancelar", key="new_quote_cancel", type="tertiary"):
            modal_state.close_modal()
            st.rerun()
        return

    result = pricing_service().add_quote(
        dataset,
        supplier_id=supplier.supplier_id,
        product_id=options[product_label],
        precio=precio,
        moneda=moneda,
        fecha_oferta=format_date(fecha),
        unidad_medida=unidad,
        cantidad_minima=moq,
        condiciones=condiciones,
        validez_oferta_fecha=format_date(validez),
        link_catalogo=link,
        registrado_por=registrado_por,
        notas=notas,
    )
    if not result.ok:
        _show_errors(result)
        return

    bump_data_cache()
    set_write_status("success", result.message)
    modal_state.close_modal()
    st.rerun()


# ---------------------------------------------------------------------------
# Asociar producto / cambiar estado de una relación
# ---------------------------------------------------------------------------


@st.dialog("Asociar producto", on_dismiss=modal_state.close_modal)
def add_relation_dialog(
    dataset: SpaceDataset, supplier: Supplier, user: AppUser, users: tuple[AppUser, ...]
) -> None:
    taken = {rel.product_id for rel in dataset.products_for_supplier(supplier.supplier_id)}
    available = {
        product.display_name: product.product_id
        for product in dataset.active_products()
        if product.product_id not in taken
    }
    if not available:
        st.info("Este suministrador ya está asociado a todos los productos activos.")
        if st.button("Cerrar", key="add_rel_close"):
            modal_state.close_modal()
            st.rerun()
        return

    with st.form("add_relation_form"):
        product_label = st.selectbox("Producto *", list(available.keys()), key="ar_producto")
        estado = st.selectbox(
            "Estado *",
            REL_ESTADO_OPCIONES,
            index=REL_ESTADO_OPCIONES.index(REL_ESTADO_POTENCIAL),
            key="ar_estado",
        )
        razon = st.text_input("Razón de descarte", key="ar_razon")
        responsable = st.selectbox(
            "Responsable", person_options(users, current=user.nombre), key="ar_responsable"
        )
        submitted = st.form_submit_button("Asociar", type="primary", width="stretch")

    if not submitted:
        return

    result = suppliers_service().add_relation(
        dataset,
        supplier_id=supplier.supplier_id,
        product_id=available[product_label],
        estado=estado,
        razon_descarte=razon,
        responsable_relacion=responsable,
    )
    if not result.ok:
        _show_errors(result)
        return

    bump_data_cache()
    set_write_status("success", result.message)
    modal_state.close_modal()
    st.rerun()


@st.dialog("Cambiar estado de la relación", on_dismiss=modal_state.close_modal)
def edit_relation_dialog(
    dataset: SpaceDataset, supplier: Supplier, rel_id: str, users: tuple[AppUser, ...]
) -> None:
    relation = next((rel for rel in dataset.relations if rel.rel_id == rel_id), None)
    if relation is None:
        st.error("Esa relación ya no existe.")
        if st.button("Cerrar", key="edit_rel_close"):
            modal_state.close_modal()
            st.rerun()
        return

    st.caption(f"{supplier.display_name} — {dataset.product_name(relation.product_id)}")

    # Keys por relación: con keys fijas, abrir el estado de una relación y luego
    # el de otra mostraría (y guardaría) el estado de la primera.
    suffix = _slug(relation.rel_id)
    with st.form(f"edit_relation_form_{suffix}"):
        estado = st.selectbox(
            "Estado *",
            REL_ESTADO_OPCIONES,
            index=REL_ESTADO_OPCIONES.index(relation.estado)
            if relation.estado in REL_ESTADO_OPCIONES
            else 0,
            key=f"er_estado_{suffix}",
        )
        razon = st.text_input(
            "Razón de descarte",
            value=relation.razon_descarte,
            key=f"er_razon_{suffix}",
            help="Obligatoria si el estado es «Descartado».",
        )
        roster = person_options(users, current=relation.responsable_relacion)
        responsable = st.selectbox(
            "Responsable",
            roster,
            index=roster.index(relation.responsable_relacion)
            if relation.responsable_relacion in roster
            else 0,
            key=f"er_responsable_{suffix}",
        )
        submitted = st.form_submit_button("Guardar", type="primary", width="stretch")

    if not submitted:
        return

    if estado == REL_ESTADO_DESCARTADO and not razon.strip():
        st.error("Si el estado es «Descartado», la razón de descarte es obligatoria.")
        return

    result = suppliers_service().update_relation(
        dataset,
        rel_id,
        estado=estado,
        razon_descarte=razon,
        responsable_relacion=responsable,
    )
    if not result.ok:
        _show_errors(result)
        return

    bump_data_cache()
    set_write_status("success", result.message)
    modal_state.close_modal()
    st.rerun()


@st.dialog("Editar ficha", width="large", on_dismiss=modal_state.close_modal)
def edit_supplier_dialog(dataset: SpaceDataset, supplier: Supplier) -> None:
    # Keys por suministrador, por el mismo motivo que en el diálogo de relación:
    # con keys fijas, editar una ficha tras otra guardaría los datos de la
    # primera sobre la segunda.
    suffix = _slug(supplier.supplier_id)
    with st.form(f"edit_supplier_form_{suffix}"):
        left, right = st.columns(2)
        nombre = left.text_input("Nombre *", value=supplier.nombre_suministrador, key=f"es_nombre_{suffix}")
        pais = right.text_input("País", value=supplier.pais, key=f"es_pais_{suffix}")
        web = left.text_input("Web", value=supplier.web, key=f"es_web_{suffix}")
        email = right.text_input("Email", value=supplier.email, key=f"es_email_{suffix}")
        direccion = st.text_input("Dirección", value=supplier.direccion, key=f"es_direccion_{suffix}")

        st.markdown("###### Contacto principal")
        c1, c2, c3 = st.columns(3)
        contacto = c1.text_input("Nombre", value=supplier.contacto_principal, key=f"es_contacto_{suffix}")
        cargo = c2.text_input("Cargo", value=supplier.cargo_contacto_principal, key=f"es_cargo_{suffix}")
        telefono = c3.text_input("Teléfono", value=supplier.telefono_principal, key=f"es_telefono_{suffix}")

        st.markdown("###### Contacto secundario")
        s1, s2, s3 = st.columns(3)
        contacto2 = s1.text_input("Nombre", value=supplier.contacto_secundario, key=f"es_contacto2_{suffix}")
        cargo2 = s2.text_input("Cargo", value=supplier.cargo_contacto_secundario, key=f"es_cargo2_{suffix}")
        telefono2 = s3.text_input("Teléfono", value=supplier.telefono_secundario, key=f"es_telefono2_{suffix}")

        notas = st.text_area(
            "Notas generales", value=supplier.notas_generales, key=f"es_notas_{suffix}", height=90
        )
        submitted = st.form_submit_button("Guardar cambios", type="primary", width="stretch")

    if not submitted:
        return

    result = suppliers_service().update_supplier(
        dataset,
        supplier.supplier_id,
        {
            "nombre_suministrador": nombre,
            "pais": pais,
            "web": web,
            "email": email,
            "direccion": direccion,
            "contacto_principal": contacto,
            "cargo_contacto_principal": cargo,
            "telefono_principal": telefono,
            "contacto_secundario": contacto2,
            "cargo_contacto_secundario": cargo2,
            "telefono_secundario": telefono2,
            "notas_generales": notas,
        },
    )
    if not result.ok:
        _show_errors(result)
        return

    bump_data_cache()
    set_write_status("success", result.message)
    modal_state.close_modal()
    st.rerun()


# ---------------------------------------------------------------------------
# Editar conversación / editar precio
# ---------------------------------------------------------------------------


def _parse_hh_mm(raw: str):
    from datetime import datetime, time

    text = (raw or "").strip()
    if not text:
        return now_madrid().time().replace(second=0, microsecond=0)
    try:
        return datetime.strptime(text, "%H:%M").time()
    except ValueError:
        return time(0, 0)


@st.dialog("Editar conversación", width="large", on_dismiss=modal_state.close_modal)
def edit_conversation_dialog(
    dataset: SpaceDataset,
    supplier: Supplier,
    conversation: Conversation,
    user: AppUser,
    users: tuple[AppUser, ...],
) -> None:
    relations = dataset.products_for_supplier(supplier.supplier_id)
    options = {dataset.product_name(rel.product_id): rel.product_id for rel in relations}
    if conversation.product_id in dataset.product_by_id:
        name = dataset.product_name(conversation.product_id)
        if name not in options:
            options = {name: conversation.product_id, **options}
    if not options:
        st.error("No hay productos asociados a este suministrador.")
        if st.button("Cerrar", key="edit_conv_close_empty"):
            modal_state.close_modal()
            st.rerun()
        return

    suffix = _slug(conversation.historial_conversacion_id)
    roster = person_options(users, current=conversation.persona_contacto, include_blank=False)
    product_labels = list(options.keys())
    product_index = 0
    for idx, (label, pid) in enumerate(options.items()):
        if pid == conversation.product_id:
            product_index = idx
            break
    tipo_index = (
        TIPO_CONVERSACION_OPCIONES.index(conversation.tipo_conversacion)
        if conversation.tipo_conversacion in TIPO_CONVERSACION_OPCIONES
        else 0
    )
    person_index = (
        roster.index(conversation.persona_contacto)
        if conversation.persona_contacto in roster
        else 0
    )

    with st.form(f"edit_conversation_form_{suffix}", clear_on_submit=False):
        c1, c2 = st.columns(2)
        product_label = c1.selectbox(
            "Producto *", product_labels, index=product_index, key=f"ec_producto_{suffix}"
        )
        tipo = c2.selectbox(
            "Tipo *", TIPO_CONVERSACION_OPCIONES, index=tipo_index, key=f"ec_tipo_{suffix}"
        )

        d1, d2, d3 = st.columns(3)
        fecha = d1.date_input(
            "Fecha *",
            value=parse_sheet_date(conversation.fecha_contacto) or today_madrid(),
            key=f"ec_fecha_{suffix}",
            format="DD/MM/YYYY",
        )
        hora = d2.time_input(
            "Hora", value=_parse_hh_mm(conversation.hora_contacto), key=f"ec_hora_{suffix}"
        )
        persona = d3.selectbox(
            "Quién ha hablado *", roster, index=person_index, key=f"ec_persona_{suffix}"
        )

        resumen = st.text_area(
            "Resumen de lo hablado *",
            value=conversation.resumen,
            key=f"ec_resumen_{suffix}",
            height=120,
        )

        st.markdown("###### Próxima acción")
        a1, a2, a3 = st.columns([2.4, 1.1, 1.5])
        detalle = a1.text_input(
            "Qué hay que hacer",
            value=conversation.proxima_accion_detalle,
            key=f"ec_accion_detalle_{suffix}",
        )
        accion_fecha = a2.date_input(
            "Fecha",
            value=parse_sheet_date(conversation.proxima_accion_fecha),
            key=f"ec_accion_fecha_{suffix}",
            format="DD/MM/YYYY",
        )
        accion_roster = person_options(users, current=conversation.proxima_accion_persona)
        accion_persona_index = (
            accion_roster.index(conversation.proxima_accion_persona)
            if conversation.proxima_accion_persona in accion_roster
            else 0
        )
        accion_persona = a3.selectbox(
            "Quién la ejecuta",
            accion_roster,
            index=accion_persona_index,
            key=f"ec_accion_persona_{suffix}",
        )
        estado_accion = st.selectbox(
            "Estado de la acción",
            _ACCION_ESTADO_UI,
            index=_accion_estado_index(conversation.estado_accion),
            key=f"ec_estado_accion_{suffix}",
            help="Completada cierra la acción; «Sin próxima acción» la elimina del bandeja.",
        )

        submitted = st.form_submit_button("Guardar cambios", type="primary", width="stretch")

    if not submitted:
        if st.button("Cancelar", key=f"edit_conv_cancel_{suffix}", type="tertiary"):
            modal_state.close_modal()
            st.rerun()
        return

    # el valor del select tal cual.
    estado, detalle, accion_fecha_str, accion_persona = _normalize_proxima_accion(
        estado_accion,
        detalle,
        format_date(accion_fecha),
        accion_persona,
    )

    result = conversations_service().update_conversation(
        dataset,
        conversation.historial_conversacion_id,
        {
            "product_id": options[product_label],
            "tipo_conversacion": tipo,
            "fecha_contacto": format_date(fecha),
            "hora_contacto": hora.strftime("%H:%M") if hora else "",
            "persona_contacto": persona,
            "resumen": resumen,
            "proxima_accion_detalle": detalle,
            "proxima_accion_fecha": accion_fecha_str,
            "proxima_accion_persona": accion_persona,
            "estado_accion": estado,
        },
    )
    if not result.ok:
        _show_errors(result)
        return

    bump_data_cache()
    set_write_status("success", result.message)
    modal_state.close_modal()
    st.rerun()


@st.dialog("Editar precio", width="large", on_dismiss=modal_state.close_modal)
def edit_quote_dialog(
    dataset: SpaceDataset,
    supplier: Supplier,
    quote: PriceQuote,
    user: AppUser,
    users: tuple[AppUser, ...],
) -> None:
    del user
    relations = dataset.products_for_supplier(supplier.supplier_id)
    options = {dataset.product_name(rel.product_id): rel.product_id for rel in relations}
    if quote.product_id in dataset.product_by_id:
        name = dataset.product_name(quote.product_id)
        if name not in options:
            options = {name: quote.product_id, **options}
    if not options:
        st.error("No hay productos asociados a este suministrador.")
        if st.button("Cerrar", key="edit_quote_close_empty"):
            modal_state.close_modal()
            st.rerun()
        return

    suffix = _slug(quote.historial_precio_id)
    roster = person_options(users, current=quote.registrado_por, include_blank=False)
    product_labels = list(options.keys())
    product_index = 0
    for idx, (label, pid) in enumerate(options.items()):
        if pid == quote.product_id:
            product_index = idx
            break
    moneda_index = (
        MONEDA_OPCIONES.index(quote.moneda)
        if quote.moneda in MONEDA_OPCIONES
        else MONEDA_OPCIONES.index(MONEDA_EUR)
    )
    unidad_options = [""] + list(UNIDAD_MEDIDA_SUGERENCIAS)
    if quote.unidad_medida and quote.unidad_medida not in unidad_options:
        unidad_options.append(quote.unidad_medida)

    with st.form(f"edit_quote_form_{suffix}", clear_on_submit=False):
        p1, p2, p3 = st.columns([2, 1.2, 1])
        product_label = p1.selectbox(
            "Producto *", product_labels, index=product_index, key=f"eq_producto_{suffix}"
        )
        precio = p2.text_input("Precio *", value=quote.precio, key=f"eq_precio_{suffix}")
        moneda = p3.selectbox(
            "Moneda *", MONEDA_OPCIONES, index=moneda_index, key=f"eq_moneda_{suffix}"
        )

        u1, u2, u3 = st.columns(3)
        unidad = u1.selectbox(
            "Unidad de medida",
            unidad_options,
            index=unidad_options.index(quote.unidad_medida)
            if quote.unidad_medida in unidad_options
            else 0,
            key=f"eq_unidad_{suffix}",
            accept_new_options=True,
        )
        moq = u2.text_input(
            "Cantidad mínima (MOQ)", value=quote.cantidad_minima, key=f"eq_moq_{suffix}"
        )
        fecha = u3.date_input(
            "Fecha de la oferta *",
            value=parse_sheet_date(quote.fecha_oferta) or today_madrid(),
            key=f"eq_fecha_{suffix}",
            format="DD/MM/YYYY",
        )

        v1, v2 = st.columns(2)
        validez = v1.date_input(
            "Válida hasta",
            value=parse_sheet_date(quote.validez_oferta_fecha),
            key=f"eq_validez_{suffix}",
            format="DD/MM/YYYY",
        )
        registrado_por = v2.selectbox(
            "Registrado por",
            roster,
            index=roster.index(quote.registrado_por) if quote.registrado_por in roster else 0,
            key=f"eq_registrado_{suffix}",
        )

        condiciones = st.text_area(
            "Condiciones", value=quote.condiciones, key=f"eq_condiciones_{suffix}", height=80
        )
        link = st.text_input(
            "Catálogo / carpeta de referencia",
            value=quote.link_catalogo,
            key=f"eq_link_{suffix}",
        )
        notas = st.text_area("Notas", value=quote.notas, key=f"eq_notas_{suffix}", height=70)

        submitted = st.form_submit_button("Guardar cambios", type="primary", width="stretch")

    if not submitted:
        if st.button("Cancelar", key=f"edit_quote_cancel_{suffix}", type="tertiary"):
            modal_state.close_modal()
            st.rerun()
        return

    result = pricing_service().update_quote(
        dataset,
        quote.historial_precio_id,
        {
            "product_id": options[product_label],
            "precio": precio,
            "moneda": moneda,
            "fecha_oferta": format_date(fecha),
            "unidad_medida": unidad,
            "cantidad_minima": moq,
            "condiciones": condiciones,
            "validez_oferta_fecha": format_date(validez),
            "link_catalogo": link,
            "registrado_por": registrado_por,
            "notas": notas,
        },
    )
    if not result.ok:
        _show_errors(result)
        return

    bump_data_cache()
    set_write_status("success", result.message)
    modal_state.close_modal()
    st.rerun()


def render_active_dialog(
    dataset: SpaceDataset, user: AppUser, users: tuple[AppUser, ...]
) -> None:
    """Despacha el modal abierto, si lo hay. Se llama una vez por rerun."""
    modal = modal_state.get_active_modal()
    if not modal:
        return

    kind = modal.get("type", "")
    if kind == "nuevo_suministrador":
        new_supplier_dialog(dataset, user, users)
        return
    if kind == "nuevo_producto":
        new_product_dialog(dataset, user)
        return
    if kind == "editar_producto":
        product = dataset.product_by_id.get(modal_state.field("product_id"))
        if product is None:
            modal_state.close_modal()
            return
        edit_product_dialog(dataset, product, user)
        return

    supplier = dataset.supplier_by_id.get(modal_state.field("supplier_id"))
    if supplier is None:
        # El proveedor desapareció (borrado en la hoja mientras el modal estaba
        # abierto): cerrar es más honesto que pintar un formulario huérfano.
        modal_state.close_modal()
        return

    if kind == "nueva_conversacion":
        new_conversation_dialog(dataset, supplier, user, users)
    elif kind == "nuevo_precio":
        new_quote_dialog(dataset, supplier, user, users)
    elif kind == "nueva_relacion":
        add_relation_dialog(dataset, supplier, user, users)
    elif kind == "editar_relacion":
        edit_relation_dialog(dataset, supplier, modal_state.field("rel_id"), users)
    elif kind == "editar_suministrador":
        edit_supplier_dialog(dataset, supplier)
    elif kind == "editar_conversacion":
        conversation = next(
            (
                item
                for item in dataset.conversations
                if item.historial_conversacion_id == modal_state.field("row_id")
            ),
            None,
        )
        if conversation is None:
            modal_state.close_modal()
            return
        edit_conversation_dialog(dataset, supplier, conversation, user, users)
    elif kind == "editar_precio":
        quote = next(
            (
                item
                for item in dataset.quotes
                if item.historial_precio_id == modal_state.field("row_id")
            ),
            None,
        )
        if quote is None:
            modal_state.close_modal()
            return
        edit_quote_dialog(dataset, supplier, quote, user, users)
