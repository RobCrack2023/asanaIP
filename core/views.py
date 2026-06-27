from django.utils import timezone
from rest_framework import viewsets, status
from rest_framework.decorators import action, api_view, permission_classes
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from django.contrib.auth import authenticate, login, logout

from .models import User, Area, Team, Project, Section, Task, Asset
from .serializers import (
    UserSerializer, AreaSerializer, TeamSerializer,
    ProjectSerializer, ProjectListSerializer, SectionSerializer, TaskSerializer,
    AssetSerializer,
)


@api_view(['POST'])
@permission_classes([AllowAny])
def login_view(request):
    username = request.data.get('username')
    password = request.data.get('password')
    user = authenticate(request, username=username, password=password)
    if user is None:
        return Response({'error': 'Credenciales inválidas'}, status=status.HTTP_401_UNAUTHORIZED)
    login(request, user)
    return Response(UserSerializer(user).data)


@api_view(['POST'])
def logout_view(request):
    logout(request)
    return Response({'ok': True})


@api_view(['GET'])
def me_view(request):
    return Response(UserSerializer(request.user).data)


class UserViewSet(viewsets.ModelViewSet):
    queryset = User.objects.all()
    serializer_class = UserSerializer


class AreaViewSet(viewsets.ModelViewSet):
    queryset = Area.objects.all()
    serializer_class = AreaSerializer

    @action(detail=True, methods=['get'])
    def teams(self, request, pk=None):
        area = self.get_object()
        teams = area.teams.all()
        return Response(TeamSerializer(teams, many=True).data)


class TeamViewSet(viewsets.ModelViewSet):
    queryset = Team.objects.all()
    serializer_class = TeamSerializer

    def get_queryset(self):
        qs = super().get_queryset()
        area_id = self.request.query_params.get('area')
        if area_id:
            qs = qs.filter(area_id=area_id)
        return qs

    @action(detail=True, methods=['post'])
    def add_member(self, request, pk=None):
        team = self.get_object()
        user_id = request.data.get('user_id')
        try:
            user = User.objects.get(pk=user_id)
        except User.DoesNotExist:
            return Response({'error': 'Usuario no encontrado'}, status=status.HTTP_404_NOT_FOUND)
        team.members.add(user)
        return Response(TeamSerializer(team).data)

    @action(detail=True, methods=['post'])
    def remove_member(self, request, pk=None):
        team = self.get_object()
        user_id = request.data.get('user_id')
        try:
            user = User.objects.get(pk=user_id)
        except User.DoesNotExist:
            return Response({'error': 'Usuario no encontrado'}, status=status.HTTP_404_NOT_FOUND)
        team.members.remove(user)
        return Response(TeamSerializer(team).data)


class ProjectViewSet(viewsets.ModelViewSet):
    queryset = Project.objects.select_related('team', 'owner').prefetch_related(
        'sections__tasks__assignee',
        'sections__tasks__assigned_by',
        'sections__tasks__subtasks',
    ).all()

    def get_serializer_class(self):
        if self.action == 'list':
            return ProjectListSerializer
        return ProjectSerializer

    def get_queryset(self):
        qs = super().get_queryset()
        team_id = self.request.query_params.get('team')
        if team_id:
            qs = qs.filter(team_id=team_id)
        return qs


class SectionViewSet(viewsets.ModelViewSet):
    queryset = Section.objects.all()
    serializer_class = SectionSerializer

    def get_queryset(self):
        qs = super().get_queryset()
        project_id = self.request.query_params.get('project')
        if project_id:
            qs = qs.filter(project_id=project_id)
        return qs

    @action(detail=False, methods=['post'])
    def reorder(self, request):
        items = request.data.get('order', [])
        for item in items:
            Section.objects.filter(pk=item['id']).update(order=item['order'])
        return Response({'ok': True})


class TaskViewSet(viewsets.ModelViewSet):
    queryset = Task.objects.select_related('assignee', 'assigned_by', 'section__project').all()
    serializer_class = TaskSerializer

    def get_queryset(self):
        from django.db.models import Q
        qs = super().get_queryset()
        user = self.request.user

        if not user.is_staff:
            qs = qs.filter(
                Q(visibility='public') |
                Q(assignee=user) |
                Q(assigned_by=user)
            )

        section_id = self.request.query_params.get('section')
        project_id = self.request.query_params.get('project')
        assignee_id = self.request.query_params.get('assignee')
        status_filter = self.request.query_params.get('status')
        parent = self.request.query_params.get('parent')

        if section_id:
            qs = qs.filter(section_id=section_id)
        if project_id:
            qs = qs.filter(section__project_id=project_id)
        if assignee_id:
            qs = qs.filter(assignee_id=assignee_id)
        if status_filter:
            qs = qs.filter(status=status_filter)
        if parent == 'none':
            qs = qs.filter(parent__isnull=True)
        elif parent:
            qs = qs.filter(parent_id=parent)

        return qs.distinct()

    def perform_update(self, serializer):
        instance = serializer.instance
        user = self.request.user
        new_assignee = serializer.validated_data.get('assignee', instance.assignee)
        new_status = serializer.validated_data.get('status', instance.status)

        extra = {}
        if new_assignee and new_assignee != instance.assignee:
            extra['assigned_by'] = user
            if user.is_staff:
                extra['assignment_status'] = Task.AssignmentStatus.DIRECT
            else:
                extra['assignment_status'] = Task.AssignmentStatus.PENDING

        if new_status == Task.Status.COMPLETED and instance.status != Task.Status.COMPLETED:
            extra['completed_at'] = timezone.now()
            serializer.save(**extra)
            if instance.recurrence_type != Task.RecurrenceType.NONE:
                instance.refresh_from_db()
                instance.create_next_occurrence()
        elif new_status != Task.Status.COMPLETED and instance.status == Task.Status.COMPLETED:
            extra['completed_at'] = None
            serializer.save(**extra)
        else:
            serializer.save(**extra)

    def perform_create(self, serializer):
        user = self.request.user
        assignee = serializer.validated_data.get('assignee')
        if assignee and assignee != user:
            if user.is_staff:
                serializer.save(assigned_by=user, assignment_status=Task.AssignmentStatus.DIRECT)
            else:
                serializer.save(assigned_by=user, assignment_status=Task.AssignmentStatus.PENDING)
        else:
            serializer.save(assigned_by=user, assignment_status=Task.AssignmentStatus.DIRECT)

    @action(detail=True, methods=['post'])
    def accept(self, request, pk=None):
        task = self.get_object()
        if task.assignee != request.user:
            return Response({'error': 'Solo el asignado puede aceptar'}, status=status.HTTP_403_FORBIDDEN)
        if task.assignment_status != Task.AssignmentStatus.PENDING:
            return Response({'error': 'Esta tarea no está pendiente de aprobación'}, status=status.HTTP_400_BAD_REQUEST)
        task.assignment_status = Task.AssignmentStatus.ACCEPTED
        task.save()
        return Response(TaskSerializer(task).data)

    @action(detail=True, methods=['post'])
    def reject(self, request, pk=None):
        task = self.get_object()
        if task.assignee != request.user:
            return Response({'error': 'Solo el asignado puede rechazar'}, status=status.HTTP_403_FORBIDDEN)
        if task.assignment_status != Task.AssignmentStatus.PENDING:
            return Response({'error': 'Esta tarea no está pendiente de aprobación'}, status=status.HTTP_400_BAD_REQUEST)
        task.assignment_status = Task.AssignmentStatus.REJECTED
        task.assignee = None
        task.save()
        return Response(TaskSerializer(task).data)

    @action(detail=False, methods=['get'])
    def pending_assignments(self, request):
        tasks = Task.objects.filter(
            assignee=request.user,
            assignment_status=Task.AssignmentStatus.PENDING,
        )
        return Response(TaskSerializer(tasks, many=True).data)

    @action(detail=True, methods=['get'])
    def subtasks(self, request, pk=None):
        task = self.get_object()
        subtasks = task.subtasks.all()
        return Response(TaskSerializer(subtasks, many=True).data)

    @action(detail=False, methods=['post'])
    def reorder(self, request):
        items = request.data.get('order', [])
        for item in items:
            Task.objects.filter(pk=item['id']).update(
                order=item['order'],
                section_id=item.get('section', None) or Task.objects.get(pk=item['id']).section_id,
            )
        return Response({'ok': True})


class AssetViewSet(viewsets.ModelViewSet):
    queryset = Asset.objects.all()
    serializer_class = AssetSerializer

    def get_queryset(self):
        qs = super().get_queryset()
        project_id = self.request.query_params.get('project')
        task_id = self.request.query_params.get('task')
        category = self.request.query_params.get('category')
        if project_id:
            qs = qs.filter(project_id=project_id)
        if task_id:
            qs = qs.filter(task_id=task_id)
        if category:
            if category == 'email':
                qs = qs.filter(asset_type=Asset.AssetType.EMAIL)
            elif category == 'link':
                qs = qs.filter(asset_type=Asset.AssetType.LINK)
            else:
                qs = qs.filter(asset_type=Asset.AssetType.FILE).exclude(mime_type='message/rfc822')
        return qs

    def perform_create(self, serializer):
        asset = serializer.save(uploaded_by=self.request.user)
        if asset.file:
            asset.file_size = asset.file.size
            import mimetypes
            mime, _ = mimetypes.guess_type(asset.file.name)
            asset.mime_type = mime or ''
            if asset.file_extension == 'eml':
                asset.asset_type = Asset.AssetType.EMAIL
                asset.mime_type = 'message/rfc822'
            if not asset.name or asset.name == 'undefined':
                asset.name = asset.file.name.split('/')[-1]
            asset.save()

    @action(detail=True, methods=['get'])
    def parse_eml(self, request, pk=None):
        import email as email_lib
        from email import policy
        import base64

        asset = self.get_object()
        if asset.file_extension != 'eml' and asset.asset_type != Asset.AssetType.EMAIL:
            return Response({'error': 'No es un archivo .eml'}, status=status.HTTP_400_BAD_REQUEST)

        try:
            with asset.file.open('rb') as f:
                msg = email_lib.message_from_binary_file(f, policy=policy.default)

            result = {
                'subject': str(msg.get('subject', '')),
                'from': str(msg.get('from', '')),
                'to': str(msg.get('to', '')),
                'cc': str(msg.get('cc', '')) or None,
                'date': str(msg.get('date', '')),
                'body_text': '',
                'body_html': '',
                'attachments': [],
            }

            att_index = 0
            if msg.is_multipart():
                for part in msg.walk():
                    content_type = part.get_content_type()
                    disposition = str(part.get('Content-Disposition', ''))

                    if 'attachment' in disposition:
                        filename = part.get_filename() or 'adjunto'
                        payload = part.get_payload(decode=True)
                        result['attachments'].append({
                            'index': att_index,
                            'filename': filename,
                            'content_type': content_type,
                            'size': len(payload) if payload else 0,
                        })
                        att_index += 1
                    elif content_type == 'text/plain' and not result['body_text']:
                        payload = part.get_payload(decode=True)
                        if payload:
                            result['body_text'] = payload.decode('utf-8', errors='replace')
                    elif content_type == 'text/html' and not result['body_html']:
                        payload = part.get_payload(decode=True)
                        if payload:
                            result['body_html'] = payload.decode('utf-8', errors='replace')
            else:
                payload = msg.get_payload(decode=True)
                if payload:
                    if msg.get_content_type() == 'text/html':
                        result['body_html'] = payload.decode('utf-8', errors='replace')
                    else:
                        result['body_text'] = payload.decode('utf-8', errors='replace')

            return Response(result)
        except Exception as e:
            return Response({'error': f'Error al parsear el archivo: {str(e)}'}, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=True, methods=['get'], url_path='eml_attachment/(?P<att_index>[0-9]+)')
    def eml_attachment(self, request, pk=None, att_index=None):
        import email as email_lib
        from email import policy
        from django.http import HttpResponse

        asset = self.get_object()
        if asset.file_extension != 'eml' and asset.asset_type != Asset.AssetType.EMAIL:
            return Response({'error': 'No es un archivo .eml'}, status=status.HTTP_400_BAD_REQUEST)

        try:
            att_index = int(att_index)
            with asset.file.open('rb') as f:
                msg = email_lib.message_from_binary_file(f, policy=policy.default)

            current = 0
            for part in msg.walk():
                disposition = str(part.get('Content-Disposition', ''))
                if 'attachment' in disposition:
                    if current == att_index:
                        payload = part.get_payload(decode=True)
                        filename = part.get_filename() or 'adjunto'
                        content_type = part.get_content_type()
                        response = HttpResponse(payload, content_type=content_type)
                        response['Content-Disposition'] = f'attachment; filename="{filename}"'
                        return response
                    current += 1

            return Response({'error': 'Adjunto no encontrado'}, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)
