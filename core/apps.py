from django.apps import AppConfig
from django.utils import timezone

class CoreConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'core'

    def ready(self):
        # Importar aquí para evitar errores de importación circular
        from django_q.tasks import schedule
        from django_q.models import Schedule

        # Evitar crear duplicados
        if not Schedule.objects.filter(name='Daily Logout').exists():
            # Programar tarea diaria a las 6 PM
            schedule(
                func='core.tasks.force_logout_all_users',  # módulo + función
                name='Daily Logout',
                schedule_type=Schedule.DAILY,
                repeats=-1,  # repetir indefinidamente
                next_run=timezone.now().replace(hour=18, minute=0, second=0, microsecond=0)
            )
