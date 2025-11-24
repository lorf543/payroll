# payroll/views.py
from django.db.models import Sum, Q, Count
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render, get_object_or_404, HttpResponse
from django.utils import timezone
from datetime import timedelta
from decimal import Decimal
from django.http import JsonResponse

from core.models import Employee, Payment, PaymentConcept,PaymentDetail, PayPeriod
from attendance.models import WorkDay



@login_required
def nomina_dashboard(request):
    """Dashboard centralizado de nómina"""
    # Verificar permisos
    # if not request.user.has_perm('core.manage_payroll'):
    #     messages.error(request, "No tienes permisos para acceder a nómina.")
    #     return redirect('employee_profile')
    
    # Períodos activos
    active_periods = PayPeriod.objects.filter(is_closed=False).order_by('-start_date')
    
    # Próximos pagos
    upcoming_payments = PayPeriod.objects.filter(
        pay_date__gte=timezone.now().date(),
        is_closed=False
    ).order_by('pay_date')
    
    # Estadísticas rápidas
    total_employees = Employee.objects.filter(is_active=True).count()
    
    # Workdays pendientes de aprobación (últimos 30 días)
    pending_workdays = WorkDay.objects.filter(
        date__gte=timezone.now().date() - timedelta(days=30),
        is_approved=False,
        employee__is_active=True
    ).count()
    
    # Pagos recientes
    recent_payments = Payment.objects.select_related('employee', 'period').order_by('-created_at')[:5]
    
    context = {
        'active_periods': active_periods,
        'upcoming_payments': upcoming_payments,
        'total_employees': total_employees,
        'pending_workdays': pending_workdays,
        'recent_payments': recent_payments,
    }
    
    return render(request, 'nomina/dashboard.html', context)


@login_required
def create_pay_period(request):
    """Crear nuevo período de pago y asignar automáticamente empleados"""
    if request.method == 'POST':
        try:
            # Datos del período
            name = request.POST.get('name')
            start_date = request.POST.get('start_date')
            end_date = request.POST.get('end_date')
            pay_date = request.POST.get('pay_date')
            frequency = request.POST.get('frequency')
            
            # Crear período
            period = PayPeriod.objects.create(
                name=name,
                start_date=start_date,
                end_date=end_date,
                pay_date=pay_date,
                frequency=frequency
            )
            
            # Obtener empleados activos
            active_employees = Employee.objects.filter(is_active=True)
            
            # Buscar workdays existentes en ese rango
            workdays_count = WorkDay.objects.filter(
                date__range=[start_date, end_date],
                employee__in=active_employees
            ).count()
            
            messages.success(request, 
                f"Período '{period.name}' creado exitosamente. "
                f"Se encontraron {workdays_count} días trabajados para {active_employees.count()} empleados activos."
            )
            
            return redirect('review_pay_period', period_id=period.id)
            
        except Exception as e:
            messages.error(request, f"Error creando período: {str(e)}")
    
    return render(request, 'nomina/create_period.html')




@login_required
def review_pay_period(request, period_id):
    """Revisar y gestionar un período de pago completo"""
    period = get_object_or_404(PayPeriod, id=period_id)
    
    # Obtener todos los empleados activos
    active_employees = Employee.objects.filter(is_active=True)
    
    # Preparar datos para cada empleado
    employees_data = []
    total_gross = Decimal('0.00')
    total_net = Decimal('0.00')
    
    for employee in active_employees:
        # Obtener workdays del empleado en el período
        workdays = WorkDay.objects.filter(
            employee=employee,
            date__range=[period.start_date, period.end_date]
        ).order_by('date')
        
        # Calcular totales
        workdays_data = []
        employee_gross = Decimal('0.00')
        employee_approved = True
        
        for workday in workdays:
            # Calcular pago si no está calculado
            if workday.total_pay == 0 and workday.productive_hours > 0:
                workday.calculate_pay()
                workday.save()
            
            workdays_data.append(workday)
            employee_gross += workday.total_pay
            
            # Verificar si todos están aprobados
            if not workday.is_approved:
                employee_approved = False
        
        # Calcular deducciones y neto
        employee_net = calculate_employee_net_salary(employee, employee_gross)
        
        employees_data.append({
            'employee': employee,
            'workdays': workdays_data,
            'workdays_count': len(workdays_data),
            'approved_count': sum(1 for w in workdays_data if w.is_approved),
            'total_gross': employee_gross,
            'total_net': employee_net,
            'fully_approved': employee_approved,
            'has_workdays': len(workdays_data) > 0,
        })
        
        total_gross += employee_gross
        total_net += employee_net
    
    # Estadísticas del período
    all_workdays = WorkDay.objects.filter(
        date__range=[period.start_date, period.end_date],
        employee__is_active=True
    )
    
    stats = {
        'total_employees': active_employees.count(),
        'employees_with_workdays': sum(1 for ed in employees_data if ed['has_workdays']),
        'total_workdays': all_workdays.count(),
        'approved_workdays': all_workdays.filter(is_approved=True).count(),
        'total_gross': total_gross,
        'total_net': total_net,
        'all_approved': all(ed['fully_approved'] for ed in employees_data if ed['has_workdays']),
    }
    
    context = {
        'period': period,
        'employees_data': employees_data,
        'stats': stats,
    }
    
    return render(request, 'nomina/period_review.html', context)



def calculate_employee_net_salary(employee, gross_salary):
    """Calcular salario neto con deducciones"""
    if gross_salary == 0:
        return Decimal('0.00')
    
    # AFP (2.87%)
    afp = gross_salary * Decimal('0.0287')
    
    # SFS (3.04%)
    sfs = gross_salary * Decimal('0.0304')
    
    # ISR (simplificado - deberías implementar tablas reales)
    isr = calculate_isr(gross_salary)
    
    total_deductions = afp + sfs + isr
    return gross_salary - total_deductions



def calculate_isr(gross_salary):
    """Cálculo simplificado de ISR"""
    # Esto es un ejemplo - implementa las tablas reales del ISR
    if gross_salary <= Decimal('416220.00'):  # Límite de exención
        return Decimal('0.00')
    elif gross_salary <= Decimal('624329.00'):
        return (gross_salary - Decimal('416220.00')) * Decimal('0.15')
    else:
        exceso = gross_salary - Decimal('624329.00')
        return (Decimal('624329.00') - Decimal('416220.00')) * Decimal('0.15') + exceso * Decimal('0.20')
    


@login_required
def approve_all_workdays(request, period_id):
    """Aprobar todos los workdays del período"""
    period = get_object_or_404(PayPeriod, id=period_id)
    
    workdays = WorkDay.objects.filter(
        date__range=[period.start_date, period.end_date],
        employee__is_active=True,
        is_approved=False
    )
    
    approved_count = 0
    for workday in workdays:
        workday.approve(request.user)
        approved_count += 1
    
    messages.success(request, f"{approved_count} días trabajados aprobados.")
    return redirect('review_pay_period', period_id=period_id)

@login_required
def generate_payroll(request, period_id):
    """Generar nómina completa para el período"""
    period = get_object_or_404(PayPeriod, id=period_id)
    
    # Verificar que todos los workdays estén aprobados
    unapproved_count = WorkDay.objects.filter(
        date__range=[period.start_date, period.end_date],
        employee__is_active=True,
        is_approved=False
    ).count()
    
    if unapproved_count > 0:
        messages.warning(request, 
            f"Hay {unapproved_count} días trabajados sin aprobar. "
            f"Por favor aprueba todos los días antes de generar la nómina."
        )
        return redirect('review_pay_period', period_id=period_id)
    
    # Generar pagos para cada empleado
    created_count = 0
    active_employees = Employee.objects.filter(is_active=True)
    
    for employee in active_employees:
        workdays = WorkDay.objects.filter(
            employee=employee,
            date__range=[period.start_date, period.end_date],
            is_approved=True
        )
        
        total_gross = sum(workday.total_pay for workday in workdays)
        
        if total_gross > 0:
            # Crear o actualizar pago
            payment, created = Payment.objects.update_or_create(
                employee=employee,
                period=period,
                defaults={
                    'gross_salary': total_gross,
                    'pay_date': period.pay_date,
                    'status': 'calculated'
                }
            )
            
            if created:
                created_count += 1
    
    messages.success(request, 
        f"Nómina generada exitosamente para {created_count} empleados. "
        f"Total período: ${sum(p.gross_salary for p in Payment.objects.filter(period=period)):,.2f}"
    )
    
    return redirect('review_pay_period', period_id=period_id)

@login_required
def toggle_workday_approval(request, workday_id):
    """Aprobar/desaprobar workday individual"""
    workday = get_object_or_404(WorkDay, id=workday_id)
    
    if workday.is_approved:
        workday.unapprove()
        action = "desaprobado"
    else:
        workday.approve(request.user)
        action = "aprobado"
    
    if request.headers.get('x-requested-with') == 'XMLHttpRequest':
        return JsonResponse({
            'success': True,
            'action': action,
            'is_approved': workday.is_approved,
            'workday_id': workday_id
        })
    
    messages.success(request, f"Día {action} para {workday.employee.full_name}.")
    return redirect('review_pay_period', period_id=request.GET.get('period_id'))