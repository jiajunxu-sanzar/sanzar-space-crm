"""Telemetría ligera: mide latencia real de operaciones caras (Sheets).

Idéntico en espíritu a ``app/telemetry.py`` de ``sanzar-crm-web``. La
telemetría es accesoria: nunca debe romper la lógica de negocio, por eso el
buffer degrada a una lista efímera si no hay ``session_state``.
"""

from __future__ import annotations

import logging
import time
from contextlib import contextmanager
from dataclasses import asdict, dataclass
from typing import Any, Iterator

import streamlit as st

logger = logging.getLogger("sanzar.crm.space")

_MAX_EVENTS = 400


@dataclass(frozen=True)
class TelemetryEvent:
    name: str
    duration_ms: int
    success: bool
    metadata: dict[str, Any]


def _events_buffer() -> list[dict[str, Any]]:
    try:
        buffer = st.session_state["telemetry_events"]
        if isinstance(buffer, list):
            return buffer
    except (KeyError, AttributeError):
        pass
    try:
        st.session_state["telemetry_events"] = []
        return st.session_state["telemetry_events"]
    except Exception:
        return []


def track_event(name: str, duration_ms: int, success: bool, **metadata: Any) -> None:
    event = TelemetryEvent(
        name=name,
        duration_ms=max(0, int(duration_ms)),
        success=bool(success),
        metadata=metadata,
    )
    buffer = _events_buffer()
    buffer.append(asdict(event))
    # Cota superior: una sesión larga no debe crecer sin límite en memoria.
    if len(buffer) > _MAX_EVENTS:
        del buffer[: len(buffer) - _MAX_EVENTS]
    logger.info("telemetry_event=%s", asdict(event))


@contextmanager
def timed(name: str, **metadata: Any) -> Iterator[None]:
    started_at = time.perf_counter()
    success = True
    try:
        yield
    except Exception:
        success = False
        raise
    finally:
        elapsed_ms = int((time.perf_counter() - started_at) * 1000)
        track_event(name, elapsed_ms, success, **metadata)


def recent_events(limit: int = 25) -> list[dict[str, Any]]:
    """Últimos eventos registrados (diagnóstico en la propia app)."""
    return list(_events_buffer())[-max(1, int(limit)) :]
