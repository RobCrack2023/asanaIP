from decimal import Decimal

from django.contrib.auth.models import AbstractUser
from django.db import models
from django.utils import timezone


def commission_on(profit, rate):
    """What a seller is owed: a percentage of the profit, never of the sale.

    A deal that loses money owes no commission — and never a negative one,
    which would turn the seller into a debtor of the company. Kept in one place
    because the quote and the project both need it, and they must agree.
    """
    return (max(Decimal(profit), Decimal('0')) * Decimal(rate) / Decimal('100')).quantize(
        Decimal('0.01'))


def markup(price, cost):
    """Margin the way the evaluación spreadsheets state it: price / cost - 1.

    Selling at three times cost is a margin of 2.0, not 0.67 — this is markup
    over cost, not gross margin over the sale price. Returns None when there
    is no cost to mark up, since dividing by zero would report an infinite
    margin on an item that is simply not costed yet.
    """
    if not cost:
        return None
    return ((Decimal(price) / Decimal(cost)) - Decimal('1')).quantize(Decimal('0.0001'))


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
    # ── What the deal promised ────────────────────────────────────────────
    # Stamped when the opportunity is won, never recomputed: the quote may be
    # edited or deleted afterwards, and the yardstick has to stay the one the
    # project was sold on.
    budget_cost = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    budget_sale = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    #: The winning quote's cost split, frozen with the rest. Stored rather
    #: than read back through a relation for the same reason as the totals:
    #: the quote can be edited or deleted, the promise cannot.
    budget_categories = models.JSONField(default=list, blank=True)
    #: The part of the budget that is an estimate to be consumed by expenses.
    budget_provision = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    #: Frozen with the rest: the seller and the rate the deal was sold under.
    commission_rate = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    commission_to = models.CharField(max_length=120, blank=True)
    #: Set when the project is closed: the books are shut, so nothing more is
    #: recorded against it until it is reopened. Closing changes nothing about
    #: the figures — the summary reads the same open or closed — it marks the day
    #: the project stopped moving, and carries what was concluded.
    closed_on = models.DateField(null=True, blank=True)
    closed_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True,
                                  related_name='+')
    closing_notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-updated_at']

    def __str__(self):
        return self.name

    @property
    def is_closed(self):
        return self.closed_on is not None

    @property
    def expense_total(self):
        return sum((expense.amount for expense in self.expenses.all()), Decimal('0'))

    @property
    def cost_summary(self):
        """What the deal promised against what it is really costing.

        Two kinds of cost sit in a budget. The fixed ones — the datalogger, the
        labour — are what they were quoted. A provision — the operating expenses —
        is an estimate standing in for what will be spent: once expenses are
        recorded they REPLACE it, they are not added to it, or the same trip would
        be counted twice. Whatever is spent beyond the provision simply adds to
        the cost, which is how an overrun like the tyre shows up.

        With no provision the formula collapses to budget plus expenses, so a
        project quoted without one behaves exactly as before.

        The sale does not move — the client accepted a document — so every extra
        peso comes straight out of the profit, and the commission, which is a
        share of that profit, moves with it.
        """
        spent = self.expense_total
        provision = self.budget_provision
        real_cost = self.budget_cost - provision + spent

        quoted_profit = self.budget_sale - self.budget_cost
        real_profit = self.budget_sale - real_cost
        budget_commission = commission_on(quoted_profit, self.commission_rate)
        real_commission = commission_on(real_profit, self.commission_rate)

        return {
            'budget_cost': self.budget_cost,
            'extra_cost': spent,
            'real_cost': real_cost,
            'budget_sale': self.budget_sale,
            'quoted_margin': markup(self.budget_sale, self.budget_cost),
            'real_margin': markup(self.budget_sale, real_cost),
            'quoted_profit': quoted_profit,
            'real_profit': real_profit,
            # What is left of the estimate. Negative means the expenses went past it.
            'provision': provision,
            'provision_balance': provision - spent,
            'commission_rate': self.commission_rate,
            'commission_to': self.commission_to,
            'budget_commission': budget_commission,
            'real_commission': real_commission,
            'quoted_net_profit': quoted_profit - budget_commission,
            'real_net_profit': real_profit - real_commission,
            'by_category': self.cost_by_category,
            'is_closed': self.is_closed,
            'closed_on': self.closed_on,
        }

    @property
    def cost_by_category(self):
        """Budgeted, provisioned, spent, and what that adds up to, per kind of cost.

        The budget side comes from the quote's own split, so the comparison
        runs on the same categories the deal was priced with — and an expense
        in a category nobody budgeted for still shows, which is the whole
        point of recording the tyre. The real cost of a category is its budget,
        less the part that was only an estimate, plus what was actually spent.
        """
        budget = {row['category']: Decimal(row['cost']) for row in self.budget_categories}
        provisioned = {row['category']: Decimal(row.get('provision', '0'))
                       for row in self.budget_categories}

        spent = {}
        for expense in self.expenses.all():
            spent[expense.category] = spent.get(expense.category, Decimal('0')) + expense.amount

        labels = dict(CostCategory.choices)
        # Zero to two places like every other money figure, so a side that was
        # never budgeted or never spent still reads as an amount.
        nothing = Decimal('0.00')

        rows = []
        for category in CostCategory.values:
            if category not in budget and category not in spent:
                continue
            budgeted = budget.get(category, nothing)
            estimate = provisioned.get(category, nothing)
            extra = spent.get(category, nothing)
            rows.append({
                'category': category,
                'label': labels[category],
                'budget': budgeted,
                'provision': estimate,
                'extra': extra,
                'real': budgeted - estimate + extra,
            })
        return rows

    def stamp_budget(self, quote):
        """Freeze what the deal promised, at the moment it is won."""
        if quote is None:
            return
        self.budget_cost = quote.total_cost
        self.budget_sale = quote.subtotal
        # Decimals are not JSON, and the strings are read back as Decimal
        # rather than float so the comparison never drifts by a cent.
        self.budget_categories = [
            {'category': row['category'], 'label': row['label'], 'cost': str(row['cost']),
             'provision': str(row['provision'])}
            for row in quote.category_totals
        ]
        self.budget_provision = quote.provision_total
        self.commission_rate = quote.commission_rate
        self.commission_to = quote.commission_to


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


class Currency(models.TextChoices):
    CLP = 'CLP', 'Peso chileno'
    USD = 'USD', 'Dólar'
    EUR = 'EUR', 'Euro'
    UF = 'UF', 'UF'


class CostCategory(models.TextChoices):
    """What kind of cost a line is, not who supplies it.

    The Cálculo sheet mixes equipment, own labour and operating expenses in one
    list and tells them apart only by writing "I&P" in the supplier column, so
    nobody can answer how much of a deal is equipment and how much is expenses.
    Naming the kind makes that a query instead of a reading exercise.

    The margins each one carries are very different in practice — imported
    equipment around 30%, own labour 180-380%, operating expenses 15-20% — so
    a blended margin says little until it is broken down.
    """

    EQUIPO = 'equipo', 'Equipo o material'
    SERVICIO = 'servicio', 'Servicio propio'
    GASTO = 'gasto', 'Gasto operacional'
    FLETE = 'flete', 'Flete y traslado'
    PREVENCION = 'prevencion', 'Prevención y EPP'
    OTRO = 'otro', 'Otro'


class Incoterm(models.TextChoices):
    DDP = 'DDP', 'DDP — entregado con derechos pagados'
    DAP = 'DAP', 'DAP — entregado en destino'
    CIF = 'CIF', 'CIF — costo, seguro y flete'
    FOB = 'FOB', 'FOB — libre a bordo'
    EXW = 'EXW', 'EXW — en fábrica'


class ExchangeRate(models.Model):
    """The UF, dollar and euro as of a given day, per company.

    The evaluación sheets keep these in three cells the team retypes from the
    Banco Central; here they are dated rows, so a cost converted last March
    can still be explained with the rate that was in force then.
    """

    organization = models.ForeignKey(Organization, on_delete=models.CASCADE,
                                     related_name='exchange_rates')
    date = models.DateField(default=timezone.localdate)
    uf = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    usd = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    eur = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    updated_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True,
                                   related_name='+')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-date', '-id']
        constraints = [
            models.UniqueConstraint(fields=['organization', 'date'],
                                    name='unique_exchange_rate_per_day'),
        ]

    def __str__(self):
        return f'{self.date}: UF {self.uf} · USD {self.usd} · EUR {self.eur}'

    @classmethod
    def current_for(cls, organization):
        return cls.objects.filter(organization=organization).first()

    def rate_for(self, currency):
        """How many pesos one unit of `currency` is worth."""
        if currency == Currency.CLP:
            return Decimal('1')
        return getattr(self, currency.lower(), Decimal('0')) or Decimal('0')


class Product(models.Model):
    """Shared master catalog of products and services quoted to clients.

    Carries both sides of the deal: what the item costs landed (`cost`) and
    what it is sold for (`unit_price`). Every change to either is kept in
    price_history, so a price can always be explained months later.

    An imported item is priced in its supplier's currency; `cost` is the
    landed CLP figure derived from it, and `cost_rate` remembers the rate
    that produced it so a stale conversion can be spotted.
    """

    organization = models.ForeignKey(Organization, on_delete=models.CASCADE, related_name='products')
    name = models.CharField(max_length=200)
    sku = models.CharField(max_length=50, blank=True)
    description = models.TextField(blank=True)
    unit = models.CharField(max_length=20, blank=True, default='unidad')
    #: What kind of cost this is. A catalog entry for "Gastos operacionales
    #: para instalación" is as legitimate as one for a datalogger — the Cálculo
    #: sheet already keeps both in the same list.
    category = models.CharField(max_length=12, choices=CostCategory.choices,
                                default=CostCategory.EQUIPO)
    #: What the supplier charges, in their own currency.
    currency = models.CharField(max_length=3, choices=Currency.choices, default=Currency.CLP)
    cost_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    #: Freight, duties and handling on top of the supplier's price. Only
    #: applied when the supplier is not delivering duty paid — see landed_cost.
    import_multiplier = models.DecimalField(max_digits=6, decimal_places=4, default=1)
    incoterm = models.CharField(max_length=10, choices=Incoterm.choices, default=Incoterm.DDP)
    #: Rate that produced `cost`; 1 for anything priced in pesos.
    cost_rate = models.DecimalField(max_digits=12, decimal_places=2, default=1)
    #: Landed cost in CLP — the DDP figure, import charges already included.
    cost = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    #: Markup applied to the cost to reach the price, as a fraction: 0.30 is
    #: a 30% markup. Quotes start from this and may override it per deal.
    default_margin = models.DecimalField(max_digits=8, decimal_places=4, default=0)
    #: Derived from cost and default_margin; kept stored so the catalog can be
    #: listed and searched by price without recomputing every row.
    unit_price = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    supplier = models.CharField(max_length=200, blank=True)
    lead_time_days = models.PositiveIntegerField(null=True, blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    #: Fields whose change is worth a history entry.
    PRICED_FIELDS = ('cost', 'unit_price', 'supplier')

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

    @property
    def margin(self):
        """Markup over cost, the convention used in the evaluación sheets.

        A margin of 3.0 means the item sells for four times its cost. This is
        deliberately not gross margin over the sale price — the two produce
        very different numbers and the team reads this one.
        """
        return self.default_margin if self.cost else None

    def apply_margin(self):
        """Restate the price from the cost and the default margin."""
        self.unit_price = (self.cost * (Decimal('1') + self.default_margin)).quantize(Decimal('0.01'))
        return self.unit_price

    @property
    def unit_profit(self):
        return self.unit_price - self.cost

    def landed_cost(self, rate):
        """Supplier price in pesos, import charges added only when we bear them.

        Under DDP the supplier delivers duty paid, so freight and duties are
        already inside their price and the multiplier must not be applied —
        this is what the Cálculo sheet's IF(Incoterm="DDP", ...) encodes.
        Applying it regardless would overstate every DDP cost.
        """
        converted = self.cost_amount * Decimal(rate)
        if self.incoterm == Incoterm.DDP:
            return converted.quantize(Decimal('0.01'))
        return (converted * self.import_multiplier).quantize(Decimal('0.01'))

    def apply_rate(self, rate):
        """Restate the landed cost at `rate`, and the price that follows it."""
        self.cost_rate = Decimal(rate)
        self.cost = self.landed_cost(rate)
        self.apply_margin()
        return self.cost

    def cost_is_stale(self, rates):
        """True when today's rate would produce a different landed cost.

        Rates are not applied automatically: silently rewriting the catalog
        every time the dollar moves would make the price history meaningless
        and change quotes in progress. The flag lets the UI offer the update.
        """
        if self.currency == Currency.CLP or rates is None:
            return False
        return rates.rate_for(self.currency) != self.cost_rate

    def record_price(self, user=None, note=''):
        return ProductPriceEntry.objects.create(
            product=self,
            cost=self.cost,
            cost_amount=self.cost_amount,
            currency=self.currency,
            cost_rate=self.cost_rate,
            unit_price=self.unit_price,
            supplier=self.supplier,
            note=note,
            recorded_by=user,
        )


class ProductPriceEntry(models.Model):
    """What a product cost and sold for at a point in time.

    Written whenever cost, price or supplier changes, so the catalog can
    answer "what were we paying for this in 2024, and who supplied it?".
    """

    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='price_history')
    cost = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    #: What the supplier charged and at what rate, so a jump in the landed
    #: cost can be told apart from a jump in the exchange rate.
    cost_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    currency = models.CharField(max_length=3, choices=Currency.choices, default=Currency.CLP)
    cost_rate = models.DecimalField(max_digits=12, decimal_places=2, default=1)
    unit_price = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    supplier = models.CharField(max_length=200, blank=True)
    note = models.CharField(max_length=255, blank=True)
    recorded_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True,
                                    related_name='+')
    recorded_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-recorded_at', '-id']
        verbose_name_plural = 'product price entries'

    def __str__(self):
        return f'{self.product.name} — {self.recorded_at:%Y-%m-%d}'

    @property
    def margin(self):
        return markup(self.unit_price, self.cost)


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

    @property
    def winning_quote(self):
        """The quote the deal was closed on.

        The approved one when there is one; otherwise the latest, which is what
        a team that never marks a quote approved will have been discussing.
        """
        return (self.quotes.filter(status=Quote.Status.APPROVED).first()
                or self.quotes.first())

    def mark_won(self, team=None, user=None, project=None):
        """Close the deal as won and put a project behind it.

        Normally the project is created here, in `team`. Pass `project` to attach
        one that already exists instead — work that was done before the deal was
        recorded, which is how a company starts using the system with real
        history. Either way the project takes the quote's budget as its yardstick.
        """
        from django.db import transaction

        if self.stage == self.Stage.GANADA:
            return self.project

        if project is None and team is None:
            raise ValueError('Hace falta un equipo para crear el proyecto.')
        if project is not None:
            taken = Opportunity.objects.filter(project=project).exclude(pk=self.pk)
            if taken.exists():
                raise ValueError('Ese proyecto ya está vinculado a otra oportunidad.')

        with transaction.atomic():
            previous = self.stage
            created = project is None
            if created:
                project = Project(
                    name=self.name,
                    description=f'Proyecto generado desde la oportunidad "{self.name}" ({self.client.name}).',
                    team=team,
                    owner=user or self.owner,
                )
            # The project inherits what the deal promised, so what it ends up
            # costing can be held against something.
            project.stamp_budget(self.winning_quote)
            project.save()
            section = project.sections.first() or Section.objects.create(
                name='General', project=project, order=0)
            self.tasks.update(section=section)
            self.project = project
            self.stage = self.Stage.GANADA
            self.save(update_fields=['project', 'stage', 'updated_at'])
            OpportunityActivity.objects.create(
                opportunity=self,
                kind=OpportunityActivity.Kind.WON,
                body=(f'Proyecto "{project.name}" creado en el equipo {team.name}.'
                      if created else f'Proyecto "{project.name}" vinculado.'),
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
    #: Rates in force when the quote was issued. Stamped for the same reason
    #: as tax_rate: the document must still read the same a year from now.
    rate_uf = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    rate_usd = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    rate_eur = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    #: Currency the figures are shown in; amounts are always stored in CLP.
    display_currency = models.CharField(max_length=3, choices=Currency.choices,
                                        default=Currency.CLP)
    # Derived from the items by recalculate(); never written by the client.
    subtotal = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    total_cost = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    tax_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    total_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    #: Share of the profit owed to whoever sold the deal, as a percentage like
    #: tax_rate. Internal: it never appears on the client's document. Free text
    #: for the seller because the person is not necessarily a user of the system.
    commission_rate = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    commission_to = models.CharField(max_length=120, blank=True)
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
        items = list(self.items.all())
        subtotal = sum((item.subtotal for item in items), Decimal('0'))
        total_cost = sum((item.cost_subtotal for item in items), Decimal('0'))
        self.subtotal = subtotal.quantize(Decimal('0.01'))
        self.total_cost = total_cost.quantize(Decimal('0.01'))
        self.tax_amount = (self.subtotal * self.tax_rate / Decimal('100')).quantize(Decimal('0.01'))
        self.total_amount = self.subtotal + self.tax_amount
        if save:
            self.save(update_fields=['subtotal', 'total_cost', 'tax_amount', 'total_amount',
                                     'updated_at'])
        return self.total_amount

    @property
    def total_profit(self):
        """Profit on the net figure — tax is collected for the state, not earned."""
        return self.subtotal - self.total_cost

    @property
    def margin(self):
        return markup(self.subtotal, self.total_cost)

    @property
    def commission_amount(self):
        """Owed to the seller: the rate over the profit, before the commission.

        The evaluación spreadsheet does the same: it shows the commission under
        the profit instead of subtracting it from the cost, so the margin keeps
        meaning what it always meant.
        """
        return commission_on(self.total_profit, self.commission_rate)

    @property
    def net_profit(self):
        """What is left once the seller has been paid."""
        return self.total_profit - self.commission_amount

    @property
    def provision_total(self):
        return sum((item.cost_subtotal for item in self.items.all() if item.is_provision),
                   Decimal('0')).quantize(Decimal('0.01'))

    @property
    def client_items(self):
        """The lines the client is shown. Internal costs never leave the company."""
        return [item for item in self.items.all() if not item.is_internal]

    @property
    def category_totals(self):
        """Cost, sale and margin split by kind of cost.

        This is the number the evaluación spreadsheet cannot give: a blended
        38% margin hides that the equipment carried 30% and the operating
        expenses were quoted almost at cost. Only categories actually used
        appear, in the order CostCategory declares them.
        """
        buckets = {}
        for item in self.items.all():
            bucket = buckets.setdefault(item.category, {'cost': Decimal('0'),
                                                        'sale': Decimal('0'),
                                                        'provision': Decimal('0.00')})
            bucket['cost'] += item.cost_subtotal
            bucket['sale'] += item.subtotal
            if item.is_provision:
                bucket['provision'] += item.cost_subtotal

        total_cost = sum((b['cost'] for b in buckets.values()), Decimal('0'))
        total_sale = sum((b['sale'] for b in buckets.values()), Decimal('0'))
        labels = dict(CostCategory.choices)

        rows = []
        for category in CostCategory.values:
            bucket = buckets.get(category)
            if bucket is None:
                continue
            rows.append({
                'category': category,
                'label': labels[category],
                'cost': bucket['cost'],
                'sale': bucket['sale'],
                'provision': bucket['provision'],
                'profit': bucket['sale'] - bucket['cost'],
                'margin': markup(bucket['sale'], bucket['cost']),
                # Share of the deal, so "where does the money go" is readable
                # without dividing in your head.
                'cost_share': (bucket['cost'] / total_cost).quantize(Decimal('0.0001'))
                              if total_cost else None,
                'sale_share': (bucket['sale'] / total_sale).quantize(Decimal('0.0001'))
                              if total_sale else None,
            })
        return rows

    @property
    def display_rate(self):
        """Divisor for showing the CLP figures in display_currency."""
        if self.display_currency == Currency.CLP:
            return Decimal('1')
        rate = getattr(self, f'rate_{self.display_currency.lower()}', Decimal('0'))
        # An unset rate would blank out every figure on the document.
        return rate or Decimal('1')

    def stamp_rates(self, rates):
        if rates is None:
            return
        self.rate_uf, self.rate_usd, self.rate_eur = rates.uf, rates.usd, rates.eur


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
    #: Copied from the product when there is one, like description and price:
    #: reclassifying the catalog later must not restate a quote already sent.
    category = models.CharField(max_length=12, choices=CostCategory.choices,
                                default=CostCategory.EQUIPO)
    unit = models.CharField(max_length=20, blank=True, default='unidad')
    quantity = models.DecimalField(max_digits=12, decimal_places=2, default=1)
    #: Landed cost per unit at the time of quoting, copied from the catalog.
    unit_cost = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    #: Markup for this line, seeded from the product and adjustable per deal.
    #: Null on lines with no cost, where the price is simply stated.
    margin = models.DecimalField(max_digits=8, decimal_places=4, null=True, blank=True)
    unit_price = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    discount_percent = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    #: A cost the company carries on this deal without charging for it: the
    #: salaries and bonuses of the people sent, the operating expenses. It counts
    #: in the cost and so lowers the margin, but it has no price and is never
    #: shown to the client. The evaluación spreadsheet writes these as a margin
    #: of -100%; here they are a kind of line instead, because a price of zero
    #: on a document the client reads would announce what it should not.
    is_internal = models.BooleanField(default=False)
    #: A cost estimated up front that real expenses then consume. Operating
    #: expenses are budgeted as a lump because nobody knows yet whether the trip
    #: will need two nights or three. Once the project runs, what is actually
    #: spent replaces the estimate instead of being added to it — otherwise the
    #: same trip is counted twice, once as the provision and once as the receipts.
    is_provision = models.BooleanField(default=False)
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

    @property
    def cost_subtotal(self):
        return (self.quantity * self.unit_cost).quantize(Decimal('0.01'))

    @property
    def profit(self):
        return self.subtotal - self.cost_subtotal

    @property
    def effective_margin(self):
        """Markup actually achieved once the discount is taken off."""
        return markup(self.subtotal, self.cost_subtotal)

    def apply_margin(self):
        """Price the line from its cost and margin, when there is a cost."""
        if self.is_internal:
            # Nothing is charged, so there is no margin to speak of and no
            # discount to give.
            self.unit_price = Decimal('0.00')
            self.margin = None
            self.discount_percent = Decimal('0')
            return self.unit_price
        if self.unit_cost and self.margin is not None:
            self.unit_price = (self.unit_cost * (Decimal('1') + self.margin)).quantize(Decimal('0.01'))
        return self.unit_price


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


class QuoteTemplate(models.Model):
    """The letterhead a quote wears when it leaves the company.

    Deliberately separate from Quote: the numbers belong to the deal, the
    identity and the wording belong to the company. One row per organization,
    edited in Plantilla de cotización and read by the PDF builder.

    Nothing here is ever costed — this model only decides how the figures the
    client is allowed to see are laid out.
    """

    #: Bands the document title and the table header. Anything darker than
    #: this reads fine with white text, which is what the PDF assumes.
    DEFAULT_ACCENT = '#2D5F8A'

    organization = models.OneToOneField(Organization, on_delete=models.CASCADE,
                                        related_name='quote_template')

    # ── Identidad ─────────────────────────────────────────────────────────
    logo = models.ImageField(upload_to='quote_templates/', blank=True, null=True)
    #: Legal name for the document, which may differ from the account name.
    company_name = models.CharField(max_length=200, blank=True)
    tax_id = models.CharField(max_length=30, blank=True)
    address = models.CharField(max_length=200, blank=True)
    phone = models.CharField(max_length=50, blank=True)
    email = models.EmailField(blank=True)
    website = models.CharField(max_length=100, blank=True)

    # ── Apariencia ────────────────────────────────────────────────────────
    accent_color = models.CharField(max_length=7, default=DEFAULT_ACCENT)
    document_title = models.CharField(max_length=60, default='COTIZACIÓN')

    # ── Columnas opcionales ───────────────────────────────────────────────
    #: Each one only removes a column; the price columns are not negotiable,
    #: and cost and margin are not offered at all — see ClientQuoteSerializer.
    show_item_number = models.BooleanField(default=True)
    show_unit = models.BooleanField(default=True)
    show_discount = models.BooleanField(default=True)
    #: The quote's own notes field is written by whoever drafts the deal and
    #: may hold remarks never meant for the client, so printing it is a choice
    #: the company makes once rather than a surprise on every document.
    show_quote_notes = models.BooleanField(default=False)

    # ── Textos ────────────────────────────────────────────────────────────
    intro_text = models.TextField(blank=True)
    terms = models.TextField(blank=True)
    footer_text = models.CharField(max_length=200, blank=True)
    signature_name = models.CharField(max_length=120, blank=True)
    signature_title = models.CharField(max_length=120, blank=True)

    updated_at = models.DateTimeField(auto_now=True)
    updated_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True,
                                   related_name='+')

    def __str__(self):
        return f'Plantilla de cotización — {self.organization.name}'

    @classmethod
    def for_organization(cls, organization):
        """The company's template, created with sane defaults on first use.

        A company that never opened the editor still has to be able to send a
        PDF, so this never returns None.
        """
        template, created = cls.objects.get_or_create(
            organization=organization,
            defaults={'company_name': organization.name},
        )
        return template


class ExpenseBlock(models.TextChoices):
    """The three groups the Gastos sheet has always used."""

    VIAJE = 'viaje', 'Viaje'
    FLETE = 'flete', 'Flete'
    OPERACIONES = 'operaciones', 'Operaciones'


#: What each block becomes when it is carried into a quote: the wording of the
#: line and the kind of cost it is. Mirrors how the Cálculo sheet writes them —
#: "Gastos operacionales para instalacion" and "Flete" as separate rows.
BLOCK_AS_QUOTE_LINE = {
    ExpenseBlock.VIAJE: ('Gastos de viaje', CostCategory.GASTO),
    ExpenseBlock.FLETE: ('Flete', CostCategory.FLETE),
    ExpenseBlock.OPERACIONES: ('Gastos operacionales', CostCategory.GASTO),
}


#: What a company can load with one click so the list is not empty on day one.
#: Names and units only — no values, since none of these has a fixed price.
STARTER_EXPENSE_CONCEPTS = [
    ('Pasajes', ExpenseBlock.VIAJE, 'tramo'),
    ('Alojamiento', ExpenseBlock.VIAJE, 'noche'),
    ('Viáticos', ExpenseBlock.VIAJE, 'día'),
    ('Flete a terreno', ExpenseBlock.FLETE, 'tramo'),
    ('Arriendo de camioneta', ExpenseBlock.OPERACIONES, 'día'),
    ('Prevencionista', ExpenseBlock.OPERACIONES, 'día'),
    ('EPP', ExpenseBlock.OPERACIONES, 'kit'),
    ('Herramientas', ExpenseBlock.OPERACIONES, 'proyecto'),
]


class ExpenseConcept(models.Model):
    """Something the company routinely pays for while executing: a night of
    lodging, a day of the rented pickup, a safety officer's day, a PPE kit.

    The concept holds no price. Hotels and rentals move with the season and the
    supplier, so there is no fixed rate to keep — only values that were true on
    a given day, kept in ExpenseRate. What a concept offers is the last known
    value and how old it is, which is exactly what someone estimating needs to
    decide whether to trust it or ask for a fresh quote.
    """

    #: A value older than this is flagged, never replaced: the same rule the
    #: exchange rates follow, for the same reason — silently restating figures
    #: under an estimate in progress would make it impossible to explain later.
    STALE_AFTER_DAYS = 90

    organization = models.ForeignKey(Organization, on_delete=models.CASCADE,
                                     related_name='expense_concepts')
    name = models.CharField(max_length=200)
    #: Where it lands in an expense sheet.
    block = models.CharField(max_length=12, choices=ExpenseBlock.choices,
                             default=ExpenseBlock.OPERACIONES)
    #: What one unit is: noche, día, kit, tramo. Lets a real expense of
    #: 260.000 for four days be read back as 65.000 a day.
    unit = models.CharField(max_length=30, default='unidad')
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['block', 'name']
        constraints = [
            models.UniqueConstraint(fields=['organization', 'name'],
                                    name='unique_expense_concept_per_organization'),
        ]

    def __str__(self):
        return self.name

    @property
    def latest_rate(self):
        """The most recent value by the date it was true, not by when it was typed.

        A receipt entered a month late must not overwrite a newer quote. Reads
        through rates.all() so a prefetch is honoured and a list of concepts
        does not cost one query per row.
        """
        rates = list(self.rates.all())
        return rates[0] if rates else None

    @property
    def age_days(self):
        latest = self.latest_rate
        return (timezone.localdate() - latest.date).days if latest else None

    @property
    def is_stale(self):
        age = self.age_days
        return age is not None and age > self.STALE_AFTER_DAYS

    def record_rate(self, unit_amount, source, *, date=None, supplier='', note='',
                    user=None, expense=None):
        return ExpenseRate.objects.create(
            concept=self, unit_amount=unit_amount, source=source,
            date=date or timezone.localdate(), supplier=supplier, note=note,
            recorded_by=user, expense=expense,
        )

    def observe(self, unit_amount, source, *, user=None):
        """Remember a value seen while estimating — unless it adds nothing.

        Typing the same price that is already on file, and recent, is not news.
        Typing it again once it has gone stale is: it confirms the value still
        holds, so it is recorded and the age starts over.
        """
        latest = self.latest_rate
        if latest and latest.unit_amount == unit_amount and not self.is_stale:
            return None
        return self.record_rate(unit_amount, source, user=user)


class ExpenseRate(models.Model):
    """What a concept cost on a given day, and how that was learned."""

    class Source(models.TextChoices):
        ESTIMADO = 'estimado', 'Estimado'
        COTIZADO = 'cotizado', 'Cotizado'
        #: Reserved for values that come from an expense registered on a
        #: project, so the label keeps meaning "money actually paid".
        REAL = 'real', 'Gasto real'

    concept = models.ForeignKey(ExpenseConcept, on_delete=models.CASCADE,
                                related_name='rates')
    unit_amount = models.DecimalField(max_digits=12, decimal_places=2)
    date = models.DateField(default=timezone.localdate)
    source = models.CharField(max_length=10, choices=Source.choices, default=Source.ESTIMADO)
    supplier = models.CharField(max_length=200, blank=True)
    note = models.CharField(max_length=255, blank=True)
    #: Set when this value was derived from a registered expense. Deleting the
    #: expense takes its value out of the history with it.
    expense = models.OneToOneField('ProjectExpense', on_delete=models.CASCADE,
                                   null=True, blank=True, related_name='rate')
    recorded_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True,
                                    related_name='+')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-date', '-id']

    def __str__(self):
        return f'{self.concept.name}: {self.unit_amount} ({self.date})'


class ExpenseSheet(models.Model):
    """The breakdown behind an operating-expense figure.

    The Gastos sheet in the spreadsheet computes viáticos, freight and site
    costs and is then read by a human who retypes the total into Cálculo — no
    formula connects them, so the breakdown is lost the moment it is used.
    Here the sheet is stored and the quote line is generated from it, which
    means a figure can still be explained a year later and the next project
    can start from the last one instead of from memory.

    Cost only: what is charged for these is the quote's business, decided by
    the margin on the line, not here.
    """

    organization = models.ForeignKey(Organization, on_delete=models.CASCADE,
                                     related_name='expense_sheets')
    opportunity = models.ForeignKey(Opportunity, on_delete=models.CASCADE,
                                    related_name='expense_sheets')
    name = models.CharField(max_length=200, default='Hoja de gastos')
    notes = models.TextField(blank=True)
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True,
                                   related_name='+')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at', '-id']

    def __str__(self):
        return f'{self.name} — {self.opportunity.name}'

    @property
    def block_totals(self):
        """One row per block that has lines, in the order the blocks are declared.

        Blocks with no lines are left out rather than shown as zero: an empty
        Flete block means freight was not costed, not that it is free.
        """
        buckets = {}
        for line in self.lines.all():
            buckets[line.block] = buckets.get(line.block, Decimal('0')) + line.subtotal

        labels = dict(ExpenseBlock.choices)
        return [
            {
                'block': block,
                'label': labels[block],
                'total': buckets[block],
                'quote_description': BLOCK_AS_QUOTE_LINE[block][0],
                'category': BLOCK_AS_QUOTE_LINE[block][1],
            }
            for block in ExpenseBlock.values if block in buckets
        ]

    @property
    def total(self):
        return sum((row['total'] for row in self.block_totals), Decimal('0'))

    def copy_lines_from(self, other):
        """Start this sheet from another one — the estimate is rarely new.

        Amounts come across as they were: a stale per-diem that gets corrected
        is still a better starting point than a blank sheet.
        """
        ExpenseLine.objects.bulk_create([
            ExpenseLine(sheet=self, block=line.block, concept=line.concept,
                        description=line.description, unit_amount=line.unit_amount,
                        quantity=line.quantity, days=line.days, order=line.order)
            for line in other.lines.all()
        ])


class ExpenseLine(models.Model):
    """One costed row: a per-unit amount, how many, and for how many days.

    The sheet the team knows also had a "Fases" column; it stopped meaning
    anything years ago and is deliberately not carried over.
    """

    sheet = models.ForeignKey(ExpenseSheet, on_delete=models.CASCADE, related_name='lines')
    block = models.CharField(max_length=12, choices=ExpenseBlock.choices,
                             default=ExpenseBlock.OPERACIONES)
    #: The concept this row was built from, when it was. The amount is still the
    #: line's own: it holds the value that was used, not a pointer to a price.
    concept = models.ForeignKey(ExpenseConcept, on_delete=models.SET_NULL, null=True,
                                blank=True, related_name='lines')
    description = models.CharField(max_length=200)
    unit_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    quantity = models.DecimalField(max_digits=10, decimal_places=2, default=1)
    #: Days the unit is paid for — nights of lodging, days of a rented pickup.
    #: One for anything charged per event rather than per day.
    days = models.DecimalField(max_digits=10, decimal_places=2, default=1)
    order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ['block', 'order', 'id']

    def __str__(self):
        return f'{self.description} — {self.subtotal}'

    @property
    def subtotal(self):
        return (self.unit_amount * self.quantity * self.days).quantize(Decimal('0.01'))


class ProjectExpense(models.Model):
    """Money the company spent executing a project.

    Always the company's cost, never the client's: what turns up during
    execution — the rented pickup's tyre — is absorbed, not re-invoiced. That
    is why there is no "billable" flag here. The sale was fixed by a document
    the client already accepted, so every row eats into the margin the quote
    promised.

    Categorised with the same CostCategory as the quote, which is what makes
    "presupuestamos 1.200.000 en gastos operacionales y llevamos 1.680.000" a
    query rather than an argument.
    """

    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name='expenses')
    #: When the money was spent, which is rarely when it was recorded.
    incurred_on = models.DateField(default=timezone.localdate)
    category = models.CharField(max_length=12, choices=CostCategory.choices,
                                default=CostCategory.GASTO)
    description = models.CharField(max_length=200)
    amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    #: Optional: what this money bought, in the company's own vocabulary. When
    #: set, the expense also teaches the concept what a unit really cost.
    concept = models.ForeignKey(ExpenseConcept, on_delete=models.SET_NULL, null=True,
                                blank=True, related_name='expenses')
    #: How many units of the concept `amount` covers: four days of the pickup,
    #: two nights of lodging. The unit value is amount divided by this.
    units = models.DecimalField(max_digits=10, decimal_places=2, default=1)
    supplier = models.CharField(max_length=200, blank=True)
    #: Invoice or receipt number, so the row can be tied to its paper.
    document = models.CharField(max_length=60, blank=True)
    notes = models.TextField(blank=True)
    recorded_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True,
                                    related_name='+')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-incurred_on', '-id']

    def __str__(self):
        return f'{self.description} — {self.amount}'

    @property
    def unit_amount(self):
        """What one unit cost, when the expense says what it bought."""
        if not self.concept_id or not self.units:
            return None
        return (self.amount / self.units).quantize(Decimal('0.01'))

    def sync_rate(self, user=None):
        """Keep the concept's value history in step with this expense.

        Created, corrected and removed together with the expense, so the
        history never carries a price from a receipt that was later fixed or
        deleted. Dated on the day the money was spent, not the day it was
        typed, which is what keeps the "latest" value honest.
        """
        unit_amount = self.unit_amount
        try:
            existing = self.rate
        except ExpenseRate.DoesNotExist:
            existing = None

        if unit_amount is None or unit_amount <= 0:
            if existing:
                existing.delete()
            return None

        values = {
            'concept': self.concept, 'unit_amount': unit_amount,
            'date': self.incurred_on, 'source': ExpenseRate.Source.REAL,
            'supplier': self.supplier, 'recorded_by': user or self.recorded_by,
            'note': f'Del gasto "{self.description}".',
        }
        rate, _ = ExpenseRate.objects.update_or_create(expense=self, defaults=values)
        return rate
