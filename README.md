# AsanaIP

Sistema de gestión de proyectos inspirado en Asana, diseñado para equipos de trabajo. Construido con Django REST Framework y React.

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

### Sistema de usuarios y permisos

| Rol | Alcance | Puede hacer |
|-----|---------|-------------|
| **Super Admin** | Global | Crear/gestionar empresas, planes y usuarios |
| **Admin de empresa** | Su organización | Gestionar áreas, equipos, proyectos, usuarios |
| **Usuario regular** | Sus equipos | Ver solo sus tareas y proyectos de sus equipos |

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
- **Sidebar** con navegación jerárquica por áreas/equipos/proyectos
- **Home** con estadísticas, "Mis tareas" con filtros, solicitudes pendientes, tareas delegadas y proyectos recientes
- **Panel de detalle** como overlay lateral para editar tareas
- Diseño responsivo inspirado en Asana
- Login/logout con sesión

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
pip install django djangorestframework django-cors-headers pillow openpyxl python-docx python-dotenv

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

| Usuario | Contraseña | Rol |
|---------|-----------|-----|
| `admin` | `admin123` | Super Admin |
| `carlos` | `pass123` | Desarrollador Senior (Desarrollo Web) |
| `maria` | `pass123` | Diseñadora UX (Diseño) |
| `pedro` | `pass123` | Product Manager (Diseño) |
| `ana` | `pass123` | QA Engineer (Desarrollo Web) |
| `luis` | `pass123` | Marketing Manager (Marketing Digital) |

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
| Tareas | `/api/tasks/` | `?project=`, `?assignee=`, `?status=`, `?assigned_by=` |
| Assets | `/api/assets/` | `?project=`, `?category=` |
| Usuarios | `/api/users/` | |

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
│   ├── models.py           # User, Organization, Plan, Area, Team, Project, Section, Task, Asset
│   ├── serializers.py      # Serializers REST
│   ├── views.py            # ViewSets + auth + file preview
│   ├── urls.py             # Router API
│   └── admin.py            # Panel admin Django
├── frontend/               # React SPA
│   ├── src/
│   │   ├── App.jsx         # Router + auth
│   │   ├── api.js          # Axios config
│   │   ├── components/     # Layout, Sidebar, Modal
│   │   └── pages/          # HomePage, ProjectView, KanbanView,
│   │                       # UsersPage, SuperAdminPage, AreaView,
│   │                       # AssetsPanel, LoginPage
│   ├── vite.config.js      # Proxy API
│   └── package.json
├── seed_data.py            # Datos de prueba
├── run.bat                 # Script de inicio rápido
└── manage.py
```

## Licencia

Proyecto privado.
