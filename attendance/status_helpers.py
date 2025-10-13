# utils/status_helpers.py
from django.utils import timezone
from attendance.models import AgentStatus

def close_active_status(employee):
    """Cierra cualquier estado activo de un empleado."""
    active = AgentStatus.objects.filter(agent=employee, end_time__isnull=True)
    if active.exists():
        active.update(end_time=timezone.now())
