from decimal import Decimal

from django.contrib.auth.models import AbstractUser
from django.db import models
from django.utils import timezone


class Plan(models.Model):
    name = models.CharField(max_length=50)
    max_users = models.PositiveIntegerField(default=10)
    max_projects = models.PositiveIntegerField(default=20)
    price = models.DecimalField(max_digits=10, decimal_places=2, default=0)

    def __str__(self):
        return self.name


class Organization(models.Model):
    name = models.CharField(max_length=200)
    slug = models.SlugField(unique=True)
    logo = models.ImageField(upload_to='org_logos/', blank=True, null=True)
    plan = models.ForeignKey(Plan, on_delete=models.SET_NULL, null=True, blank=True)
    max_users = models.PositiveIntegerField(default=10)
    is_active = models.BooleanField(default=True)
    # Last number handed to a quote. Never decreases, so numbering stays unique
    # even when a quote is deleted.
    quote_counter = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['name']

    def __str__(self):
        return self.name

    @property
    def users_count(self):
        return self.members.filter(is_active=True).count()

    @property
    def projects_count(self):
        return Project.objects.filter(team__area__organization=self).count()


class User(AbstractUser):
    avatar = models.ImageField(upload_to='avatars/', blank=True, null=True)
    job_title = models.CharField(max_length=100, blank=True)
    organization = models.ForeignKey(Organization, on_delete=models.SET_NULL, null=True, blank=True, related_name='members')
    is_super_admin = models.BooleanField(default=False)
    is_sales = models.BooleanField(default=False)

    class Meta:
        ordering = ['first_name', 'last_name']

    def __str__(self):
        return self.get_full_name() or self.username


class Area(models.Model):
    name = models.CharField(max_length=100)
    description = models.TextField(blank=True)
    color = models.CharField(max_length=7, default='#4573D2')
    organization = models.ForeignKey(Organization, on_delete=models.CASCADE, related_name='areas', null=True)
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
    section = models.ForeignKey(Section, on_delete=models.CASCADE, related_name='tasks', null=True, blank=True)
    opportunity = models.ForeignKey('Opportunity', on_delete=models.SET_NULL, null=True, blank=True, related_name='tasks')
    assignee = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='assigned_tasks')
    assigned_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='tasks_assigned_by')
    assignment_status = models.CharField(max_length=20, choices=AssignmentStatus.choices, default=AssignmentStatus.DIRECT)
    visibility = models.CharField(max_length=10, choices=Visibility.choices, default=Visibility.PUBLIC)
    parent = models.ForeignKey('self', on_delete=models.CASCADE, null=True, blank=True, related_name='subtasks')
    priority = models.CharField(max_length=10, choices=Priority.choices, default=Priority.MEDIUM)
    status = models.CharField(max_length=15, choices=Status.choices, default=Status.PENDING)
    completion_note = models.TextField(blank=True)
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


class Asset(models.Model):
    class AssetType(models.TextChoices):
        FILE = 'file', 'Archivo'
        LINK = 'link', 'Enlace'
        EMAIL = 'email', 'Correo'

    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name='assets')
    task = models.ForeignKey(Task, on_delete=models.SET_NULL, null=True, blank=True, related_name='assets')
    asset_type = models.CharField(max_length=10, choices=AssetType.choices, default=AssetType.FILE)
    name = models.CharField(max_length=300)
    file = models.FileField(upload_to='assets/%Y/%m/', blank=True, null=True)
    url = models.URLField(max_length=1000, blank=True)
    file_size = models.PositiveIntegerField(default=0)
    mime_type = models.CharField(max_length=100, blank=True)
    uploaded_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='uploaded_assets')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return self.name

    @property
    def file_extension(self):
        if self.file and self.file.name:
            return self.file.name.rsplit('.', 1)[-1].lower() if '.' in self.file.name else ''
        return ''

    @property
    def category(self):
        ext = self.file_extension
        if self.asset_type == self.AssetType.LINK:
            return 'link'
        if self.asset_type == self.AssetType.EMAIL or ext == 'eml':
            return 'email'
        if ext in ('jpg', 'jpeg', 'png', 'gif', 'webp', 'svg', 'bmp'):
            return 'image'
        if ext in ('pdf',):
            return 'pdf'
        if ext in ('doc', 'docx'):
            return 'word'
        if ext in ('xls', 'xlsx', 'csv'):
            return 'excel'
        if ext in ('ppt', 'pptx'):
            return 'powerpoint'
        return 'other'


class Notification(models.Model):
    class Verb(models.TextChoices):
        TASK_ASSIGNED = 'task_assigned', 'Asignación pendiente de aprobación'
        TASK_ASSIGNED_DIRECT = 'task_assigned_direct', 'Tarea asignada'
        ASSIGNMENT_ACCEPTED = 'assignment_accepted', 'Asignación aceptada'
        ASSIGNMENT_REJECTED = 'assignment_rejected', 'Asignación rechazada'
        OPPORTUNITY_WON = 'opportunity_won', 'Oportunidad ganada — proyecto creado'

    recipient = models.ForeignKey(User, on_delete=models.CASCADE, related_name='notifications')
    actor = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='+')
    verb = models.CharField(max_length=30, choices=Verb.choices)
    task = models.ForeignKey(Task, on_delete=models.SET_NULL, null=True, blank=True, related_name='notifications')
    message = models.CharField(max_length=255)
    is_read = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return self.message


class Client(models.Model):
    organization = models.ForeignKey(Organization, on_delete=models.CASCADE, related_name='clients')
    name = models.CharField(max_length=200)
    contact_name = models.CharField(max_length=200, blank=True)
    email = models.EmailField(blank=True)
    phone = models.CharField(max_length=50, blank=True)
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['name']

    def __str__(self):
        return self.name


class Product(models.Model):
    """Catalog of products and services quoted to clients."""

    organization = models.ForeignKey(Organization, on_delete=models.CASCADE, related_name='products')
    name = models.CharField(max_length=200)
    sku = models.CharField(max_length=50, blank=True)
    description = models.TextField(blank=True)
    unit = models.CharField(max_length=20, blank=True, default='unidad')
    unit_price = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['name']
        constraints = [
            models.UniqueConstraint(
                fields=['organization', 'sku'],
                condition=~models.Q(sku=''),
                name='unique_sku_per_organization',
            ),
        ]

    def __str__(self):
        return self.name


class Opportunity(models.Model):
    class Stage(models.TextChoices):
        PROSPECTO = 'prospecto', 'Prospecto'
        COTIZACION_ENVIADA = 'cotizacion_enviada', 'Cotización enviada'
        NEGOCIACION = 'negociacion', 'Negociación'
        GANADA = 'ganada', 'Ganada'
        PERDIDA = 'perdida', 'Perdida'

    organization = models.ForeignKey(Organization, on_delete=models.CASCADE, related_name='opportunities')
    client = models.ForeignKey(Client, on_delete=models.CASCADE, related_name='opportunities')
    name = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    stage = models.CharField(max_length=20, choices=Stage.choices, default=Stage.PROSPECTO)
    estimated_amount = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    owner = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='owned_opportunities')
    expected_close_date = models.DateField(null=True, blank=True)
    lost_reason = models.CharField(max_length=255, blank=True)
    project = models.ForeignKey(Project, on_delete=models.SET_NULL, null=True, blank=True, related_name='opportunities')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-updated_at']

    def __str__(self):
        return f'{self.name} ({self.client.name})'

    def mark_won(self, team, user=None):
        from django.db import transaction

        if self.stage == self.Stage.GANADA:
            return self.project

        with transaction.atomic():
            previous = self.stage
            project = Project.objects.create(
                name=self.name,
                description=f'Proyecto generado desde la oportunidad "{self.name}" ({self.client.name}).',
                team=team,
                owner=user or self.owner,
            )
            section = Section.objects.create(name='General', project=project, order=0)
            self.tasks.update(section=section)
            self.project = project
            self.stage = self.Stage.GANADA
            self.save(update_fields=['project', 'stage', 'updated_at'])
            OpportunityActivity.objects.create(
                opportunity=self,
                kind=OpportunityActivity.Kind.WON,
                body=f'Proyecto "{project.name}" creado en el equipo {team.name}.',
                from_stage=previous,
                to_stage=self.stage,
                author=user,
            )
        return project

    def mark_lost(self, reason='', user=None):
        previous = self.stage
        self.stage = self.Stage.PERDIDA
        self.lost_reason = reason
        self.save(update_fields=['stage', 'lost_reason', 'updated_at'])
        OpportunityActivity.objects.create(
            opportunity=self,
            kind=OpportunityActivity.Kind.LOST,
            body=reason,
            from_stage=previous,
            to_stage=self.stage,
            author=user,
        )

    def log_stage_change(self, previous, user=None):
        """Record a stage move that did not come through mark_won / mark_lost."""
        if previous == self.stage:
            return None
        kind = OpportunityActivity.Kind.STAGE_CHANGE
        if self.stage == self.Stage.GANADA:
            kind = OpportunityActivity.Kind.WON
        elif self.stage == self.Stage.PERDIDA:
            kind = OpportunityActivity.Kind.LOST
        return OpportunityActivity.objects.create(
            opportunity=self,
            kind=kind,
            from_stage=previous,
            to_stage=self.stage,
            author=user,
        )


class Quote(models.Model):
    class Status(models.TextChoices):
        DRAFT = 'draft', 'Borrador'
        SENT = 'sent', 'Enviada'
        APPROVED = 'approved', 'Aprobada'
        REJECTED = 'rejected', 'Rechazada'

    #: Chile's VAT. Stored per quote so past documents keep the rate they were issued with.
    DEFAULT_TAX_RATE = Decimal('19.00')

    opportunity = models.ForeignKey(Opportunity, on_delete=models.CASCADE, related_name='quotes')
    # Denormalized from the opportunity: the running number is per company and
    # needs a database constraint, which cannot span a relation.
    organization = models.ForeignKey(Organization, on_delete=models.CASCADE, related_name='quotes')
    number = models.PositiveIntegerField(null=True, blank=True)
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.DRAFT)
    issue_date = models.DateField(default=timezone.localdate)
    valid_until = models.DateField(null=True, blank=True)
    tax_rate = models.DecimalField(max_digits=5, decimal_places=2, default=DEFAULT_TAX_RATE)
    # Derived from the items by recalculate(); never written by the client.
    subtotal = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    tax_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    total_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']
        constraints = [
            models.UniqueConstraint(
                fields=['organization', 'number'],
                condition=models.Q(number__isnull=False),
                name='unique_quote_number_per_organization',
            ),
        ]

    def __str__(self):
        return f'{self.reference} — {self.opportunity.name}'

    @property
    def reference(self):
        return f'Cotización N° {self.number}' if self.number else 'Cotización sin número'

    @property
    def is_expired(self):
        return bool(self.valid_until and self.valid_until < timezone.localdate())

    def assign_number(self):
        """Take the next running number from the company's counter.

        The counter only ever moves forward, so a number that reached a client
        is never handed to a second document — deleting a quote leaves a gap
        rather than freeing its number. Must run inside a transaction.
        """
        if self.number:
            return self.number
        organization = (
            Organization.objects.select_for_update().get(pk=self.organization_id)
        )
        organization.quote_counter += 1
        organization.save(update_fields=['quote_counter'])
        self.number = organization.quote_counter
        return self.number

    def recalculate(self, save=True):
        subtotal = sum((item.subtotal for item in self.items.all()), Decimal('0'))
        self.subtotal = subtotal.quantize(Decimal('0.01'))
        self.tax_amount = (self.subtotal * self.tax_rate / Decimal('100')).quantize(Decimal('0.01'))
        self.total_amount = self.subtotal + self.tax_amount
        if save:
            self.save(update_fields=['subtotal', 'tax_amount', 'total_amount', 'updated_at'])
        return self.total_amount


class QuoteItem(models.Model):
    """A line on a quote.

    The product is a pointer for reporting, but description and unit_price are
    copied at the time of quoting: editing the catalog later must not silently
    rewrite a document already sent to a client.
    """

    quote = models.ForeignKey(Quote, on_delete=models.CASCADE, related_name='items')
    product = models.ForeignKey(Product, on_delete=models.SET_NULL, null=True, blank=True,
                               related_name='quote_items')
    description = models.CharField(max_length=200)
    unit = models.CharField(max_length=20, blank=True, default='unidad')
    quantity = models.DecimalField(max_digits=12, decimal_places=2, default=1)
    unit_price = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    discount_percent = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ['order', 'id']

    def __str__(self):
        return f'{self.description} x{self.quantity}'

    @property
    def subtotal(self):
        gross = self.quantity * self.unit_price
        discount = gross * self.discount_percent / Decimal('100')
        return (gross - discount).quantize(Decimal('0.01'))


class OpportunityActivity(models.Model):
    """One timeline per opportunity: what the team did, and how the stage moved.

    Manual entries (notes, calls, meetings, emails) and system entries (stage
    moves) share a table so the detail page renders a single chronological
    story instead of stitching two lists together.
    """

    class Kind(models.TextChoices):
        NOTE = 'note', 'Nota'
        CALL = 'call', 'Llamada'
        MEETING = 'meeting', 'Reunión'
        EMAIL = 'email', 'Correo'
        STAGE_CHANGE = 'stage_change', 'Cambio de etapa'
        WON = 'won', 'Oportunidad ganada'
        LOST = 'lost', 'Oportunidad perdida'

    #: Kinds a user may post through the API; the rest are written by the system.
    MANUAL_KINDS = (Kind.NOTE, Kind.CALL, Kind.MEETING, Kind.EMAIL)

    opportunity = models.ForeignKey(Opportunity, on_delete=models.CASCADE, related_name='activities')
    kind = models.CharField(max_length=20, choices=Kind.choices, default=Kind.NOTE)
    body = models.TextField(blank=True)
    from_stage = models.CharField(max_length=20, blank=True)
    to_stage = models.CharField(max_length=20, blank=True)
    # Separate from created_at so a call can be logged after it happened.
    occurred_at = models.DateTimeField(default=timezone.now)
    author = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='+')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-occurred_at', '-id']
        verbose_name_plural = 'opportunity activities'

    def __str__(self):
        return f'{self.get_kind_display()} — {self.opportunity.name}'

    @property
    def is_system(self):
        return self.kind not in self.MANUAL_KINDS
