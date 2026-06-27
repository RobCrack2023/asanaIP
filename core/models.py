from django.contrib.auth.models import AbstractUser
from django.db import models


class User(AbstractUser):
    avatar = models.ImageField(upload_to='avatars/', blank=True, null=True)
    job_title = models.CharField(max_length=100, blank=True)

    class Meta:
        ordering = ['first_name', 'last_name']

    def __str__(self):
        return self.get_full_name() or self.username


class Area(models.Model):
    name = models.CharField(max_length=100)
    description = models.TextField(blank=True)
    color = models.CharField(max_length=7, default='#4573D2')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['name']

    def __str__(self):
        return self.name


class Team(models.Model):
    name = models.CharField(max_length=100)
    area = models.ForeignKey(Area, on_delete=models.CASCADE, related_name='teams')
    description = models.TextField(blank=True)
    members = models.ManyToManyField(User, related_name='teams', blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['name']

    def __str__(self):
        return self.name


class Project(models.Model):
    name = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    team = models.ForeignKey(Team, on_delete=models.CASCADE, related_name='projects')
    color = models.CharField(max_length=7, default='#4573D2')
    owner = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='owned_projects')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-updated_at']

    def __str__(self):
        return self.name


class Section(models.Model):
    name = models.CharField(max_length=200)
    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name='sections')
    order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ['order']

    def __str__(self):
        return f'{self.project.name} / {self.name}'


class Task(models.Model):
    class Priority(models.TextChoices):
        LOW = 'low', 'Baja'
        MEDIUM = 'medium', 'Media'
        HIGH = 'high', 'Alta'
        URGENT = 'urgent', 'Urgente'

    class Status(models.TextChoices):
        PENDING = 'pending', 'Pendiente'
        IN_PROGRESS = 'in_progress', 'En progreso'
        COMPLETED = 'completed', 'Completada'

    class RecurrenceType(models.TextChoices):
        NONE = 'none', 'Sin repetición'
        WEEKLY = 'weekly', 'Semanal'
        MONTHLY = 'monthly', 'Mensual'
        YEARLY = 'yearly', 'Anual'

    class AssignmentStatus(models.TextChoices):
        DIRECT = 'direct', 'Asignación directa'
        PENDING = 'pending_approval', 'Pendiente de aprobación'
        ACCEPTED = 'accepted', 'Aceptada'
        REJECTED = 'rejected', 'Rechazada'

    class Visibility(models.TextChoices):
        PUBLIC = 'public', 'Pública'
        PRIVATE = 'private', 'Privada'

    title = models.CharField(max_length=500)
    description = models.TextField(blank=True)
    section = models.ForeignKey(Section, on_delete=models.CASCADE, related_name='tasks')
    assignee = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='assigned_tasks')
    assigned_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='tasks_assigned_by')
    assignment_status = models.CharField(max_length=20, choices=AssignmentStatus.choices, default=AssignmentStatus.DIRECT)
    visibility = models.CharField(max_length=10, choices=Visibility.choices, default=Visibility.PUBLIC)
    parent = models.ForeignKey('self', on_delete=models.CASCADE, null=True, blank=True, related_name='subtasks')
    priority = models.CharField(max_length=10, choices=Priority.choices, default=Priority.MEDIUM)
    status = models.CharField(max_length=15, choices=Status.choices, default=Status.PENDING)
    start_date = models.DateField(null=True, blank=True)
    due_date = models.DateField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    order = models.PositiveIntegerField(default=0)
    recurrence_type = models.CharField(max_length=10, choices=RecurrenceType.choices, default=RecurrenceType.NONE)
    recurrence_day = models.PositiveSmallIntegerField(null=True, blank=True, help_text='Día: 0-6 para semanal (lun-dom), 1-31 para mensual, ignored para anual (usa due_date)')
    recurrence_end_date = models.DateField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['order']

    def __str__(self):
        return self.title

    def create_next_occurrence(self):
        """Al completar una tarea recurrente, crea la siguiente ocurrencia."""
        from datetime import timedelta
        from calendar import monthrange
        import datetime

        if self.recurrence_type == self.RecurrenceType.NONE:
            return None

        base_date = self.due_date or datetime.date.today()

        if self.recurrence_type == self.RecurrenceType.WEEKLY:
            next_date = base_date + timedelta(weeks=1)
        elif self.recurrence_type == self.RecurrenceType.MONTHLY:
            month = base_date.month + 1
            year = base_date.year
            if month > 12:
                month = 1
                year += 1
            day = min(self.recurrence_day or base_date.day, monthrange(year, month)[1])
            next_date = datetime.date(year, month, day)
        elif self.recurrence_type == self.RecurrenceType.YEARLY:
            next_date = base_date.replace(year=base_date.year + 1)
        else:
            return None

        if self.recurrence_end_date and next_date > self.recurrence_end_date:
            return None

        duration = None
        if self.start_date and self.due_date:
            duration = (self.due_date - self.start_date).days

        new_start = None
        if duration is not None:
            new_start = next_date - timedelta(days=duration)

        new_task = Task.objects.create(
            title=self.title,
            description=self.description,
            section=self.section,
            assignee=self.assignee,
            parent=self.parent,
            priority=self.priority,
            status=self.Status.PENDING,
            start_date=new_start,
            due_date=next_date,
            order=self.order,
            recurrence_type=self.recurrence_type,
            recurrence_day=self.recurrence_day,
            recurrence_end_date=self.recurrence_end_date,
            visibility=self.visibility,
        )
        return new_task
