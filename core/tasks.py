from datetime import datetime
from django.contrib.sessions.models import Session
from django.utils import timezone
from django.db import transaction
import logging

from core.management.commands.auto_logout_campaigns import auto_logout_by_campaign


def run_auto_logout_task():
    result = auto_logout_by_campaign()
    return result

logger = logging.getLogger(__name__)

from .models import Campaign, Employee
from attendance.models import WorkDay, ActivitySession

# python manage.py shell
# from core.tasks import auto_logout_by_campaign
# auto_logout_by_campaign()


# --------------------------------------------------
# 🔐 Session utilities
# --------------------------------------------------

# def logout_user(user):
#     sessions = Session.objects.filter()
#     for session in sessions:
#         data = session.get_decoded()
#         if data.get('_auth_user_id') == str(user.id):
#             session.delete()


def force_logout_all_users():
    """
    Deletes all active sessions, effectively logging out all users.
    """
    Session.objects.all().delete()
    print(f"[{datetime.now()}] All users have been logged out by Django Q task.")


# # --------------------------------------------------
# # ⏰ Auto Logout by Campaign
# # --------------------------------------------------

# def auto_logout_by_campaign():
#     """
#     Automatically logs out employees whose campaigns reached shutdown time.

#     - Safely handles both naive and timezone-aware datetimes.
#     - Designed for cron/Celery scheduled execution.
#     """
#     now = timezone.localtime(timezone.now()) if timezone.is_aware(timezone.now()) else datetime.now()
#     current_time = now.time()
#     logger.info(f"🕒 Running auto_logout_by_campaign at {current_time}")

#     campaigns = Campaign.objects.filter(is_active=True, shutdown_time__isnull=False)
#     if not campaigns.exists():
#         logger.info("⚠️ No active campaigns with shutdown_time defined.")
#         return "No campaigns to process."

#     total_logged_out = 0
#     for campaign in campaigns:
#         shutdown = campaign.shutdown_time
#         logger.info(f"📢 Checking campaign '{campaign.name}' (shutdown={shutdown})")

#         if current_time < shutdown:
#             logger.debug(f"⏳ Not yet time for '{campaign.name}'.")
#             continue

#         employees = Employee.objects.filter(current_campaign=campaign, is_logged_in=True)
#         logger.info(f"👥 Found {employees.count()} logged-in employees in '{campaign.name}'")

#         for employee in employees:
#             try:
#                 with transaction.atomic():
#                     if _logout_employee(employee, now):
#                         total_logged_out += 1
#                         logger.info(f"✅ {employee} logged out automatically.")
#             except Exception as e:
#                 logger.error(f"❌ Error logging out {employee}: {e}")

#     logger.info(f"🏁 Auto logout finished — {total_logged_out} employees logged out.")
#     return f"{total_logged_out} employees logged out."


# # ----------------------------------------------------------------------
# # 🔧 Helpers
# # ----------------------------------------------------------------------

# def _logout_employee(employee, now):
#     """Safely ends all active work sessions and logs the employee out."""
#     try:
#         _delete_user_sessions(employee.user)

#         work_day = WorkDay.objects.filter(employee=employee, status="active").first()
#         if not work_day:
#             logger.info(f"⚠️ {employee} has no active WorkDay.")
#             return False

#         session = work_day.get_active_session()
#         if session:
#             session.end_time = now
#             session.notes = (f"{session.notes or ''}\nLogout by system").strip()
#             session.save(update_fields=["end_time", "notes"])
#         else:
#             ActivitySession.objects.create(
#                 work_day=work_day,
#                 session_type="technical",
#                 start_time=now,
#                 end_time=now,
#                 notes="Logout by system (no active session)",
#                 auto_created=True
#             )

#         work_day.check_out = now
#         work_day.status = "completed"
#         work_day.notes = (f"{work_day.notes or ''}\nLogout by system").strip()
#         work_day.calculate_metrics()
#         work_day.save(update_fields=[
#             "check_out", "status", "notes",
#             "total_work_time", "total_break_time",
#             "total_lunch_time", "productive_hours",
#             "break_count"
#         ])

#         employee.is_logged_in = False
#         employee.last_logout = now
#         employee.save(update_fields=["is_logged_in", "last_logout"])

#         return True
#     except Exception as e:
#         logger.error(f"❌ Failed to logout {employee}: {e}")
#         return False


# def _delete_user_sessions(user):
#     """Deletes all active sessions for the specified user."""
#     deleted = 0
#     for session in Session.objects.all():
#         try:
#             data = session.get_decoded()
#             if data.get('_auth_user_id') == str(user.id):
#                 session.delete()
#                 deleted += 1
#         except Exception:
#             continue
#     logger.debug(f"🗑️ {deleted} sessions deleted for {user.username}")
#     return deleted


# from django_q.models import Schedule
# from django.utils import timezone

# Schedule.objects.update_or_create(
#     name="Auto Logout by Campaign",
#     defaults={
#         "func": "core.tasks.auto_logout_by_campaign",
#         "schedule_type": Schedule.DAILY,  # ✅ Once per day
#         "repeats": -1,
#     },
# )