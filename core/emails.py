from django.core.mail import send_mail
from django.conf import settings


def _app_url():
    return getattr(settings, 'APP_URL', 'http://localhost:5173')


def _send(subject, body, to_email):
    if not to_email:
        return
    try:
        send_mail(
            subject=subject,
            message=body,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[to_email],
            fail_silently=True,
        )
    except Exception:
        pass


def notify_task_assigned(task, assigned_by):
    """Notifica al asignado cuando le delegan una tarea (requiere aprobación)."""
    assignee = task.assignee
    if not assignee or not assignee.email:
        return

    project_name = task.section.project.name if task.section and task.section.project else 'un proyecto'
    assignee_name = assignee.get_full_name() or assignee.username
    assigner_name = assigned_by.get_full_name() or assigned_by.username

    body = (
        f"Hola {assignee_name},\n\n"
        f"{assigner_name} te ha asignado la siguiente tarea:\n\n"
        f"  Tarea:    {task.title}\n"
        f"  Proyecto: {project_name}\n"
    )
    if task.due_date:
        body += f"  Fecha límite: {task.due_date.strftime('%d/%m/%Y')}\n"

    body += (
        f"\nPuedes aceptar o rechazar esta asignación desde el Home de AsanaIP:\n"
        f"  {_app_url()}\n\n"
        f"— AsanaIP"
    )

    _send(f"[AsanaIP] Te asignaron una tarea: {task.title}", body, assignee.email)


def notify_task_assigned_direct(task, assigned_by):
    """Notifica al asignado cuando un admin le asigna directamente (sin aprobación)."""
    assignee = task.assignee
    if not assignee or not assignee.email:
        return

    project_name = task.section.project.name if task.section and task.section.project else 'un proyecto'
    assignee_name = assignee.get_full_name() or assignee.username
    assigner_name = assigned_by.get_full_name() or assigned_by.username

    body = (
        f"Hola {assignee_name},\n\n"
        f"{assigner_name} te ha asignado la tarea:\n\n"
        f"  Tarea:    {task.title}\n"
        f"  Proyecto: {project_name}\n"
    )
    if task.due_date:
        body += f"  Fecha límite: {task.due_date.strftime('%d/%m/%Y')}\n"

    body += (
        f"\nIngresá a AsanaIP para ver los detalles:\n"
        f"  {_app_url()}\n\n"
        f"— AsanaIP"
    )

    _send(f"[AsanaIP] Nueva tarea asignada: {task.title}", body, assignee.email)


def notify_assignment_accepted(task):
    """Notifica a quien asignó que el destinatario aceptó la tarea."""
    assigned_by = task.assigned_by
    if not assigned_by or not assigned_by.email:
        return

    assignee_name = task.assignee.get_full_name() or task.assignee.username if task.assignee else 'el usuario'
    assigner_name = assigned_by.get_full_name() or assigned_by.username

    body = (
        f"Hola {assigner_name},\n\n"
        f"{assignee_name} ha ACEPTADO la tarea que le asignaste:\n\n"
        f"  Tarea: {task.title}\n\n"
        f"Podés hacer seguimiento desde AsanaIP:\n"
        f"  {_app_url()}\n\n"
        f"— AsanaIP"
    )

    _send(f"[AsanaIP] Tarea aceptada: {task.title}", body, assigned_by.email)


def notify_assignment_rejected(task):
    """Notifica a quien asignó que el destinatario rechazó la tarea."""
    assigned_by = task.assigned_by
    if not assigned_by or not assigned_by.email:
        return

    # El rechazo limpia el assignee, guardamos el nombre antes de que se pierda
    assignee_name = getattr(task, '_rejected_by_name', 'El usuario')
    assigner_name = assigned_by.get_full_name() or assigned_by.username

    body = (
        f"Hola {assigner_name},\n\n"
        f"{assignee_name} ha RECHAZADO la tarea que le asignaste:\n\n"
        f"  Tarea: {task.title}\n\n"
        f"La tarea ya no tiene asignado. Podés reasignarla desde AsanaIP:\n"
        f"  {_app_url()}\n\n"
        f"— AsanaIP"
    )

    _send(f"[AsanaIP] Tarea rechazada: {task.title}", body, assigned_by.email)
