from django.apps import AppConfig
from django.core.management import call_command
from django.db.models.signals import post_migrate

def setup_schedules(sender, **kwargs):
    from django.core.management import call_command
    call_command('setup_schedules')

class CoreConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'core'

    def ready(self):
        from django.db.models.signals import post_migrate
        post_migrate.connect(setup_schedules, sender=self)