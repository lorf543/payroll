from django.apps import AppConfig
from django.db.models.signals import post_migrate

def setup_schedules(sender, **kwargs):
    from django.core.management import call_command
    try:
        call_command('setup_schedules')
    except Exception as e:
        import logging
        logger = logging.getLogger(__name__)
        logger.error(f"❌ Error setting up schedules: {e}")

class CoreConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'core'

    def ready(self):
        # Conectar signal para ejecutar después de migraciones
        post_migrate.connect(setup_schedules, sender=self)
        import core.signals 
