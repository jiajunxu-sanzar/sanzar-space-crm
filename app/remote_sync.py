"""Detección de cambios hechos directamente en el Excel.

Alguien puede editar la hoja a mano mientras la app está abierta. En vez de
releer todo en cada rerun (caro y derrochador de cuota), se consulta el
``modifiedTime`` del fichero en **Drive**, que no consume cuota de la Sheets
API, como mucho una vez cada ``REMOTE_SYNC_POLL_SECONDS``.

Si el timestamp cambió, se invalidan las cachés de datos y la siguiente lectura
vuelve a Sheets.
"""

from __future__ import annotations

import time

import streamlit as st

from app.cache import sheets_service
from config.settings import CONFIG

_LAST_POLL_KEY = "_remote_sync_last_poll_ts"
_LAST_MODIFIED_KEY = "_remote_sync_last_modified"
_FAILURES_KEY = "_remote_sync_failures"

# Tras varios fallos seguidos se deja de sondear en esta sesión: si Drive no
# responde, insistir en cada rerun solo añade latencia a cada interacción.
_MAX_CONSECUTIVE_FAILURES = 3


def reset_remote_sync_state() -> None:
    for key in (_LAST_POLL_KEY, _LAST_MODIFIED_KEY, _FAILURES_KEY):
        st.session_state.pop(key, None)


def check_remote_changes() -> bool:
    """True si el Excel cambió desde la última comprobación (e invalida cachés)."""
    poll_seconds = int(CONFIG.remote_sync_poll_seconds or 0)
    if poll_seconds <= 0 or not CONFIG.google_sheet_id:
        return False
    if int(st.session_state.get(_FAILURES_KEY, 0)) >= _MAX_CONSECUTIVE_FAILURES:
        return False

    now = time.monotonic()
    last_poll = float(st.session_state.get(_LAST_POLL_KEY, 0.0))
    if last_poll and (now - last_poll) < poll_seconds:
        return False
    st.session_state[_LAST_POLL_KEY] = now

    try:
        modified = sheets_service().get_modified_time()
    except Exception:  # noqa: BLE001 — el poll es accesorio, nunca bloquea
        st.session_state[_FAILURES_KEY] = int(st.session_state.get(_FAILURES_KEY, 0)) + 1
        return False

    st.session_state[_FAILURES_KEY] = 0
    previous = str(st.session_state.get(_LAST_MODIFIED_KEY, "") or "")
    st.session_state[_LAST_MODIFIED_KEY] = modified

    # La primera lectura solo establece la línea base: no es un cambio.
    if not previous or not modified or previous == modified:
        return False

    from app.state import soft_reload_data

    soft_reload_data()
    return True
