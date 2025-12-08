from django.shortcuts import render, get_object_or_404, redirect
from django.http import JsonResponse, HttpResponseForbidden,HttpResponse
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_POST
from django.contrib.auth.decorators import user_passes_test
from django.views.decorators.http import require_http_methods
from django.utils import timezone
from django.contrib import messages
from django.contrib.sessions.models import Session
from django.db import transaction
from datetime import datetime, time, timedelta,date
from django.core.paginator import Paginator
from django.db.models import Q
from django.contrib.auth.models import User
from django.contrib.auth import logout
from django.db import transaction
from django_q.tasks import async_task
from django.core.files.storage import default_storage
from django.http import FileResponse
from django.core.files.base import ContentFile
import os


from django.views.generic import DetailView
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
import json

import openpyxl
from openpyxl.styles import Font, Alignment
from openpyxl.utils import get_column_letter
import csv


from core.models import Employee, Campaign
from .forms import EmployeeProfileForm,ActivitySessionForm, OccurrenceForm
from .models import WorkDay,ActivitySession, Occurrence
from .status_helpers import close_active_status
from .utility import *
from core.utils.payroll import get_effective_pay_rate
from .tasks import generate_and_email_team_report
# Create your views here.


def format_duration_simple(duration):
    """
    Acepta timedelta, segundos, minutos o strings numéricos y devuelve 'Xh YYm'
    """
    if not duration:
        return "0h 00m"

    try:
        # Si es timedelta → convertir a segundos
        if hasattr(duration, "total_seconds"):
            total_seconds = int(duration.total_seconds())

        # Si es string numérico → convertir
        elif isinstance(duration, str) and duration.isdigit():
            total_seconds = int(duration)

        # Si es número → asumir que viene en segundos grandes o minutos pequeños
        elif isinstance(duration, (int, float)):
            # Heurística: si es muy grande, probablemente ya está en segundos
            if duration > 3600:  # más de 1 hora en segundos
                total_seconds = int(duration)
            else:
                # probablemente son minutos → convertir a segundos
                total_seconds = int(duration) * 60
        else:
            return "0h 00m"

        hours = total_seconds // 3600
        minutes = (total_seconds % 3600) // 60

        if hours > 0:
            return f"{hours}h {minutes:02d}m"
        return f"{minutes}m"

    except Exception:
        return "0h 00m"


def force_logout_all_users(request):
    """
    Deletes all active sessions and properly closes all work sessions.
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
                workday.calculate_daily_totals()  # Recalcular métricas
                workday.save()
            
            # 3. ✅ Marcar todos los empleados como logout
            employee_count = Employee.objects.filter(is_logged_in=True).update(
                is_logged_in=False,
                last_logout=now
            )
            
            # 4. ✅ Eliminar sesiones de autenticación
            session_auth_count = Session.objects.all().count()
            Session.objects.all().delete()
            
            # Mensaje de confirmación
            message = (
                f"✅ Force logout completed at {now}:\n"
                f"• {session_count} active work sessions closed\n"
                f"• {workday_count} active workdays completed\n" 
                f"• {employee_count} employees logged out\n"
                f"• {session_auth_count} authentication sessions deleted"
            )
            
            print(f"[{datetime.now()}] {message}")
            
            return HttpResponse(message)
            
    except Exception as e:
        error_message = f"❌ Error during force logout: {str(e)}"
        print(f"[{datetime.now()}] {error_message}")
        return HttpResponse(error_message, status=500)



def is_supervisor(user):
    return user.is_staff or user.groups.filter(name='Supervisors').exists()

@login_required
def agent_dashboard(request):
    employee = get_object_or_404(Employee, user=request.user)
    today = timezone.now().date()
    now = timezone.now()

    work_day, _ = WorkDay.objects.get_or_create(employee=employee, date=today)
    current_session = work_day.sessions.filter(end_time__isnull=True).last()
    history = work_day.sessions.all().order_by('-start_time')

    def fmt(td):
        """Formatea timedelta a formato legible"""
        if not td: return "0h 00m"
        total_sec = int(td.total_seconds())
        h, m = divmod(total_sec // 60, 60)
        return f"{h}h {m:02d}m" if h else f"{m}m"

    # 🔥 CÁLCULO EN TIEMPO REAL
    # Obtener todas las sesiones completadas
    completed_sessions = work_day.sessions.filter(end_time__isnull=False)
    
    # Calcular tiempos de sesiones completadas
    completed_work = timedelta(0)
    completed_break = timedelta(0)
    completed_lunch = timedelta(0)
    break_count = 0
    
    for session in completed_sessions:
        if session.duration:
            if session.session_type == 'work':
                completed_work += session.duration
            elif session.session_type == 'break':
                completed_break += session.duration
                break_count += 1
            elif session.session_type == 'lunch':
                completed_lunch += session.duration

    # 🔥 Si hay sesión activa, añadir su tiempo transcurrido
    active_work_time = timedelta(0)
    active_break_time = timedelta(0)
    active_lunch_time = timedelta(0)
    
    if current_session:
        elapsed = now - current_session.start_time
        if current_session.session_type == 'work':
            active_work_time = elapsed
        elif current_session.session_type == 'break':
            active_break_time = elapsed
        elif current_session.session_type == 'lunch':
            active_lunch_time = elapsed

    # Totales en tiempo real
    total_work = completed_work + active_work_time
    total_break = completed_break + active_break_time
    total_lunch = completed_lunch + active_lunch_time
    total_time = total_work + total_break + total_lunch

    # 🔥 CÁLCULO DE GANANCIAS DINÁMICO
    payable_hours = total_work.total_seconds() / 3600
    
    # Obtener rate del campaign del empleado
    rate = 0.0
    if employee.current_campaign and employee.current_campaign.hour_rate:
        rate = float(employee.current_campaign.hour_rate)
    
    estimated_earnings = payable_hours * rate

    # Datos para el timer de sesión actual
    current_duration = str(now - current_session.start_time).split('.')[0] if current_session else "0:00:00"
    start_time_iso = current_session.start_time.isoformat() if current_session else None

    # 🔥 Datos adicionales para cálculos dinámicos en frontend
    check_in_iso = work_day.check_in.isoformat() if work_day.check_in else None
    
    daily_stats = {
        'total': fmt(total_time),
        'payable': fmt(total_work),
        'break': fmt(total_break),
        'lunch': fmt(total_lunch),
        'payable_hours': round(payable_hours, 2),
        'money': f"${estimated_earnings:.2f}",
        'break_count': break_count,
        'hourly_rate': rate,
        # 🔥 Datos en segundos para JavaScript
        'total_work_seconds': int(total_work.total_seconds()),
        'total_break_seconds': int(total_break.total_seconds()),
        'total_lunch_seconds': int(total_lunch.total_seconds()),
        'completed_work_seconds': int(completed_work.total_seconds()),
        'completed_break_seconds': int(completed_break.total_seconds()),
        'completed_lunch_seconds': int(completed_lunch.total_seconds()),
    }

    context = {
        'employee': employee,
        'work_day': work_day,
        'current_session': current_session,
        'current_duration': current_duration,
        'start_time_iso': start_time_iso,
        'check_in_iso': check_in_iso,
        'is_active_session': bool(current_session),
        'daily_stats': daily_stats,
        'history': history,
        'today': today,
        'current_session_type': current_session.session_type if current_session else '',
        'form_create_occurrence': OccurrenceForm(),
    }

    return render(request, 'attendance/agent_dashboard.html', context)



@require_http_methods(["POST"])
@login_required
def start_activity(request):
    """
    Iniciar una nueva actividad (HTMX endpoint)
    Con protección contra race conditions y validación de estado duplicado
    """
    employee = get_object_or_404(Employee, user=request.user)
    today = timezone.now().date()

    try:
        with transaction.atomic():
            # ✅ Lock para prevenir race conditions
            work_day = WorkDay.objects.select_for_update().get_or_create(
                employee=employee, 
                date=today
            )[0]

            session_type = request.POST.get('session_type', 'work')

            # ✅ Si es "end_of_day", usar la función específica
            if session_type == 'end_of_day':
                return end_work_day(request)

            # ✅ Verificar SI HAY sesión activa DENTRO de la transacción
            active_session = work_day.get_active_session()
            
            # ✅ NUEVA VALIDACIÓN: Prevenir cambiar al mismo estado
            if active_session and active_session.session_type == session_type:
                messages.error(request, f"You are already in {active_session.get_session_type_display()} status. Please select a different status.")
                return _render_attendance_dashboard(request, employee, work_day)
            
            # ✅ Iniciar nueva sesión (solo si no hay sesión activa y no es el mismo estado)
            session = work_day.start_work_session(
                session_type=session_type,
                notes=request.POST.get('notes', '')
            )

            messages.success(request, f"Status changed to {session.get_session_type_display()}")

            return _render_attendance_dashboard(request, employee, work_day)

    except Exception as e:
        messages.error(request, "System error. Please try again.")
        return _render_attendance_dashboard(request, employee, work_day)

def _render_attendance_dashboard(request, employee, work_day):
    """Función helper para renderizar el dashboard"""
    daily_stats = calculate_daily_stats(work_day)
    history = work_day.sessions.all().order_by('start_time')
    
    context = {
        'employee': employee,
        'work_day': work_day,
        'current_session': work_day.get_active_session(),
        'daily_stats': daily_stats,
        'history': history,
        'today': timezone.now().date(),
    }
    return render(request, 'attendance/agent_dashboard.html', context)

@require_http_methods(["POST"])
@login_required
def end_work_day(request):
    """
    Finalizar día completo (HTMX endpoint)
    """
    employee = get_object_or_404(Employee, user=request.user)
    today = timezone.now().date()
    
    try:
        work_day = WorkDay.objects.get(employee=employee, date=today)
        work_day.end_work_day()
        
        # Recalcular estadísticas finales
        daily_stats = calculate_daily_stats(work_day)
        history = work_day.sessions.all().order_by('start_time')
        
        context = {
            'employee': employee,
            'work_day': work_day,
            'current_session': None,
            'daily_stats': daily_stats,
            'history': history,
            'today': today,
        }
        
        # Mensaje de éxito
        messages.success(request, "Work day ended successfully")
        
        # Retornar todo el dashboard actualizado
        return render(request, 'attendance/agent_dashboard.html', context)
        
    except WorkDay.DoesNotExist:
        return JsonResponse({'error': 'No active work day found'}, status=400)

def calculate_daily_stats(work_day):
    """
    Calcular estadísticas diarias - versión simple
    """
    employee = work_day.employee
    current_campaign = employee.current_campaign
    
    # Tiempos
    total_work_time = work_day.total_work_time or timedelta(0)
    total_break_time = work_day.total_break_time or timedelta(0)
    total_lunch_time = work_day.total_lunch_time or timedelta(0)
    total_time = total_work_time + total_break_time + total_lunch_time
    
    def format_duration(duration):
        """Formatear timedelta a formato legible: 1h 30m"""
        if not duration:
            return "0h 00m"
        
        total_seconds = int(duration.total_seconds())
        hours = total_seconds // 3600
        minutes = (total_seconds % 3600) // 60
        
        if hours > 0:
            return f"{hours}h {minutes:02d}m"
        else:
            return f"{minutes}m"
    
    # Cálculo simple de ganancias
    payable_hours = total_work_time.total_seconds() / 3600
    
    # Tomar el pay rate de la campaña o usar default
    if current_campaign and current_campaign.hour_rate:
        hourly_rate = float(current_campaign.hour_rate)
    else:
        hourly_rate = 1.00  # Default
    
    estimated_earnings = payable_hours * hourly_rate
    
    return {
        'total': format_duration(total_time),
        'payable': format_duration(total_work_time),
        'break': format_duration(total_break_time),
        'lunch': format_duration(total_lunch_time),
        'payable_hours': round(payable_hours, 2),
        'money': f"${estimated_earnings:.2f}",
        'break_count': work_day.break_count or 0,
        'hourly_rate': hourly_rate,
    }



@login_required
def attendance_history(request):
    """
    Vista principal del historial de asistencia - CORREGIDA
    """
    employee = get_object_or_404(Employee, user=request.user)
    
    # Parámetros de filtrado
    date_from = request.GET.get('date_from')
    date_to = request.GET.get('date_to')
    
    work_days = WorkDay.objects.filter(employee=employee).order_by('-date')
    
    # Filtrar por fechas
    if date_from:
        work_days = work_days.filter(date__gte=datetime.strptime(date_from, '%Y-%m-%d'))
    if date_to:
        work_days = work_days.filter(date__lte=datetime.strptime(date_to, '%Y-%m-%d'))

    # Paginación
    paginator = Paginator(work_days, 10)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)


    # Preparar datos para cada día
    days_data = []
    for work_day in page_obj:
        sessions = work_day.sessions.all().order_by('start_time')
        days_data.append({
            'work_day': work_day,
            'sessions': sessions,
            'work_time': format_duration_simple(work_day.total_work_time),
            'break_time': format_duration_simple(work_day.total_break_time),
            'lunch_time': format_duration_simple(work_day.total_lunch_time),
        })
    
    context = {
        'employee': employee,
        'days_data': days_data,
        'page_obj': page_obj,
        'date_from': date_from,
        'date_to': date_to,
        'total_days': work_days.count(),
    }
    
    return render(request, 'attendance/attendance_history.html', context)


@login_required
def export_attendance_excel(request):
    """
    Exporta el historial de asistencia filtrado a un archivo Excel (.xlsx)
    """
    employee = get_object_or_404(Employee, user=request.user)

    # Filtros (mismos que en attendance_history)
    date_from = request.GET.get('date_from')
    date_to = request.GET.get('date_to')

    work_days = WorkDay.objects.filter(employee=employee).order_by('-date')
    if date_from:
        work_days = work_days.filter(date__gte=date_from)
    if date_to:
        work_days = work_days.filter(date__lte=date_to)

    # Crear workbook y hoja
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Attendance History"

    # Título
    ws.merge_cells("A1:E1")
    title_cell = ws["A1"]
    title_cell.value = f"Attendance History - {employee.user.username}"
    title_cell.font = Font(size=14, bold=True)
    title_cell.alignment = Alignment(horizontal="center", vertical="center")

    # Encabezados
    headers = ['Date', 'Work Time', 'Break Time', 'Lunch Time', 'Total Sessions']
    ws.append(headers)

    # Estilos para encabezados
    for col_num, header in enumerate(headers, 1):
        cell = ws.cell(row=2, column=col_num)
        cell.font = Font(bold=True)
        cell.alignment = Alignment(horizontal="center", vertical="center")
        ws.column_dimensions[get_column_letter(col_num)].width = 18


    # Agregar datos
    for work_day in work_days:
        sessions = work_day.sessions.all().order_by('start_time')
        ws.append([
            work_day.date.strftime("%Y-%m-%d"),
            format_duration_simple(work_day.total_work_time),
            format_duration_simple(work_day.total_break_time),
            format_duration_simple(work_day.total_lunch_time),
            sessions.count(),
        ])

    # Preparar respuesta HTTP
    response = HttpResponse(
        content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    )
    filename = f"attendance_history_{employee.user.username}.xlsx"
    response['Content-Disposition'] = f'attachment; filename="{filename}"'

    wb.save(response)
    return response



@login_required
def day_detail(request, date_str):
    """
    Vista detallada de un día específico - CORREGIDA
    """
    employee = get_object_or_404(Employee, user=request.user)
    
    try:
        date_obj = datetime.strptime(date_str, '%Y-%m-%d').date()
        work_day = WorkDay.objects.get(employee=employee, date=date_obj)
        
        sessions = work_day.sessions.all().order_by('start_time')
        
        # Calcular estadísticas del día con manejo de errores
        try:
            money_calculated = calculate_daily_stats(work_day)['money']
        except (AttributeError, TypeError, KeyError):
            money_calculated = "$0.00"
        
        daily_stats = {
            'work_time': format_duration_simple(work_day.total_work_time),
            'break_time': format_duration_simple(work_day.total_break_time),
            'lunch_time': format_duration_simple(work_day.total_lunch_time),
            'money': money_calculated,
            'break_count': work_day.break_count or 0,
        }
        
        context = {
            'employee': employee,
            'work_day': work_day,
            'sessions': sessions,
            'daily_stats': daily_stats,
            'date': date_obj,
        }
        
        return render(request, 'attendance/day_detail.html', context)
        
    except (ValueError, WorkDay.DoesNotExist):
        messages.error(request, "Day not found or no data available.")
        return redirect('attendance_history')
    


@login_required
def employee_profile(request, employee_id=None):
    """
    Vista del perfil del empleado
    """
    # Si no se proporciona employee_id, mostrar el perfil del usuario actual
    if employee_id is None:
        employee = get_object_or_404(Employee, user=request.user)
    else:
        employee = get_object_or_404(Employee, id=employee_id)
    
    # Verificar permisos: solo el propio empleado o superusers pueden ver información sensible
    can_view_sensitive = (request.user == employee.user) or request.user.is_superuser
    
    # Calcular estadísticas de pago si tiene permisos
    payment_stats = calculate_payment_stats(employee) if can_view_sensitive else None
    
    # Obtener campaña actual
    current_campaign = employee.current_campaign
    
    # Preparar skills como lista
    skills_list = []
    if employee.skills:
        skills_list = [skill.strip() for skill in employee.skills.split(',')]
    
    context = {
        'employee': employee,
        'current_campaign': current_campaign,
        'payment_stats': payment_stats,
        'skills_list': skills_list,
        'can_view_sensitive': can_view_sensitive,
    }
    
    return render(request, 'core/employee_profile.html', context)


def calculate_payment_stats(employee):
    """
    Calcular estadísticas de pago para el empleado
    """
    pay_method = None

    
    # Usar hourly rate del puesto como base
    if employee.current_campaign.hour_rate:
        base_rate = float(employee.current_campaign.hour_rate)
        pay_method = 'Campaign Rate / hour'

    
    print(base_rate)
    
    return {
        'pay_method': pay_method,
        'base_rate': base_rate,
        'monthly_earnings': base_rate * 160,
    }

@login_required
def edit_employee_profile(request, employee_id):
    """
    Vista para editar el perfil del empleado
    """
    employee = get_object_or_404(Employee, id=employee_id)
    
    # Verificar que el usuario puede editar este perfil
    if request.user != employee.user and not request.user.is_superuser:
        messages.error(request, "You don't have permission to edit this profile.")
        return redirect('employee_profile')
    
    if request.method == 'POST':
        form = EmployeeProfileForm(request.POST, instance=employee)
        if form.is_valid():
            form.save()
            messages.success(request, "Profile updated successfully!")
            return redirect('employee_profile')
    else:
        form = EmployeeProfileForm(instance=employee)
    
    context = {
        'employee': employee, 
        'form': form,
    }
    
    return render(request, 'core/edit_profile.html', context)




@login_required
def supervisor_dashboard(request):
    """
    Dashboard principal para supervisores
    """
    try:
        # Obtener el empleado que es supervisor
        supervisor = Employee.objects.get(user=request.user, is_supervisor=True)
    except Employee.DoesNotExist:
        messages.error(request, "You don't have supervisor privileges.")
        return redirect('employee_profile')
    
    # Obtener los miembros del equipo con información del usuario
    team_members = Employee.objects.filter(supervisor=supervisor).select_related(
        'user', 'position', 'department', 'current_campaign'
    )

    # Estadísticas del equipo
    total_team_members = team_members.count()
    logged_in_count = team_members.filter(is_logged_in=True).count()
    active_in_campaign = team_members.filter(current_campaign__isnull=False).count()

    
    # Obtener WorkDays de hoy para el equipo
    today = timezone.now().date()
    team_workdays = WorkDay.objects.filter(
        employee__in=team_members,
        date=today
    ).select_related('employee')
    
    # Obtener información de sesiones (logins) más recientes
    from django.contrib.sessions.models import Session
    from django.contrib.auth import get_user_model
    
    User = get_user_model()
    
    # Preparar datos para cada miembro del equipo
    team_data = []
    for member in team_members:
        try:
            workday_today = team_workdays.get(employee=member)
            current_session = workday_today.get_active_session()
            daily_stats = calculate_daily_stats(workday_today)
        except WorkDay.DoesNotExist:
            workday_today = None
            current_session = None
            daily_stats = None
        
        team_data.append({
            'employee': member,
            'workday': workday_today,
            'current_session': current_session,
            'formatted_session': workday_today.get_formatted_session() if workday_today else None,
            'daily_stats': daily_stats,
        })
            
    context = {
        'supervisor': supervisor,
        'team_data': team_data,
        'total_team_members': total_team_members,
        'logged_in_count': logged_in_count,
        'active_in_campaign': active_in_campaign,
        'today': today,
    }
    
    return render(request, 'supervisor/supervisor_dashboard.html', context)




from tempfile import NamedTemporaryFile

login_required
def export_team_report_excel(request):
    """
    Genera y descarga directamente el reporte de equipo en Excel (sin email).
    """
    try:
        supervisor = Employee.objects.get(user=request.user, is_supervisor=True)
    except Employee.DoesNotExist:
        messages.error(request, "You don't have supervisor privileges.")
        return redirect('employee_profile')

    date_from = request.GET.get("date_from")
    date_to = request.GET.get("date_to")

    if not date_from or not date_to:
        messages.error(request, "Please select valid dates.")
        return redirect("supervisor_dashboard")

    # Convertir fechas
    date_from_dt = datetime.strptime(date_from, "%Y-%m-%d").date()
    date_to_dt = datetime.strptime(date_to, "%Y-%m-%d").date()

    # Obtener miembros del equipo
    team_members = Employee.objects.filter(supervisor=supervisor)

    work_days = (
        WorkDay.objects.filter(employee__in=team_members, date__range=(date_from_dt, date_to_dt))
        .select_related("employee", "employee__user")
        .prefetch_related("sessions")
        .order_by("date", "employee__user__last_name")
    )

    # Crear Excel
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Team Report"

    bold = Font(bold=True)
    center = Alignment(horizontal="center")

    # Títulos
    ws.merge_cells("A1:Q1")
    ws["A1"] = f"Team Report - Supervisor: {supervisor.user.get_full_name()}"
    ws["A1"].font = Font(bold=True, size=14)
    ws["A1"].alignment = center

    ws.merge_cells("A2:Q2")
    ws["A2"] = f"Generated: {timezone.now().strftime('%Y-%m-%d %H:%M:%S')}"
    ws["A2"].alignment = center

    ws.append([])

    headers = [
        "Agent Name", "Date", "Attendance Status", "Week",
        "Time In",
        "Break 1-start", "Break 1-end", "Break1 Duration",
        "Break 2-start", "Break 2-end", "Break2 Duration",
        "Lunch start", "Lunch end", "Lunch Duration",
        "Time Out",
        "Total Hours",
        "Notes",
    ]
    ws.append(headers)
    for col in range(1, len(headers) + 1):
        ws.cell(row=4, column=col).font = bold
        ws.cell(row=4, column=col).alignment = center

    # Helpers
    def fmt_time(t):
        return t.strftime("%H:%M") if t else "-"

    def fmt_duration(s):
        if not s or not s.start_time or not s.end_time:
            return "-"
        delta = s.end_time - s.start_time
        minutes = delta.total_seconds() // 60
        seconds = int(delta.total_seconds() % 60)
        return f"{int(minutes):02d}:{seconds:02d}"

    def fmt_total(td):
        if td is None:
            return "0.00"
        return f"{td.total_seconds() / 3600:.2f}"

    # Filas
    for wd in work_days:
        sessions = wd.sessions.all()
        work_sessions = sessions.filter(session_type="work").order_by("start_time")
        break_sessions = sessions.filter(session_type="break").order_by("start_time")
        lunch_sessions = sessions.filter(session_type="lunch").order_by("start_time")

        time_in = work_sessions.first().start_time if work_sessions else None
        time_out = work_sessions.last().end_time if work_sessions else None
        break1 = break_sessions[0] if len(break_sessions) >= 1 else None
        break2 = break_sessions[1] if len(break_sessions) >= 2 else None
        lunch = lunch_sessions[0] if lunch_sessions else None

        ws.append([
            wd.employee.user.get_full_name(),
            wd.date.strftime("%m/%d/%Y"),
            wd.get_day_status(),
            wd.date.isocalendar()[1],
            fmt_time(time_in),
            fmt_time(break1.start_time if break1 else None),
            fmt_time(break1.end_time if break1 else None),
            fmt_duration(break1) if break1 else "-",
            fmt_time(break2.start_time if break2 else None),
            fmt_time(break2.end_time if break2 else None),
            fmt_duration(break2) if break2 else "-",
            fmt_time(lunch.start_time if lunch else None),
            fmt_time(lunch.end_time if lunch else None),
            fmt_duration(lunch) if lunch else "-",
            fmt_time(time_out),
            fmt_total(wd.total_work_time),
            wd.notes or "",
        ])

    # Ajustar ancho columnas
    for col_cells in ws.columns:
        max_len = max(len(str(c.value)) if c.value else 0 for c in col_cells)
        ws.column_dimensions[get_column_letter(col_cells[0].column)].width = max_len + 2

    # Crear nombre del archivo
    filename = f"team_report_{supervisor.user.username}_{timezone.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
    
    # Guardar en archivo temporal
    with NamedTemporaryFile(delete=False, suffix='.xlsx') as tmp_file:
        wb.save(tmp_file.name)
        temp_path = tmp_file.name

    try:
        # Leer el archivo y devolverlo como respuesta HTTP
        with open(temp_path, 'rb') as f:
            response = HttpResponse(
                f.read(),
                content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
            )
            response['Content-Disposition'] = f'attachment; filename="{filename}"'
            return response
    finally:
        # Limpiar archivo temporal
        if os.path.exists(temp_path):
            os.remove(temp_path)

@login_required
def team_attendance_history(request):
    """
    Historial de asistencia del equipo completo
    """
    try:
        supervisor = Employee.objects.get(user=request.user, is_supervisor=True)
    except Employee.DoesNotExist:
        messages.error(request, "You don't have supervisor privileges.")
        return redirect('employee_profile')
    
    # Parámetros de filtrado
    date_from = request.GET.get('date_from')
    date_to = request.GET.get('date_to')
    employee_id = request.GET.get('employee')
    
    # Obtener miembros del equipo
    team_members = Employee.objects.filter(supervisor=supervisor)
    
    # Obtener WorkDays del equipo
    work_days = WorkDay.objects.filter(employee__in=team_members).order_by('-date')
    
    # Aplicar filtros
    if date_from:
        work_days = work_days.filter(date__gte=date_from)
    if date_to:
        work_days = work_days.filter(date__lte=date_to)
    if employee_id:
        work_days = work_days.filter(employee_id=employee_id)
    
    # Paginación
    paginator = Paginator(work_days, 15)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    # Preparar datos para cada día
    days_data = []
    for work_day in page_obj:
        sessions = work_day.sessions.all().order_by('start_time')
        days_data.append({
            'work_day': work_day,
            'sessions': sessions,
            'work_time': format_duration_simple(work_day.total_work_time),
            'break_time': format_duration_simple(work_day.total_break_time),
            'lunch_time': format_duration_simple(work_day.total_lunch_time),
        })
    
    context = {
        'supervisor': supervisor,
        'team_members': team_members,
        'days_data': days_data,
        'page_obj': page_obj,
        'date_from': date_from,
        'date_to': date_to,
        'selected_employee': employee_id,
        'total_days': work_days.count(),
    }
    
    return render(request, 'supervisor/team_attendance_history.html', context)

@login_required
def employee_attendance_detail(request, employee_id):
    """
    Vista detallada de asistencia de un empleado específico
    """
    try:
        employee = Employee.objects.get(id=employee_id, is_active=True)
        supervisor = Employee.objects.get(user=request.user, is_supervisor=True)
    except Employee.DoesNotExist:
        messages.error(request, "Employee not found.")
        return redirect('employee_profile')
    
    
    # Parámetros de filtrado
    date_from = request.GET.get('date_from')
    date_to = request.GET.get('date_to')
    
    # Obtener WorkDays del empleado
    work_days = WorkDay.objects.filter(employee=employee).order_by('-date')
    
    if date_from:
        work_days = work_days.filter(date__gte=date_from)
    if date_to:
        work_days = work_days.filter(date__lte=date_to)
    
    # Paginación
    paginator = Paginator(work_days, 10)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    # Estadísticas del empleado
    total_work_days = work_days.count()
    total_work_time = sum((wd.total_work_time.total_seconds() for wd in work_days if wd.total_work_time), 0)
    avg_work_time = total_work_time / total_work_days if total_work_days > 0 else 0
    
    context = {
        'supervisor': supervisor,
        'employee': employee,
        'page_obj': page_obj,
        'date_from': date_from,
        'date_to': date_to,
        'total_work_days': total_work_days,

        # FIX: total_work_time está en segundos → usar seconds, NO minutes
        'total_work_time': format_duration_simple(timedelta(seconds=total_work_time)),

        # FIX: avg_work_time también en segundos
        'avg_work_time': format_duration_simple(timedelta(seconds=avg_work_time)),
    }
    
    return render(request, 'supervisor/employee_attendance_detail.html', context)

@login_required
def export_employee_attendance_excel(request, employee_id):
    """Exporta los registros de asistencia de un empleado específico a Excel (.xlsx) con detalle de breaks y lunch."""
    try:
        supervisor = Employee.objects.get(user=request.user, is_supervisor=True)
    except Employee.DoesNotExist:
        messages.error(request, "You don't have supervisor privileges.")
        return redirect('employee_profile')

    employee = get_object_or_404(Employee, id=employee_id, supervisor=supervisor)

    # Filtros de fechas
    date_from = request.GET.get('date_from')
    date_to = request.GET.get('date_to')
    if not date_from or not date_to:
        messages.error(request, "You must select a valid start and end date before generating the report.")
        return redirect(request.META.get('HTTP_REFERER', 'employee_profile'))

    try:
        date_from_parsed = datetime.strptime(date_from, "%Y-%m-%d").date()
        date_to_parsed = datetime.strptime(date_to, "%Y-%m-%d").date()
        if date_from_parsed > date_to_parsed:
            messages.error(request, "The start date cannot be later than the end date.")
            return redirect(request.META.get('HTTP_REFERER', 'employee_profile'))
    except ValueError:
        messages.error(request, "Invalid date format. Please select valid dates.")
        return redirect(request.META.get('HTTP_REFERER', 'employee_profile'))

    work_days = WorkDay.objects.filter(
        employee=employee,
        date__range=(date_from_parsed, date_to_parsed)
    ).prefetch_related('sessions').order_by('date')

    # Crear workbook
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Attendance Report"

    bold_font = Font(bold=True)
    center_align = Alignment(horizontal="center")

    # Formateadores
    def format_timedelta(td):
        if not td:
            return "00:00:00"
        total_seconds = int(td.total_seconds())
        hours, remainder = divmod(total_seconds, 3600)
        minutes, seconds = divmod(remainder, 60)
        return f"{hours:02}:{minutes:02}:{seconds:02}"

    def format_duration(s):
        if s.start_time and s.end_time:
            return format_timedelta(s.end_time - s.start_time)
        return "—"

    # Encabezado principal
    ws.merge_cells('A1:P1')
    ws['A1'] = f"Attendance Report for {employee.user.get_full_name()}"
    ws['A1'].font = Font(bold=True, size=14)
    ws['A1'].alignment = center_align

    ws.merge_cells('A2:P2')
    ws['A2'] = f"Date range: {date_from} to {date_to}"
    ws['A2'].alignment = center_align

    ws.merge_cells('A3:P3')
    ws['A3'] = f"Generated at: {timezone.now().strftime('%Y-%m-%d %H:%M:%S')}"
    ws['A3'].alignment = center_align
    ws.append([])

    # Encabezados
    headers = [
        "Date", "Day", "Status", "Check In", "Check Out", "Total Work Time",
        "Break1 Start", "Break1 End", "Break1 Duration",
        "Break2 Start", "Break2 End", "Break2 Duration",
        "Lunch Start", "Lunch End", "Lunch Duration",
        "Work Sessions Count"
    ]
    ws.append(headers)

    for col_num in range(1, len(headers) + 1):
        cell = ws.cell(row=5, column=col_num)
        cell.font = bold_font
        cell.alignment = center_align

    total_seconds = 0

    for wd in work_days:
        total_time = wd.total_work_time or timedelta()
        total_seconds += total_time.total_seconds()

        check_in = wd.check_in.strftime("%I:%M %p") if wd.check_in else "—"
        check_out = wd.check_out.strftime("%I:%M %p") if wd.check_out else "—"

        breaks = [s for s in wd.sessions.all() if s.session_type == 'break'][:2]
        lunch = [s for s in wd.sessions.all() if s.session_type == 'lunch'][:1]

        def fmt_time(t): return t.strftime("%I:%M %p") if t else "—"
        def fmt_duration(s): return s.end_time - s.start_time if s.start_time and s.end_time else None

        break1 = fmt_duration(breaks[0]) if len(breaks) > 0 else None
        break2 = fmt_duration(breaks[1]) if len(breaks) > 1 else None
        lunch_d = fmt_duration(lunch[0]) if lunch else None

        work_sessions_count = wd.sessions.filter(session_type='work').count()

        # Convertir total_time a formato Excel (fracción de día)
        excel_total_time = total_time.total_seconds() / 86400  # 1 día = 86400 s

        row = [
            wd.date.strftime("%Y-%m-%d"),
            wd.date.strftime("%A"),
            wd.get_status_display(),
            check_in,
            check_out,
            excel_total_time,  # numérico, no string
            fmt_time(breaks[0].start_time) if len(breaks) > 0 else "—",
            fmt_time(breaks[0].end_time) if len(breaks) > 0 else "—",
            str(break1) if break1 else "—",
            fmt_time(breaks[1].start_time) if len(breaks) > 1 else "—",
            fmt_time(breaks[1].end_time) if len(breaks) > 1 else "—",
            str(break2) if break2 else "—",
            fmt_time(lunch[0].start_time) if lunch else "—",
            fmt_time(lunch[0].end_time) if lunch else "—",
            str(lunch_d) if lunch_d else "—",
            work_sessions_count
        ]
        ws.append(row)

        # Aplica formato h:mm a la columna "Total Work Time" (columna 6)
        ws.cell(row=ws.max_row, column=6).number_format = "[h]:mm"

    # --- Fila resumen ---
    ws.append([])
    total_time_final = timedelta(seconds=total_seconds)
    excel_total_final = total_time_final.total_seconds() / 86400
    ws.append(["", "", "", "", "TOTAL WORK TIME:", excel_total_final])
    ws.cell(row=ws.max_row, column=5).font = bold_font
    ws.cell(row=ws.max_row, column=6).font = bold_font
    ws.cell(row=ws.max_row, column=6).number_format = "[h]:mm"

    # Ajustar anchos
    for i, column_cells in enumerate(ws.columns, 1):
        length = max(len(str(cell.value)) if cell.value else 0 for cell in column_cells)
        ws.column_dimensions[get_column_letter(i)].width = length + 2

    # Crear respuesta
    safe_name = f"{employee.user.first_name}_{employee.user.last_name}".replace(" ", "_")
    filename = f"attendance_{safe_name}_{timezone.now().strftime('%Y%m%d')}.xlsx"

    response = HttpResponse(
        content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    )
    response['Content-Disposition'] = f'attachment; filename="{filename}"'
    wb.save(response)
    return response




@login_required
def supervisor_day_detail(request, employee_id, date_str):
    try:
        supervisor = Employee.objects.get(user=request.user, is_supervisor=True)
    except Employee.DoesNotExist:
        messages.error(request, "You don't have supervisor privileges.")
        return redirect('employee_profile')

    employee = get_object_or_404(Employee, id=employee_id, supervisor=supervisor)

    try:
        date_obj = datetime.strptime(date_str, '%Y-%m-%d').date()
        work_day = WorkDay.objects.get(employee=employee, date=date_obj)
        sessions = work_day.sessions.all().order_by('start_time')

        if not sessions.exists():
            messages.warning(request, "No sessions found for this day.")
            return redirect('employee_attendance_detail', employee_id=employee.id)

        # Calcular hora de inicio y fin del día
        day_start = sessions.first().start_time
        day_end = sessions.last().end_time or datetime.now()
        total_day_duration = day_end - day_start

        # Totales por tipo de sesión
        def total_duration_for(session_type):
            total = timedelta()
            for s in sessions.filter(session_type=session_type, end_time__isnull=False):
                total += (s.end_time - s.start_time)
            return total

        total_work = total_duration_for('work')
        total_break = total_duration_for('break')
        total_lunch = total_duration_for('lunch')

        # Horas pagables (solo 'work')
        payable_hours = total_work

        context = {
            'supervisor': supervisor,
            'employee': employee,
            'work_day': work_day,
            'sessions': sessions,
            'date': date_obj,
            'total_day_duration': total_day_duration,
            'total_work': total_work,
            'total_break': total_break,
            'total_lunch': total_lunch,
            'payable_hours': payable_hours,
            'day_start': day_start,
            'day_end': day_end,
        }

        return render(request, 'supervisor/supervisor_day_detail.html', context)

    except (ValueError, WorkDay.DoesNotExist):
        messages.error(request, "Day not found or no data available.")
        return redirect('employee_attendance_detail', employee_id=employee_id)
    


@login_required(login_url='/accounts/login/')
def edit_session(request, pk):
    session = get_object_or_404(ActivitySession, pk=pk)


    # if not is_supervisor(request.user):
    #     return HttpResponseForbidden(render(request, "403.html"))
    
    if request.method == 'POST':
        form = ActivitySessionForm(request.POST, instance=session)
        if form.is_valid():
            form.save()
            return redirect('supervisor_day_detail', employee_id=session.work_day.employee.id, date_str=session.work_day.date.strftime('%Y-%m-%d'))
    else:
        form = ActivitySessionForm(instance=session)
    return render(request, 'supervisor/edit_session.html', {'form': form, 'session': session})



@login_required(login_url='/accounts/login/')
def delete_session(request, pk):
    session = get_object_or_404(ActivitySession, pk=pk)

    # if not is_supervisor(request.user):
    #     return HttpResponseForbidden(render(request, "403.html"))
    
    if request.method == 'POST':
        # Guardamos la información de la sesión antes de eliminarla para la redirección
        work_day = session.work_day
        employee_id = work_day.employee.id
        date_str = work_day.date.strftime('%Y-%m-%d')
        
        # Eliminar la sesión
        session.delete()
        
        # Recalcular los totales del día
        work_day.calculate_daily_totals()
        
        # Actualizar información de ajustes
        work_day.update_adjustment_info(request.user)
        
        return redirect('supervisor_day_detail', employee_id=employee_id, date_str=date_str)
    
    # Para solicitudes GET, mostramos la página de confirmación
    return render(request, 'supervisor/delete_session.html', {'session': session})

@login_required(login_url='/accounts/login/')
def workday_editor_view(request, workday_id):
    workday = get_object_or_404(WorkDay, id=workday_id)
    sessions = workday.sessions.all()

    sessions_data = []
    for s in sessions:
        # Manejar end_time que puede ser None (sesión en curso)
        end_time_formatted = s.end_time.strftime('%H:%M') if s.end_time else "En curso"
        
        sessions_data.append({
            'id': s.id,
            'type': s.get_session_type_display(),
            'type_code': s.session_type,
            'start': s.start_time.strftime('%H:%M'),
            'end': end_time_formatted,
        })

    referer = request.META.get('HTTP_REFERER', '/')

    return render(request, 'supervisor/workday_timeline.html', {
        'workday': workday,
        'sessions': sessions,
        'sessions_json': json.dumps(sessions_data),
        'referer': referer
    })


@login_required(login_url='/accounts/login/')
@require_http_methods(["POST"])
def update_session(request, session_id):
    session = get_object_or_404(ActivitySession, id=session_id)
    
    # if not is_supervisor(request.user):
    #     return JsonResponse({'success': False, 'message': 'Unauthorized'}, status=403)
    
    try:
        new_start = request.POST.get('start')
        new_end = request.POST.get('end')
        adjustment_reason = request.POST.get('adjustment_reason', '')
        
        # Convertir tiempos
        workday_date = session.work_day.date
        new_start_time = datetime.combine(workday_date, datetime.strptime(new_start, '%H:%M').time())
        new_end_time = datetime.combine(workday_date, datetime.strptime(new_end, '%H:%M').time())
        
        # Ajustar la sesión
        session.adjust_times(
            new_start_time=new_start_time,
            new_end_time=new_end_time,
            adjusted_by=request.user,
            notes=adjustment_reason
        )
        
        # Registrar en el WorkDay
        session.work_day.add_adjustment_record(
            adjusted_by=request.user,
            reason=adjustment_reason,
            sessions_affected=[session.id]
        )
        
        # Recalcular y preparar respuesta
        workday = session.work_day
        workday.calculate_daily_totals()
        
        # Preparar datos de respuesta
        updated_sessions = []
        for s in workday.sessions.all().order_by('start_time'):
            updated_sessions.append({
                'id': s.id,
                'start': s.start_time.strftime('%H:%M'),
                'end': s.end_time.strftime('%H:%M'),
                'duration': s.duration_minutes,
                'is_adjusted': s.is_adjusted
            })
        
        return JsonResponse({
            'success': True,
            'updated_sessions': updated_sessions,
            'total_work': workday.total_work_minutes,
            'total_breaks': workday.total_break_minutes,
            'total_lunch': workday.total_lunch_minutes,
            'adjustment_reason': adjustment_reason
        })
        
    except Exception as e:
        return JsonResponse({'success': False, 'message': str(e)})
    


#Occurrence crud

@login_required
def occurrence_list(request):

    occurrences = Occurrence.objects.filter(employee=request.user)
    return render(request, 'occurrences/occurrence_list.html', {
        'occurrences': occurrences
    })

@login_required
def occurrence_create(request):

    if request.method == 'POST':
        form = OccurrenceForm(request.POST)
        if form.is_valid():
            occurrence = form.save(commit=False)
            occurrence.employee = request.user
            occurrence.save()
            messages.success(request, 'Occurrence created successfully!')
            return redirect('occurrence_list')
    else:
        form = OccurrenceForm()
    
    return render(request, 'occurrences/occurrence_form.html', {
        'form': form,
        'title': 'Create Occurrence'
    })

@login_required
def occurrence_update(request, pk):

    occurrence = get_object_or_404(Occurrence, pk=pk, employee=request.user)
    
    if request.method == 'POST':
        form = OccurrenceForm(request.POST, instance=occurrence)
        if form.is_valid():
            form.save()
            messages.success(request, 'Occurrence updated successfully!')
            return redirect('occurrence_list')
    else:
        form = OccurrenceForm(instance=occurrence)
    
    return render(request, 'occurrences/occurrence_form.html', {
        'form': form,
        'title': 'Update Occurrence',
        'occurrence': occurrence
    })

@login_required
def occurrence_detail(request, pk):

    occurrence = get_object_or_404(Occurrence, pk=pk, employee=request.user)
    return render(request, 'occurrences/occurrence_detail.html', {
        'occurrence': occurrence
    })

@login_required
def occurrence_delete(request, pk):

    occurrence = get_object_or_404(Occurrence, pk=pk, employee=request.user)
    
    if request.method == 'POST':
        occurrence.delete()
        messages.success(request, 'Occurrence deleted successfully!')
        return redirect('occurrence_list')
    
    return render(request, 'occurrences/occurrence_confirm_delete.html', {
        'occurrence': occurrence
    })