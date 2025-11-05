from datetime import datetime
from django.contrib.sessions.models import Session
from django.utils import timezone
from django.db import transaction
import logging

logger = logging.getLogger(__name__)

from .models import Campaign, Employee
from attendance.models import WorkDay, ActivitySession


# --------------------------------------------------
# 🔐 Session utilities
# --------------------------------------------------

def logout_user(user):
    sessions = Session.objects.filter()
    for session in sessions:
        data = session.get_decoded()
        if data.get('_auth_user_id') == str(user.id):
            session.delete()


def force_logout_all_users():
    """
    Deletes all active sessions, effectively logging out all users.
    """
    Session.objects.all().delete()
    print(f"[{datetime.now()}] All users have been logged out by Django Q task.")


# --------------------------------------------------
# ⏰ Auto Logout by Campaign
# --------------------------------------------------

def auto_logout_by_campaign():
    """
    Cierra automáticamente la jornada laboral de empleados cuyas campañas
    alcanzaron la hora de apagado (shutdown_time).

    ✅ Compatible con USE_TZ=False
    ✅ Seguro si en el futuro se activa USE_TZ=True
    """
    # --- Safe datetime handling ---
    now = timezone.now()
    # If USE_TZ = False, timezone.now() is naive; if True, it’s aware.
    if timezone.is_naive(now):
        # Local naive datetime
        now = datetime.now()
    else:
        # Convert to local timezone if USE_TZ=True
        now = timezone.localtime(now)

    current_time = now.time()
    logger.info(f"🕒 Ejecutando auto_logout_by_campaign a las {current_time}")

    # --- Buscar campañas activas con hora de apagado definida ---
    campaigns = Campaign.objects.filter(is_active=True, shutdown_time__isnull=False)
    if not campaigns.exists():
        logger.info("⚠️ No hay campañas activas con shutdown_time definido.")
        return "No campaigns with shutdown_time"

    total_logged_out = 0
    for campaign in campaigns:
        try:
            shutdown = campaign.shutdown_time
            logger.info(f"📢 Revisando campaña '{campaign.name}' (shutdown={shutdown})")

            if current_time >= shutdown:
                employees = Employee.objects.filter(current_campaign=campaign, is_logged_in=True)
                logger.info(f"👥 {employees.count()} empleados conectados en '{campaign.name}'")

                for emp in employees:
                    with transaction.atomic():
                        success = _logout_employee(emp)
                        if success:
                            total_logged_out += 1
                            logger.info(f"✅ Empleado '{emp}' desconectado automáticamente.")
                        else:
                            logger.warning(f"⚠️ No se pudo cerrar sesión para '{emp}'")
            else:
                logger.debug(f"⏳ Todavía no es hora para '{campaign.name}'")

        except Exception as e:
            logger.error(f"❌ Error procesando campaña '{campaign.name}': {str(e)}")

    logger.info(f"🏁 Auto logout completado. Total empleados deslogueados: {total_logged_out}")
    return f"Auto logout completed. {total_logged_out} employees logged out."


# --------------------------------------------------
# 🧰 Helpers
# --------------------------------------------------

def _logout_employee(employee):
    """
    Cierra sesión del empleado y finaliza su jornada laboral de forma segura.
    """
    try:
        now = datetime.now() if timezone.is_naive(timezone.now()) else timezone.localtime()

        # 1️⃣ Eliminar sesiones activas del usuario
        _delete_user_sessions(employee.user)

        # 2️⃣ Buscar WorkDay activo
        work_day = WorkDay.objects.filter(employee=employee, status='active').first()
        if not work_day:
            logger.info(f"⚠️ {employee} no tiene WorkDay activo.")
            return False

        # 3️⃣ Cerrar sesión activa (si existe)
        active_session = work_day.get_active_session()
        if active_session:
            active_session.end_time = now
            active_session.notes = ((active_session.notes or "") + "\nLogout by system").strip()
            active_session.save(update_fields=["end_time", "notes"])
            logger.debug(f"🗒️ Sesión activa cerrada para {employee}")
        else:
            # Si no hay sesión activa, crear una técnica para registrar el evento
            ActivitySession.objects.create(
                work_day=work_day,
                session_type="technical",
                start_time=now,
                end_time=now,
                notes="Logout by system (no active session)",
                auto_created=True
            )

        # 4️⃣ Finalizar el día laboral
        work_day.check_out = now
        work_day.status = "completed"
        work_day.notes = ((work_day.notes or "") + "\nLogout by system").strip()
        work_day.calculate_metrics()
        work_day.save(update_fields=[
            "check_out", "status", "notes",
            "total_work_time", "total_break_time",
            "total_lunch_time", "productive_hours",
            "break_count"
        ])

        # 5️⃣ Marcar empleado como desconectado
        employee.is_logged_in = False
        employee.last_logout = now
        employee.save(update_fields=["is_logged_in", "last_logout"])

        return True

    except Exception as e:
        logger.error(f"❌ Error al cerrar sesión para {employee}: {str(e)}")
        return False


def _delete_user_sessions(user):
    """
    Elimina todas las sesiones activas de un usuario.
    """
    deleted = 0
    for session in Session.objects.all():
        try:
            data = session.get_decoded()
            if data.get('_auth_user_id') == str(user.id):
                session.delete()
                deleted += 1
        except Exception:
            continue
    logger.debug(f"🗑️ {deleted} sesiones eliminadas para {user.username}")
    return deleted




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