from django.core.management.base import BaseCommand
from django.utils import timezone
from django.db import transaction
from django.contrib.sessions.models import Session
from datetime import datetime, time
import logging

from core.models import Campaign, Employee
from attendance.models import WorkDay, ActivitySession

logger = logging.getLogger(__name__)



#python manage.py auto_logout_campaigns


# from django_q.models import Schedule

# Schedule.objects.create(
#     name="Auto logout by campaign",
#     func="your_app.tasks.run_auto_logout_task",
#     schedule_type=Schedule.HOURLY,  # or Schedule.DAILY
# )

# from django_q.models import Schedule

# Schedule.objects.create(
#     name="Auto logout by campaign",
#     func="django.core.management.call_command",
#     args="auto_logout_campaigns",
#     schedule_type=Schedule.HOURLY,  # or Schedule.DAILY
# )


class Command(BaseCommand):
    help = "Automatically logs out employees whose campaigns have reached their shutdown time."

    def handle(self, *args, **options):
        result = auto_logout_by_campaign()
        self.stdout.write(self.style.SUCCESS(result))

def auto_logout_by_campaign():
    """
    Automatically logs out employees whose campaigns reached shutdown time.
    Only affects employees in campaigns that have reached shutdown time.
    """
    now = timezone.now()
    current_time = timezone.localtime(now).time()
    
    logger.info(f"🕒 Running auto_logout_by_campaign at {current_time}")

    # Solo campañas activas con shutdown_time definido
    campaigns = Campaign.objects.filter(
        is_active=True, 
        shutdown_time__isnull=False
    )
    
    if not campaigns.exists():
        logger.info("⚠️ No active campaigns with shutdown_time defined.")
        return "No campaigns to process."

    total_logged_out = 0
    campaigns_processed = 0

    for campaign in campaigns:
        shutdown = campaign.shutdown_time
        logger.info(f"📢 Checking campaign '{campaign.name}' (shutdown={shutdown})")

        # Si no es hora de shutdown, saltar
        if current_time < shutdown:
            logger.debug(f"⏰ Campaign '{campaign.name}' not yet at shutdown time")
            continue

        campaigns_processed += 1
        
        # Solo empleados LOGUEADOS en ESTA campaña
        employees = Employee.objects.filter(
            current_campaign=campaign, 
            is_logged_in=True
        )
        logger.info(f"👥 Found {employees.count()} logged-in employees in '{campaign.name}'")

        for employee in employees:
            try:
                with transaction.atomic():
                    if _logout_employee(employee, now):
                        total_logged_out += 1
                        logger.info(f"✅ {employee} logged out automatically.")
                    else:
                        logger.warning(f"⚠️ Failed to logout {employee}")
                        
            except Exception as e:
                logger.error(f"❌ Error logging out {employee}: {e}", exc_info=True)
                # Continuar con el siguiente empleado

    logger.info(f"🏁 Auto logout finished — {total_logged_out} employees logged out from {campaigns_processed} campaigns.")
    return f"{total_logged_out} employees logged out from {campaigns_processed} campaigns."

def _logout_employee(employee, now):
    """
    Safely ends active work sessions and logs the employee out.
    Returns True if successful, False otherwise.
    """
    try:
        with transaction.atomic():
            # 1. Encontrar el día activo
            work_day = WorkDay.objects.filter(
                employee=employee, 
                status="active"
            ).first()
            
            if not work_day:
                logger.warning(f"📅 No active workday found for {employee}")
                # Pero igual marcar como logout si no hay día activo
                employee.is_logged_in = False
                employee.last_logout = now
                employee.save(update_fields=["is_logged_in", "last_logout"])
                return True

            # 2. Cerrar sesión activa si existe
            active_session = work_day.get_active_session()
            if active_session:
                active_session.end_time = now
                notes = f"{active_session.notes or ''}\nAuto-logout by system at {now.strftime('%H:%M')}".strip()
                active_session.notes = notes
                active_session.save(update_fields=["end_time", "notes"])
                logger.debug(f"📝 Closed active session for {employee}")
            else:
                # Crear sesión técnica para registrar el logout
                ActivitySession.objects.create(
                    work_day=work_day,
                    session_type="technical",
                    start_time=now - timezone.timedelta(minutes=1),  # 1 minuto antes
                    end_time=now,
                    notes="Auto-logout by system (no active session found)",
                    auto_created=True
                )
                logger.debug(f"📝 Created technical session for {employee}")

            # 3. Actualizar WorkDay
            work_day.check_out = now
            work_day.status = "completed"
            work_day_notes = f"{work_day.notes or ''}\nAuto-logout by system at {now.strftime('%H:%M')}".strip()
            work_day.notes = work_day_notes
            
            # Recalcular métricas
            work_day.calculate_daily_totals()
            
            work_day.save(update_fields=[
                "check_out", "status", "notes",
                "total_work_time", "total_break_time",
                "total_lunch_time", "productive_hours",
                "break_count", "updated_at"
            ])

            # 4. Actualizar Employee - SOLO ESTE EMPLEADO
            employee.is_logged_in = False
            employee.last_logout = now
            employee.save(update_fields=["is_logged_in", "last_logout", "updated_at"])

            # 5. Eliminar sesiones de este usuario específico
            sessions_deleted = _delete_user_sessions(employee.user)
            logger.debug(f"🗑️ Deleted {sessions_deleted} sessions for {employee.user.username}")

            return True

    except Exception as e:
        logger.error(f"❌ Critical error logging out {employee}: {e}", exc_info=True)
        return False

def _delete_user_sessions(user):
    """Deletes all active sessions for a specific user."""
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
    
    return deleted

# Función adicional para forzar logout de TODOS (solo para emergencias)
def force_logout_all_users():
    """
    Deletes all active sessions and marks all employees as logged out.
    USE WITH CAUTION - only for emergencies.
    """
    now = timezone.now()
    logger.warning("🚨 FORCE LOGOUT ALL USERS - EMERGENCY FUNCTION")
    
    try:
        with transaction.atomic():
            # 1. Marcar todos los empleados como logout
            employees_updated = Employee.objects.filter(is_logged_in=True).update(
                is_logged_in=False,
                last_logout=now
            )
            
            # 2. Eliminar todas las sesiones
            sessions_count = Session.objects.all().count()
            Session.objects.all().delete()
            
            logger.warning(f"🚨 Emergency logout: {employees_updated} employees logged out, {sessions_count} sessions deleted")
            
    except Exception as e:
        logger.error(f"❌ Error in force_logout_all_users: {e}")
        raise