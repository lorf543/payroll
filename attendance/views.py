from django.shortcuts import render, get_object_or_404, redirect,HttpResponse
from django.http import JsonResponse, HttpResponseForbidden
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_POST
from django.contrib.auth.decorators import user_passes_test
from django.views.decorators.http import require_http_methods
from django.utils import timezone
from django.contrib import messages
from django.contrib.sessions.models import Session
from django.db import transaction
from datetime import datetime, time, timedelta
from django.core.paginator import Paginator
from django.db.models import Q
from .forms import EmployeeProfileForm,ActivitySessionForm

import openpyxl
from openpyxl.styles import Font, Alignment
from openpyxl.utils import get_column_letter
import csv


from core.models import Employee, Campaign
from .models import WorkDay,ActivitySession
from .status_helpers import close_active_status
from .utility import *
from core.utils.payroll import get_effective_pay_rate
# Create your views here.

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
    }

    return render(request, 'attendance/agent_dashboard.html', context)



@require_http_methods(["POST"])
@login_required
def start_activity(request):
    """
    Iniciar una nueva actividad (HTMX endpoint)
    """
    employee = get_object_or_404(Employee, user=request.user)
    today = timezone.now().date()

    # ✅ Crear o recuperar el WorkDay automáticamente
    work_day, _ = WorkDay.objects.get_or_create(employee=employee, date=today)

    session_type = request.POST.get('session_type', 'work')

    # ✅ Si es "end_of_day", usar la función específica

    
    if session_type == 'end_of_day':
        return end_work_day(request)

    # ✅ Iniciar nueva sesión y registrar el check_in si aplica
    session = work_day.start_work_session(
        session_type=session_type,
        notes=request.POST.get('notes', '')
    )

    # ✅ Recalcular estadísticas actualizadas
    daily_stats = calculate_daily_stats(work_day)
    history = work_day.sessions.all().order_by('start_time')

    context = {
        'employee': employee,
        'work_day': work_day,
        'current_session': session,
        'daily_stats': daily_stats,
        'history': history,
        'today': today,
    }


    messages.success(request, f"Status changed to {session.get_session_type_display()}")


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
    
    # Obtener todos los WorkDays del empleado
    work_days = WorkDay.objects.filter(employee=employee).order_by('-date')
    
    # Aplicar filtros
    if date_from:
        work_days = work_days.filter(date__gte=date_from)
    if date_to:
        work_days = work_days.filter(date__lte=date_to)
    
    # Paginación
    paginator = Paginator(work_days, 10)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    # Función auxiliar para formatear duración
    def format_duration_simple(duration):
        if not duration:
            return "0h 00m"
        total_seconds = int(duration.total_seconds())
        hours = total_seconds // 3600
        minutes = (total_seconds % 3600) // 60
        if hours > 0:
            return f"{hours}h {minutes:02d}m"
        return f"{minutes}m"
    
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

    # Función auxiliar para formato
    def format_duration_simple(duration):
        if not duration:
            return "0h 00m"
        total_seconds = int(duration.total_seconds())
        hours = total_seconds // 3600
        minutes = (total_seconds % 3600) // 60
        return f"{hours}h {minutes:02d}m" if hours > 0 else f"{minutes}m"

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


                
        # Función para formatear duración
        def format_duration_simple(duration):
            if not duration:
                return "0h 00m"
            total_seconds = int(duration.total_seconds())
            hours = total_seconds // 3600
            minutes = (total_seconds % 3600) // 60
            if hours > 0:
                return f"{hours}h {minutes:02d}m"
            return f"{minutes}m"
        
        # Calcular estadísticas del día con formato correcto
        daily_stats = {
            'work_time': format_duration_simple(work_day.total_work_time),
            'break_time': format_duration_simple(work_day.total_break_time),
            'lunch_time': format_duration_simple(work_day.total_lunch_time),
            'money': calculate_daily_stats(work_day)['money'],
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
    
    # Obtener los miembros del equipo
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



@login_required
def export_team_report_excel(request):
    """
    Exporta el reporte general de asistencia del equipo supervisado a Excel.
    Cada fila representa un empleado por fecha.
    Incluye hasta 2 breaks y 1 lunch con horas de inicio, fin y duración.
    """
    try:
        supervisor = Employee.objects.get(user=request.user, is_supervisor=True)
    except Employee.DoesNotExist:
        messages.error(request, "You don't have supervisor privileges.")
        return redirect('employee_profile')

    # Filtros
    date_from = request.GET.get('date_from')
    date_to = request.GET.get('date_to')


    # Validación de fechas
    if not date_from or not date_to:
        messages.error(request, "Please select valid start and end dates before generating the report.")
        return redirect('supervisor_dashboard')

    try:
        date_from_dt = datetime.strptime(date_from, "%Y-%m-%d").date()
        date_to_dt = datetime.strptime(date_to, "%Y-%m-%d").date()
    except ValueError:
        messages.error(request, "Invalid date format. Please use YYYY-MM-DD.")
        return redirect('supervisor_dashboard')

    # Miembros del equipo
    team_members = Employee.objects.filter(supervisor=supervisor).select_related('user', 'current_campaign')


    # WorkDays filtrados
    work_days = WorkDay.objects.filter(
        employee__in=team_members,
        date__gte=date_from_dt,
        date__lte=date_to_dt
    ).select_related('employee', 'employee__current_campaign').prefetch_related('sessions').order_by('date', 'employee__user__last_name')

    # Crear workbook y hoja
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Team Report"

    bold_font = Font(bold=True)
    center_align = Alignment(horizontal="center")

    # Título del reporte
    ws.merge_cells('A1:L1')
    ws['A1'] = f"Team Report - Supervisor: {supervisor.user.get_full_name()}"
    ws['A1'].font = Font(bold=True, size=14)
    ws['A1'].alignment = center_align

    ws.merge_cells('A2:L2')
    ws['A2'] = f"Generated at: {timezone.now().strftime('%Y-%m-%d %H:%M:%S')}"
    ws['A2'].alignment = center_align

    ws.append([])

    # Encabezados
    headers = [
        "Date", "Employee", "Total Work Time",
        "Break1 Start", "Break1 End", "Break1 Duration",
        "Break2 Start", "Break2 End", "Break2 Duration",
        "Lunch Start", "Lunch End", "Lunch Duration",
        "Work Sessions Count"
    ]
    ws.append(headers)
    for col in range(1, len(headers) + 1):
        ws.cell(row=4, column=col).font = bold_font
        ws.cell(row=4, column=col).alignment = center_align

    # Agrupar WorkDays por fecha y empleado
    from collections import defaultdict
    grouped = defaultdict(list)
    for wd in work_days:
        grouped[(wd.date, wd.employee)].append(wd)

    # Filas de datos
    for (date, employee), wds in sorted(grouped.items(), key=lambda x: (x[0][0], x[0][1].user.last_name)):
        wd = wds[0]  # Solo habrá un WorkDay por fecha y empleado

        employee_name = employee.user.get_full_name()
        total_work = str(wd.total_work_time) if wd.total_work_time else "0:00:00"

        # Filtrar sesiones
        breaks = [s for s in wd.sessions.all() if s.session_type == 'break'][:2]
        lunch = [s for s in wd.sessions.all() if s.session_type == 'lunch'][:1]

        # Obtener tiempos y duración
        def format_duration(s):
            if s.start_time and s.end_time:
                delta = s.end_time - s.start_time
                return str(delta)
            return "—"

        break1_start = breaks[0].start_time.strftime("%H:%M:%S") if len(breaks) > 0 else "—"
        break1_end = breaks[0].end_time.strftime("%H:%M:%S") if len(breaks) > 0 and breaks[0].end_time else "—"
        break1_duration = format_duration(breaks[0]) if len(breaks) > 0 else "—"

        break2_start = breaks[1].start_time.strftime("%H:%M:%S") if len(breaks) > 1 else "—"
        break2_end = breaks[1].end_time.strftime("%H:%M:%S") if len(breaks) > 1 and breaks[1].end_time else "—"
        break2_duration = format_duration(breaks[1]) if len(breaks) > 1 else "—"

        lunch_start = lunch[0].start_time.strftime("%H:%M:%S") if lunch else "—"
        lunch_end = lunch[0].end_time.strftime("%H:%M:%S") if lunch and lunch[0].end_time else "—"
        lunch_duration = format_duration(lunch[0]) if lunch else "—"

        # Contar sesiones de trabajo
        work_sessions_count = wd.sessions.filter(session_type='work').count()

        ws.append([
            date.strftime("%Y-%m-%d"),
            employee_name,
            total_work,
            break1_start, break1_end, break1_duration,
            break2_start, break2_end, break2_duration,
            lunch_start, lunch_end, lunch_duration,
            work_sessions_count
        ])

    # Ajustar ancho de columnas automáticamente
    for i, column_cells in enumerate(ws.columns, 1):
        length = max(len(str(cell.value)) if cell.value else 0 for cell in column_cells)
        ws.column_dimensions[get_column_letter(i)].width = length + 2

    # Crear respuesta
    response = HttpResponse(content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
    filename = f"team_report_{supervisor.user.last_name}_{timezone.now().strftime('%Y%m%d')}.xlsx"
    response['Content-Disposition'] = f'attachment; filename="{filename}"'
    wb.save(response)
    return response




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
        supervisor = Employee.objects.get(user=request.user, is_supervisor=True)
    except Employee.DoesNotExist:
        messages.error(request, "You don't have supervisor privileges.")
        return redirect('employee_profile')
    
    # Verificar que el empleado pertenezca al equipo del supervisor
    employee = get_object_or_404(Employee, id=employee_id, supervisor=supervisor)
    
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
        'total_work_time': format_duration_simple(timedelta(seconds=total_work_time)),
        'avg_work_time': format_duration_simple(timedelta(seconds=avg_work_time)),
    }
    
    return render(request, 'supervisor/employee_attendance_detail.html', context)


@login_required
def export_employee_attendance_csv(request, employee_id):
    """Exporta los registros de asistencia de un empleado específico a CSV."""
    try:
        supervisor = Employee.objects.get(user=request.user, is_supervisor=True)
    except Employee.DoesNotExist:
        messages.error(request, "You don't have supervisor privileges.")
        return redirect('employee_profile')

    employee = get_object_or_404(Employee, id=employee_id, supervisor=supervisor)

    # Filtros aplicados
    date_from = request.GET.get('date_from')
    date_to = request.GET.get('date_to')

    # Validación de fechas
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

    # Obtener WorkDays filtrados
    work_days = WorkDay.objects.filter(employee=employee, date__range=(date_from_parsed, date_to_parsed)).order_by('-date')

    # Nombre del archivo
    safe_name = f"{employee.user.first_name}_{employee.user.last_name}".replace(" ", "_")
    filename = f"attendance_{safe_name}.csv"

    # Crear respuesta CSV
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = f'attachment; filename="{filename}"'

    writer = csv.writer(response)
    writer.writerow([f"Attendance Report for {employee.user.get_full_name()}"])
    writer.writerow([f"Date range: {date_from} to {date_to}"])
    writer.writerow(["Generated at:", timezone.now().strftime("%Y-%m-%d %H:%M:%S")])
    writer.writerow([])

    # Encabezados
    writer.writerow([
        "Date", "Day", "Status", "Check In", "Check Out",
        "Total Work Time", "Breaks", "Sessions Count"
    ])

    # Sumar total de horas trabajadas
    total_seconds = 0

    # Filas
    for wd in work_days:
        total_time = wd.total_work_time
        if total_time:
            total_seconds += total_time.total_seconds()
        total_time_str = format_duration_simple(total_time) if total_time else "0h 00m"

        writer.writerow([
            wd.date.strftime("%Y-%m-%d"),
            wd.date.strftime("%A"),
            wd.get_status_display(),
            wd.check_in.strftime("%I:%M %p") if wd.check_in else "—",
            wd.check_out.strftime("%I:%M %p") if wd.check_out else "—",
            total_time_str,
            wd.break_count,
            wd.sessions.count(),
        ])

    # Agregar fila resumen
    writer.writerow([])
    writer.writerow(["TOTAL WORK TIME:", format_duration_simple(timedelta(seconds=total_seconds))])

    return response

# Función auxiliar para formatear duración
def format_duration_simple(duration):
    """Formatear timedelta a formato legible"""
    if not duration:
        return "0h 00m"
    
    total_seconds = int(duration.total_seconds())
    hours = total_seconds // 3600
    minutes = (total_seconds % 3600) // 60
    
    if hours > 0:
        return f"{hours}h {minutes:02d}m"
    return f"{minutes}m"



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