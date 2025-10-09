from django.apps import AppConfig
from django.utils import timezone
from django.db.utils import OperationalError
from django.db import ProgrammingError

class CoreConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'core'

    def ready(self):
        try:
            from django_q.models import Schedule
            from django_q.tasks import schedule

            if not Schedule.objects.filter(name='Daily Logout').exists():
                schedule(
                    func='core.tasks.force_logout_all_users',
                    name='Daily Logout',
                    schedule_type=Schedule.DAILY,
                    repeats=-1
                )
        except (OperationalError, ProgrammingError):
            # La base de datos aún no está lista (migrate en progreso)
            pass