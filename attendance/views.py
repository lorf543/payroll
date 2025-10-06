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

from core.models import Employee
from .forms import AgentStatusForm
from datetime import datetime, time, timedelta
# Create your views here.



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

def get_pay_periods(reference_date, periods=6):
    """Genera periodos de pago quincenales"""
    periods_list = []
    
    # Determinar el periodo actual (1-15 o 16-fin de mes)
    if reference_date.day <= 15:
        current_period_start = reference_date.replace(day=1)
        current_period_end = reference_date.replace(day=15)
    else:
        current_period_start = reference_date.replace(day=16)
        # Último día del mes
        next_month = current_period_start.replace(day=28) + timedelta(days=4)
        current_period_end = next_month - timedelta(days=next_month.day)
    
    # Generar periodos hacia atrás
    for i in range(periods):
        period_start = current_period_start - timedelta(days=15 * i)
        period_end = current_period_end - timedelta(days=15 * i)
        
        # Ajustar para meses anteriores
        if period_start.day > 15:
            period_start = period_start.replace(day=16)
            period_end = period_end.replace(day=1) - timedelta(days=1)
        else:
            prev_month = period_start.replace(day=1) - timedelta(days=1)
            period_start = prev_month.replace(day=16)
            period_end = prev_month
        
        periods_list.append({
            'start_date': period_start,
            'end_date': period_end,
            'name': f"{period_start.strftime('%b %d')} - {period_end.strftime('%b %d, %Y')}",
            'is_current': i == 0
        })
    
    return sorted(periods_list, key=lambda x: x['start_date'], reverse=True)

def calculate_pay_period_data(employee, start_date, end_date):
    """Calcula estadísticas para un periodo específico"""
    start_datetime = timezone.make_aware(datetime.combine(start_date, time.min))
    end_datetime = timezone.make_aware(datetime.combine(end_date, time.max))
    
    # Obtener registros del periodo
    records = AgentStatus.objects.filter(
        agent=employee,
        start_time__range=(start_datetime, end_datetime)
    )
    
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
    """Obtiene estadísticas diarias de los últimos días"""
    daily_stats = []
    
    for i in range(days):
        day = timezone.localdate() - timedelta(days=i)
        day_start = timezone.make_aware(datetime.combine(day, time.min))
        day_end = timezone.make_aware(datetime.combine(day, time.max))
        
        records = AgentStatus.objects.filter(
            agent=employee,
            start_time__range=(day_start, day_end)
        )
        
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
        })
    
    return daily_stats



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
        return redirect('account_login')  # or your own login view name
    
    employee = Employee.objects.get(user=request.user)
    today = timezone.localdate()
    start_of_day = timezone.make_aware(datetime.combine(today, time.min))
    end_of_day = timezone.make_aware(datetime.combine(today, time.max))

    records = AgentStatus.objects.filter(
        agent=employee,
        start_time__range=(start_of_day, end_of_day)
    ).order_by('start_time')

    total = timedelta()
    break_time = timedelta()
    lunch_time = timedelta()
    payable = timedelta()
    now = timezone.now()

    history = []

    for rec in records:
        end_time = rec.end_time or now
        duration = end_time - rec.start_time
        duration_str = format_timedelta(duration)

        # Acumular tiempos
        total += duration
        
        if rec.status == 'break':
            break_time += duration
        elif rec.status == 'lunch':
            lunch_time += duration
        elif rec.status == 'ready': 
            payable += duration

        # Agregar al historial
        history.append({
            'status': rec.status,
            'start_time': rec.start_time,
            'end_time': rec.end_time,
            'notes': rec.notes,
            'duration_str': format_timedelta(duration),
        })

    # 🔥 NUEVO: Cálculo inteligente de pago
    daily_earnings, pay_method = calculate_employee_pay(employee, payable)
    payment_info = get_payment_method_display(employee)

    context = {
        'employee': employee,
        'current_status': records.filter(end_time__isnull=True).first(),
        'form': AgentStatusForm(),
        'daily_stats': {
            'total': format_timedelta(payable),
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

