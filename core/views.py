from django.shortcuts import render,get_object_or_404,redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.contrib.auth.models import User 

from django.utils.timezone import now
from django.db.models import Sum, Count, Avg
from django.db.models.functions import ExtractYear

from django.utils import timezone
from datetime import timedelta
from datetime import date

from .models import Employee, Payment,Department, Position
from .forms import EmployeeForm, UploadCSVForm

import csv
# Create your views here.


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
        if not employee.position.hour_rate == None:
            montly_payment_hour = employee.position.hour_rate * 80 * 2
        else: montly_payment_hour = 0
        
    except Employee.DoesNotExist:
        return render(request, 'core/404.html', status=404)

    context = {'employee':employee,'montly_payment_hour':montly_payment_hour}
    return render(request, 'core/employee_detail.html', context)