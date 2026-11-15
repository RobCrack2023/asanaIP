# AsanaIP

Gestión de proyectos y CRM comercial en una sola herramienta: el pipeline de ventas y la ejecución del proyecto viven en el mismo sistema, así que una oportunidad ganada se convierte en un proyecto con sus tareas sin volver a escribir nada.

Construido con Django REST Framework y React.

## Características principales

### Gestión de tareas
- **Vista Lista** con columnas de responsable, fechas, prioridad y estado
- **Vista Kanban** con columnas arrastrables por sección
- **Drag & Drop** para reordenar tareas entre secciones
- **Subtareas** dentro de cada tarea
- **Tareas recurrentes** (semanal, mensual, anual) con regeneración automática al completar
- **Fechas de inicio y límite** con rango visible en la lista
- **Prioridad** (Baja, Media, Alta, Urgente) y **estados** (Pendiente, En progreso, Completada)
- **Visibilidad** pública o privada por tarea

### Organización
- **Jerarquía**: Áreas → Equipos → Proyectos → Secciones → Tareas
- **Vista de Área** con equipos, miembros y proyectos
- Crear áreas, equipos y proyectos desde el sidebar
- Selector de colores por proyecto y área

### CRM comercial

**Pipeline**
- **Tablero Kanban** de oportunidades con arrastre entre etapas, conteo y monto por columna
- Etapas: Prospecto → Cotización enviada → Negociación → Ganada / Perdida
- Cerrar una oportunidad pide lo que la etapa no puede llevar: el equipo que tomará el proyecto, o el motivo de la pérdida
- **Ganar una oportunidad crea el proyecto** y traslada sus tareas a él, en una transacción
- Vista de lista alternativa con filtros por etapa y cliente

**Bitácora**
- Timeline único por oportunidad: notas, llamadas, reuniones y correos que registra el equipo
- Los **cambios de etapa se registran solos**, con autor y fecha — la API no acepta que se inventen ni permite borrarlos
- `occurred_at` separado de `created_at`, para registrar hoy una llamada de ayer

**Cotizaciones**
- Ítems como filas con FK opcional al catálogo, cantidad, margen y descuento por línea
- **IVA configurable** (19% por defecto), guardado en cada documento para que una cotización antigua conserve su tasa
- **Correlativo por empresa** que solo avanza: borrar una cotización deja un hueco en vez de reutilizar un número que ya llegó a un cliente
- Fecha de emisión, validez y aviso de vencida
- Costo, utilidad y margen calculados en el servidor; los montos que envía el cliente se ignoran
- **Categoría por línea** (equipo · servicio propio · gasto operacional · flete · prevención y EPP), heredada del catálogo y ajustable por trato
- **Líneas de costo interno**: un costo que la empresa asume en el trato (sueldos y bonos de quienes van a terreno, gastos operacionales). Cuenta en el costo y por lo tanto baja el margen, pero **no se cobra y no sale en el documento del cliente**. La planilla EF lo escribe como margen de −100%; acá es un tipo de línea, porque una línea en $0 en un documento que lee el cliente avisaría lo que no debe
- **Comisión del vendedor**: un porcentaje de la **utilidad**, no de la venta, y sin comisión negativa si el trato pierde plata. Se muestra debajo de la utilidad, como en la planilla EF, así que **no altera el margen**. Nunca sale en el documento del cliente
- **Provisión**: una línea puede marcarse como provisión, independiente de si es interna. Al ganar el trato el proyecto sella cuánto del presupuesto es estimación
- **Composición del costo**: costo, venta y margen abiertos por categoría, en vivo mientras se cotiza y guardados con el documento. Un margen mezclado de 49% esconde que los equipos rindieron 38%, la mano de obra 180% y los gastos se cotizaron casi a costo
- Reclasificar el catálogo **no altera** las cotizaciones ya emitidas: la categoría se copia al cotizar, igual que la descripción y el precio
- Lectura en CLP, USD, EUR o UF con la tasa con que se emitió

**Hojas de gastos**
- Los gastos operacionales se **desglosan antes de cotizarlos**: tres bloques (viaje, flete, operaciones) con `unitario × cantidad × días`
- En la planilla este cálculo vive en una hoja que **ninguna fórmula referencia**: alguien saca el total y lo teclea en la cotización, y el detalle se pierde. Acá queda guardado y la línea se **genera** desde él
- Una hoja nueva puede **partir de otra**: el próximo proyecto arranca del anterior, no de la memoria
- Cada bloque se lleva a la cotización como su propia línea con su categoría — "Gastos de viaje" y "Flete" separados, como los escribe la hoja Cálculo
- Es **solo costo**: lo que se cobra por esos gastos lo decide el margen de la línea. Borrar una hoja no toca las cotizaciones que produjo

**Conceptos de gasto**
- Lo que se paga seguido ejecutando (alojamiento, camioneta, prevencionista, EPP...). **No guardan un precio**: hoteles y arriendos cambian, así que guardan los valores con su fecha
- Al armar una hoja de gastos se parte de un concepto y se ve el **último valor conocido y qué tan viejo es**. Pasados 90 días se marca desactualizado; nunca se reemplaza solo
- La referencia **la manda la fecha en que el valor fue cierto**, no cuándo se tecleó: una boleta cargada tarde no pisa una cotización más nueva
- Lo que se escribe en una hoja queda como valor de referencia. Si se vuelve a escribir un valor viejo, se da por confirmado y su edad vuelve a cero
- Un gasto real puede indicar qué compró y cuántas unidades (260.000 por 4 días = 65.000 por día) y **enseña el valor real** al concepto. Corregir o borrar el gasto corrige o borra ese valor
- "Cargar conceptos básicos" crea los habituales **sin valor**: ninguno tiene precio fijo

**Costos de ejecución**
- Al ganar la oportunidad, el proyecto **sella el presupuesto** de la cotización con que se cerró — totales y desglose por categoría. Editar o borrar esa cotización después no mueve la vara
- Una oportunidad puede ganarse **sobre un proyecto que ya existe** (`mark_won(project=...)`): sirve para cargar trabajo ya ejecutado. El proyecto toma el presupuesto de la cotización, no se pisa su descripción y un proyecto no puede respaldar dos oportunidades
- Los gastos que aparecen ejecutando se registran en el proyecto con fecha, categoría, proveedor y documento
- **Son siempre costo de la empresa**, nunca del cliente: la venta la fijó un documento ya aceptado, así que cada gasto sale de la utilidad. Por eso no existe una marca de "recuperable"
- Los gastos van **encima** del presupuesto: nadie va a volver a teclear el datalogger que ya cotizó. **Salvo que la cotización tenga una provisión**: una línea marcada como provisión (típicamente los gastos operacionales) es una estimación que los gastos reales **reemplazan**, porque estaban dentro de ella. Sumar ambos contaría el mismo viaje dos veces. Lo que se gasta por sobre la provisión sí sube el costo, que es como aparece un imprevisto como el neumático
- **Resumen del proyecto**: una página que junta lo que está repartido entre la cotización, los gastos y los archivos: el trato, qué se hizo, cotizado contra real (venta, costo, utilidad, margen, comisión y utilidad neta), gastos por categoría y por día, los mayores, documentos y conclusiones. Se calcula siempre desde los registros, así que no puede discrepar de ellos
- **Cerrar un proyecto** marca el día y quién, guarda las conclusiones y **deja de aceptar gastos** (ni nuevos, ni editar, ni borrar, ni mover). Las cifras no cambian. Se puede reabrir, y las conclusiones se conservan. El resumen y el cierre son solo para staff o ventas
- La pestaña Costos muestra cuánto queda de la provisión, el costo real por categoría y la comisión del vendedor contra la utilidad real
- La pestaña **Costos** del proyecto muestra margen cotizado → margen real, y el presupuestado contra el real por categoría. Solo la ve staff o ventas; el equipo que ejecuta abre el proyecto pero no lo que deja

**Documento para el cliente**
- **PDF generado desde `ClientQuoteSerializer`**, que no incluye costo, margen ni utilidad: lo que no se serializa no puede filtrarse por la API, por una página guardada ni por un payload copiado
- La vista previa en pantalla y el archivo se arman con **el mismo payload**, así que no pueden discrepar
- **Plantilla por empresa**: logo, razón social, RUT, contacto, color, título del documento, presentación, condiciones comerciales, firma y pie de página
- Columnas opcionales (numeración, unidad, descuento). El costo y el margen no son una opción: no forman parte del documento
- Las observaciones de la cotización **no se imprimen salvo que se active**, porque ese campo puede tener notas internas

**Catálogo de productos**
- Costo y precio en la misma ficha: el precio se **deriva del costo y el margen**, nunca se teclea
- Un gasto operacional, un flete o la prevención son **fichas de catálogo como cualquier equipo**, con su propia categoría y su propio margen — así los trata la hoja Cálculo
- Costeo en la moneda del proveedor (CLP, USD, EUR, UF) con Incoterm y multiplicador de importación
- El multiplicador se aplica **solo cuando el Incoterm no es DDP** — bajo DDP el proveedor ya cubre flete y aranceles
- **Historial de precios**: cada cambio de costo, precio o proveedor queda registrado con autor y fecha, guardando el monto en moneda de origen junto a la tasa, de modo que una subida se puede atribuir al proveedor o al tipo de cambio

**Tipos de cambio**
- UF, dólar y euro como filas con fecha, por empresa
- Registrar un día que ya existe lo sobreescribe: corregir un tipeo es volver a escribirlo
- Las tasas **nunca se aplican solas**. Un movimiento marca los productos afectados y el catálogo se recalcula solo cuando alguien lo pide, para no reescribir costos bajo cotizaciones en curso ni llenar el historial de ruido

### Sistema de usuarios y permisos

| Rol | Alcance | Puede hacer |
|-----|---------|-------------|
| **Super Admin** | Global | Crear/gestionar empresas, planes y usuarios |
| **Admin de empresa** | Su organización | Gestionar áreas, equipos, proyectos, usuarios |
| **Usuario regular** | Sus equipos | Ver solo sus tareas y proyectos de sus equipos |

El módulo comercial (clientes, oportunidades, cotizaciones, productos y tipos de
cambio) requiere `is_staff` o `is_sales`. Toda relación entre registros está
acotada a la organización de quien hace la petición, así que una empresa no
puede apuntar a los clientes, oportunidades ni productos de otra.

### Aprobación de asignaciones
- **Admin** asigna tareas directamente (sin aprobación)
- **Usuario regular** asigna a otro → el destinatario debe **aceptar o rechazar**
- Sección "Solicitudes de asignación" en el Home con botones de aceptar/rechazar
- Sección "Tareas que asigné" para seguimiento de delegaciones con estado

### Multi-empresa (Multi-tenancy)
- Panel de **Super Admin** independiente para gestionar empresas
- **Planes** con cuotas de usuarios (Free, Pro, Enterprise)
- Aislamiento total de datos entre empresas
- Activar/desactivar empresas

### Assets y visor de archivos
- Subir archivos al proyecto (docs, imágenes, PDFs, emails)
- Agregar enlaces/URLs como recursos
- **Visor inline** (sin descargar):
  - **PDF**: renderizado nativo del navegador
  - **Imágenes**: preview en modal
  - **Excel (.xlsx)**: tabla HTML con hojas
  - **Word (.docx)**: HTML formateado con headings y tablas
  - **Correos (.eml)**: visor completo con De, Para, CC, fecha, cuerpo HTML y adjuntos descargables
  - **Texto/CSV/código**: visor monoespaciado
- Filtros por categoría (documento, imagen, correo, enlace)
- Detección automática de charset (UTF-8, Latin-1, Windows-1252)

### Interfaz
- **Sidebar** con navegación jerárquica por áreas/equipos/proyectos, más Clientes, Oportunidades y Productos
- **Home** con estadísticas, "Mis tareas" con filtros, solicitudes pendientes, tareas delegadas y proyectos recientes
- **Panel de detalle** como overlay lateral para editar tareas
- Diseño responsivo inspirado en Asana
- Login/logout con sesión

### Convención de margen

El margen es **markup sobre el costo** (`precio / costo - 1`), la convención de
las evaluaciones financieras en planilla: vender a tres veces el costo es un
margen de 2,0, o 200%. Deliberadamente **no** es margen sobre el precio de
venta — las dos convenciones dan números muy distintos y el equipo lee esta.
Un ítem sin costo cargado reporta margen nulo, no infinito.

## Stack tecnológico

| Componente | Tecnología |
|------------|-----------|
| Backend | Django 6 + Django REST Framework |
| Frontend | React 19 + Vite |
| Base de datos | SQLite (desarrollo) |
| Drag & Drop | @dnd-kit |
| Iconos | Lucide React |
| PDF de cotizaciones | reportlab |
| Visor Excel | openpyxl |
| Visor Word | python-docx |
| Parser Email | Módulo email de Python (built-in) |
| Montos | `Decimal` de punta a punta (nunca float) |

## Instalación

### Requisitos
- Python 3.10+
- Node.js 18+

### Inicio rápido (Windows)

```bash
git clone https://github.com/RobCrack2023/asanaIP.git
cd asanaIP
run.bat
```

El script `run.bat` hace todo automáticamente:
1. Crea el entorno virtual e instala dependencias Python
2. Instala dependencias del frontend (npm)
3. Aplica migraciones de base de datos
4. Carga datos de prueba si la DB está vacía
5. Inicia Django (puerto 8000) y React (puerto 5173)

### Inicio manual

```bash
# Backend
python -m venv venv
venv\Scripts\activate        # Windows
# source venv/bin/activate   # Linux/Mac
pip install -r requirements.txt

cp .env.example .env       # completá las variables
python manage.py migrate
python seed_data.py
python manage.py runserver

# Frontend (otra terminal)
cd frontend
npm install
npm run dev
```

Abrir `http://localhost:5173` en el navegador.

## Credenciales de prueba

Las crea `seed_data.py`. `run.bat` lo ejecuta solo cuando la base no tiene
ningún usuario, así que en una instalación con datos reales no se cargan.

| Usuario | Contraseña | Rol |
|---------|-----------|-----|
| `admin` | `admin123` | Super Admin |
| `carlos` | `pass123` | Desarrollador Senior (Desarrollo Web) |
| `maria` | `pass123` | Diseñadora UX (Diseño) |
| `pedro` | `pass123` | Product Manager (Diseño) |
| `ana` | `pass123` | QA Engineer (Desarrollo Web) |
| `luis` | `pass123` | Marketing Manager (Marketing Digital) |

## Tests

```bash
python manage.py test core
```

Cubren el aislamiento entre empresas, el registro automático de cambios de
etapa, el cálculo de totales e IVA, el correlativo de cotizaciones, la
conversión de monedas con Incoterm y el historial de precios.

## API Endpoints

### Autenticación
| Método | Endpoint | Descripción |
|--------|----------|-------------|
| POST | `/api/auth/login/` | Login |
| POST | `/api/auth/logout/` | Logout |
| GET | `/api/auth/me/` | Usuario actual |

### Recursos (CRUD)
| Recurso | Endpoint | Filtros |
|---------|----------|---------|
| Áreas | `/api/areas/` | |
| Equipos | `/api/teams/` | `?area=` |
| Proyectos | `/api/projects/` | `?team=` |
| Secciones | `/api/sections/` | `?project=` |
| Tareas | `/api/tasks/` | `?project=`, `?section=`, `?opportunity=`, `?assignee=`, `?status=`, `?assigned_by=`, `?parent=` |
| Assets | `/api/assets/` | `?project=`, `?category=` |
| Usuarios | `/api/users/` | |
| Notificaciones | `/api/notifications/` | |

### CRM
| Recurso | Endpoint | Filtros |
|---------|----------|---------|
| Clientes | `/api/clients/` | |
| Oportunidades | `/api/opportunities/` | `?client=`, `?stage=` |
| Bitácora | `/api/opportunity-activities/` | `?opportunity=` |
| Cotizaciones | `/api/quotes/` | `?opportunity=` |
| Productos | `/api/products/` | `?active=1` |
| Tipos de cambio | `/api/exchange-rates/` | |
| Hojas de gastos | `/api/expense-sheets/` | `?opportunity=` |
| Gastos de ejecución | `/api/project-expenses/` | `?project=` |
| Conceptos de gasto | `/api/expense-concepts/` | `?block=`, `?active=1` |
| Plantilla de cotización | `/api/quote-template/` | GET todos, PUT/PATCH solo staff |

### Acciones especiales
| Método | Endpoint | Descripción |
|--------|----------|-------------|
| POST | `/api/tasks/{id}/accept/` | Aceptar asignación |
| POST | `/api/tasks/{id}/reject/` | Rechazar asignación |
| GET | `/api/tasks/pending_assignments/` | Mis asignaciones pendientes |
| POST | `/api/tasks/reorder/` | Reordenar tareas |
| GET, POST | `/api/expense-concepts/{id}/rates/` | Historial de valores de un concepto, y agregar uno |
| POST | `/api/expense-concepts/starter/` | Cargar los conceptos básicos, sin valor |
| GET | `/api/projects/{id}/summary/` | Resumen general del proyecto (staff o ventas) |
| POST | `/api/projects/{id}/close/` · `/reopen/` | Cerrar con fecha y conclusiones, o reabrir |
| GET | `/api/projects/{id}/costs/` | Margen cotizado contra margen real (staff o ventas) |
| GET | `/api/quotes/{id}/client-view/` | La cotización sin costos ni márgenes |
| GET | `/api/quotes/{id}/pdf/` | PDF para el cliente (`?download=1` para forzar descarga) |
| GET | `/api/assets/{id}/preview/` | Vista previa de archivo |
| GET | `/api/assets/{id}/parse_eml/` | Parsear correo .eml |
| GET | `/api/assets/{id}/eml_attachment/{index}/` | Descargar adjunto de .eml |
| GET | `/api/notifications/unread_count/` | Notificaciones sin leer |
| POST | `/api/notifications/{id}/mark_read/` | Marcar una como leída |
| POST | `/api/notifications/mark_all_read/` | Marcar todas como leídas |
| POST | `/api/opportunities/{id}/mark_won/` | Ganar oportunidad y crear el proyecto (requiere `team_id`) |
| POST | `/api/opportunities/{id}/mark_lost/` | Perder oportunidad (acepta `reason`) |
| GET | `/api/products/{id}/price_history/` | Historial de costos y precios |
| POST | `/api/products/refresh_costs/` | Recalcular costos importados con la tasa vigente |
| GET | `/api/exchange-rates/current/` | Tasas vigentes |

### Super Admin
| Método | Endpoint | Descripción |
|--------|----------|-------------|
| GET/POST | `/api/organizations/` | CRUD empresas |
| GET | `/api/organizations/{id}/users/` | Usuarios de empresa |
| POST | `/api/organizations/{id}/add_user/` | Agregar usuario a empresa |
| POST | `/api/organizations/{id}/toggle_active/` | Activar/desactivar empresa |
| GET/POST | `/api/plans/` | CRUD planes |

## Estructura del proyecto

```
asanaIP/
├── config/                 # Configuración Django
│   ├── settings.py
│   ├── urls.py
│   └── wsgi.py
├── core/                   # App principal
│   ├── models.py           # Proyectos: User, Organization, Plan, Area, Team,
│   │                       #   Project, Section, Task, Asset, Notification
│   │                       # CRM: Client, Opportunity, OpportunityActivity,
│   │                       #   Quote, QuoteItem, Product, ProductPriceEntry,
│   │                       #   ExchangeRate
│   ├── serializers.py      # Serializers REST + OrgScopedRelatedField
│   ├── views.py            # ViewSets + auth + file preview
│   ├── urls.py             # Router API
│   ├── emails.py           # Avisos por correo
│   ├── notifications.py    # Notificaciones in-app
│   ├── tests.py            # Suite de tests
│   └── admin.py            # Panel admin Django
├── frontend/               # React SPA
│   ├── src/
│   │   ├── App.jsx         # Router + auth
│   │   ├── api.js          # Axios config
│   │   ├── stages.js       # Etapas del pipeline (espeja Opportunity.Stage)
│   │   ├── dates.js        # Formato de fechas y selector de mes
│   │   ├── components/     # Layout, Sidebar, Modal, NotificationBell,
│   │   │                   # ClientFormModal, OutcomeModals, ExchangeRatesModal
│   │   └── pages/          # HomePage, ProjectView, KanbanView, AreaView,
│   │                       # ClientsPage, OpportunitiesPage, PipelineBoard,
│   │                       # OpportunityDetailPage, ProductsPage,
│   │                       # UsersPage, SuperAdminPage, AssetsPanel, LoginPage
│   ├── vite.config.js      # Proxy API
│   └── package.json
├── seed_data.py            # Datos de prueba
├── run.bat                 # Script de inicio rápido
└── manage.py
```

## Licencia

Proyecto privado.
