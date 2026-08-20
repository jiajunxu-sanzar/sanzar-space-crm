"""Tema visual de la app: un único ``<style>`` inyectado una vez por rerun.

El CSS se organiza en bloques y se compone a partir de las variables generadas
por ``ui/design_tokens.py``, así que no hay ni un color hardcodeado aquí.

**Reglas de movimiento** (ver DESIGN-space.md § Movimiento, y el manifiesto de
design engineering de Emil Kowalski del que salen):

- Ninguna animación supera 300 ms (aquí, 260 ms como techo).
- Nunca ``ease-in`` en UI; entrar/salir con ``--ui-ease-out``.
- Solo se animan ``transform`` y ``opacity`` — nunca ``width``/``height``/
  ``margin``/``padding``, que fuerzan layout en cada fotograma.
- Nada entra desde ``scale(0)``: se entra desde ``scale(0.97)`` + ``opacity: 0``.
- Nunca ``transition: all``: siempre propiedades explícitas.
- ``:hover`` detrás de ``@media (hover: hover) and (pointer: fine)``.
- ``prefers-reduced-motion`` conserva color y opacidad y elimina movimiento.
- Entradas en grupo escalonadas 40 ms, sin bloquear la interacción.
"""

from __future__ import annotations

from functools import lru_cache

import streamlit as st

from ui.design_tokens import css_variables

_FONT_IMPORT = (
    "@import url('https://fonts.googleapis.com/css2?"
    "family=Inter:wght@400;500;600;700&display=swap');"
)

# --- Chrome de Streamlit --------------------------------------------------

_BASE_CSS = """
body, .stApp { font-family: var(--ui-font) !important; }

/* Ocultar el chrome de Streamlit (Deploy / menú / decoración) manteniendo vivo
   el header: ahí vive el botón » para reabrir el sidebar compactado. */
[data-testid="stDecoration"],
[data-testid="stAppDeployButton"],
[data-testid="stToolbarActions"],
[data-testid="stMainMenu"],
[data-testid="stStatusWidget"] { display: none !important; }
header[data-testid="stHeader"] { background: transparent !important; }

[data-testid="stExpandSidebarButton"] {
  display: flex !important;
  visibility: visible !important;
  opacity: 1 !important;
  pointer-events: auto !important;
  position: fixed !important;
  top: 0.55rem !important;
  left: 0.55rem !important;
  z-index: 1000000 !important;
}
[data-testid="stExpandSidebarButton"] button {
  background: var(--ui-bg-elevated) !important;
  border: 1px solid var(--ui-border) !important;
  border-radius: var(--ui-radius-md) !important;
  color: var(--ui-text) !important;
  box-shadow: 0 1px 3px rgba(15, 23, 42, 0.08) !important;
}

.block-container {
  padding-top: 2rem;
  padding-bottom: 3rem;
  max-width: 1480px;
}
.main .block-container { background: var(--ui-bg-page); }
div[data-testid="stSidebar"] {
  background: var(--ui-sidebar);
  border-right: 1px solid var(--ui-border);
}

h1 { font-weight: 600 !important; letter-spacing: -0.02em; color: var(--ui-text) !important; }
h2, h3, h4 { font-weight: 600 !important; color: var(--ui-text) !important; }
h5 { margin: 0 0 var(--ui-spacing-sm) 0; color: var(--ui-text); font-weight: 600 !important; }
a { color: var(--ui-accent); text-decoration: none; }
a:hover { text-decoration: underline; }
"""

# --- Botones --------------------------------------------------------------

_BUTTONS_CSS = """
/* Propiedades explícitas, nunca `transition: all`. Solo transform/opacity y
   los colores (que sí pueden animarse sin coste de layout). */
.stButton > button {
  transition:
    background-color var(--ui-duration-fast) var(--ui-ease-out),
    border-color var(--ui-duration-fast) var(--ui-ease-out),
    color var(--ui-duration-fast) var(--ui-ease-out),
    transform var(--ui-duration-instant) var(--ui-ease-out);
  will-change: transform;
}
/* Feedback de pulsación: 0.97 es perceptible sin parecer un juguete. */
.stButton > button:active { transform: scale(0.97); }

.stButton > button[kind="primary"],
div[data-testid="stSidebar"] button[kind="primary"] {
  background-color: var(--ui-accent) !important;
  color: var(--ui-accent-contrast) !important;
  border: 1px solid var(--ui-accent) !important;
  border-radius: var(--ui-radius-md) !important;
  font-weight: 550 !important;
}
.stButton > button[kind="secondary"],
.stButton > button[kind="tertiary"] {
  background: var(--ui-bg-elevated) !important;
  color: var(--ui-text) !important;
  border: 1px solid var(--ui-border) !important;
  border-radius: var(--ui-radius-md) !important;
  font-weight: 500 !important;
}
.stButton > button.space-btn-strong {
  background-color: var(--ui-primary-strong) !important;
  color: var(--ui-primary-strong-contrast) !important;
  border: 1px solid var(--ui-primary-strong) !important;
}

/* Botón «+» del catálogo de productos: cuadrado con borde redondeado. */
[class*="st-key-prod_open_"] button {
  min-width: 2.25rem !important;
  min-height: 2.25rem !important;
  width: 2.25rem !important;
  height: 2.25rem !important;
  padding: 0 !important;
  display: inline-flex !important;
  align-items: center !important;
  justify-content: center !important;
  background: var(--ui-bg-elevated) !important;
  border: 1px solid var(--ui-border-strong) !important;
  border-radius: var(--ui-radius-md) !important;
  font-size: 1.125rem !important;
  font-weight: 600 !important;
  line-height: 1 !important;
}

/* Volver (solo flecha) centrado en su recuadro. */
[class*="st-key-prod_back"] button,
[class*="st-key-sup_back"] button {
  min-width: 2.25rem !important;
  min-height: 2.25rem !important;
  width: 2.25rem !important;
  height: 2.25rem !important;
  padding: 0 !important;
  display: inline-flex !important;
  align-items: center !important;
  justify-content: center !important;
  margin-left: auto !important;
  margin-right: auto !important;
  background: var(--ui-bg-elevated) !important;
  border: 1px solid var(--ui-border-strong) !important;
  border-radius: var(--ui-radius-md) !important;
}

/* Lápiz de editar histórico. */
[class*="st-key-hist_edit_"] button {
  min-width: 2.25rem !important;
  min-height: 2.25rem !important;
  width: 2.25rem !important;
  height: 2.25rem !important;
  padding: 0 !important;
  display: inline-flex !important;
  align-items: center !important;
  justify-content: center !important;
  background: var(--ui-bg-elevated) !important;
  border: 1px solid var(--ui-border-strong) !important;
  border-radius: var(--ui-radius-md) !important;
}

@media (hover: hover) and (pointer: fine) {
  .stButton > button[kind="primary"]:hover {
    background-color: var(--ui-accent-hover) !important;
    border-color: var(--ui-accent-hover) !important;
  }
  .stButton > button[kind="secondary"]:hover,
  .stButton > button[kind="tertiary"]:hover {
    background: var(--ui-hairline-soft) !important;
    border-color: var(--ui-border-strong) !important;
  }
  .stButton > button.space-btn-strong:hover {
    background-color: var(--ui-primary-strong-active) !important;
    border-color: var(--ui-primary-strong-active) !important;
  }
  [class*="st-key-prod_open_"] button:hover {
    background: var(--ui-hairline-soft) !important;
    border-color: var(--ui-accent) !important;
    color: var(--ui-accent) !important;
  }
}
"""

# --- Sidebar --------------------------------------------------------------

_SIDEBAR_CSS = """
div[data-testid="stSidebar"] .block-container,
div[data-testid="stSidebar"] > div:first-child { padding-top: 1.1rem; }

.space-brand { display: flex; align-items: center; gap: 10px; padding: 2px 4px 12px; }
.space-brand-mark {
  width: 30px; height: 30px; border-radius: var(--ui-radius-md);
  background: var(--ui-accent); color: var(--ui-accent-contrast);
  display: flex; align-items: center; justify-content: center;
  font-weight: 700; font-size: 0.9375rem; letter-spacing: -0.02em; flex-shrink: 0;
}
.space-brand-name {
  font-size: 1rem; font-weight: 650; letter-spacing: -0.02em;
  color: var(--ui-text); line-height: 1.1;
}
.space-brand-sub { font-size: 0.6875rem; color: var(--ui-text-muted); margin-top: 1px; }

.space-user-chip {
  display: flex; align-items: center; gap: 10px;
  padding: 8px 10px; margin: 2px 0 10px;
  border: 1px solid var(--ui-border); border-radius: 10px;
  background: var(--ui-bg-elevated);
}
.space-user-avatar {
  width: 28px; height: 28px; border-radius: var(--ui-radius-full, 999px);
  background: var(--sanzar-green-soft); color: var(--ui-accent-hover);
  display: flex; align-items: center; justify-content: center;
  font-size: 0.75rem; font-weight: 700; flex-shrink: 0;
}
.space-user-name {
  font-size: 0.8438rem; font-weight: 600; color: var(--ui-text); line-height: 1.2;
  overflow: hidden; text-overflow: ellipsis; white-space: nowrap;
}
.space-user-role {
  font-size: 0.6875rem; color: var(--ui-text-muted);
  text-transform: uppercase; letter-spacing: 0.05em;
}

.space-nav-section {
  margin: 12px 0 2px; padding: 0 4px;
  font-size: 0.6875rem; font-weight: 650; text-transform: uppercase;
  letter-spacing: 0.08em; color: var(--ui-text-muted);
}
[class*="st-key-space_nav"] div[data-testid="stVerticalBlock"] { gap: 0.14rem; }
[class*="st-key-nav_btn_"] button {
  width: 100%;
  justify-content: flex-start !important;
  text-align: left !important;
  background: transparent !important;
  border: none !important;
  box-shadow: none !important;
  border-radius: var(--ui-radius-md) !important;
  padding: 0.32rem 0.55rem !important;
  min-height: 2.1rem !important;
  font-weight: 500 !important;
  font-size: 0.875rem !important;
  color: var(--ui-text-body) !important;
}
/* Navegar es una acción de decenas de veces al día: sin animación de entrada,
   solo el cambio de color. */
[class*="st-key-nav_btn_"] button:active { transform: none; }
[class*="st-key-nav_btn_"] button [data-testid="stIconMaterial"] {
  font-size: 1.05rem; color: var(--ui-text-muted);
}
[class*="st-key-nav_btn_"] button[kind="primary"] {
  background: var(--sanzar-green-soft) !important;
  color: var(--ui-accent-hover) !important;
  font-weight: 600 !important;
}
[class*="st-key-nav_btn_"] button[kind="primary"] [data-testid="stIconMaterial"] {
  color: var(--ui-accent) !important;
}
[class*="st-key-nav_btn_"] button:focus:not(:focus-visible) { box-shadow: none !important; }

@media (hover: hover) and (pointer: fine) {
  [class*="st-key-nav_btn_"] button:hover {
    background: var(--ui-hairline-soft) !important;
    color: var(--ui-text) !important;
  }
}

[class*="st-key-nav_util_"] button {
  background: transparent !important;
  border: 1px solid var(--ui-border) !important;
  border-radius: var(--ui-radius-md) !important;
  color: var(--ui-text-muted) !important;
  font-size: 0.8125rem !important;
  font-weight: 500 !important;
  min-height: 1.9rem !important;
  padding: 0.2rem 0.5rem !important;
}
.space-sidebar-divider {
  border: none; border-top: 1px solid var(--ui-border); margin: 12px 0 8px;
}
.space-login-title {
  margin: 4px 0 0 !important; font-size: 1.05rem !important;
  font-weight: 650 !important; color: var(--ui-text) !important;
}
.space-login-sub {
  font-size: 0.8125rem; color: var(--ui-text-muted); margin: 2px 0 8px;
}
"""

# --- Pantalla de arranque y login (área principal) ------------------------
#
# El login vive en el lienzo, no en la barra lateral: un formulario escondido
# en el sidebar deja la pantalla en blanco, y una pantalla en blanco no se lee
# como «falta iniciar sesión», se lee como «esto está roto».

_LOGIN_CSS = """
[class*="st-key-space_login_card"],
[class*="st-key-space_boot_card"] {
  margin-top: 7vh;
  padding: 30px 32px 26px;
  border: 1px solid var(--ui-border);
  border-radius: var(--ui-radius-lg);
  background: var(--ui-bg-elevated);
  box-shadow: 0 1px 3px rgba(15, 23, 42, 0.05), 0 12px 32px rgba(15, 23, 42, 0.04);
  animation: space-enter var(--ui-duration-slow) var(--ui-ease-out) both;
}
[class*="st-key-space_login_card"] .space-brand,
[class*="st-key-space_boot_card"] .space-brand {
  padding: 0 0 18px;
}
.space-login-heading {
  margin: 0 0 4px !important;
  font-size: 1.4rem !important;
  font-weight: 650 !important;
  letter-spacing: -0.025em !important;
  color: var(--ui-text) !important;
}
.space-login-help {
  margin: 0 0 18px !important;
  font-size: 0.875rem;
  line-height: 1.55;
  color: var(--ui-text-muted);
}
.space-login-help code {
  font-size: 0.8125rem;
  padding: 1px 5px;
  border-radius: var(--ui-radius-sm, 6px);
  background: var(--ui-hairline-soft);
  color: var(--ui-text-body);
}
[class*="st-key-space_boot_card"] .space-login-heading { color: var(--ui-semantic-error) !important; }
"""

# --- Cabeceras, KPIs, tarjetas y chips ------------------------------------

_CONTENT_CSS = """
.space-page-header {
  margin: 0 0 1.15rem; padding-bottom: 0.85rem;
  border-bottom: 1px solid var(--ui-border);
}
.space-page-title {
  margin: 0 !important; padding: 0 !important;
  font-size: 1.55rem !important; font-weight: 650 !important;
  letter-spacing: -0.025em !important; line-height: 1.2 !important;
  color: var(--ui-text) !important;
}
.space-page-desc {
  margin: 4px 0 0 !important; padding: 0 !important;
  font-size: 0.875rem; color: var(--ui-text-muted); line-height: 1.45;
}

/* KPIs */
.space-kpi-row {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(168px, 1fr));
  gap: var(--ui-spacing-sm);
  margin-bottom: var(--ui-spacing-lg);
}
.space-kpi {
  border: 1px solid var(--ui-border); border-radius: var(--ui-radius-lg);
  background: var(--ui-bg-elevated); padding: 14px 16px;
  transition: transform var(--ui-duration-fast) var(--ui-ease-out);
}
.space-kpi-label {
  font-size: 0.6875rem; font-weight: 600; text-transform: uppercase;
  letter-spacing: 0.07em; color: var(--ui-text-muted); margin-bottom: 6px;
}
.space-kpi-value {
  font-size: 1.75rem; font-weight: 650; letter-spacing: -0.03em;
  line-height: 1; color: var(--ui-text);
}
.space-kpi-hint { font-size: 0.75rem; color: var(--ui-text-muted); margin-top: 6px; }
.space-kpi--success { border-color: var(--ui-kpi-success-border); background: var(--ui-kpi-success-bg); }
.space-kpi--warning { border-color: var(--ui-kpi-warning-border); background: var(--ui-kpi-warning-bg); }
.space-kpi--danger  { border-color: var(--ui-kpi-danger-border);  background: var(--ui-kpi-danger-bg); }
.space-kpi--info    { border-color: var(--ui-kpi-info-border);    background: var(--ui-kpi-info-bg); }

/* Tarjeta "más barato por producto" */
.space-card {
  border: 1px solid var(--ui-border); border-radius: var(--ui-radius-lg);
  background: var(--ui-bg-elevated); padding: 16px 18px; height: 100%;
  transition:
    border-color var(--ui-duration-base) var(--ui-ease-out),
    box-shadow var(--ui-duration-base) var(--ui-ease-out),
    transform var(--ui-duration-base) var(--ui-ease-out);
}
.space-card-head {
  display: flex; align-items: baseline; justify-content: space-between;
  gap: 10px; margin-bottom: 10px;
}
.space-card-title {
  font-size: 1rem; font-weight: 650; letter-spacing: -0.015em; color: var(--ui-text);
}
.space-card-eyebrow {
  font-size: 0.6875rem; font-weight: 600; text-transform: uppercase;
  letter-spacing: 0.07em; color: var(--ui-text-muted);
}
.space-card-price {
  font-size: 1.5rem; font-weight: 650; letter-spacing: -0.03em;
  color: var(--ui-price-winner); line-height: 1.1;
}
.space-card-supplier { font-size: 0.9375rem; font-weight: 550; color: var(--ui-text); margin-top: 2px; }
.space-card-meta { font-size: 0.75rem; color: var(--ui-text-muted); margin-top: 6px; line-height: 1.5; }
.space-card-empty {
  font-size: 0.8125rem; color: var(--ui-text-muted);
  padding: 10px 0 4px; line-height: 1.5;
}
.space-card-divider { border: none; border-top: 1px solid var(--ui-hairline-soft); margin: 12px 0 10px; }

@media (hover: hover) and (pointer: fine) {
  .space-card:hover {
    border-color: var(--ui-border-strong);
    box-shadow: 0 2px 10px rgba(15, 23, 42, 0.06);
    transform: translateY(-1px);
  }
}

/* Chips de estado */
.space-chip {
  display: inline-flex; align-items: center; gap: 5px;
  padding: 2px 9px; border-radius: var(--ui-radius-pill, 9999px);
  font-size: 0.75rem; font-weight: 600; line-height: 1.6; white-space: nowrap;
}
.space-chip-row { display: flex; flex-wrap: wrap; gap: 6px; }

/* Filas de lista (botones que parecen tabla) */
[class*="st-key-supplier_row_"] button,
[class*="st-key-action_row_"] button {
  width: 100%;
  justify-content: flex-start !important;
  text-align: left !important;
  background: transparent !important;
  border: none !important;
  border-bottom: 1px solid var(--ui-hairline-soft) !important;
  border-radius: var(--ui-radius-sm, 6px) !important;
  padding: 0.4rem 0.6rem !important;
  min-height: 2.1rem !important;
  font-size: 0.8438rem !important;
  font-weight: 450 !important;
  color: var(--ui-text-body) !important;
  box-shadow: none !important;
}
@media (hover: hover) and (pointer: fine) {
  [class*="st-key-supplier_row_"] button:hover,
  [class*="st-key-action_row_"] button:hover {
    background: var(--ui-hairline-soft) !important;
    color: var(--ui-text) !important;
  }
}

/* Bloques de la ficha */
.space-detail-header {
  display: flex; align-items: center; gap: 14px;
  padding: 16px 18px; margin-bottom: var(--ui-spacing-md);
  border: 1px solid var(--ui-border); border-radius: var(--ui-radius-lg);
  background: var(--ui-surface-soft);
}
.space-detail-avatar {
  width: 44px; height: 44px; border-radius: var(--ui-radius-md);
  background: var(--sanzar-green-soft); color: var(--ui-accent-hover);
  display: flex; align-items: center; justify-content: center;
  font-size: 1rem; font-weight: 700; flex-shrink: 0;
}
.space-detail-name {
  font-size: 1.25rem; font-weight: 650; letter-spacing: -0.02em; color: var(--ui-text);
}
.space-detail-meta { font-size: 0.8125rem; color: var(--ui-text-muted); margin-top: 3px; }

.space-field-grid {
  display: grid; grid-template-columns: repeat(auto-fit, minmax(210px, 1fr));
  gap: 12px 20px; margin: 6px 0 4px;
}
.space-field-label {
  font-size: 0.6875rem; font-weight: 600; text-transform: uppercase;
  letter-spacing: 0.06em; color: var(--ui-text-muted);
}
.space-field-value { font-size: 0.875rem; color: var(--ui-text); margin-top: 2px; word-break: break-word; }

/* Entradas de histórico */
.space-history-item {
  border: 1px solid var(--ui-border); border-left: 3px solid var(--ui-border-strong);
  border-radius: var(--ui-radius-md); background: var(--ui-bg-elevated);
  padding: 12px 14px; margin-bottom: 8px;
}
.space-history-item--email     { border-left-color: var(--ui-semantic-info); }
.space-history-item--reunion   { border-left-color: var(--ui-semantic-purple); }
.space-history-item--llamada   { border-left-color: var(--ui-semantic-success); }
.space-history-head {
  display: flex; align-items: center; justify-content: space-between;
  gap: 10px; margin-bottom: 6px; flex-wrap: wrap;
}
.space-history-title { font-size: 0.875rem; font-weight: 600; color: var(--ui-text); }
.space-history-body { font-size: 0.8438rem; color: var(--ui-text-body); line-height: 1.55; white-space: pre-wrap; }
.space-history-foot { font-size: 0.75rem; color: var(--ui-text-muted); margin-top: 8px; }

/* Placeholders "Próximamente" */
.space-soon {
  border: 1px dashed var(--ui-border-strong); border-radius: var(--ui-radius-lg);
  background: var(--ui-surface-soft); padding: 32px 28px; text-align: center;
}
.space-soon-title { font-size: 1.05rem; font-weight: 650; color: var(--ui-text); margin-bottom: 6px; }
.space-soon-text { font-size: 0.875rem; color: var(--ui-text-muted); line-height: 1.6; max-width: 62ch; margin: 0 auto; }

.space-empty {
  border: 1px solid var(--ui-border); border-radius: var(--ui-radius-lg);
  background: var(--ui-surface-soft); padding: 22px 20px; text-align: center;
  font-size: 0.875rem; color: var(--ui-text-muted); line-height: 1.6;
}

div[data-testid="stDataFrame"] { border-radius: var(--ui-radius-md); overflow: hidden; }
"""

# --- Movimiento -----------------------------------------------------------

_MOTION_CSS = """
/* Entrada de contenido: opacidad + un desplazamiento mínimo, nunca scale(0).
   260 ms es el techo de toda la app. */
@keyframes space-enter {
  from { opacity: 0; transform: translateY(6px); }
  to   { opacity: 1; transform: translateY(0); }
}
.space-card, .space-kpi, .space-history-item {
  animation: space-enter var(--ui-duration-slow) var(--ui-ease-out) both;
}
/* Stagger de 40 ms: la parrilla entra como un grupo, no como un pelotón.
   Nunca bloquea la interacción — el contenido ya es clicable desde el primer
   fotograma porque solo animamos opacidad y transform. */
.space-kpi:nth-child(2)  { animation-delay: calc(var(--ui-stagger-step) * 1); }
.space-kpi:nth-child(3)  { animation-delay: calc(var(--ui-stagger-step) * 2); }
.space-kpi:nth-child(4)  { animation-delay: calc(var(--ui-stagger-step) * 3); }
.space-kpi:nth-child(5)  { animation-delay: calc(var(--ui-stagger-step) * 4); }
.space-kpi:nth-child(n+6) { animation-delay: calc(var(--ui-stagger-step) * 5); }

/* Diálogos: escalan desde 0.97, centrados (un modal no nace de un trigger). */
div[data-testid="stDialog"] > div {
  animation: space-dialog-enter var(--ui-duration-base) var(--ui-ease-out) both;
  transform-origin: center;
}
@keyframes space-dialog-enter {
  from { opacity: 0; transform: scale(0.97); }
  to   { opacity: 1; transform: scale(1); }
}

/* Reducir movimiento ≠ cero movimiento: se conservan opacidad y color, que
   ayudan a entender qué ha cambiado, y se elimina el desplazamiento. */
@media (prefers-reduced-motion: reduce) {
  .space-card, .space-kpi, .space-history-item,
  div[data-testid="stDialog"] > div {
    animation-duration: var(--ui-duration-instant);
    animation-delay: 0ms !important;
    animation-name: space-fade-only;
  }
  @keyframes space-fade-only {
    from { opacity: 0; }
    to   { opacity: 1; }
  }
  .stButton > button:active { transform: none; }
  .space-card:hover { transform: none; }
}
"""


@lru_cache(maxsize=1)
def _stylesheet() -> str:
    """CSS completo, compuesto una sola vez por proceso."""
    return "\n".join(
        (
            "<style>",
            _FONT_IMPORT,
            css_variables(),
            _BASE_CSS,
            _BUTTONS_CSS,
            _SIDEBAR_CSS,
            _LOGIN_CSS,
            _CONTENT_CSS,
            _MOTION_CSS,
            "</style>",
        )
    )


def apply_theme() -> None:
    """Inyecta el tema. Llamar una vez, al principio de ``streamlit_app.py``."""
    st.markdown(_stylesheet(), unsafe_allow_html=True)


def reset_theme_cache() -> None:
    """Recompone el CSS (útil al tocar los .md de diseño en desarrollo)."""
    _stylesheet.cache_clear()
