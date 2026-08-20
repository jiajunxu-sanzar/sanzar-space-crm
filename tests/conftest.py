"""Fixtures y polyfills compartidos por la suite.

Dos cosas que la suite necesita para no depender de la red ni de Streamlit:

1. ``st.dialog`` no existe en todas las versiones instaladas y varias páginas lo
   usan como decorador a nivel de módulo. Se parchea con un no-op antes de
   cualquier import.
2. ``make_dataset`` construye un ``SpaceDataset`` desde diccionarios, así que
   los tests de agregación no tocan Google Sheets.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd
import pytest
import streamlit as st

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

if not hasattr(st, "dialog"):

    def _dialog_polyfill(*_args: object, **_kwargs: object):
        def _decorator(fn):
            return fn

        return _decorator

    st.dialog = _dialog_polyfill  # type: ignore[attr-defined]


from config.settings import (  # noqa: E402
    HISTORICO_CONVERSACIONES_HEADERS,
    HISTORICO_PRECIOS_HEADERS,
    PRODUCTOS_CAMPOS_SCHEMA_HEADERS,
    PRODUCTOS_CAMPOS_VALORES_HEADERS,
    PRODUCTOS_HEADERS,
    SUMINISTRADOR_PRODUCTO_HEADERS,
    SUMINISTRADORES_HEADERS,
    USUARIOS_HEADERS,
)
from services.dataset import SpaceDataset  # noqa: E402


def _frame(rows: list[dict] | None, headers: tuple[str, ...]) -> pd.DataFrame:
    frame = pd.DataFrame(rows or [], columns=list(headers))
    for header in headers:
        if header not in frame.columns:
            frame[header] = ""
    return frame.fillna("").astype(str)


def make_dataset(
    *,
    productos: list[dict] | None = None,
    suministradores: list[dict] | None = None,
    relaciones: list[dict] | None = None,
    conversaciones: list[dict] | None = None,
    precios: list[dict] | None = None,
    campos_schema: list[dict] | None = None,
    campos_valores: list[dict] | None = None,
    usuarios: list[dict] | None = None,
) -> SpaceDataset:
    """``SpaceDataset`` en memoria a partir de filas sueltas."""
    return SpaceDataset(
        productos=_frame(productos, PRODUCTOS_HEADERS),
        campos_schema=_frame(campos_schema, PRODUCTOS_CAMPOS_SCHEMA_HEADERS),
        campos_valores=_frame(campos_valores, PRODUCTOS_CAMPOS_VALORES_HEADERS),
        suministradores=_frame(suministradores, SUMINISTRADORES_HEADERS),
        relaciones=_frame(relaciones, SUMINISTRADOR_PRODUCTO_HEADERS),
        conversaciones=_frame(conversaciones, HISTORICO_CONVERSACIONES_HEADERS),
        precios=_frame(precios, HISTORICO_PRECIOS_HEADERS),
        usuarios=_frame(usuarios, USUARIOS_HEADERS),
    )


@pytest.fixture
def dataset_factory():
    return make_dataset
