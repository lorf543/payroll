from datetime import datetime
from django.contrib.sessions.models import Session
from django.utils import timezone
from django.db import transaction
import logging

from core.models import Campaign, Employee
from attendance.models import ActivitySession, WorkDay

logger = logging.getLogger(__name__)



#from django_q.models import Schedule

# # Programar logout automático por campaña (ejecutar cada hora)
# Schedule.objects.get_or_create(
#     name="Auto Logout by Campaign - Hourly",
#     func='your_app.utils.auto_logout_by_campaign',
#     schedule_type=Schedule.HOURLY,
# )

# # Programar force logout de emergencia (ejecutar cada 6 horas como prevención)
# Schedule.objects.get_or_create(
#     name="Force Logout All - Emergency",
#     func='your_app.utils.force_logout_all_users', 
#     schedule_type=Schedule.HOURLY * 6,
#     repeats=-1  # Se repite indefinidamente
# )


def auto_logout_by_campaign(request=None):
    """
    Unified function for automatic logout by campaign shutdown time.
    
    Can be used as:
    - Django Q scheduled task (call without request)
    - Web view (call with request)
    - Management command
    """
    now = timezone.now()
    current_time = timezone.localtime(now).time()
    
    logger.info(f"🕒 Running auto_logout_by_campaign at {current_time}")

    campaigns = Campaign.objects.filter(is_active=True, shutdown_time__isnull=False)
    if not campaigns.exists():
        logger.info("⚠️ No active campaigns with shutdown_time defined.")
        return _return_result("No campaigns to process.", request)

    total_logged_out = 0
    campaigns_processed = 0
    detailed_results = []

    for campaign in campaigns:
        shutdown = campaign.shutdown_time
        logger.info(f"📢 Checking campaign '{campaign.name}' (shutdown={shutdown})")

        if current_time < shutdown:
            logger.debug(f"⏳ Not yet time for '{campaign.name}'.")
            continue

        campaigns_processed += 1
        employees = Employee.objects.filter(current_campaign=campaign, is_logged_in=True)
        campaign_logged_out = 0
        
        logger.info(f"👥 Found {employees.count()} logged-in employees in '{campaign.name}'")

        for employee in employees:
            try:
                with transaction.atomic():
                    if _logout_employee_comprehensive(employee, now, "Campaign shutdown"):
                        total_logged_out += 1
                        campaign_logged_out += 1
                        logger.info(f"✅ {employee} logged out automatically from campaign '{campaign.name}'")
            except Exception as e:
                logger.error(f"❌ Error logging out {employee} from campaign '{campaign.name}': {e}")

        detailed_results.append(f"Campaign '{campaign.name}': {campaign_logged_out} employees logged out")

    # Result summary
    result_message = (
        f"🏁 Auto logout finished — {total_logged_out} employees logged out from {campaigns_processed} campaigns.\n"
        f"Details:\n" + "\n".join(f"• {result}" for result in detailed_results)
    )
    
    logger.info(result_message)
    return _return_result(result_message, request)


def force_logout_all_users(request=None):
    """
    Unified function for force logout all users.
    
    Can be used as:
    - Django Q emergency task (call without request)  
    - Web view (call with request)
    - Management command
    """
    now = timezone.now()
    
    try:
        with transaction.atomic():
            # 1. ✅ Cerrar todas las ActivitySession activas
            active_sessions = ActivitySession.objects.filter(end_time__isnull=True)
            session_count = active_sessions.count()
            
            for session in active_sessions:
                session.end_time = now
                session.notes = f"{session.notes or ''}\nForcefully closed by system at {now}".strip()
                session.save(update_fields=['end_time', 'notes'])
            
            # 2. ✅ Actualizar WorkDays activos
            active_workdays = WorkDay.objects.filter(status='active')
            workday_count = active_workdays.count()
            
            for workday in active_workdays:
                workday.check_out = now
                workday.status = 'completed'
                workday.notes = f"{workday.notes or ''}\nForcefully closed by system at {now}".strip()
                workday.calculate_daily_totals()
                workday.save()
            
            # 3. ✅ Marcar todos los empleados como logout
            employee_count = Employee.objects.filter(is_logged_in=True).update(
                is_logged_in=False,
                last_logout=now
            )
            
            # 4. ✅ Eliminar sesiones de autenticación
            session_auth_count = Session.objects.all().count()
            Session.objects.all().delete()
            
            result_message = (
                f"✅ Force logout completed at {now}:\n"
                f"• {session_count} active work sessions closed\n"
                f"• {workday_count} active workdays completed\n" 
                f"• {employee_count} employees logged out\n"
                f"• {session_auth_count} authentication sessions deleted"
            )
            
            logger.info(result_message)
            return _return_result(result_message, request)
            
    except Exception as e:
        error_message = f"❌ Error during force logout: {str(e)}"
        logger.error(error_message)
        return _return_result(error_message, request, is_error=True)


def _logout_employee_comprehensive(employee, now, reason="System"):
    """
    Comprehensive employee logout - safely closes all active sessions.
    """
    try:
        with transaction.atomic():
            # 1. Cerrar ActivitySessions activas del empleado
            active_sessions = ActivitySession.objects.filter(
                work_day__employee=employee,
                end_time__isnull=True
            )
            
            for session in active_sessions:
                session.end_time = now
                session.notes = f"{session.notes or ''}\nAuto-logout: {reason} at {now}".strip()
                session.save(update_fields=['end_time', 'notes'])
            
            # 2. Cerrar WorkDays activos del empleado
            active_workdays = WorkDay.objects.filter(
                employee=employee,
                status='active'
            )
            
            for workday in active_workdays:
                workday.check_out = now
                workday.status = 'completed'
                workday.notes = f"{workday.notes or ''}\nAuto-logout: {reason} at {now}".strip()
                workday.calculate_daily_totals()
                workday.save()
            
            # 3. Eliminar sesiones de autenticación del usuario
            _delete_user_sessions_comprehensive(employee.user)
            
            # 4. Actualizar estado del empleado
            employee.is_logged_in = False
            employee.last_logout = now
            employee.save(update_fields=['is_logged_in', 'last_logout', 'updated_at'])
            
            logger.debug(f"✅ Comprehensive logout completed for {employee}")
            return True
            
    except Exception as e:
        logger.error(f"❌ Comprehensive logout failed for {employee}: {e}")
        return False


def _delete_user_sessions_comprehensive(user):
    """Delete all sessions for a specific user."""
    deleted = 0
    for session in Session.objects.all():
        try:
            data = session.get_decoded()
            if data.get('_auth_user_id') == str(user.id):
                session.delete()
                deleted += 1
        except Exception as e:
            logger.debug(f"Could not decode session: {e}")
            continue
    
    logger.debug(f"🗑️ {deleted} auth sessions deleted for {user.username}")
    return deleted


def _return_result(message, request=None, is_error=False):
    """
    Helper to return appropriate response based on context.
    """
    if request is None:
        # Called as task/command - return string
        return message
    else:
        # Called as web view - return HttpResponse
        from django.http import HttpResponse
        status = 500 if is_error else 200
        return HttpResponse(message, status=status)