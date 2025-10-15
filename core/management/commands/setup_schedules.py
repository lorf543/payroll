# core/management/commands/setup_schedules.py
from django.core.management.base import BaseCommand
from django_q.models import Schedule
from django_q.tasks import schedule

class Command(BaseCommand):
    help = 'Setup initial DjangoQ schedules'

    def handle(self, *args, **options):
        # Crear schedule solo si no existe
        if not Schedule.objects.filter(name='Daily Logout').exists():
            schedule(
                func='core.tasks.force_logout_all_users',
                name='Daily Logout',
                schedule_type=Schedule.DAILY,
                repeats=-1
            )
            self.stdout.write(
                self.style.SUCCESS('Successfully created Daily Logout schedule')
            )
        else:
            self.stdout.write('Daily Logout schedule already exists')