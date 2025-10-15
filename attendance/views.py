from django.contrib.auth import logout
from django.shortcuts import render, get_object_or_404, redirect,HttpResponse
from django.views.decorators.http import require_POST
from django.contrib.auth.decorators import login_required
from django.utils import timezone
from core.models import Department
from decimal import Decimal, ROUND_HALF_UP
from django.contrib import messages
from django.contrib.sessions.models import Session
from django.db import transaction
from django.utils.timezone import now
from datetime import datetime, time, timedelta
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.utils import get_column_letter
from django.db.models import Case, When, ExpressionWrapper, F, DurationField, Sum
from django.core.paginator import Paginator


import csv


from core.models import Employee
from .forms import AgentStatusForm
from .models import Attendance, AgentStatus, Campaign
from core.models import PayPeriod
from .status_helpers import close_active_status
from .utility import *
from core.utils.payroll import get_effective_pay_rate
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
    
    # Historial diario de los últimos 7 días (usando la nueva función)
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

@login_required(login_url='account_login')
def employee_status_history(request):
    """Historial completo de todos los status del empleado"""
    try:
        employee = Employee.objects.get(user=request.user)
        
        # Obtener todos los status del empleado ordenados por fecha
        status_history = AgentStatus.objects.filter(
            agent=employee
        ).select_related('campaign').order_by('-start_time')

        ready_statuses = AgentStatus.objects.filter(
            agent=employee,
            status='ready'
        )
        total_ready_duration = sum(
            (
                (status.end_time or timezone.now()) - status.start_time
                for status in ready_statuses
                if status.start_time
            ),
            timedelta(0)
        )
        # Convert timedelta → hours (float)
        total_ready_hours = total_ready_duration.total_seconds() / 3600
        hours, remainder = divmod(total_ready_duration.total_seconds(), 3600)
        minutes = remainder // 60
        formatted_ready_time = f"{int(hours)}h {int(minutes)}m"
        
        # Paginación - 50 registros por página
        paginator = Paginator(status_history, 50)
        page_number = request.GET.get('page')
        page_obj = paginator.get_page(page_number)
        
        # Estadísticas
        total_records = status_history.count()

                
        context = {
            'employee': employee,
            'page_obj': page_obj,
            'total_records': total_records,
            'total_ready_hours':formatted_ready_time

        }
        
        return render(request, 'attendance/employee_status_history.html', context)
        
    except Employee.DoesNotExist:
        messages.error(request, "Employee profile not found.")
        return redirect('home')        

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
        # Cerrar cualquier estado activo
        close_active_status(employee)

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
        supervisor = Employee.objects.get(user=request.user, is_supervisor=True)
        team_members = Employee.objects.filter(supervisor=supervisor, is_active=True)

        # Agregar el estado actual a cada agente
        for agent in team_members:
            agent.current_status = AgentStatus.get_current_status(agent)

        context = {
            'supervisor': supervisor,
            'team_members': team_members,
            'current_time': timezone.now(),
        }

        return render(request, 'attendance/supervisor_dashboard.html', context)

    except Employee.DoesNotExist:
        messages.error(request, "You are not a supervisor.")
        return redirect('home')


@login_required
def supervisor_dashboard_partial(request):
    """Renderiza solo la tabla de agentes (para refresco con HTMX)"""
    supervisor = Employee.objects.get(user=request.user, is_supervisor=True)
    team_members = Employee.objects.filter(supervisor=supervisor, is_active=True)

    for agent in team_members:
        agent.current_status = AgentStatus.get_current_status(agent)

    return render(request, 'attendance/partials/agents_table.html', {
        'team_members': team_members,
        'current_time': timezone.now(),
    })




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
        ).select_related('agent').order_by('-start_time')[:5]
        
        context = {
            'today_activity': today_activity,
        }
        
        return render(request, 'attendance/partials/activity_timeline.html', context)
    except Employee.DoesNotExist:
        return HttpResponse(status=403)
    
def employee_status_list(request, id_employee):
    employee = get_object_or_404(Employee, id=id_employee)
    today = now().date()

    statuses = AgentStatus.objects.filter(
        agent=employee,
        start_time__date=today  # 👈 filtrado directo por fecha
    ).order_by('-start_time')

    return render(request, 'attendance/employee_status_list.html', {
        'employee': employee,
        'statuses': statuses,
        'today': today,
    })

@login_required
def add_status_note(request, status_id):
    """Add note to existing status record"""
    status_record = get_object_or_404(AgentStatus, id=status_id)
    
    if request.method == 'POST':
        notes = request.POST.get('notes', '').strip()
        if notes:
            status_record.notes = notes
            status_record.save()
            messages.success(request, 'Note added successfully.')
        else:
            messages.error(request, 'Note cannot be empty.')
    
    return redirect(request.META.get('HTTP_REFERER', 'supervisor_dashboard'))


def employee_force_logout(request, employee_id):
    target_employee = get_object_or_404(Employee, id=employee_id)

    try:
        requester_employee = Employee.objects.get(user=request.user)
    except Employee.DoesNotExist:
        messages.error(request, 'You need an employee profile to perform this action.')
        return redirect('supervisor_dashboard')

    if (
        requester_employee.is_supervisor and 
        target_employee.supervisor == requester_employee and
        target_employee.user
    ):
        # Cerrar sesiones activas
        sessions = Session.objects.filter(expire_date__gte=timezone.now())
        for session in sessions:
            data = session.get_decoded()
            if data.get('_auth_user_id') == str(target_employee.user.id):
                session.delete()
                break

        # Actualizar estado del agente
        with transaction.atomic():
            close_active_status(target_employee)  # 👈 usa la misma función
            new_status = AgentStatus.objects.create(
                agent=target_employee,
                status='offline',
                start_time=timezone.now(),
                notes='Forced logout by supervisor'
            )

            if hasattr(target_employee, 'current_status'):
                target_employee.current_status = new_status
                target_employee.save(update_fields=['current_status'])

        messages.success(
            request,
            f'{target_employee.user.get_full_name()} has been logged out and set to Offline.'
        )

    else:
        messages.error(request, 'You can only logout employees from your own team.')

    return redirect('supervisor_dashboard')


def export_employees_excel(request):
    response = HttpResponse(content_type='text/csv; charset=utf-8')
    response['Content-Disposition'] = 'attachment; filename=employees_payroll_detailed.csv'

    writer = csv.writer(response)
    
    # Encabezados más detallados
    writer.writerow([
        'Employee Code', 'First Name', 'Last Name', 'Email', 
        'Identification', 'Department', 'Position', 'Supervisor',
        'Pay Type', 'Base Rate', 'Overtime Rate', 'Bonus',
        'Total Hours', 'Regular Hours', 'Overtime Hours',
        'Gross Salary', 'AFP (2.87%)', 'SFS (3.04%)', 'ISR', 
        'Other Deductions', 'Total Deductions', 'Net Salary',
        'Bank Name', 'Account Number', 'Period'
    ])

    today = timezone.now().date()
    period_start = today.replace(day=1)
    period_end = today
    period_name = f"{period_start.strftime('%b %Y')}"

    employees = Employee.objects.select_related('user', 'position', 'department', 'supervisor').all()

    for employee in employees:
        # ✅ Calculate total hours and separate regular/overtime
        ready_statuses = AgentStatus.objects.filter(
            agent=employee,
            status='ready',
            start_time__date__range=[period_start, period_end]
        )

        total_seconds = 0
        for status in ready_statuses:
            end_time = status.end_time or timezone.now()
            if end_time.date() > period_end:
                end_time = timezone.make_aware(datetime.combine(period_end, datetime.max.time()))
            
            duration = end_time - status.start_time
            total_seconds += duration.total_seconds()

        total_hours = Decimal(total_seconds) / Decimal(3600) if total_seconds > 0 else Decimal('0')
        total_hours = round(total_hours, 2)
        
        # Calcular horas regulares y extra (simplificado)
        regular_hours = min(total_hours, Decimal('160'))  # 160 horas mensuales
        overtime_hours = max(total_hours - Decimal('160'), Decimal('0'))

        # ✅ Get payroll info
        payroll_info = get_effective_pay_rate(employee, total_hours=total_hours)
        
        # ✅ Calcular deducciones
        gross_salary = payroll_info['net_salary']
        deductions = calculate_employee_deductions(gross_salary)
        
        # Información del supervisor
        supervisor_name = ""
        if employee.supervisor and employee.supervisor.user:
            supervisor_name = f"{employee.supervisor.user.get_full_name()}"

        writer.writerow([
            employee.employee_code,
            employee.user.first_name if employee.user else '',
            employee.user.last_name if employee.user else '',
            employee.user.email if employee.user else '',
            employee.identification,
            employee.department.name if employee.department else 'N/A',
            employee.position.name if employee.position else 'N/A',
            supervisor_name,
            payroll_info['pay_type'].title(),
            float(payroll_info['base_rate']),
            float(payroll_info['overtime_rate']),
            float(payroll_info['bonus']),
            float(total_hours),
            float(regular_hours),
            float(overtime_hours),
            float(gross_salary),
            float(deductions['afp']),
            float(deductions['sfs']),
            float(deductions['isr']),
            float(deductions['other_deductions']),
            float(deductions['total_deductions']),
            float(deductions['net_income']),
            employee.bank_name or 'N/A',
            employee.bank_account or 'N/A',
            period_name
        ])

    return response

def calculate_employee_deductions(total_earnings, year=None):
    """
    Calcular deducciones legales para República Dominicana
    """
    if year is None:
        year = datetime.now().year
    
    # Validar que total_earnings sea Decimal
    if not isinstance(total_earnings, Decimal):
        total_earnings = Decimal(str(total_earnings))
    
    # Asegurar que sea positivo
    total_earnings = max(total_earnings, Decimal('0'))
    
    # AFP (Administradora de Fondos de Pensiones) - 2.87%
    afp = (total_earnings * Decimal('0.0287')).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
    
    # SFS (Sistema de Fondo de Salud) - 3.04%
    sfs = (total_earnings * Decimal('0.0304')).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
    
    # Base para ISR (Ingreso imponible)
    taxable_income = total_earnings - afp - sfs
    
    # Calcular ISR según las escalas
    isr = calculate_isr(taxable_income, year)
    
    # Otras deducciones (podrían incluir préstamos, etc.)
    other_deductions = Decimal('0')
    
    total_deductions = afp + sfs + isr + other_deductions
    
    return {
        'afp': afp,
        'sfs': sfs, 
        'isr': isr,
        'other_deductions': other_deductions,
        'total_deductions': total_deductions,
        'taxable_income': taxable_income,
        'net_income': total_earnings - total_deductions
    }

def calculate_isr(taxable_income, year=2024):
    """
    Calcular Impuesto Sobre la Renta según escalas oficiales de RD
    Escalas basadas en el año 2024
    """
    if not isinstance(taxable_income, Decimal):
        taxable_income = Decimal(str(taxable_income))
    
    # Asegurar que sea positivo
    taxable_income = max(taxable_income, Decimal('0'))
    
    # Escalas ISR 2024 para República Dominicana
    # (Estas escalas pueden cambiar anualmente)
    if year == 2024:
        scales = [
            (Decimal('416220.00'), Decimal('0.00'), Decimal('0.00')),    # Exento
            (Decimal('624329.00'), Decimal('0.15'), Decimal('416220.01')), # 15%
            (Decimal('867123.00'), Decimal('0.20'), Decimal('624329.01')), # 20%
            (Decimal('999999999.00'), Decimal('0.25'), Decimal('867123.01'))  # 25%
        ]
        
        # Montos fijos por escalón (acumulado de escalones anteriores)
        fixed_amounts = {
            1: Decimal('0'),      # Escalón 1: Exento
            2: Decimal('31216'),  # Escalón 2: 31,216
            3: Decimal('79776')   # Escalón 3: 79,776
        }
    else:
        # Para otros años, usar escalas por defecto (2024)
        # En una implementación real, tendrías diferentes escalas por año
        scales = [
            (Decimal('416220.00'), Decimal('0.00'), Decimal('0.00')),
            (Decimal('624329.00'), Decimal('0.15'), Decimal('416220.01')),
            (Decimal('867123.00'), Decimal('0.20'), Decimal('624329.01')),
            (Decimal('999999999.00'), Decimal('0.25'), Decimal('867123.01'))
        ]
        fixed_amounts = {
            1: Decimal('0'),
            2: Decimal('31216'), 
            3: Decimal('79776')
        }
    
    # Encontrar el escalón correspondiente
    for i, (limit, rate, base) in enumerate(scales, 1):
        if taxable_income <= limit:
            if i == 1:  # Primer escalón (exento)
                return Decimal('0')
            else:
                # Calcular ISR para este escalón
                excess = taxable_income - base
                calculated_isr = fixed_amounts[i] + (excess * rate)
                return calculated_isr.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
    
    # Si excede todas las escalas (no debería pasar)
    return Decimal('0')
