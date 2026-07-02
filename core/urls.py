from django.urls import path, include
from rest_framework.routers import DefaultRouter
from . import views

router = DefaultRouter()
router.register(r'users', views.UserViewSet)
router.register(r'areas', views.AreaViewSet)
router.register(r'teams', views.TeamViewSet)
router.register(r'projects', views.ProjectViewSet)
router.register(r'sections', views.SectionViewSet)
router.register(r'tasks', views.TaskViewSet)
router.register(r'assets', views.AssetViewSet)
router.register(r'organizations', views.OrganizationViewSet)
router.register(r'plans', views.PlanViewSet)
router.register(r'notifications', views.NotificationViewSet, basename='notification')

urlpatterns = [
    path('auth/login/', views.login_view, name='login'),
    path('auth/logout/', views.logout_view, name='logout'),
    path('auth/me/', views.me_view, name='me'),
    path('', include(router.urls)),
]
