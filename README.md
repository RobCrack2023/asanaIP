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
- Lectura en CLP, USD, EUR o UF con la tasa con que se emitió

**Catálogo de productos**
- Costo y precio en la misma ficha: el precio se **deriva del costo y el margen**, nunca se teclea
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

### Acciones especiales
| Método | Endpoint | Descripción |
|--------|----------|-------------|
| POST | `/api/tasks/{id}/accept/` | Aceptar asignación |
| POST | `/api/tasks/{id}/reject/` | Rechazar asignación |
| GET | `/api/tasks/pending_assignments/` | Mis asignaciones pendientes |
| POST | `/api/tasks/reorder/` | Reordenar tareas |
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
