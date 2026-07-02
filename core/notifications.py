from .models import Notification


def _project_name(task):
    return task.section.project.name if task.section and task.section.project else 'un proyecto'


def notify_task_assigned(task, assigned_by):
    """Asignado: le delegaron una tarea (requiere su aprobación)."""
    if not task.assignee:
        return
    actor_name = assigned_by.get_full_name() or assigned_by.username
    Notification.objects.create(
        recipient=task.assignee,
        actor=assigned_by,
        verb=Notification.Verb.TASK_ASSIGNED,
        task=task,
        message=f'{actor_name} te asignó "{task.title}" — requiere tu aprobación',
    )


def notify_task_assigned_direct(task, assigned_by):
    """Asignado: un admin le asignó una tarea directamente."""
    if not task.assignee:
        return
    actor_name = assigned_by.get_full_name() or assigned_by.username
    Notification.objects.create(
        recipient=task.assignee,
        actor=assigned_by,
        verb=Notification.Verb.TASK_ASSIGNED_DIRECT,
        task=task,
        message=f'{actor_name} te asignó "{task.title}"',
    )


def notify_assignment_accepted(task):
    """Quien asignó: el destinatario aceptó la tarea."""
    if not task.assigned_by:
        return
    assignee_name = task.assignee.get_full_name() or task.assignee.username if task.assignee else 'El usuario'
    Notification.objects.create(
        recipient=task.assigned_by,
        actor=task.assignee,
        verb=Notification.Verb.ASSIGNMENT_ACCEPTED,
        task=task,
        message=f'{assignee_name} aceptó "{task.title}"',
    )


def notify_assignment_rejected(task):
    """Quien asignó: el destinatario rechazó la tarea."""
    if not task.assigned_by:
        return
    assignee_name = getattr(task, '_rejected_by_name', 'El usuario')
    Notification.objects.create(
        recipient=task.assigned_by,
        actor=None,
        verb=Notification.Verb.ASSIGNMENT_REJECTED,
        task=task,
        message=f'{assignee_name} rechazó "{task.title}"',
    )
