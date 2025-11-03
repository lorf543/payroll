from django.contrib.sessions.models import Session

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.db.models import Sum, Count
from django.shortcuts import render, get_object_or_404, redirect, HttpResponse
from django.utils import timezone
from django.utils.timezone import now

from .models import Employee, Payment, Department, Position
from .forms import EmployeeForm, UploadCSVForm



@login_required(login_url='account_login')
def home_view(request):
    """Panel principal del empleado con resumen de pagos."""
    try:
        employee = Employee.objects.get(user=request.user)
    except Employee.DoesNotExist:
        # Crear Employee automáticamente
        try:
            from core.models import Department, Position
            
            # Obtener o crear defaults
            default_dept, _ = Department.objects.get_or_create(
                name="General Department",
                defaults={'description': 'Departamento por defecto'}
            )
            default_position, _ = Position.objects.get_or_create(
                title="General Position", 
                defaults={'description': 'Posición por defecto'}
            )
            
            employee = Employee.objects.create(
                user=request.user,
                first_name=request.user.first_name or request.user.username,
                last_name=request.user.last_name or "Usuario",
                department=default_dept,
                position=default_position,
                is_supervisor=False,
                is_it=False
            )
            
            messages.success(request, "¡Bienvenido! Tu perfil de empleado ha sido creado automáticamente.")
            
        except Exception as e:
            messages.error(request, f"Error creando perfil: {str(e)}")
            return render(request, "error.html", {
                "error": "No se pudo crear tu perfil de empleado. Contacta al administrador."
            })
    
    # Resto de tu código original...
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


def list_employees(requeest):
    employees = Employee.objects.all()

    context = {
        'employees':employees
    }
    return render(requeest,'core/employees.html',context)

def logout_all_users(request):
    """
    Cerrar sesión de todos los usuarios activos
    Solo accesible para superusers
    """
    try:
        # 1. Eliminar todas las sesiones activas
        sessions_deleted = Session.objects.all().delete()
        
        # 2. Actualizar estado de empleados
        employees_updated = Employee.objects.filter(is_logged_in=True).update(
            is_logged_in=False,
            last_logout=timezone.now()
        )
        
        # 3. Mensaje de éxito
        messages.success(
            request, 
            f"✅ All users have been logged out. {employees_updated} employees updated."
        )
        
        return redirect('admin:index')  # Redirigir al admin
        
    except Exception as e:
        messages.error(request, f"❌ Error logging out all users: {str(e)}")
        return redirect('admin:index')




