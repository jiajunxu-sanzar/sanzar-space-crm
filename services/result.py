"""Resultado uniforme de toda operación de escritura.

Las páginas nunca capturan excepciones de gspread: llaman a un servicio y
reciben un ``WriteResult``. Así el manejo de errores es idéntico en toda la app
y un fallo de red se ve como un mensaje, no como una traza de Streamlit.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True, slots=True)
class WriteResult:
    ok: bool
    message: str = ""
    entity_id: str = ""
    errors: tuple[str, ...] = ()
    data: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def success(cls, message: str, *, entity_id: str = "", **data: Any) -> "WriteResult":
        return cls(ok=True, message=message, entity_id=entity_id, data=data)

    @classmethod
    def failure(cls, *errors: str) -> "WriteResult":
        clean = tuple(error for error in errors if error)
        return cls(ok=False, message=clean[0] if clean else "Operación no válida.", errors=clean)

    @classmethod
    def from_exception(cls, exc: BaseException, *, action: str = "guardar") -> "WriteResult":
        return cls(ok=False, message=f"No se pudo {action}: {exc}", errors=(str(exc),))

    def __bool__(self) -> bool:
        return self.ok
