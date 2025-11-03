# core/tasks.py
from django.contrib.sessions.models import Session
from django.utils import timezone
from django.db import transaction

import logging
logger = logging.getLogger(__name__)

from .models import Campaign, Employee
from attendance.models import WorkDay, ActivitySession

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
    print(f"[{timezone.now()}] All users have been logged out by Django Q task.")



logger = logging.getLogger(__name__)

def auto_logout_employees():
    """
    Tarea Django Q para desloguear automáticamente a empleados
    cuyo tiempo de shutdown ha terminado
    """
    now = timezone.localtime()
    current_time = now.time()
    logger.info(f"🔁 Django Q Auto logout task triggered at local time: {current_time}")

    try:
        # Buscar empleados que están logueados en campañas activas con shutdown time
        employees = Employee.objects.filter(
            current_campaign__isnull=False,
            current_campaign__is_active=True,
            current_campaign__shutdown_time__isnull=False,
        ).select_related('current_campaign', 'user')

        logger.info(f"Found {employees.count()} employees currently logged in with active campaigns.")

        if not employees.exists():
            logger.info("⚠️ No employees found matching the criteria.")
            return "No employees found to logout"

        logged_out_count = 0
        errors = []
        
        for emp in employees:
            campaign = emp.current_campaign
            logger.debug(
                f"Checking employee '{emp}' in campaign '{campaign.name}' "
                f"(shutdown_time={campaign.shutdown_time})"
            )

            if current_time >= campaign.shutdown_time:
                try:
                    with transaction.atomic():
                        success = perform_employee_logout(emp)
                        if success:
                            finalize_employee_work_day(emp)
                            logged_out_count += 1
                            logger.info(f"✅ Employee '{emp}' logged out successfully.")
                        else:
                            errors.append(f"Failed to logout employee {emp}")
                            logger.error(f"❌ Failed to logout employee '{emp}'")
                            
                except Exception as e:
                    error_msg = f"Error logging out employee '{emp}': {str(e)}"
                    errors.append(error_msg)
                    logger.error(f"❌ {error_msg}")
            else:
                logger.debug(
                    f"🕒 Not time yet for '{emp}'. Current time: {current_time}, "
                    f"shutdown time: {campaign.shutdown_time}"
                )

        result_msg = f"Auto logout completed. {logged_out_count} employees logged out."
        if errors:
            result_msg += f" Errors: {len(errors)}"
            logger.warning(f"Completed with {len(errors)} errors")
        
        logger.info(f"✅ {result_msg}")
        return result_msg
        
    except Exception as e:
        error_msg = f"❌ Critical error in auto_logout_employees: {str(e)}"
        logger.error(error_msg)
        return error_msg

def perform_employee_logout(employee):
    """
    Función auxiliar para realizar el logout de un empleado
    CON PROTECCIÓN EXPLÍCITA de current_campaign
    """
    try:
        # Guardar el estado original
        original_campaign = employee.current_campaign
        original_campaign_id = employee.current_campaign_id
        
        logger.info(f"🔒 PROTECTING - Employee '{employee}' current_campaign: {original_campaign}")

        # 1. Eliminar sesiones activas del usuario
        if employee.user:
            sessions_deleted = delete_user_sessions(employee.user)
            logger.info(f"📊 Deleted {sessions_deleted} sessions for user {employee.user.username}")
        else:
            logger.warning(f"⚠️ Employee '{employee}' has no associated user account")
            return False

        # 2. VERIFICACIÓN Y RESTAURACIÓN si fue modificado
        employee.refresh_from_db()
        if employee.current_campaign_id != original_campaign_id:
            logger.warning(f"🚨 DETECTED UNAUTHORIZED CHANGE - Restoring campaign for '{employee}'")
            # Restaurar el valor original
            employee.current_campaign_id = original_campaign_id
            employee.save(update_fields=['current_campaign_id'])
            logger.info(f"✅ RESTORED - Employee '{employee}' current_campaign restored to: {original_campaign}")

        logger.info(f"👤 Employee '{employee}' sessions cleared (current campaign protected)")
        
        return True
        
    except Exception as e:
        logger.error(f"❌ Error in perform_employee_logout for {employee}: {str(e)}")
        return False

def delete_user_sessions(user):
    """
    Elimina todas las sesiones activas de un usuario
    """
    sessions_deleted = 0
    try:
        sessions = Session.objects.all()
        for session in sessions:
            try:
                session_data = session.get_decoded()
                if session_data.get('_auth_user_id') == str(user.id):
                    session.delete()
                    sessions_deleted += 1
                    logger.debug(f"🗑️ Session deleted for user {user.username}")
            except Exception as e:
                logger.warning(f"⚠️ Error decoding session: {str(e)}")
                continue
                
        logger.info(f"✅ Total sessions deleted for {user.username}: {sessions_deleted}")
        return sessions_deleted
    except Exception as e:
        logger.error(f"❌ Error deleting sessions for user {user.username}: {str(e)}")
        return 0    



def finalize_employee_work_day(employee):
    """
    Cierra el día laboral del empleado, agrega nota al WorkDay y a la última sesión activa,
    actualiza métricas y marca al empleado como deslogueado.
    """
    try:
        today = timezone.localdate()

        # Buscar el WorkDay activo
        work_day = WorkDay.objects.filter(
            employee=employee,
            date=today,
            status='active'
        ).first()

        if not work_day:
            logger.info(f"⚠️ No active WorkDay found for {employee} on {today}")
            return False

        now = timezone.now()

        # Cerrar sesión activa y dejar nota
        active_session = work_day.get_active_session()
        if active_session:
            active_session.end_time = now
            note_msg = f"Logout by the system at {now.strftime('%H:%M:%S')}"
            active_session.notes = ((active_session.notes or "") + f"\n{note_msg}").strip()
            active_session.save(update_fields=['end_time', 'notes'])
            logger.info(f"🗒️ Added system logout note to session of {employee}")
        else:
            # Si no hay sesión activa, crear una sesión técnica para registro
            ActivitySession.objects.create(
                work_day=work_day,
                session_type='technical',
                start_time=now,
                end_time=now,
                notes="System auto-logout (no active session)",
                auto_created=True
            )
            logger.info(f"⚙️ Created technical session for system logout (no active session)")

        # Actualizar WorkDay con nota general y marcarlo como completado
        day_note = f"Auto-logout by the system at {now.strftime('%H:%M:%S')} (shutdown time reached)"
        work_day.check_out = now
        work_day.status = 'completed'
        work_day.notes = ((work_day.notes or "") + f"\n{day_note}").strip()
        work_day.calculate_metrics()
        work_day.save(update_fields=[
            'check_out', 'status', 'notes', 'total_work_time',
            'total_break_time', 'total_lunch_time',
            'productive_hours', 'break_count'
        ])
        logger.info(f"🏁 WorkDay finalized automatically for {employee}")

        # Actualizar estado del empleado
        employee.is_logged_in = False
        employee.last_logout = now
        employee.save(update_fields=['is_logged_in', 'last_logout'])
        logger.info(f"👤 Employee '{employee}' marked as logged out (system auto-logout)")

        return True

    except Exception as e:
        logger.error(f"❌ Error finalizing workday for {employee}: {str(e)}")
        return False
    
#celery -A payroll worker --pool=solo --loglevel=info
