from django.shortcuts import render,get_object_or_404,redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.contrib.auth.models import User 

from django.utils.timezone import now
from django.db.models import Sum, Count, Avg
from django.db.models.functions import ExtractYear

from django.utils import timezone
from datetime import timedelta
from decimal import Decimal
from datetime import date

from .models import Employee, Payment,Department, Position
from .forms import EmployeeForm, UploadCSVForm

import csv
# Create your views here.

def timedelta_to_hours(td):
    return Decimal(td.total_seconds()) / Decimal(3600)


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
        


@login_required(login_url='account_login')
def home_view(request):
    employee = get_object_or_404(Employee, user=request.user)
    payments = Payment.objects.filter(employee=employee)


    # Latest payment
    last_payment = payments.first()

    # Totals for the current year
    current_year = now().year
    year_payments = payments.filter(pay_date__year=current_year)
    total_year = year_payments.aggregate(total=Sum("net_salary"))["total"] or 0
    total_payments = year_payments.count()
    avg_monthly = total_year / 12 if total_year else 0

    context = {
        "employee": employee,
        "payments": payments,
        "last_payment": last_payment,
        "total_year": total_year,
        "total_payments": total_payments,
        "avg_monthly": avg_monthly,
    }
    return render(request, "index.html", context)


def admin_dashboard(request):
    # Department statistics
    departments = Department.objects.annotate(
        employee_count=Count('employee')
    ).order_by('-annual_budget')
    
    total_department_budget = Department.objects.aggregate(
        total_budget=Sum('annual_budget')
    )['total_budget'] or 0
    
    # Employee statistics
    total_employees = Employee.objects.count()
    active_employees = Employee.objects.filter(is_active=True).count()
    total_departments = Department.objects.count()
    total_positions = Position.objects.count()
    
    # Contract type statistics
    full_time_count = Employee.objects.filter(
        position__contract_type='full_time', 
        is_active=True
    ).count()
    
    part_time_count = Employee.objects.filter(
        position__contract_type='part_time', 
        is_active=True
    ).count()
    
    temporary_count = Employee.objects.filter(
        position__contract_type='temporary', 
        is_active=True
    ).count()
    
    intern_count = Employee.objects.filter(
        position__contract_type='intern', 
        is_active=True
    ).count()
    
    # Tenure statistics
    current_year = date.today().year
    employees_with_tenure = Employee.objects.filter(is_active=True)
    total_tenure = 0
    for employee in employees_with_tenure:
        total_tenure += (current_year - employee.hire_date.year)
    
    average_tenure = total_tenure / active_employees if active_employees > 0 else 0
    
    # New hires this year
    new_hires_this_year = Employee.objects.filter(
        hire_date__year=current_year
    ).count()
    
    # Recent employees for the table
    employees = Employee.objects.select_related(
        'user', 'position', 'department'
    ).filter(is_active=True).order_by('-hire_date')[:50]
    
    context = {
        'departments': departments,
        'total_department_budget': total_department_budget,
        'total_employees': total_employees,
        'active_employees': active_employees,
        'total_departments': total_departments,
        'total_positions': total_positions,
        'full_time_count': full_time_count,
        'part_time_count': part_time_count,
        'temporary_count': temporary_count,
        'intern_count': intern_count,
        'average_tenure': round(average_tenure, 1),
        'new_hires_this_year': new_hires_this_year,
        'employees': employees,
    }
    
    return render(request, 'core/components/admin_dashboard.html', context)



def perfil_edit(request, employee_id):
    # Obtener el empleado por ID, no por user
    employee = get_object_or_404(Employee, id=employee_id)
    
    # Verificar que el usuario tiene permisos para editar este perfil
    if request.user != employee.user and not request.user.is_staff:
        messages.error(request, "You don't have permission to edit this profile.")
        return redirect('home')
    
    if request.method == 'POST':
        form = EmployeeForm(request.POST, instance=employee)
        if form.is_valid():
            try:
                form.save()
                messages.success(request, "Profile updated successfully.")
                return redirect('employees_detail', employee_id=employee.id)
            except Exception as e:
                messages.error(request, f"Error saving profile: {str(e)}")
        else:
            # Mostrar errores del formulario
            print("Form errors:", form.errors)
            messages.error(request, "Please correct the errors below.")
    else:
        form = EmployeeForm(instance=employee)
    
    context = {
        'employee': employee, 
        'form': form
    }
    return render(request, 'core/forms/edit_perfil.html', context)



@login_required(login_url='account_login')
def employees_view(request):
    employees = Employee.objects.all()

    context = {'employees':employees}
    return render(request,'core/employees.html', context)


@login_required(login_url='account_login')
def employees_detail(request, employee_id):
    try:
        employee = Employee.objects.get(id=employee_id)
        
        # 🔥 NUEVO: Cálculo completo de pagos usando la función existente
        # Simulamos un tiempo productivo para el cálculo mensual (80 horas * 2 semanas)
        sample_payable_time = timedelta(hours=80 * 2)
        monthly_earnings, pay_method = calculate_employee_pay(employee, sample_payable_time)
        
        # Cálculo del pago por horas (para comparación)
        if employee.position.hour_rate:
            montly_payment_hour = employee.position.hour_rate * 80 * 2
        else:
            montly_payment_hour = 0
        
        # Información detallada del método de pago
        payment_info = get_payment_method_display(employee)
        
        # Estadísticas de pago para mostrar en el template
        payment_stats = {
            'monthly_earnings': monthly_earnings,
            'pay_method': pay_method,
            'payment_info': payment_info,
            'hourly_rate_equivalent': round(monthly_earnings / (80 * 2), 2) if not employee.fixed_rate else employee.position.hour_rate,
            'montly_payment_hour': montly_payment_hour,  # Mantener compatibilidad
            'is_fixed_rate': employee.fixed_rate,
            'custom_salary': employee.custom_base_salary,
            'position_salary': employee.position.base_salary,
            'position_hour_rate': employee.position.hour_rate,
        }

    except Employee.DoesNotExist:
        return render(request, 'core/404.html', status=404)

    context = {
        'employee': employee,
        'montly_payment_hour': montly_payment_hour,  # Para compatibilidad
        'payment_stats': payment_stats,  # 🔥 NUEVO: Datos completos de pago
    }
    return render(request, 'core/employee_detail.html', context)