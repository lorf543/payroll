from django.core.management.base import BaseCommand
from django_q.models import Schedule

class Command(BaseCommand):
    help = 'Setup scheduled tasks for Django Q'

    def handle(self, *args, **kwargs):
        from core.tasks import auto_logout_by_campaign

        # Registrar tarea de auto-logout cada minuto
        schedule_name = "Auto Logout by Campaign"
        Schedule.objects.update_or_create(
            name=schedule_name,
            defaults={
                "func": "core.tasks.auto_logout_by_campaign",
                "schedule_type": Schedule.MINUTES,
                "minutes": 1,
                "repeats": -1,
            }
        )
        self.stdout.write(self.style.SUCCESS(f"✅ Django Q schedule '{schedule_name}' registered successfully."))
