"""Capa de caché — el único sitio donde se decide cuándo se va a Google Sheets.

Dos niveles:

- ``@st.cache_resource``: los servicios (objetos con conexión), uno por proceso.
- ``@st.cache_data``: los datos, con TTL y **versión** en ``session_state``.
  Incrementar la versión (``app.state.bump_data_cache``) invalida la entrada sin
  borrar el resto de cachés.

Todo el «Excel» se lee de una vez en ``load_dataset_cached``: una sola llamada
API por refresco, en vez de una por pestaña. Los bloques ``timed(...)`` solo se
ejecutan en cache *miss* (Streamlit cortocircuita el cuerpo en un hit), así que
la telemetría mide latencia real de lectura, no de caché.
"""

from __future__ import annotations

import pandas as pd
import streamlit as st

from app.telemetry import timed
from config.settings import CONFIG, USUARIOS_HEADERS, USUARIOS_WORKSHEET_NAME
from services.conversations_service import ConversationsService
from services.dataset import SpaceDataset
from services.pricing_service import PricingService
from services.products_service import ProductsService
from services.sheets_service import SheetsService
from services.suppliers_service import SuppliersService
from services.users_service import UsersService

_TTL = max(30, int(CONFIG.data_cache_ttl_seconds))


# --- Servicios (uno por proceso) ------------------------------------------


@st.cache_resource(show_spinner=False)
def sheets_service() -> SheetsService:
    return SheetsService()


@st.cache_resource(show_spinner=False)
def products_service() -> ProductsService:
    return ProductsService(sheets_service())


@st.cache_resource(show_spinner=False)
def suppliers_service() -> SuppliersService:
    return SuppliersService(sheets_service())


@st.cache_resource(show_spinner=False)
def conversations_service() -> ConversationsService:
    return ConversationsService(sheets_service())


@st.cache_resource(show_spinner=False)
def pricing_service() -> PricingService:
    return PricingService(sheets_service())


@st.cache_resource(show_spinner=False)
def users_service() -> UsersService:
    return UsersService(sheets_service())


# --- Datos ----------------------------------------------------------------


@st.cache_data(ttl=_TTL, show_spinner=False)
def load_dataset_cached(version: int = 0) -> SpaceDataset:
    """Todas las pestañas en UNA llamada API. ``version`` invalida la entrada."""
    with timed("load_dataset_cached", version=version):
        return SpaceDataset.load(sheets_service())


@st.cache_data(ttl=_TTL, show_spinner=False)
def load_users_frame_cached(version: int = 0) -> pd.DataFrame:
    """Hoja `Usuarios` sola: hace falta ANTES del login, antes del dataset.

    Va cacheada porque se lee en cada rerun para pintar la barra lateral; sin
    caché sería una llamada a la API por cada clic de cada usuario.
    """
    with timed("load_users_frame_cached", version=version):
        return sheets_service().read_worksheet_df(
            USUARIOS_WORKSHEET_NAME, USUARIOS_HEADERS
        )


def load_dataset(version: int = 0) -> SpaceDataset:
    """Como ``load_dataset_cached`` pero degradando a vacío si Sheets falla.

    Que la API esté caída no debe dejar al usuario ante una traza: la app pinta
    su aviso y sigue navegable.
    """
    try:
        return load_dataset_cached(version)
    except Exception as exc:  # noqa: BLE001
        st.session_state["_dataset_error"] = str(exc)
        return SpaceDataset.empty()


def dataset_error() -> str:
    return str(st.session_state.get("_dataset_error", "") or "")


def clear_dataset_error() -> None:
    st.session_state.pop("_dataset_error", None)


def clear_data_cache() -> None:
    """Vacía la caché de datos y suelta la conexión cacheada a la hoja."""
    st.cache_data.clear()
    try:
        sheets_service().invalidate_caches()
    except Exception:  # noqa: BLE001 — limpiar caché nunca debe romper la app
        pass
