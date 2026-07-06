from .models import Notification


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


def notify_opportunity_won(opportunity, project, user):
    """Asignados de tareas de la oportunidad + dueño: se ganó el negocio y se creó el proyecto."""
    recipients = {t.assignee for t in opportunity.tasks.all() if t.assignee}
    if opportunity.owner:
        recipients.add(opportunity.owner)

    for recipient in recipients:
        Notification.objects.create(
            recipient=recipient,
            actor=user,
            verb=Notification.Verb.OPPORTUNITY_WON,
            task=None,
            message=f'La oportunidad "{opportunity.name}" fue ganada — se creó el proyecto "{project.name}"',
        )
