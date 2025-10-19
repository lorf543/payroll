from datetime import date, datetime, timedelta, time
from decimal import Decimal
import csv

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.db.models import Sum, Count
from django.shortcuts import render, get_object_or_404, redirect
from django.utils import timezone
from django.utils.timezone import now

from .models import Employee, Payment, Department, Position
from .forms import EmployeeForm, UploadCSVForm
from .tasks import sleeptime


# ==============================
# 🔧 Utility Functions
# ==============================

def timedelta_to_hours(td):
    """Convierte un timedelta en horas (Decimal)."""
    return Decimal(td.total_seconds()) / Decimal(3600)


def calculate_employee_pay(employee, payable_time):
    """
    Calcula el pago del empleado basado en su configuración:
    1. Salario fijo (custom o de posición)
    2. Por horas (custom o de posición)
    """
    payable_hours = timedelta_to_hours(payable_time)

    # 1️⃣ Empleado con salario fijo
    if employee.fixed_rate:
        if employee.custom_base_salary and employee.custom_base_salary > 0:
            # Salario fijo personalizado
            daily_salary = employee.custom_base_salary / Decimal(22)
            return round(daily_salary, 2), "fixed_custom"
        elif employee.position and employee.position.base_salary and employee.position.base_salary > 0:
            # Salario fijo basado en posición
            daily_salary = employee.position.base_salary / Decimal(22)
            return round(daily_salary, 2), "fixed_position"
        elif employee.position and employee.position.hour_rate:
            # Fijo por defecto basado en tarifa horaria
            return round(employee.position.hour_rate * Decimal(8), 2), "fixed_default"
        else:
            return Decimal(0), "fixed_unknown"

    # 2️⃣ Empleado por horas
    else:
        if employee.custom_base_salary and employee.custom_base_salary > 0:
            return round(employee.custom_base_salary * payable_hours, 2), "hourly_custom"
        elif employee.position and employee.position.hour_rate:
            return round(employee.position.hour_rate * payable_hours, 2), "hourly_position"
        else:
            return Decimal(0), "hourly_unknown"


def get_payment_method_display(employee):
    """Devuelve descripción del método de pago del empleado."""
    if employee.fixed_rate:
        if employee.custom_base_salary:
            return f"Salario fijo: ${employee.custom_base_salary:,.2f}/mes"
        elif employee.position and employee.position.base_salary:
            return f"Salario fijo: ${employee.position.base_salary:,.2f}/mes"
        elif employee.position and employee.position.hour_rate:
            return f"Salario fijo: ${employee.position.hour_rate * 8 * 22:,.2f}/mes"
        else:
            return "Salario fijo no definido"
    else:
        if employee.custom_base_salary:
            return f"Por horas: ${employee.custom_base_salary:,.2f}/hora"
        elif employee.position and employee.position.hour_rate:
            return f"Por horas: ${employee.position.hour_rate:,.2f}/hora"
        else:
            return "Por horas: tarifa no definida"


# ==============================
# 🏠 Dashboard Views
# ==============================
sleeptime
@login_required(login_url='account_login')
def home_view(request):
    """Panel principal del empleado con resumen de pagos."""
    employee = get_object_or_404(Employee, user=request.user)
    payments = Payment.objects.filter(employee=employee).order_by('-pay_date')

    # Último pago
    last_payment = payments.first()

    # Totales del año actual
    current_year = now().year
    year_payments = payments.filter(
        # period__start_date__year=current_year,
        status='paid'
    )
    total_year = year_payments.aggregate(total=Sum("net_salary"))["total"] or 0
    total_payments = year_payments.count()
    
    # Promedio quincenal (24 quincenas al año)
    avg_monthly = total_year / 12 if total_year else 0

    context = {
        "employee": employee,
        "payments": payments[:12],  # Últimos 12 pagos (6 meses)
        "last_payment": last_payment,
        "total_year": total_year,
        "total_payments": total_payments,
        "avg_monthly": avg_monthly,
    }
    return render(request, "index.html", context)


@login_required(login_url='account_login')
def admin_dashboard(request):
    """Panel administrativo con estadísticas generales."""
    # Estadísticas de departamentos
    departments = Department.objects.annotate(employee_count=Count('employee')).order_by('-annual_budget')
    total_department_budget = Department.objects.aggregate(total_budget=Sum('annual_budget'))['total_budget'] or 0

    # Estadísticas de empleados
    total_employees = Employee.objects.count()
    active_employees = Employee.objects.filter(is_active=True).count()
    total_departments = Department.objects.count()
    total_positions = Position.objects.count()

    # Tipos de contrato
    contract_types = ['full_time', 'part_time', 'temporary', 'intern']
    contract_counts = {
        ct: Employee.objects.filter(position__contract_type=ct, is_active=True).count()
        for ct in contract_types
    }

    # Antigüedad promedio
    current_year = date.today().year
    total_tenure = sum(current_year - e.hire_date.year for e in Employee.objects.filter(is_active=True))
    average_tenure = total_tenure / active_employees if active_employees > 0 else 0

    # Nuevas contrataciones
    new_hires_this_year = Employee.objects.filter(hire_date__year=current_year).count()

    # Empleados recientes
    employees = Employee.objects.select_related('user', 'position', 'department').filter(is_active=True).order_by('-hire_date')[:50]

    context = {
        'departments': departments,
        'total_department_budget': total_department_budget,
        'total_employees': total_employees,
        'active_employees': active_employees,
        'total_departments': total_departments,
        'total_positions': total_positions,
        **contract_counts,
        'average_tenure': round(average_tenure, 1),
        'new_hires_this_year': new_hires_this_year,
        'employees': employees,
    }
    return render(request, 'core/components/admin_dashboard.html', context)


# ==============================
# 👤 Employee Views
# ==============================

@login_required(login_url='account_login')
def employees_view(request):
    """Lista de empleados."""
    employees = Employee.objects.all()
    return render(request, 'core/employees.html', {'employees': employees})


@login_required(login_url='account_login')
def employees_detail(request, employee_id):
    """Detalle del empleado con estadísticas de pago simuladas."""
    employee = get_object_or_404(Employee, id=employee_id)

    sample_payable_time = timedelta(hours=160)  # Simulación de 2 semanas (80h * 2)
    monthly_earnings, pay_method = calculate_employee_pay(employee, sample_payable_time)

    hour_rate = getattr(employee.position, 'hour_rate', None) or Decimal(0)
    montly_payment_hour = hour_rate * Decimal(160)

    payment_info = get_payment_method_display(employee)

    payment_stats = {
        'monthly_earnings': monthly_earnings,
        'pay_method': pay_method,
        'payment_info': payment_info,
        'hourly_rate_equivalent': round(monthly_earnings / Decimal(160), 2) if not employee.fixed_rate else hour_rate,
        'montly_payment_hour': montly_payment_hour,
        'is_fixed_rate': employee.fixed_rate,
        'custom_salary': employee.custom_base_salary,
        'position_salary': getattr(employee.position, 'base_salary', 0),
        'position_hour_rate': hour_rate,
    }

    context = {
        'employee': employee,
        'montly_payment_hour': montly_payment_hour,
        'payment_stats': payment_stats,
    }
    return render(request, 'core/employee_detail.html', context)


@login_required(login_url='account_login')
def perfil_edit(request, employee_id):
    """Editar perfil del empleado."""
    employee = get_object_or_404(Employee, id=employee_id)

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
            print("Form errors:", form.errors)
            messages.error(request, "Please correct the errors below.")
    else:
        form = EmployeeForm(instance=employee)

    return render(request, 'core/forms/edit_perfil.html', {'employee': employee, 'form': form})



