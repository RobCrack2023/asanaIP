from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from .models import User, Area, Team, Project, Section, Task, Asset, Organization, Plan


@admin.register(Plan)
class PlanAdmin(admin.ModelAdmin):
    list_display = ['name', 'max_users', 'max_projects', 'price']


@admin.register(Organization)
class OrganizationAdmin(admin.ModelAdmin):
    list_display = ['name', 'slug', 'plan', 'max_users', 'is_active', 'created_at']
    list_filter = ['is_active', 'plan']
    prepopulated_fields = {'slug': ('name',)}


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    list_display = ['username', 'email', 'first_name', 'last_name', 'job_title', 'is_staff']
    fieldsets = BaseUserAdmin.fieldsets + (
        ('Perfil', {'fields': ('avatar', 'job_title')}),
    )


@admin.register(Area)
class AreaAdmin(admin.ModelAdmin):
    list_display = ['name', 'color', 'created_at']


@admin.register(Team)
class TeamAdmin(admin.ModelAdmin):
    list_display = ['name', 'area', 'created_at']
    list_filter = ['area']
    filter_horizontal = ['members']


@admin.register(Project)
class ProjectAdmin(admin.ModelAdmin):
    list_display = ['name', 'team', 'owner', 'created_at']
    list_filter = ['team__area', 'team']


@admin.register(Section)
class SectionAdmin(admin.ModelAdmin):
    list_display = ['name', 'project', 'order']
    list_filter = ['project']


@admin.register(Task)
class TaskAdmin(admin.ModelAdmin):
    list_display = ['title', 'section', 'assignee', 'priority', 'status', 'start_date', 'due_date']
    list_filter = ['status', 'priority', 'section__project']
    search_fields = ['title', 'description']


@admin.register(Asset)
class AssetAdmin(admin.ModelAdmin):
    list_display = ['name', 'asset_type', 'project', 'uploaded_by', 'created_at']
    list_filter = ['asset_type', 'project']
