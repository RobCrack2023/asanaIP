from rest_framework import serializers
from .models import User, Area, Team, Project, Section, Task


class UserSerializer(serializers.ModelSerializer):
    full_name = serializers.SerializerMethodField()
    teams = serializers.SerializerMethodField()
    password = serializers.CharField(write_only=True, required=False, min_length=6)

    class Meta:
        model = User
        fields = ['id', 'username', 'email', 'first_name', 'last_name',
                  'full_name', 'avatar', 'job_title', 'is_active', 'is_staff',
                  'password', 'teams']
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
        fields = ['id', 'title', 'description', 'section', 'assignee', 'assignee_name',
                  'assigned_by', 'assigned_by_name', 'assignment_status',
                  'parent', 'priority', 'status', 'start_date', 'due_date', 'completed_at',
                  'order', 'subtasks_count',
                  'visibility',
                  'recurrence_type', 'recurrence_day', 'recurrence_end_date',
                  'created_at', 'updated_at']
        read_only_fields = ['id', 'completed_at', 'created_at', 'updated_at']


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
