# core/tasks.py
from django.contrib.sessions.models import Session
from django.utils import timezone



from .models import Campaign



def force_logout_all_users():
    """
    Deletes all active sessions, effectively logging out all users.
    """
    Session.objects.all().delete()
    print(f"[{timezone.now()}] All users have been logged out by Django Q task.")



def logout_users_at_shutdown():
    """Logs out all users whose campaign shutdown time matches current time."""
    now = timezone.localtime().time().replace(second=0, microsecond=0)
    campaigns = Campaign.objects.filter(shutdown_time=now, is_active=True)

    for campaign in campaigns:
        employees = campaign.employees.all()
        for emp in employees:
            user = getattr(emp, "user", None)  # assuming Employee has OneToOneField to User
            if user:
                user.is_active = False  # or use your logout logic
                user.save()
                print(f"[{timezone.now()}] Logged out {user.username} from {campaign.name}")

    print(f"[{timezone.now()}] Checked shutdowns — {campaigns.count()} campaigns triggered.")


#celery -A payroll worker --pool=solo --loglevel=info
