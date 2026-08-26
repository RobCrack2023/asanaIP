from django.db import transaction
from rest_framework import serializers
from .models import (
    User, Area, Team, Project, Section, Task, Asset, Organization, Plan, Notification,
    Client, Opportunity, OpportunityActivity, Quote, QuoteItem, Product,
    ProductPriceEntry,
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


class ProductPriceEntrySerializer(serializers.ModelSerializer):
    recorded_by_name = serializers.CharField(source='recorded_by.get_full_name',
                                             read_only=True, default=None)
    margin = serializers.DecimalField(max_digits=8, decimal_places=4, read_only=True)

    class Meta:
        model = ProductPriceEntry
        fields = ['id', 'cost', 'unit_price', 'margin', 'supplier', 'note',
                  'recorded_by', 'recorded_by_name', 'recorded_at']
        read_only_fields = fields


class ProductSerializer(serializers.ModelSerializer):
    margin = serializers.DecimalField(max_digits=8, decimal_places=4, read_only=True)
    unit_profit = serializers.DecimalField(max_digits=12, decimal_places=2, read_only=True)

    class Meta:
        model = Product
        fields = ['id', 'name', 'sku', 'description', 'unit', 'cost', 'unit_price',
                  'margin', 'unit_profit', 'supplier', 'lead_time_days', 'is_active',
                  'created_at', 'updated_at']
        read_only_fields = ['id', 'margin', 'unit_profit', 'created_at', 'updated_at']

    def validate_unit_price(self, value):
        if value < 0:
            raise serializers.ValidationError('El precio no puede ser negativo.')
        return value

    def validate_cost(self, value):
        if value < 0:
            raise serializers.ValidationError('El costo no puede ser negativo.')
        return value

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

    def create(self, validated_data):
        product = super().create(validated_data)
        product.record_price(user=self._user(), note='Alta en el catálogo.')
        return product

    def update(self, instance, validated_data):
        before = {field: getattr(instance, field) for field in Product.PRICED_FIELDS}
        product = super().update(instance, validated_data)
        # Renaming a product or flipping is_active is not a price change.
        if any(getattr(product, field) != before[field] for field in Product.PRICED_FIELDS):
            product.record_price(user=self._user())
        return product


class QuoteItemSerializer(serializers.ModelSerializer):
    product = OrgScopedRelatedField(queryset=Product.objects.all(), required=False, allow_null=True)
    subtotal = serializers.DecimalField(max_digits=12, decimal_places=2, read_only=True)
    cost_subtotal = serializers.DecimalField(max_digits=12, decimal_places=2, read_only=True)
    profit = serializers.DecimalField(max_digits=12, decimal_places=2, read_only=True)
    margin = serializers.DecimalField(max_digits=8, decimal_places=4, read_only=True)

    class Meta:
        model = QuoteItem
        fields = ['id', 'product', 'description', 'unit', 'quantity', 'unit_cost', 'unit_price',
                  'discount_percent', 'subtotal', 'cost_subtotal', 'profit', 'margin', 'order']
        read_only_fields = ['id', 'subtotal', 'cost_subtotal', 'profit', 'margin']

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

    class Meta:
        model = Quote
        fields = ['id', 'opportunity', 'number', 'reference', 'status', 'status_display',
                  'issue_date', 'valid_until', 'is_expired', 'tax_rate', 'items',
                  'subtotal', 'total_cost', 'total_profit', 'margin',
                  'tax_amount', 'total_amount', 'notes', 'created_at', 'updated_at']
        # Every money figure is derived from the items; the client sends the
        # breakdown and the rate, never the sums.
        read_only_fields = ['id', 'number', 'subtotal', 'total_cost', 'total_profit', 'margin',
                            'tax_amount', 'total_amount', 'created_at', 'updated_at']

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
        QuoteItem.objects.bulk_create([
            QuoteItem(quote=quote, order=order, **item)
            for order, item in enumerate(items_data)
        ])

    @transaction.atomic
    def create(self, validated_data):
        items_data = validated_data.pop('items', [])
        quote = Quote(
            organization=validated_data['opportunity'].organization, **validated_data
        )
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
