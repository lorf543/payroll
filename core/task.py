# core/tasks.py
from django.contrib.sessions.models import Session
from django.utils import timezone

def force_logout_all_users():
    """
    Deletes all active sessions, effectively logging out all users.
    """
    Session.objects.all().delete()
    print(f"[{timezone.now()}] All users have been logged out by Django Q task.")
