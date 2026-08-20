---
extends: DESIGN-cal.md
colors:
  brand-accent: "#2D6A4F"
  brand-accent-hover: "#1E4D38"
  brand-accent-soft: "#EAF4EE"
  brand-accent-contrast: "#FFFFFF"
  semantic-success: "#4CAF78"
  semantic-warning: "#F5A623"
  semantic-error: "#E05252"
  semantic-info: "#4A90D9"
  semantic-purple: "#7C5CBF"
  bucket-past: "#B0B8C1"
  bucket-today: "#2D6A4F"
  bucket-future: "#6EB5E0"
  supplier-confirmado: "#4CAF78"
  supplier-potencial: "#4A90D9"
  supplier-descartado: "#B0B8C1"
  price-winner: "#2D6A4F"
  price-expired: "#F5A623"
motion:
  duration-instant: 100ms
  duration-fast: 160ms
  duration-base: 200ms
  duration-slow: 260ms
  ease-out: cubic-bezier(0.23, 1, 0.32, 1)
  ease-in-out: cubic-bezier(0.77, 0, 0.175, 1)
  stagger-step: 40ms
components:
  button-primary:
    backgroundColor: "{colors.brand-accent}"
    textColor: "{colors.brand-accent-contrast}"
  button-primary-active:
    backgroundColor: "{colors.brand-accent-hover}"
    textColor: "{colors.brand-accent-contrast}"
  button-primary-strong:
    backgroundColor: "{colors.primary}"
    textColor: "{colors.on-primary}"
  button-primary-strong-active:
    backgroundColor: "{colors.primary-active}"
    textColor: "{colors.on-primary}"
---

## Sanzar Space CRM — capa de marca

Extiende [DESIGN-cal.md](DESIGN-cal.md) con la paleta Sanzar, **idéntica a la
de `sanzar-crm-web`**: quien use los dos CRMs debe sentir que son la misma
familia de producto. Neutros, tipografía, espaciado y radios se heredan de Cal.

### Tipografía

Cal Sans no está disponible públicamente. Se usa **Inter** (400–700) con
`letter-spacing: -0.02em` en títulos display, como sustituto documentado.

### CTA dual

| Contexto | Componente | Color |
|---|---|---|
| Uso diario | `button-primary` | `brand-accent` (#2D6A4F) |
| Acción irreversible | `button-primary-strong` | Cal `primary` (#111111) |

### Semántica propia de este CRM

| Concepto | Token | Hex |
|---|---|---|
| Proveedor confirmado | `supplier-confirmado` | #4CAF78 |
| Potencial proveedor | `supplier-potencial` | #4A90D9 |
| Descartado | `supplier-descartado` | #B0B8C1 |
| Precio ganador | `price-winner` | #2D6A4F |
| Oferta caducada | `price-expired` | #F5A623 |

Los chips derivan fondo/borde/texto desde el color base mezclando con blanco en
`ui/design_tokens.py::pastel_triplet`, así que añadir un estado nuevo es añadir
un token, no escribir tres hex a mano.

### Movimiento

Los tokens `motion.*` implementan las reglas de *design engineering* que sigue
esta app (ver `ui/theme.py`):

- Ninguna animación de UI pasa de **300 ms**; el máximo real aquí es 260 ms.
- Nunca `ease-in` en interfaz: retrasa el arranque y se percibe como lag.
  Entrar/salir usa `ease-out`; moverse en pantalla, `ease-in-out`.
- Solo se animan `transform` y `opacity` (compuestas en GPU). Nunca `width`,
  `height`, `margin` ni `padding`: fuerzan layout en cada fotograma.
- Nada entra desde `scale(0)`: se entra desde `scale(0.97)` + `opacity: 0`.
- El `:hover` va detrás de `@media (hover: hover) and (pointer: fine)` para que
  no se dispare al tocar en pantallas táctiles.
- Todo respeta `prefers-reduced-motion`: se conserva el color y la opacidad
  (ayudan a entender el cambio) y se elimina el movimiento.
- Las entradas en grupo escalonan **40 ms** por elemento, sin bloquear nunca la
  interacción.
