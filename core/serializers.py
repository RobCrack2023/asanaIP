import re
from decimal import Decimal

from django.db import transaction
from django.utils import timezone
from rest_framework import serializers
from .models import (
    User, Area, Team, Project, Section, Task, Asset, Organization, Plan, Notification,
    Client, Opportunity, OpportunityActivity, Quote, QuoteItem, Product,
    ProductPriceEntry, ExchangeRate, Currency, QuoteTemplate, CostCategory,
    ExpenseSheet, ExpenseLine, ProjectExpense,
)


class OrgScopedRelatedField(serializers.PrimaryKeyRelatedField):
    """Relation restricted to rows of the requesting user's organization.

    The default PrimaryKeyRelatedField accepts any pk in the table, so without
    this a user could point a quote or an opportunity at another company's
    records — and read the related name back out of the response.
    """

    def __init__(self, org_lookup='organization', **kwargs):
        self.org_lookup = org_lookup
        super().__init__(**kwargs)

    def get_queryset(self):
        queryset = super().get_queryset()
        request = self.context.get('request')
        organization = getattr(getattr(request, 'user', None), 'organization', None)
        if organization is None:
            return queryset.none()
        return queryset.filter(**{self.org_lookup: organization})


class PlanSerializer(serializers.ModelSerializer):
    class Meta:
        model = Plan
        fields = ['id', 'name', 'max_users', 'max_projects', 'price']


class OrganizationSerializer(serializers.ModelSerializer):
    plan_name = serializers.CharField(source='plan.name', read_only=True, default=None)
    users_count = serializers.IntegerField(read_only=True)
    projects_count = serializers.IntegerField(read_only=True)

    class Meta:
        model = Organization
        fields = ['id', 'name', 'slug', 'logo', 'plan', 'plan_name',
                  'max_users', 'is_active', 'users_count', 'projects_count', 'created_at']
        read_only_fields = ['id', 'created_at']


class UserSerializer(serializers.ModelSerializer):
    full_name = serializers.SerializerMethodField()
    teams = serializers.SerializerMethodField()
    password = serializers.CharField(write_only=True, required=False, min_length=6)

    class Meta:
        model = User
        fields = ['id', 'username', 'email', 'first_name', 'last_name',
                  'full_name', 'avatar', 'job_title', 'is_active', 'is_staff',
                  'is_super_admin', 'is_sales', 'organization', 'password', 'teams']
        read_only_fields = ['id']

    def get_full_name(self, obj):
        return obj.get_full_name() or obj.username

    def get_teams(self, obj):
        return [{'id': t.id, 'name': t.name} for t in obj.teams.all()]

    def create(self, validated_data):
        password = validated_data.pop('password', None)
        user = User(**validated_data)
        if password:
            user.set_password(password)
        user.save()
        return user

    def update(self, instance, validated_data):
        password = validated_data.pop('password', None)
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        if password:
            instance.set_password(password)
        instance.save()
        return instance


class AreaSerializer(serializers.ModelSerializer):
    teams_count = serializers.IntegerField(source='teams.count', read_only=True)

    class Meta:
        model = Area
        fields = ['id', 'name', 'description', 'color', 'teams_count', 'created_at']
        read_only_fields = ['id', 'created_at']


class TeamSerializer(serializers.ModelSerializer):
    area_name = serializers.CharField(source='area.name', read_only=True)
    members_count = serializers.IntegerField(source='members.count', read_only=True)
    members = UserSerializer(many=True, read_only=True)
    member_ids = serializers.PrimaryKeyRelatedField(
        queryset=User.objects.all(), many=True, write_only=True, source='members', required=False
    )

    class Meta:
        model = Team
        fields = ['id', 'name', 'area', 'area_name', 'description',
                  'members', 'member_ids', 'members_count', 'created_at']
        read_only_fields = ['id', 'created_at']


class TaskSerializer(serializers.ModelSerializer):
    assignee_name = serializers.CharField(source='assignee.get_full_name', read_only=True, default=None)
    assigned_by_name = serializers.CharField(source='assigned_by.get_full_name', read_only=True, default=None)
    subtasks_count = serializers.IntegerField(source='subtasks.count', read_only=True)

    class Meta:
        model = Task
        fields = ['id', 'title', 'description', 'section', 'opportunity', 'assignee', 'assignee_name',
                  'assigned_by', 'assigned_by_name', 'assignment_status',
                  'parent', 'priority', 'status', 'completion_note', 'start_date', 'due_date', 'completed_at',
                  'order', 'subtasks_count',
                  'visibility',
                  'recurrence_type', 'recurrence_day', 'recurrence_end_date',
                  'created_at', 'updated_at']
        read_only_fields = ['id', 'completed_at', 'created_at', 'updated_at']
        extra_kwargs = {'section': {'required': False, 'allow_null': True}}

    def validate(self, data):
        section = data.get('section', getattr(self.instance, 'section', None))
        opportunity = data.get('opportunity', getattr(self.instance, 'opportunity', None))
        if not section and not opportunity:
            raise serializers.ValidationError('La tarea debe pertenecer a una sección o a una oportunidad.')
        return data


class SectionSerializer(serializers.ModelSerializer):
    tasks = TaskSerializer(many=True, read_only=True)

    class Meta:
        model = Section
        fields = ['id', 'name', 'project', 'order', 'tasks']
        read_only_fields = ['id']


class ProjectSerializer(serializers.ModelSerializer):
    team_name = serializers.CharField(source='team.name', read_only=True)
    owner_name = serializers.CharField(source='owner.get_full_name', read_only=True, default=None)
    sections = SectionSerializer(many=True, read_only=True)
    tasks_count = serializers.SerializerMethodField()

    class Meta:
        model = Project
        fields = ['id', 'name', 'description', 'team', 'team_name', 'color',
                  'owner', 'owner_name', 'sections', 'tasks_count',
                  'created_at', 'updated_at']
        read_only_fields = ['id', 'created_at', 'updated_at']

    def get_tasks_count(self, obj):
        return Task.objects.filter(section__project=obj).count()


class ProjectListSerializer(serializers.ModelSerializer):
    team_name = serializers.CharField(source='team.name', read_only=True)
    tasks_count = serializers.SerializerMethodField()

    class Meta:
        model = Project
        fields = ['id', 'name', 'description', 'team', 'team_name', 'color',
                  'owner', 'tasks_count', 'created_at', 'updated_at']
        read_only_fields = ['id', 'created_at', 'updated_at']

    def get_tasks_count(self, obj):
        return Task.objects.filter(section__project=obj).count()


class AssetSerializer(serializers.ModelSerializer):
    uploaded_by_name = serializers.CharField(source='uploaded_by.get_full_name', read_only=True, default=None)
    category = serializers.CharField(read_only=True)
    file_extension = serializers.CharField(read_only=True)

    class Meta:
        model = Asset
        fields = ['id', 'project', 'task', 'asset_type', 'name', 'file', 'url',
                  'file_size', 'mime_type', 'category', 'file_extension',
                  'uploaded_by', 'uploaded_by_name', 'created_at']
        read_only_fields = ['id', 'file_size', 'mime_type', 'uploaded_by', 'created_at']


class NotificationSerializer(serializers.ModelSerializer):
    actor_name = serializers.CharField(source='actor.get_full_name', read_only=True, default=None)
    project_id = serializers.IntegerField(source='task.section.project_id', read_only=True, default=None)

    class Meta:
        model = Notification
        fields = ['id', 'actor', 'actor_name', 'verb', 'task', 'project_id',
                  'message', 'is_read', 'created_at']
        read_only_fields = fields


class ClientSerializer(serializers.ModelSerializer):
    opportunities_count = serializers.IntegerField(source='opportunities.count', read_only=True)

    class Meta:
        model = Client
        fields = ['id', 'name', 'contact_name', 'email', 'phone', 'notes',
                  'opportunities_count', 'created_at']
        read_only_fields = ['id', 'created_at']


class ExchangeRateSerializer(serializers.ModelSerializer):
    updated_by_name = serializers.CharField(source='updated_by.get_full_name',
                                            read_only=True, default=None)

    class Meta:
        model = ExchangeRate
        fields = ['id', 'date', 'uf', 'usd', 'eur', 'updated_by', 'updated_by_name', 'created_at']
        read_only_fields = ['id', 'updated_by', 'created_at']

    def validate(self, attrs):
        for field in ('uf', 'usd', 'eur'):
            value = attrs.get(field, getattr(self.instance, field, None))
            if value is not None and value < 0:
                raise serializers.ValidationError({field: 'El valor no puede ser negativo.'})
        return attrs

    def create(self, validated_data):
        """Recording rates for a day that already has them overwrites it.

        There is one true set of rates per day, and correcting a typo is the
        common case — the unique constraint would otherwise surface as a 500.
        """
        organization = validated_data.pop('organization')
        date = validated_data.pop('date', timezone.localdate())
        rates, _ = ExchangeRate.objects.update_or_create(
            organization=organization, date=date, defaults=validated_data,
        )
        return rates


class ProductPriceEntrySerializer(serializers.ModelSerializer):
    recorded_by_name = serializers.CharField(source='recorded_by.get_full_name',
                                             read_only=True, default=None)
    margin = serializers.DecimalField(max_digits=8, decimal_places=4, read_only=True)

    class Meta:
        model = ProductPriceEntry
        fields = ['id', 'cost', 'cost_amount', 'currency', 'cost_rate', 'unit_price',
                  'margin', 'supplier', 'note', 'recorded_by', 'recorded_by_name', 'recorded_at']
        read_only_fields = fields


class ProductSerializer(serializers.ModelSerializer):
    margin = serializers.DecimalField(max_digits=8, decimal_places=4, read_only=True)
    category_display = serializers.CharField(source='get_category_display', read_only=True)
    unit_profit = serializers.DecimalField(max_digits=12, decimal_places=2, read_only=True)
    cost_is_stale = serializers.SerializerMethodField()

    class Meta:
        model = Product
        fields = ['id', 'name', 'sku', 'description', 'unit', 'category',
                  'category_display',
                  'currency', 'cost_amount', 'import_multiplier', 'incoterm',
                  'cost_rate', 'cost', 'cost_is_stale', 'default_margin', 'unit_price',
                  'margin', 'unit_profit', 'supplier', 'lead_time_days', 'is_active',
                  'created_at', 'updated_at']
        # The catalog is costed and marked up; the price falls out of the two.
        # cost and cost_rate likewise follow from cost_amount, currency and
        # the rate in force — sending any of them would let them disagree.
        read_only_fields = ['id', 'cost', 'cost_rate', 'cost_is_stale', 'unit_price',
                            'margin', 'unit_profit', 'category_display',
                            'created_at', 'updated_at']

    def get_cost_is_stale(self, obj):
        return obj.cost_is_stale(self._rates())

    def _rates(self):
        organization = getattr(self._user(), 'organization', None)
        if organization is None:
            return None
        # Cached per serializer instance so a product list does not run one
        # query per row.
        if not hasattr(self, '_cached_rates'):
            self._cached_rates = ExchangeRate.current_for(organization)
        return self._cached_rates

    def validate_default_margin(self, value):
        if value <= -1:
            raise serializers.ValidationError('El margen no puede dejar el precio en cero o negativo.')
        return value

    def validate_cost_amount(self, value):
        if value < 0:
            raise serializers.ValidationError('El costo no puede ser negativo.')
        return value

    def validate_import_multiplier(self, value):
        if value <= 0:
            raise serializers.ValidationError('El multiplicador de importación debe ser mayor que cero.')
        return value

    def validate(self, attrs):
        currency = attrs.get('currency', getattr(self.instance, 'currency', Currency.CLP))
        if currency != Currency.CLP:
            rates = self._rates()
            if rates is None or not rates.rate_for(currency):
                raise serializers.ValidationError({
                    'currency': f'No hay un valor de {currency} cargado. '
                                'Registra el tipo de cambio antes de costear en esta moneda.'
                })
        return attrs

    def validate_sku(self, value):
        sku = (value or '').strip()
        if not sku:
            return ''
        organization = self.context['request'].user.organization
        clashes = Product.objects.filter(organization=organization, sku__iexact=sku)
        if self.instance:
            clashes = clashes.exclude(pk=self.instance.pk)
        if clashes.exists():
            raise serializers.ValidationError('Ya existe un producto con este código.')
        return sku

    def _user(self):
        request = self.context.get('request')
        return getattr(request, 'user', None) if request else None

    def _apply_current_rate(self, product):
        rates = self._rates()
        rate = rates.rate_for(product.currency) if rates else Decimal('1')
        product.apply_rate(rate if product.currency != Currency.CLP else Decimal('1'))
        product.save(update_fields=['cost', 'cost_rate', 'unit_price'])

    def create(self, validated_data):
        product = super().create(validated_data)
        self._apply_current_rate(product)
        product.record_price(user=self._user(), note='Alta en el catálogo.')
        return product

    def update(self, instance, validated_data):
        before = {field: getattr(instance, field) for field in Product.PRICED_FIELDS}
        product = super().update(instance, validated_data)
        self._apply_current_rate(product)
        # Renaming a product or flipping is_active is not a price change.
        if any(getattr(product, field) != before[field] for field in Product.PRICED_FIELDS):
            product.record_price(user=self._user())
        return product


class QuoteItemSerializer(serializers.ModelSerializer):
    product = OrgScopedRelatedField(queryset=Product.objects.all(), required=False, allow_null=True)
    category_display = serializers.CharField(source='get_category_display', read_only=True)
    subtotal = serializers.DecimalField(max_digits=12, decimal_places=2, read_only=True)
    cost_subtotal = serializers.DecimalField(max_digits=12, decimal_places=2, read_only=True)
    profit = serializers.DecimalField(max_digits=12, decimal_places=2, read_only=True)
    effective_margin = serializers.DecimalField(max_digits=8, decimal_places=4, read_only=True)

    class Meta:
        model = QuoteItem
        fields = ['id', 'product', 'description', 'category', 'category_display',
                  'unit', 'quantity', 'unit_cost', 'margin',
                  'unit_price', 'discount_percent', 'subtotal', 'cost_subtotal', 'profit',
                  'effective_margin', 'order']
        # unit_price follows from unit_cost and margin on any costed line.
        read_only_fields = ['id', 'subtotal', 'cost_subtotal', 'profit', 'effective_margin',
                            'category_display']

    def validate_margin(self, value):
        if value is not None and value <= -1:
            raise serializers.ValidationError('El margen no puede dejar el precio en cero o negativo.')
        return value

    def validate(self, attrs):
        """A line needs either a cost to mark up or a price stated outright."""
        # A line taken from the catalog inherits its kind unless it says
        # otherwise, the same way it inherits the cost.
        product = attrs.get('product')
        if product and 'category' not in attrs:
            attrs['category'] = product.category

        cost = attrs.get('unit_cost') or 0
        margin = attrs.get('margin')
        if cost and margin is None:
            raise serializers.ValidationError(
                {'margin': 'Indica el margen a aplicar sobre el costo.'}
            )
        if not cost and not attrs.get('unit_price'):
            raise serializers.ValidationError(
                {'unit_price': 'Un ítem sin costo necesita un precio.'}
            )
        return attrs

    def validate_description(self, value):
        description = (value or '').strip()
        if not description:
            raise serializers.ValidationError('El ítem necesita una descripción.')
        return description

    def validate_quantity(self, value):
        if value <= 0:
            raise serializers.ValidationError('La cantidad debe ser mayor que cero.')
        return value

    def validate_unit_price(self, value):
        if value < 0:
            raise serializers.ValidationError('El precio unitario no puede ser negativo.')
        return value

    def validate_unit_cost(self, value):
        if value < 0:
            raise serializers.ValidationError('El costo unitario no puede ser negativo.')
        return value

    def validate_discount_percent(self, value):
        if not 0 <= value <= 100:
            raise serializers.ValidationError('El descuento debe estar entre 0 y 100.')
        return value


class QuoteSerializer(serializers.ModelSerializer):
    opportunity = OrgScopedRelatedField(queryset=Opportunity.objects.all())
    items = QuoteItemSerializer(many=True, required=False)
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    reference = serializers.CharField(read_only=True)
    is_expired = serializers.BooleanField(read_only=True)
    total_profit = serializers.DecimalField(max_digits=12, decimal_places=2, read_only=True)
    margin = serializers.DecimalField(max_digits=8, decimal_places=4, read_only=True)
    display_rate = serializers.DecimalField(max_digits=12, decimal_places=2, read_only=True)
    category_totals = serializers.ReadOnlyField()

    class Meta:
        model = Quote
        fields = ['id', 'opportunity', 'number', 'reference', 'status', 'status_display',
                  'issue_date', 'valid_until', 'is_expired', 'tax_rate', 'items',
                  'subtotal', 'total_cost', 'total_profit', 'margin', 'category_totals',
                  'tax_amount', 'total_amount', 'display_currency', 'display_rate',
                  'rate_uf', 'rate_usd', 'rate_eur', 'notes', 'created_at', 'updated_at']
        # Every money figure is derived from the items; the client sends the
        # breakdown and the rate, never the sums. The exchange rates are
        # stamped from the company's table at issue time.
        read_only_fields = ['id', 'number', 'subtotal', 'total_cost', 'total_profit', 'margin',
                            'category_totals', 'tax_amount', 'total_amount', 'display_rate',
                            'rate_uf', 'rate_usd', 'rate_eur', 'created_at', 'updated_at']

    def validate_tax_rate(self, value):
        if not 0 <= value <= 100:
            raise serializers.ValidationError('La tasa de impuesto debe estar entre 0 y 100.')
        return value

    def validate(self, attrs):
        issue_date = attrs.get('issue_date', getattr(self.instance, 'issue_date', None))
        valid_until = attrs.get('valid_until', getattr(self.instance, 'valid_until', None))
        if issue_date and valid_until and valid_until < issue_date:
            raise serializers.ValidationError(
                {'valid_until': 'La validez no puede ser anterior a la fecha de emisión.'}
            )
        return attrs

    def _write_items(self, quote, items_data):
        quote.items.all().delete()
        items = []
        for order, data in enumerate(items_data):
            item = QuoteItem(quote=quote, order=order, **data)
            # Price is derived, so a client sending its own is simply ignored.
            item.apply_margin()
            items.append(item)
        QuoteItem.objects.bulk_create(items)

    @transaction.atomic
    def create(self, validated_data):
        items_data = validated_data.pop('items', [])
        organization = validated_data['opportunity'].organization
        quote = Quote(organization=organization, **validated_data)
        quote.stamp_rates(ExchangeRate.current_for(organization))
        quote.assign_number()
        quote.save()
        self._write_items(quote, items_data)
        quote.recalculate()
        return quote

    @transaction.atomic
    def update(self, instance, validated_data):
        items_data = validated_data.pop('items', None)
        quote = super().update(instance, validated_data)
        if items_data is not None:
            self._write_items(quote, items_data)
        quote.recalculate()
        return quote


class OpportunityActivitySerializer(serializers.ModelSerializer):
    opportunity = OrgScopedRelatedField(queryset=Opportunity.objects.all())
    kind_display = serializers.CharField(source='get_kind_display', read_only=True)
    author_name = serializers.CharField(source='author.get_full_name', read_only=True, default=None)
    from_stage_display = serializers.SerializerMethodField()
    to_stage_display = serializers.SerializerMethodField()
    is_system = serializers.BooleanField(read_only=True)

    class Meta:
        model = OpportunityActivity
        fields = ['id', 'opportunity', 'kind', 'kind_display', 'body',
                  'from_stage', 'from_stage_display', 'to_stage', 'to_stage_display',
                  'occurred_at', 'author', 'author_name', 'is_system', 'created_at']
        # Stage moves and authorship are recorded by the server, never posted.
        read_only_fields = ['id', 'from_stage', 'to_stage', 'author', 'created_at']

    def _stage_label(self, value):
        if not value:
            return None
        try:
            return Opportunity.Stage(value).label
        except ValueError:
            return value

    def get_from_stage_display(self, obj):
        return self._stage_label(obj.from_stage)

    def get_to_stage_display(self, obj):
        return self._stage_label(obj.to_stage)

    def validate_kind(self, value):
        if value not in OpportunityActivity.MANUAL_KINDS:
            raise serializers.ValidationError(
                'Solo se pueden registrar notas, llamadas, reuniones o correos; '
                'los cambios de etapa los registra el sistema.'
            )
        return value

    def validate_body(self, value):
        body = (value or '').strip()
        if not body:
            raise serializers.ValidationError('Escribe el detalle de la actividad.')
        return body


class OpportunitySerializer(serializers.ModelSerializer):
    client = OrgScopedRelatedField(queryset=Client.objects.all())
    owner = OrgScopedRelatedField(queryset=User.objects.all(), required=False, allow_null=True)
    client_name = serializers.CharField(source='client.name', read_only=True)
    owner_name = serializers.CharField(source='owner.get_full_name', read_only=True, default=None)
    stage_display = serializers.CharField(source='get_stage_display', read_only=True)
    tasks_count = serializers.IntegerField(source='tasks.count', read_only=True)
    quotes = QuoteSerializer(many=True, read_only=True)

    class Meta:
        model = Opportunity
        fields = ['id', 'client', 'client_name', 'name', 'description', 'stage', 'stage_display',
                  'estimated_amount', 'owner', 'owner_name', 'expected_close_date',
                  'lost_reason', 'project', 'tasks_count', 'quotes', 'created_at', 'updated_at']
        read_only_fields = ['id', 'project', 'created_at', 'updated_at']


class ClientQuoteItemSerializer(serializers.ModelSerializer):
    """A quote line stripped of everything the client must not see."""

    subtotal = serializers.DecimalField(max_digits=12, decimal_places=2, read_only=True)

    class Meta:
        model = QuoteItem
        # unit_cost, margin, cost_subtotal, profit and effective_margin are
        # deliberately absent — see ClientQuoteSerializer.
        fields = ['id', 'description', 'unit', 'quantity', 'unit_price',
                  'discount_percent', 'subtotal', 'order']
        read_only_fields = fields


class ClientQuoteSerializer(serializers.ModelSerializer):
    """The quote as the client is allowed to see it.

    Cost, margin and profit are left out of the field list rather than hidden
    at render time: a field that is never serialized cannot leak through the
    API, a saved page or a copied payload. This serializer is the single
    source of what leaves the company — the PDF is built from it too, so a
    field added here reaches the client on every channel at once.
    """

    items = ClientQuoteItemSerializer(many=True, read_only=True)
    reference = serializers.CharField(read_only=True)
    is_expired = serializers.BooleanField(read_only=True)
    display_rate = serializers.DecimalField(max_digits=12, decimal_places=2, read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    opportunity_name = serializers.CharField(source='opportunity.name', read_only=True)
    client_name = serializers.CharField(source='opportunity.client.name', read_only=True)
    client_contact = serializers.CharField(source='opportunity.client.contact_name', read_only=True)
    client_email = serializers.CharField(source='opportunity.client.email', read_only=True)
    client_phone = serializers.CharField(source='opportunity.client.phone', read_only=True)
    owner_name = serializers.CharField(source='opportunity.owner.get_full_name',
                                       read_only=True, default='')

    class Meta:
        model = Quote
        fields = ['id', 'number', 'reference', 'status', 'status_display',
                  'issue_date', 'valid_until', 'is_expired', 'tax_rate', 'items',
                  'subtotal', 'tax_amount', 'total_amount',
                  'display_currency', 'display_rate', 'notes',
                  'opportunity_name', 'client_name', 'client_contact',
                  'client_email', 'client_phone', 'owner_name']
        read_only_fields = fields


class QuoteTemplateSerializer(serializers.ModelSerializer):
    updated_by_name = serializers.CharField(source='updated_by.get_full_name',
                                            read_only=True, default='')

    class Meta:
        model = QuoteTemplate
        fields = ['logo', 'company_name', 'tax_id', 'address', 'phone', 'email', 'website',
                  'accent_color', 'document_title',
                  'show_item_number', 'show_unit', 'show_discount', 'show_quote_notes',
                  'intro_text', 'terms', 'footer_text',
                  'signature_name', 'signature_title',
                  'updated_at', 'updated_by_name']
        read_only_fields = ['updated_at', 'updated_by_name']

    def validate_accent_color(self, value):
        colour = (value or '').strip()
        if not re.fullmatch(r'#[0-9A-Fa-f]{6}', colour):
            raise serializers.ValidationError('Usa un color en formato #RRGGBB.')
        return colour.upper()

    def validate_document_title(self, value):
        title = (value or '').strip()
        if not title:
            raise serializers.ValidationError('El documento necesita un título.')
        return title


class ExpenseLineSerializer(serializers.ModelSerializer):
    subtotal = serializers.DecimalField(max_digits=12, decimal_places=2, read_only=True)
    block_display = serializers.CharField(source='get_block_display', read_only=True)

    class Meta:
        model = ExpenseLine
        fields = ['id', 'block', 'block_display', 'description',
                  'unit_amount', 'quantity', 'days', 'subtotal', 'order']
        read_only_fields = ['id', 'subtotal', 'block_display']

    def validate_description(self, value):
        description = (value or '').strip()
        if not description:
            raise serializers.ValidationError('La línea necesita una descripción.')
        return description

    def validate_unit_amount(self, value):
        if value < 0:
            raise serializers.ValidationError('El valor unitario no puede ser negativo.')
        return value

    def validate_quantity(self, value):
        if value <= 0:
            raise serializers.ValidationError('La cantidad debe ser mayor que cero.')
        return value

    def validate_days(self, value):
        if value <= 0:
            raise serializers.ValidationError('Los días deben ser mayores que cero.')
        return value


class ExpenseSheetSerializer(serializers.ModelSerializer):
    opportunity = OrgScopedRelatedField(queryset=Opportunity.objects.all())
    lines = ExpenseLineSerializer(many=True, required=False)
    block_totals = serializers.ReadOnlyField()
    total = serializers.DecimalField(max_digits=12, decimal_places=2, read_only=True)
    created_by_name = serializers.CharField(source='created_by.get_full_name',
                                            read_only=True, default='')
    #: Start from an existing sheet instead of a blank one. Write-only: it is
    #: an instruction for the create, not a relation worth keeping.
    copy_from = OrgScopedRelatedField(queryset=ExpenseSheet.objects.all(),
                                      required=False, allow_null=True, write_only=True)

    class Meta:
        model = ExpenseSheet
        fields = ['id', 'opportunity', 'name', 'notes', 'lines', 'block_totals', 'total',
                  'copy_from', 'created_by_name', 'created_at', 'updated_at']
        read_only_fields = ['id', 'block_totals', 'total', 'created_by_name',
                            'created_at', 'updated_at']

    def validate_name(self, value):
        name = (value or '').strip()
        if not name:
            raise serializers.ValidationError('La hoja necesita un nombre.')
        return name

    def _write_lines(self, sheet, lines_data):
        sheet.lines.all().delete()
        ExpenseLine.objects.bulk_create([
            ExpenseLine(sheet=sheet, **data) for data in lines_data
        ])

    @transaction.atomic
    def create(self, validated_data):
        lines_data = validated_data.pop('lines', None)
        source = validated_data.pop('copy_from', None)
        sheet = ExpenseSheet.objects.create(
            organization=validated_data['opportunity'].organization,
            created_by=self.context['request'].user,
            **validated_data,
        )
        if lines_data:
            self._write_lines(sheet, lines_data)
        elif source is not None:
            sheet.copy_lines_from(source)
        return sheet

    @transaction.atomic
    def update(self, instance, validated_data):
        lines_data = validated_data.pop('lines', None)
        validated_data.pop('copy_from', None)
        sheet = super().update(instance, validated_data)
        if lines_data is not None:
            self._write_lines(sheet, lines_data)
        return sheet


class ProjectExpenseSerializer(serializers.ModelSerializer):
    project = OrgScopedRelatedField(queryset=Project.objects.all(),
                                    org_lookup='team__area__organization')
    category_display = serializers.CharField(source='get_category_display', read_only=True)
    recorded_by_name = serializers.CharField(source='recorded_by.get_full_name',
                                             read_only=True, default='')

    class Meta:
        model = ProjectExpense
        fields = ['id', 'project', 'incurred_on', 'category', 'category_display',
                  'description', 'amount', 'supplier', 'document', 'notes',
                  'recorded_by_name', 'created_at']
        read_only_fields = ['id', 'category_display', 'recorded_by_name', 'created_at']

    def validate_description(self, value):
        description = (value or '').strip()
        if not description:
            raise serializers.ValidationError('El gasto necesita una descripción.')
        return description

    def validate_amount(self, value):
        if value <= 0:
            raise serializers.ValidationError('El monto debe ser mayor que cero.')
        return value
