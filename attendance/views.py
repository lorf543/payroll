import json
from django.shortcuts import render, get_object_or_404, redirect,HttpResponse
from django.db.models import Sum, F, DurationField, ExpressionWrapper
from django.template.loader import render_to_string
from django.views.decorators.http import require_POST
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from django.contrib.auth.decorators import login_required
from django.utils.decorators import method_decorator
from django.views.generic import ListView, CreateView, UpdateView, DeleteView
from django.urls import reverse_lazy
from django.db.models import Count, Q
from django.utils import timezone
from django.forms import modelform_factory, modelformset_factory
from datetime import datetime, timedelta
from .models import Attendance, LeaveType, AgentStatus
from core.models import Department
from decimal import Decimal
from django.contrib import messages

from core.models import Employee
from .forms import AgentStatusForm
from datetime import datetime, time, timedelta
# Create your views here.


def get_last_day_of_month(date):
    """Devuelve el último día del mes dado."""
    next_month = date.replace(day=28) + timedelta(days=4)
    return next_month - timedelta(days=next_month.day)

def get_pay_periods(reference_date, periods=6):
    """Genera periodos de pago quincenales hacia atrás desde la fecha de referencia."""
    periods_list = []

    # Determinar si estamos en la primera o segunda quincena
    if reference_date.day <= 15:
        current_start = reference_date.replace(day=1)
        current_end = reference_date.replace(day=15)
    else:
        current_start = reference_date.replace(day=16)
        current_end = get_last_day_of_month(reference_date)

    # Generar los periodos hacia atrás
    for _ in range(periods):
        periods_list.append({
            'start_date': current_start,
            'end_date': current_end,
            'name': f"{current_start.strftime('%b %d')} - {current_end.strftime('%b %d, %Y')}",
            'is_current': len(periods_list) == 0
        })

        # Retroceder una quincena
        if current_start.day == 16:
            # Ir a la primera quincena del mismo mes
            current_end = current_start.replace(day=15)
            current_start = current_start.replace(day=1)
        else:
            # Ir a la segunda quincena del mes anterior
            prev_month = (current_start.replace(day=1) - timedelta(days=1))
            current_start = prev_month.replace(day=16)
            current_end = get_last_day_of_month(prev_month)

    return periods_list

def calculate_pay_period_data(employee, start_date, end_date):
    """Calcula estadísticas para un periodo específico"""
    start_datetime = timezone.make_aware(datetime.combine(start_date, time.min))
    end_datetime = timezone.make_aware(datetime.combine(end_date, time.max))
    
    # Obtener registros del periodo
    records = AgentStatus.objects.filter(
        agent=employee,
        start_time__range=(start_datetime, end_datetime)
    ).order_by('-start_time')
    
    # Calcular tiempos
    total_payable = timedelta()
    total_break = timedelta()
    total_lunch = timedelta()
    
    for record in records:
        end_time = record.end_time or timezone.now()
        if end_time > end_datetime:
            end_time = end_datetime
        if record.start_time < start_datetime:
            start_time = start_datetime
        else:
            start_time = record.start_time
            
        duration = end_time - start_time
        
        if record.status == 'ready':
            total_payable += duration
        elif record.status == 'break':
            total_break += duration
        elif record.status == 'lunch':
            total_lunch += duration
    
    # Calcular pago
    earnings, pay_method = calculate_employee_pay(employee, total_payable)
    
    return {
        'start_date': start_date,
        'end_date': end_date,
        'total_payable': total_payable,
        'total_break': total_break,
        'total_lunch': total_lunch,
        'payable_hours': timedelta_to_hours(total_payable),
        'earnings': earnings,
        'pay_method': pay_method,
        'days_worked': records.dates('start_time', 'day').count(),
    }

def get_recent_daily_stats(employee, days=7):
    """Obtiene estadísticas diarias de los últimos días incluyendo primer y último status"""
    daily_stats = []
    
    for i in range(days):
        day = timezone.localdate() - timedelta(days=i)
        day_start = timezone.make_aware(datetime.combine(day, time.min))
        day_end = timezone.make_aware(datetime.combine(day, time.max))
        
        # Get all records for the day, ordered by time
        records = AgentStatus.objects.filter(
            agent=employee,
            start_time__range=(day_start, day_end)
        ).order_by('start_time')
        
        # Calculate first and last records
        first_record = records.first()
        last_record = records.last()
        
        # Calculate payable time
        daily_payable = timedelta()
        for record in records:
            if record.status == 'ready':
                end_time = record.end_time or min(timezone.now(), day_end)
                start_time = max(record.start_time, day_start)
                daily_payable += (end_time - start_time)
        
        daily_earnings, _ = calculate_employee_pay(employee, daily_payable)
        
        daily_stats.append({
            'date': day,
            'payable_hours': timedelta_to_hours(daily_payable),
            'earnings': daily_earnings,
            'is_weekend': day.weekday() >= 5,
            'records_count': records.count(),
            'first_record': first_record,
            'last_record': last_record,
        })
    
    return daily_stats


@login_required(login_url='account_login')
def employee_payroll_dashboard(request):
    """Dashboard para que empleados vean su historial, horas trabajadas y ganancias"""
    employee = Employee.objects.get(user=request.user)
    
    # Fechas para los últimos 6 periodos de pago (quincenales)
    today = timezone.localdate()
    pay_periods = get_pay_periods(today, periods=6)
    
    payroll_data = []
    for period in pay_periods:
        period_data = calculate_pay_period_data(employee, period['start_date'], period['end_date'])
        payroll_data.append(period_data)
    
    # Estadísticas del mes actual
    current_month_start = today.replace(day=1)
    current_month_end = (current_month_start + timedelta(days=32)).replace(day=1) - timedelta(days=1)
    month_stats = calculate_pay_period_data(employee, current_month_start, current_month_end)
    
    # Historial diario de los últimos 7 días
    recent_days = get_recent_daily_stats(employee, days=7)
    
    context = {
        'employee': employee,
        'payroll_data': payroll_data,
        'month_stats': month_stats,
        'recent_days': recent_days,
        'current_period': pay_periods[0] if pay_periods else None,
    }
    
    return render(request, 'attendance/payroll_dashboard.html', context)




#agent_status.html


def timedelta_to_hours(td):
    return Decimal(td.total_seconds()) / Decimal(3600)

def format_timedelta(td):
    total_seconds = int(td.total_seconds())
    hours, remainder = divmod(total_seconds, 3600)
    minutes = (remainder // 60)
    return f"{hours}h {minutes}m"


def calculate_employee_pay(employee, payable_time):
    """
    Calcula el pago del empleado basado en su configuración:
    1. Fixed rate (pago fijo diario)
    2. Hourly rate (pago por hora)
    3. Base salary + hourly (mixto)
    """
    payable_hours = timedelta_to_hours(payable_time)
    
    # 1. Empleado con salario fijo (independiente de horas trabajadas)
    if employee.fixed_rate:
        if employee.custom_base_salary and employee.custom_base_salary > 0:
            # Salario fijo personalizado
            daily_salary = employee.custom_base_salary / 22  # Asumiendo 22 días laborales al mes
            return round(daily_salary, 2), "fixed_custom"
        elif employee.position.base_salary and employee.position.base_salary > 0:
            # Salario fijo basado en posición
            daily_salary = employee.position.base_salary / 22
            return round(daily_salary, 2), "fixed_position"
        else:
            # Salario fijo por defecto
            return round(employee.position.hour_rate * 8, 2), "fixed_default"
    
    # 2. Empleado por horas
    else:
        if employee.custom_base_salary and employee.custom_base_salary > 0:
            # Pago por horas con tarifa personalizada
            return round(employee.custom_base_salary * payable_hours, 2), "hourly_custom"
        else:
            # Pago por horas con tarifa de posición
            return round(employee.position.hour_rate * payable_hours, 2), "hourly_position"



def get_payment_method_display(employee):
    """Retorna la descripción del método de pago"""
    if employee.fixed_rate:
        if employee.custom_base_salary:
            return f"Salario fijo: ${employee.custom_base_salary:,.2f}/mes"
        elif employee.position.base_salary:
            return f"Salario fijo: ${employee.position.base_salary:,.2f}/mes"
        else:
            return f"Salario fijo: ${employee.position.hour_rate * 8 * 22:,.2f}/mes"
    else:
        if employee.custom_base_salary:
            return f"Por horas: ${employee.custom_base_salary:,.2f}/hora"
        else:
            return f"Por horas: ${employee.position.hour_rate:,.2f}/hora"
        

def agent_status_dashboard(request):
    if not request.user.is_authenticated:
        return redirect('account_login')
    
    employee = Employee.objects.get(user=request.user)
    today = timezone.localdate()
    start_of_day = timezone.make_aware(datetime.combine(today, time.min))
    end_of_day = timezone.make_aware(datetime.combine(today, time.max))

    # Handle form submission
    if request.method == 'POST':
        form = AgentStatusForm(request.POST)
        if form.is_valid():
            status_record = form.save(commit=False)
            status_record.agent = employee
            
            # End current status if exists
            current_active = AgentStatus.objects.filter(
                agent=employee,
                end_time__isnull=True
            ).first()
            
            if current_active:
                current_active.end_time = timezone.now()
                current_active.save()
                messages.info(request, f"Ended {current_active.get_status_display()} status")
            
            status_record.save()
            messages.success(request, f"Status changed to {status_record.get_status_display()}")
            return redirect('agent_status_dashboard')
    else:
        form = AgentStatusForm()

    records = AgentStatus.objects.filter(
        agent=employee,
        start_time__range=(start_of_day, end_of_day)
    )

    total = break_time = lunch_time = payable = timedelta()
    now = timezone.now()
    history = []

    for rec in records:
        end_time = rec.end_time or now
        duration = end_time - rec.start_time

        total += duration
        if rec.status == 'break':
            break_time += duration
        elif rec.status == 'lunch':
            lunch_time += duration
        elif rec.status == 'ready':
            payable += duration

        history.append({
            'status': rec.status,
            'start_time': rec.start_time,
            'end_time': rec.end_time,
            'notes': rec.notes,
            'duration_str': format_timedelta(duration),
        })

    daily_earnings, pay_method = calculate_employee_pay(employee, payable)
    payment_info = get_payment_method_display(employee)

    context = {
        'employee': employee,
        'current_status': records.filter(end_time__isnull=True).first(),
        'form': form,
        'daily_stats': {
            'total': format_timedelta(total),
            'break': format_timedelta(break_time),
            'lunch': format_timedelta(lunch_time),
            'payable': format_timedelta(payable),
            'money': daily_earnings,
            'pay_method': pay_method,
            'payment_info': payment_info,
            'payable_hours': round(timedelta_to_hours(payable), 2),
        },
        'history': history,
    }
    return render(request, 'attendance/agent_status.html', context)

@require_POST
@login_required
def change_agent_status(request, agent_id):
    employee = get_object_or_404(Employee, id=agent_id, user=request.user)
    form = AgentStatusForm(request.POST)
    if form.is_valid():
        # Terminar status activo
        current = AgentStatus.objects.filter(agent=employee, end_time__isnull=True).first()
        if current:
            current.end_time = timezone.now()
            current.save()

        new_status = form.save(commit=False)
        new_status.agent = employee
        new_status.start_time = timezone.now()
        new_status.end_time = None
        new_status.save()

        return render(request, 'attendance/partials/current_status.html', {
            'current_status': new_status
        })

    return render(request, 'attendance/partials/status_form.html', {
        'form': form,
        'employee': employee,
    })

@login_required
def attendance_dashboard(request):
    today = timezone.now().date()
    
    # Today's statistics
    today_attendance = Attendance.objects.filter(date=today).select_related(
        'employee__user', 'employee__department'
    )
    
    total_employees = Employee.objects.filter(is_active=True).count()
    present_today = today_attendance.filter(status__in=['present', 'late', 'half_day']).count()
    late_today = today_attendance.filter(status='late').count()
    
    today_stats = {
        'present': present_today,
        'late': late_today,
        'attendance_rate': round((present_today / total_employees) * 100) if total_employees > 0 else 0,
        'late_rate': round((late_today / total_employees) * 100) if total_employees > 0 else 0,
    }
    
    # Monthly statistics
    month_start = today.replace(day=1)
    monthly_attendance = Attendance.objects.filter(date__gte=month_start, date__lte=today)
    
    monthly_stats = {
        'avg_daily_attendance': round(monthly_attendance.filter(status__in=['present', 'late', 'half_day']).count() / today.day),
        'attendance_rate': 95,  # Calculate based on your logic
        'absences': monthly_attendance.filter(status='absent').count(),
        'avg_daily_absence': round(monthly_attendance.filter(status='absent').count() / today.day),
    }
    
    # Department statistics
    departments = Department.objects.all()
    department_stats = []
    for dept in departments:
        dept_employees = dept.employee_set.filter(is_active=True).count()
        dept_present = today_attendance.filter(
            employee__department=dept,
            status__in=['present', 'late', 'half_day']
        ).count()
        
        department_stats.append({
            'name': dept.name,
            'total': dept_employees,
            'present': dept_present,
            'attendance_rate': round((dept_present / dept_employees) * 100) if dept_employees > 0 else 0,
        })
    
    context = {
        'today_stats': today_stats,
        'monthly_stats': monthly_stats,
        'department_stats': department_stats,
        'today_attendance': today_attendance,
        'employees': Employee.objects.filter(is_active=True),
        'departments': departments,
    }
    
    return render(request, 'attendance/attendance_dashboard.html', context)


@login_required
def supervisor_dashboard(request):
    """Dashboard para supervisores ver el estado de sus agentes"""
    try:
        # Obtener el empleado que es supervisor
        supervisor = Employee.objects.get(user=request.user, is_supervisor=True)
        
        # Obtener agentes asignados (team_members por la relación ForeignKey)
        team_members = Employee.objects.filter(supervisor=supervisor, is_active=True)
        
        context = {
            'supervisor': supervisor,
            'team_members': team_members,
        }
        
        return render(request, 'attendance/supervisor_dashboard.html', context)
        
    except Employee.DoesNotExist:
        return redirect('agent_status_dashboard')




@login_required
# @cache_control(no_cache=True, must_revalidate=True, no_store=True)
def supervisor_stats_api(request):
    """API endpoint para obtener estadísticas actualizadas del equipo"""
    try:
        # Get supervisor
        supervisor = Employee.objects.get(user=request.user, is_supervisor=True)
        
        # Get team members
        team_members = Employee.objects.filter(supervisor=supervisor, is_active=True)
        
        # Get current statuses
        current_statuses = AgentStatus.objects.filter(
            agent__in=team_members,
            end_time__isnull=True  # Estados activos
        ).select_related('agent')
        
        # Create status map
        agent_status_map = {status.agent_id: status for status in current_statuses}
        
        # Team statistics
        team_stats = {
            'total_agents': team_members.count(),
            'ready_count': current_statuses.filter(status='ready').count(),
            'break_count': current_statuses.filter(status='break').count(),
            'lunch_count': current_statuses.filter(status='lunch').count(),
            'training_count': current_statuses.filter(status='training').count(),
            'meeting_count': current_statuses.filter(status='meeting').count(),
            'offline_count': current_statuses.filter(status='offline').count(),
        }
        
        # Today's activity (last 10 activities)
        today = timezone.localdate()
        start_of_day = timezone.make_aware(datetime.combine(today, time.min))
        
        today_activity = AgentStatus.objects.filter(
            agent__in=team_members,
            start_time__gte=start_of_day
        ).select_related('agent').order_by('-start_time')[:10]
        
        context = {
            'team_stats': team_stats,
            'today_activity': today_activity,
            'agent_status_map': agent_status_map,
            'current_time': timezone.now(),
        }
        
        return render(request, 'attendance/partials/supervisor_stats.html', context)
        
    except Employee.DoesNotExist:
        return HttpResponse(status=403)
    


@login_required
def supervisor_agents_api(request):
    """API para la tabla de agentes"""
    try:
        supervisor = Employee.objects.get(user=request.user, is_supervisor=True)
        team_members = Employee.objects.filter(supervisor=supervisor, is_active=True)
        
        current_statuses = AgentStatus.objects.filter(
            agent__in=team_members,
            end_time__isnull=True
        ).select_related('agent')
        
        agent_status_map = {status.agent_id: status for status in current_statuses}
        
        context = {
            'team_members': team_members,
            'agent_status_map': agent_status_map,
            'current_time': timezone.now(),
        }
        
        return render(request, 'attendance/partials/agents_table.html', context)
    except Employee.DoesNotExist:
        return HttpResponse(status=403)

@login_required
def supervisor_activity_api(request):
    """API para la línea de tiempo de actividad"""
    try:
        supervisor = Employee.objects.get(user=request.user, is_supervisor=True)
        team_members = Employee.objects.filter(supervisor=supervisor, is_active=True)
        
        today = timezone.localdate()
        start_of_day = timezone.make_aware(datetime.combine(today, time.min))
        
        today_activity = AgentStatus.objects.filter(
            agent__in=team_members,
            start_time__gte=start_of_day
        ).select_related('agent').order_by('-start_time')[:10]
        
        context = {
            'today_activity': today_activity,
        }
        
        return render(request, 'attendance/partials/activity_timeline.html', context)
    except Employee.DoesNotExist:
        return HttpResponse(status=403)
    




# views.py
import openpyxl
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.utils import get_column_letter
from django.http import HttpResponse
from django.utils import timezone
from datetime import datetime
from django.contrib.auth.decorators import login_required, user_passes_test

@login_required
@user_passes_test(lambda u: u.is_staff or getattr(u, 'employee', None) and u.employee.is_it)
def export_employees_excel(request):
    """Export employee list to Excel with basic information"""
    # Get all active employees with related data
    employees = Employee.objects.select_related(
        'user', 
        'position', 
        'department', 
        'supervisor'
    ).filter(is_active=True).order_by('department__name', 'employee_code')
    
    # Create workbook and worksheet
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Employee List"
    
    # Define styles
    header_font = Font(bold=True, color="FFFFFF", size=12)
    header_fill = PatternFill(start_color="366092", end_color="366092", fill_type="solid")
    center_align = Alignment(horizontal='center', vertical='center')
    left_align = Alignment(horizontal='left', vertical='center')
    
    # Thin border style
    thin_border = Border(
        left=Side(style='thin'),
        right=Side(style='thin'),
        top=Side(style='thin'),
        bottom=Side(style='thin')
    )
    
    # Define columns for basic info
    columns = [
        ('Employee Code', 15),
        ('ID Number', 18),
        ('Full Name', 25),
        ('Email', 30),
        ('Position', 20),
        ('Department', 20),
        ('Supervisor', 20),
        ('Hire Date', 12),
        ('Status', 10),
        ('Phone', 15),
        ('City', 15),
    ]
    
    # Create headers
    for col_num, (column_title, column_width) in enumerate(columns, 1):
        cell = ws.cell(row=1, column=col_num, value=column_title)
        cell.font = header_font
        cell.fill = header_fill
        cell.alignment = center_align
        cell.border = thin_border
        ws.column_dimensions[get_column_letter(col_num)].width = column_width
    
    # Add data rows
    for row_num, employee in enumerate(employees, 2):
        # Get supervisor name
        supervisor_name = ""
        if employee.supervisor:
            if employee.supervisor.user:
                supervisor_name = f"{employee.supervisor.user.get_full_name()}"
            else:
                supervisor_name = f"EMP-{employee.supervisor.employee_code}"
        
        # Get employee full name
        full_name = ""
        if employee.user:
            full_name = employee.user.get_full_name()
            if not full_name.strip():
                full_name = employee.user.username
        else:
            full_name = f"EMP-{employee.employee_code}"
        
        # Get email
        email = ""
        if employee.user:
            email = employee.user.email
        elif employee.email:
            email = employee.email
        
        row_data = [
            employee.employee_code,
            employee.identification,
            full_name,
            email,
            employee.position.name if employee.position else "Not assigned",
            employee.department.name if employee.department else "Not assigned",
            supervisor_name,
            employee.hire_date.strftime("%Y-%m-%d") if employee.hire_date else "Not set",
            "Active",
            employee.phone or "Not set",
            employee.city or "Not set",
        ]
        
        for col_num, value in enumerate(row_data, 1):
            cell = ws.cell(row=row_num, column=col_num, value=value)
            cell.alignment = left_align
            cell.border = thin_border
            
            # Center align specific columns
            if col_num in [1, 8, 9]:
                cell.alignment = center_align
    
    # Add summary information
    summary_row = len(employees) + 4
    
    # Summary title
    ws.cell(row=summary_row, column=1, value="REPORT SUMMARY").font = Font(bold=True, size=14)
    summary_row += 1
    
    # Summary data
    summary_data = [
        f"Total Employees: {len(employees)}",
        f"Report Generated: {timezone.now().strftime('%Y-%m-%d %H:%M')}",
        f"Generated By: {request.user.get_full_name() or request.user.username}",
    ]
    
    for i, summary_line in enumerate(summary_data):
        ws.cell(row=summary_row + i, column=1, value=summary_line).font = Font(bold=True)
    
    # Department breakdown
    dept_summary_row = summary_row + len(summary_data) + 1
    ws.cell(row=dept_summary_row, column=1, value="DEPARTMENT BREAKDOWN").font = Font(bold=True)
    dept_summary_row += 1
    
    # Count employees by department
    from django.db.models import Count
    dept_counts = employees.values('department__name').annotate(count=Count('id')).order_by('-count')
    
    for i, dept in enumerate(dept_counts):
        dept_name = dept['department__name'] or 'No Department'
        ws.cell(row=dept_summary_row + i, column=1, value=f"{dept_name}: {dept['count']} employees")
    
    # Freeze header row
    ws.freeze_panes = "A2"
    
    # Create response
    response = HttpResponse(
        content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    )
    filename = f"employee_list_{timezone.now().strftime('%Y%m%d_%H%M')}.xlsx"
    response['Content-Disposition'] = f'attachment; filename="{filename}"'
    
    # Save workbook to response
    wb.save(response)
    return response

