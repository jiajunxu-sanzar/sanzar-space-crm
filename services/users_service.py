"""Usuarios de la app y sus roles (hoja `Usuarios`, propia de este CRM).

Hoja independiente de la `Usuarios CRM` de ``sanzar-crm-web``: este proyecto es
aparte, con su propio Google Sheet y su propio proyecto de Google Cloud. Si en
el futuro se decide compartir el alta de personal, basta apuntar
``USUARIOS_WORKSHEET_NAME`` a la otra hoja y mapear los roles.
"""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from app.navigation import (
    ROLE_ADMIN,
    ROLE_COMERCIAL,
    ROLE_COMPRADOR,
    KNOWN_APP_ROLES,
    normalize_role,
)
from config.settings import (
    EMPLOYEE_ID_PREFIX,
    NO,
    SI,
    USUARIOS_HEADERS,
    USUARIOS_WORKSHEET_NAME,
)
from services.ids import next_sequential_id
from services.result import WriteResult
from services.sheet_date_format import timestamp_now
from services.sheets_service import SheetsService

# Contraseña de arranque. Solo se usa al sembrar la hoja por primera vez; a
# partir de ahí manda lo que haya en `Usuarios`.
_BOOTSTRAP_PASSWORD = "2026"


@dataclass(frozen=True, slots=True)
class AppUser:
    employee_id: str
    nombre: str
    role: str = ROLE_COMERCIAL
    activo: bool = True
    password: str = ""
    notas: str = ""

    @property
    def initials(self) -> str:
        parts = [part for part in self.nombre.split() if part]
        if not parts:
            return "?"
        if len(parts) == 1:
            return parts[0][:2].upper()
        return (parts[0][0] + parts[-1][0]).upper()

    def to_row(self) -> dict[str, str]:
        return {
            "employee_id": self.employee_id,
            "nombre": self.nombre,
            "rol": self.role,
            "activo": SI if self.activo else NO,
            "password": self.password,
            "notas": self.notas,
        }


def users_from_frame(df: pd.DataFrame) -> tuple[AppUser, ...]:
    """Convierte la hoja `Usuarios` en objetos, descartando filas incompletas."""
    if df is None or df.empty:
        return ()
    out: list[AppUser] = []
    for row in df.fillna("").astype(str).to_dict("records"):
        employee_id = str(row.get("employee_id", "")).strip()
        nombre = str(row.get("nombre", "")).strip()
        if not employee_id or not nombre:
            continue
        activo_raw = str(row.get("activo", SI)).strip().casefold()
        out.append(
            AppUser(
                employee_id=employee_id,
                nombre=nombre,
                role=normalize_role(str(row.get("rol", ""))),
                # Solo un "no" explícito desactiva: una celda vacía en una hoja
                # rellenada a mano no debe dejar a nadie fuera de la app.
                activo=activo_raw not in {"no", "false", "0"},
                password=str(row.get("password", "")).strip(),
                notas=str(row.get("notas", "")).strip(),
            )
        )
    return tuple(out)


def active_users(users: tuple[AppUser, ...]) -> tuple[AppUser, ...]:
    return tuple(user for user in users if user.activo)


def user_names(users: tuple[AppUser, ...], *, only_active: bool = True) -> list[str]:
    """Nombres para los desplegables de «quién hizo / quién hace»."""
    pool = active_users(users) if only_active else users
    return sorted({user.nombre for user in pool if user.nombre}, key=str.casefold)


def person_options(
    users: tuple[AppUser, ...],
    *,
    current: str = "",
    include_blank: bool = True,
) -> list[str]:
    """Opciones de selectbox: plantilla activa + el valor actual si es histórico.

    Sin esto, editar una entrada antigua de alguien que ya no está en la hoja
    borraría silenciosamente su nombre al guardar.
    """
    roster = user_names(users)
    current_clean = str(current or "").strip()
    if current_clean and current_clean not in roster:
        roster = roster + [current_clean]
    return ([""] + roster) if include_blank else roster


def seed_users_if_empty(sheets: SheetsService, df: pd.DataFrame) -> tuple[AppUser, ...]:
    """Siembra un único admin si la hoja está vacía, para poder entrar la 1ª vez.

    Nunca sobrescribe: solo actúa si la hoja se leyó correctamente y no tiene
    ninguna fila. Un fallo de API que devolviera un DataFrame vacío no debe
    resetear las contraseñas de todo el equipo.
    """
    if df is not None and not df.empty:
        return users_from_frame(df)

    # Mismo formato que genera ``next_sequential_id`` (``EMP-001``), para que la
    # columna no acabe mezclando dos convenciones.
    bootstrap = AppUser(
        employee_id=f"{EMPLOYEE_ID_PREFIX}-001",
        nombre="Administrador",
        role=ROLE_ADMIN,
        activo=True,
        password=_BOOTSTRAP_PASSWORD,
        notas=f"Usuario inicial creado automáticamente el {timestamp_now()}. Cambia la contraseña.",
    )
    try:
        sheets.append_row(USUARIOS_WORKSHEET_NAME, USUARIOS_HEADERS, bootstrap.to_row())
    except Exception:  # noqa: BLE001 — sin usuarios la app ya avisa en el login
        return ()
    return (bootstrap,)


class UsersService:
    def __init__(self, sheets: SheetsService) -> None:
        self.sheets = sheets

    @staticmethod
    def validate(
        users: tuple[AppUser, ...],
        *,
        nombre: str,
        rol: str,
        password: str,
        exclude_employee_id: str = "",
    ) -> tuple[str, ...]:
        errors: list[str] = []
        clean_name = (nombre or "").strip()
        if not clean_name:
            errors.append("El nombre es obligatorio.")
        elif any(
            user.nombre.casefold() == clean_name.casefold()
            and user.employee_id != exclude_employee_id
            for user in users
        ):
            errors.append(f"Ya existe un usuario llamado «{clean_name}».")

        if rol not in KNOWN_APP_ROLES:
            errors.append(f"Rol no válido: {rol}. Usa admin, comprador o comercial.")
        if len(str(password or "").strip()) < 4:
            errors.append("La contraseña debe tener al menos 4 caracteres.")
        return tuple(errors)

    def create_user(
        self,
        users: tuple[AppUser, ...],
        *,
        nombre: str,
        rol: str = ROLE_COMPRADOR,
        password: str = "",
        activo: bool = True,
        notas: str = "",
    ) -> WriteResult:
        errors = self.validate(users, nombre=nombre, rol=rol, password=password)
        if errors:
            return WriteResult.failure(*errors)

        user = AppUser(
            employee_id=next_sequential_id(
                EMPLOYEE_ID_PREFIX, (item.employee_id for item in users), width=3
            ),
            nombre=nombre.strip(),
            role=rol,
            activo=activo,
            password=str(password).strip(),
            notas=(notas or "").strip(),
        )
        try:
            self.sheets.append_row(USUARIOS_WORKSHEET_NAME, USUARIOS_HEADERS, user.to_row())
        except Exception as exc:  # noqa: BLE001
            return WriteResult.from_exception(exc, action="crear el usuario")
        return WriteResult.success(
            f"Usuario «{user.nombre}» creado ({user.employee_id}).", entity_id=user.employee_id
        )

    def update_user(
        self,
        users: tuple[AppUser, ...],
        employee_id: str,
        *,
        nombre: str,
        rol: str,
        password: str,
        activo: bool,
        notas: str = "",
    ) -> WriteResult:
        target = str(employee_id or "").strip()
        existing = next((user for user in users if user.employee_id == target), None)
        if existing is None:
            return WriteResult.failure(f"No existe el usuario {employee_id}.")

        errors = self.validate(
            users, nombre=nombre, rol=rol, password=password, exclude_employee_id=target
        )
        if errors:
            return WriteResult.failure(*errors)

        # Nadie debe poder dejar la app sin ningún administrador activo.
        remaining_admins = [
            user
            for user in users
            if user.activo and user.role == ROLE_ADMIN and user.employee_id != target
        ]
        will_be_admin = activo and rol == ROLE_ADMIN
        if not remaining_admins and not will_be_admin:
            return WriteResult.failure(
                "No puedes dejar la app sin ningún administrador activo. "
                "Crea otro admin antes de cambiar este."
            )

        updated = AppUser(
            employee_id=target,
            nombre=nombre.strip(),
            role=rol,
            activo=activo,
            password=str(password).strip(),
            notas=(notas or "").strip(),
        )
        try:
            written = self.sheets.update_row_by_id(
                USUARIOS_WORKSHEET_NAME,
                USUARIOS_HEADERS,
                "employee_id",
                target,
                updated.to_row(),
            )
        except Exception as exc:  # noqa: BLE001
            return WriteResult.from_exception(exc, action="actualizar el usuario")

        if not written:
            return WriteResult.failure("No se encontró la fila en la hoja Usuarios.")
        return WriteResult.success("Usuario actualizado.", entity_id=target)


__all__ = [
    "AppUser",
    "UsersService",
    "active_users",
    "person_options",
    "seed_users_if_empty",
    "user_names",
    "users_from_frame",
    "ROLE_ADMIN",
    "ROLE_COMPRADOR",
    "ROLE_COMERCIAL",
]
