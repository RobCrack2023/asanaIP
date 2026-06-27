"""Seed script to populate the database with sample data."""
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from core.models import User, Area, Team, Project, Section, Task

# Create superuser
admin, _ = User.objects.get_or_create(
    username='admin',
    defaults={
        'email': 'admin@asanaip.local',
        'first_name': 'Admin',
        'last_name': 'Principal',
        'is_staff': True,
        'is_superuser': True,
        'job_title': 'Administrador',
    }
)
admin.set_password('admin123')
admin.save()

# Create users
users_data = [
    ('carlos', 'Carlos', 'García', 'Desarrollador Senior'),
    ('maria', 'María', 'López', 'Diseñadora UX'),
    ('pedro', 'Pedro', 'Martínez', 'Product Manager'),
    ('ana', 'Ana', 'Rodríguez', 'QA Engineer'),
    ('luis', 'Luis', 'Hernández', 'Marketing Manager'),
]
users = {}
for username, first, last, title in users_data:
    user, _ = User.objects.get_or_create(
        username=username,
        defaults={
            'email': f'{username}@asanaip.local',
            'first_name': first,
            'last_name': last,
            'job_title': title,
        }
    )
    user.set_password('pass123')
    user.save()
    users[username] = user

# Create areas
tech = Area.objects.get_or_create(name='Tecnología', defaults={'description': 'Desarrollo y soporte técnico', 'color': '#4573D2'})[0]
mkt = Area.objects.get_or_create(name='Marketing', defaults={'description': 'Marketing y comunicación', 'color': '#E8384F'})[0]
product = Area.objects.get_or_create(name='Producto', defaults={'description': 'Gestión de producto', 'color': '#FD9A00'})[0]

# Create teams
dev_team = Team.objects.get_or_create(name='Desarrollo Web', defaults={'area': tech, 'description': 'Equipo de desarrollo frontend y backend'})[0]
dev_team.members.set([admin, users['carlos'], users['ana']])

design_team = Team.objects.get_or_create(name='Diseño', defaults={'area': product, 'description': 'Equipo de diseño UX/UI'})[0]
design_team.members.set([users['maria'], users['pedro']])

mkt_team = Team.objects.get_or_create(name='Marketing Digital', defaults={'area': mkt, 'description': 'Campañas y contenido digital'})[0]
mkt_team.members.set([users['luis']])

# Create projects
proj1 = Project.objects.get_or_create(
    name='Rediseño Portal Web',
    defaults={'team': dev_team, 'color': '#4573D2', 'owner': users['carlos'], 'description': 'Rediseño completo del portal principal'}
)[0]

proj2 = Project.objects.get_or_create(
    name='App Móvil v2',
    defaults={'team': dev_team, 'color': '#7C3AED', 'owner': admin, 'description': 'Segunda versión de la aplicación móvil'}
)[0]

proj3 = Project.objects.get_or_create(
    name='Campaña Q3',
    defaults={'team': mkt_team, 'color': '#E8384F', 'owner': users['luis'], 'description': 'Campaña de marketing del tercer trimestre'}
)[0]

# Create sections and tasks for "Rediseño Portal Web"
backlog = Section.objects.get_or_create(name='Backlog', project=proj1, defaults={'order': 0})[0]
doing = Section.objects.get_or_create(name='En Progreso', project=proj1, defaults={'order': 1})[0]
review = Section.objects.get_or_create(name='En Revisión', project=proj1, defaults={'order': 2})[0]
done = Section.objects.get_or_create(name='Completado', project=proj1, defaults={'order': 3})[0]

tasks_data = [
    (backlog, 'Definir paleta de colores', users['maria'], 'high', 'pending', 0),
    (backlog, 'Crear wireframes de la home', users['maria'], 'high', 'pending', 1),
    (backlog, 'Investigar frameworks CSS', users['carlos'], 'medium', 'pending', 2),
    (doing, 'Configurar proyecto React', users['carlos'], 'high', 'in_progress', 0),
    (doing, 'Diseñar componentes base', users['maria'], 'medium', 'in_progress', 1),
    (review, 'Maqueta de la landing page', users['carlos'], 'high', 'in_progress', 0),
    (done, 'Documento de requerimientos', users['pedro'], 'urgent', 'completed', 0),
    (done, 'Setup del repositorio', admin, 'high', 'completed', 1),
]

for section, title, assignee, priority, status, order in tasks_data:
    Task.objects.get_or_create(
        title=title,
        section=section,
        defaults={
            'assignee': assignee,
            'priority': priority,
            'status': status,
            'order': order,
        }
    )

# Sections and tasks for "App Móvil v2"
s1 = Section.objects.get_or_create(name='Por hacer', project=proj2, defaults={'order': 0})[0]
s2 = Section.objects.get_or_create(name='En desarrollo', project=proj2, defaults={'order': 1})[0]

Task.objects.get_or_create(title='Configurar React Native', section=s1, defaults={'assignee': users['carlos'], 'priority': 'high', 'status': 'pending', 'order': 0})
Task.objects.get_or_create(title='Diseñar pantalla de login', section=s1, defaults={'assignee': users['maria'], 'priority': 'medium', 'status': 'pending', 'order': 1})
Task.objects.get_or_create(title='API de autenticación', section=s2, defaults={'assignee': admin, 'priority': 'high', 'status': 'in_progress', 'order': 0})

print('Datos de prueba creados exitosamente!')
print(f'  - {User.objects.count()} usuarios')
print(f'  - {Area.objects.count()} áreas')
print(f'  - {Team.objects.count()} equipos')
print(f'  - {Project.objects.count()} proyectos')
print(f'  - {Section.objects.count()} secciones')
print(f'  - {Task.objects.count()} tareas')
print()
print('Credenciales:')
print('  Admin: admin / admin123')
print('  Usuarios: carlos, maria, pedro, ana, luis / pass123')
