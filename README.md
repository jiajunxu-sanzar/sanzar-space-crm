# Sanzar Space CRM — suministradores

CRM dedicado a la relación con **suministradores** (proveedores de
componentes), separado del CRM comercial de clientes (`sanzar-crm-web`) pero
construido con el mismo stack y los mismos patrones, para que el equipo pueda
mantener los dos con el mismo conocimiento.

Para cada producto que Sanzar necesita fabricar o incorporar (hoy motores,
slip-rings y rodamientos; mañana lo que haga falta) responde a una pregunta:
**¿quién es ahora mismo el mejor suministrador, y por qué?** — con el histórico
de conversaciones y de precios detrás, en vez de rebuscando en correos.

---

## Arranque rápido

```bash
cd sanzar-crm-space
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

cp .env.example .env          # y rellena GOOGLE_SHEET_ID
# coloca el JSON del service account en config/credentials/service_account.json

streamlit run streamlit_app.py
```

La carpeta de las pantallas se llama `views/`, **no `pages/`**: Streamlit
convierte automáticamente cualquier `pages/` en una navegación multipágina
propia, y al pinchar en ella se ejecutaría `views/home.py` suelto —un módulo
que solo define `render()`— dejando la pantalla en blanco.

La primera vez que arranca, la app **crea las pestañas que falten** en la hoja
con sus cabeceras y añade columnas nuevas si el modelo ha crecido. No borra ni
reordena nada que ya exista.

Si la hoja `Usuarios` está vacía, se siembra un único usuario
`Administrador / EMP-001` con contraseña `2026`. **Cámbiala desde
Usuarios → Gestionar en cuanto entres.**

### Credenciales de Google

El acceso se hace con una cuenta de servicio en un proyecto de Google Cloud
**separado** del que usa `sanzar-crm-web`, para que la cuota de la API no se
comparta entre ambos CRMs (la cuota es por proyecto, no por app):

1. La hoja debe ser un **Google Sheet nativo**, no un `.xlsx` subido a Drive.
   La Sheets API no puede leer ni escribir un `.xlsx` crudo.
2. En [console.cloud.google.com](https://console.cloud.google.com), proyecto
   nuevo → habilitar **Google Sheets API** y **Google Drive API**.
3. Crear una cuenta de servicio en ese proyecto y descargar su clave JSON.
4. Compartir la hoja con el `client_email` que aparece dentro del JSON, con rol
   **Editor**.
5. Mover el JSON a `config/credentials/service_account.json` (esa carpeta está
   en `.gitignore`).

En Streamlit Cloud no se sube el JSON: se pega su contenido en *Secrets* bajo
`[gcp_service_account]` y `app/secrets.py` lo detecta automáticamente.

---

## Las cinco páginas

| Página | Qué hace | Roles |
|---|---|---|
| **Home** | KPIs y una tarjeta por producto con el suministrador **más barato ahora mismo**, su precio y la fecha de la oferta. Botón directo a la ficha. | todos |
| **Acciones** | Tu bandeja: próximas acciones pendientes, **vencidas primero**. Un admin puede ver la de todo el equipo. | admin, comprador |
| **Suministradores** | Lista con filtros (producto, país, buscador, mostrar descartados) y ficha con tres bloques: datos generales, conversaciones y precios. | admin, comprador |
| **Compras** | Reservada — «Próximamente». | admin, comprador |
| **Ofertas** | Reservada — «Próximamente» (flujo inverso: ofertas que Sanzar envía). | admin, comercial |

`Usuarios` es la sexta pestaña, exclusiva de admin: altas, roles y un
diagnóstico de conexión, volumen de datos y latencia real de las últimas
operaciones.

### Roles

| Rol | Ve |
|---|---|
| `admin` | Todo, incluida `Usuarios` |
| `comprador` | Home, Acciones, Suministradores, Compras |
| `comercial` | Home, Ofertas |

Un rol desconocido en la hoja cae a `comercial` (el de menor privilegio): un
error de escritura nunca puede escalar permisos.

---

## Modelo de datos

Un único Google Sheet con estas pestañas (documentadas también dentro del
propio Excel, en la hoja `Indice`, que la app regenera al arrancar):

| Hoja | Qué guarda | Tipo |
|---|---|---|
| `Indice` | Documentación de cada hoja | Meta |
| `Productos` | Un producto = una fila | Maestro |
| `ProductosCamposSchema` | Qué campos técnicos tiene cada producto | Esquema dinámico |
| `ProductosCamposValores` | El valor de cada campo, por producto | Datos (EAV) |
| `Suministradores` | Identidad y contacto, independiente del producto | Maestro |
| `SuministradorProducto` | Relación N:M con su estado | Relación |
| `HistoricoConversaciones` | Cada email/reunión/llamada | Histórico |
| `HistoricoPrecios` | Cada precio recibido | Histórico |
| `Usuarios` | Acceso y roles | Maestro |

Dos decisiones que explican casi todo el diseño:

**Esquema técnico dinámico.** Un motor y un rodamiento no comparten
especificaciones. En vez de una hoja `Productos` ancha con todas las columnas
posibles, el esquema vive en dos hojas: `ProductosCamposSchema` dice *qué*
campos tiene cada producto, `ProductosCamposValores` dice *cuánto valen*.
Dar de alta un producto con especificaciones nunca vistas es añadir filas —
nunca migrar la hoja ni tocar código. Es el mismo patrón que ya usa
`InventarioCamposModelo` en el CRM de clientes.

**Identidad separada de la relación.** Un mismo proveedor puede estar
«confirmado» para slip-rings y «descartado» para rodamientos a la vez. Si el
estado viviera en la ficha del proveedor eso sería imposible de representar,
así que `Suministradores` guarda quién es y `SuministradorProducto` guarda en
qué punto está para cada producto.

### Convenciones

- Identificadores `entidad_id` en `snake_case`; claves legibles (`PRD-0001`,
  `SUP-0007`) para maestros y con sufijo aleatorio (`CNV-3f9a2b7c`) para los
  históricos, donde dos altas simultáneas colisionarían con un contador.
- Fechas como texto `DD/MM/AAAA`; la lectura tolera ISO y otras variantes
  porque una hoja editada a mano siempre acaba teniendo de todo.
- Toda fila lleva `created_at` / `updated_at` (hora de Madrid, no la del
  servidor).
- Los números se parsean tolerando locale español y americano: «1.250,50» son
  mil doscientos cincuenta.

---

## Cómo está montado

```
streamlit_app.py       Punto de entrada: tema, esquema, login, navegación, despacho
app/                   Sesión y plataforma (auth, navigation, cache, state, telemetry)
config/settings.py     Nombres de pestaña, cabeceras y listas de valores — fuente de verdad
models/                Product, Supplier, Conversation, PriceQuote (from_row / to_row)
services/              Lógica: Sheets, esquema, dataset, altas, ranking, bandeja
views/                 Una por pestaña, más los formularios modales
ui/                    Tokens de diseño, tema y componentes
tests/                 pytest — 200 pruebas, sin red
```

### Decisiones de rendimiento

Están heredadas de `sanzar-crm-web`, donde ya se pagó el aprendizaje:

- **Todo el Excel en una llamada.** `SpaceDataset.load()` hace un único
  `values.batchGet` de las 8 pestañas y construye en memoria todos los índices
  que la app necesita. Un refresco cuesta 1 llamada API, no 8.
- **Caché con versión.** Los loaders reciben un contador de `session_state`;
  incrementarlo invalida esa entrada sin borrar el resto ni perder filtros.
- **Escritura mínima.** Un alta es un `append_row`; cerrar una acción es
  escribir **una celda**. La hoja completa solo se reescribe en el bootstrap.
- **Detección de cambios barata.** Un poll del `modifiedTime` en Drive (que no
  consume cuota de Sheets) avisa si alguien editó el Excel a mano.
- **El esquema se valida una vez por proceso**, no en cada rerun: en el CRM de
  clientes eso fue una fuga silenciosa de cuota que costó detectar.
- **Objetos `Worksheet` y cabeceras cacheados**: `spreadsheet.worksheet(name)`
  dispara una petición de metadatos en cada llamada de gspread.
- **Reintentos con backoff y jitter** solo ante errores transitorios (429/5xx,
  red). Un 403 se propaga inmediatamente: reintentarlo no arregla un permiso.

### Diseño y movimiento

Los tokens viven en el frontmatter de `DESIGN-cal.md` (base) y
`DESIGN-space.md` (marca Sanzar), no en Python, para que el documento de diseño
y el código no puedan divergir. La paleta es idéntica a la de `sanzar-crm-web`.

El sistema de movimiento sigue las reglas de *design engineering* de
[Emil Kowalski](https://animations.dev): ninguna animación pasa de 300 ms (aquí
el techo real es 260 ms), nunca `ease-in` en interfaz, solo se animan
`transform` y `opacity`, nada entra desde `scale(0)`, el `:hover` va detrás de
`@media (hover: hover) and (pointer: fine)`, las entradas en grupo escalonan
40 ms, y `prefers-reduced-motion` conserva color y opacidad pero elimina el
movimiento. Hay un test que lo verifica sobre el CSS generado.

---

## Tests

```bash
python -m pytest -q
```

No tocan la red. Tres capas:

- **Unitarias** por servicio de agregación (ranking de precios, bandeja de
  acciones, esquema dinámico, validaciones, formatos).
- **`tests/test_sheets_write_safety.py`** — que una columna añadida a mano a la
  hoja no se borre al editar una fila, y que un hueco en la cabecera no
  desplace los valores.
- **`tests/test_app_smoke.py`** — ejecuta la app entera con `AppTest`
  sustituyendo solo la capa de Google: login, permisos por rol, cada página
  pintándose con datos reales, y regresiones (navegar a una ficha, no arrastrar
  datos entre formularios, ids duplicados en la hoja).

---

## Fuera de alcance por ahora

- Conversión automática de divisas. Si dos suministradores del mismo producto
  cotizan en EUR y USD, la app muestra un ganador **por moneda** en vez de
  inventarse un tipo de cambio.
- Alarmas de estancamiento. La lógica está escrita y probada
  (`services/actions_stats.stagnant_relations`), pero todavía no se muestra en
  ninguna página.
- Exportación de comparativas a PDF.
