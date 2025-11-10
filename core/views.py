from django.contrib.sessions.models import Session

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.db.models import Sum, Count
from django.shortcuts import render, get_object_or_404, redirect, HttpResponse
from django.utils import timezone
from django.utils.timezone import now
from django.db.models import Count, Sum, Avg, Q
from django.utils import timezone
from datetime import timedelta
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.views.generic import TemplateView

from .models import Employee, Payment, Department, Position, Campaign
from attendance.models import WorkDay
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
                defaults={'description': 'Default Department'}
            )
            default_position, _ = Position.objects.get_or_create(
                title="General Position", 
                defaults={'description': 'Default position'}
            )
            
            employee = Employee.objects.create(
                user=request.user,
                first_name=request.user.first_name or request.user.username,
                last_name=request.user.last_name or "User",
                department=default_dept,
                position=default_position,
                is_supervisor=False,
                is_it=False
            )
            
            messages.success(request, "Welcome! Your employee profile has been automatically created.")
            
        except Exception as e:
            messages.error(request, f"Error creando perfil: {str(e)}")
            return render(request, "error.html", {
                "error": "Your employee profile could not be created. Contact the administrator.."
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


def list_employees(request):
    query = request.GET.get('q', '').strip()
    employees = Employee.objects.select_related('user').all()

    if query:
        employees = employees.filter(
            Q(user__first_name__icontains=query) |
            Q(user__last_name__icontains=query) |
            Q(department__name__icontains=query)  # si department es un FK, ajusta a department__nombre o similar
        )

    context = {
        'employees': employees,
    }
    return render(request, 'core/employees.html', context)

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


class ManagementDashboardView(LoginRequiredMixin, UserPassesTestMixin, TemplateView):
    template_name = 'management/dashboard.html'
    
    def test_func(self):
        """Solo CEO, managers y supervisores senior pueden acceder"""
        user_employee = getattr(self.request.user, 'employee', None)
        return user_employee and (
            user_employee.is_supervisor or 
            user_employee.position.name.lower() in ['ceo', 'manager', 'director', 'executive']
        )
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # Fechas para filtros
        today = timezone.now().date()
        week_ago = today - timedelta(days=7)
        month_ago = today - timedelta(days=30)
        
        # Métricas principales
        context.update({
            'total_employees': Employee.objects.filter(is_active=True).count(),
            'active_campaigns': Campaign.objects.filter(is_active=True).count(),
            'total_departments': Department.objects.count(),
            'logged_in_today': Employee.objects.filter(is_logged_in=True).count(),
        })
        
        # Datos por campaña
        context['campaigns_data'] = self.get_campaigns_data()
        context['department_stats'] = self.get_department_stats()
        context['attendance_trends'] = self.get_attendance_trends()
        context['top_performers'] = self.get_top_performers()
        
        return context
    
    def get_campaigns_data(self):
        """Obtener estadísticas detalladas por campaña"""
        campaigns = Campaign.objects.filter(is_active=True).annotate(
            employee_count=Count('active_employees', distinct=True),
            total_work_hours=Sum('active_employees__work_days__productive_hours'),
            avg_productivity=Avg('active_employees__work_days__productive_hours')
        )
        
        campaigns_data = []
        for campaign in campaigns:
            # Calcular métricas adicionales
            logged_in_count = campaign.active_employees.filter(is_logged_in=True).count()
            attendance_rate = (logged_in_count / campaign.employee_count * 100) if campaign.employee_count > 0 else 0
            
            campaigns_data.append({
                'campaign': campaign,
                'employee_count': campaign.employee_count,
                'logged_in_count': logged_in_count,
                'attendance_rate': round(attendance_rate, 1),
                'total_work_hours': campaign.total_work_hours or 0,
                'avg_productivity': round(campaign.avg_productivity or 0, 2),
                'completion_percentage': self.calculate_campaign_completion(campaign),
            })
        
        return sorted(campaigns_data, key=lambda x: x['employee_count'], reverse=True)
    
    def get_department_stats(self):
        """Estadísticas por departamento"""
        departments = Department.objects.annotate(
            employee_count=Count('employee', distinct=True),
            supervisor_count=Count('employee', filter=Q(employee__is_supervisor=True)),
            logged_in_count=Count('employee', filter=Q(employee__is_logged_in=True)),
            total_budget=Sum('annual_budget')
        )
        
        return [
            {
                'department': dept,
                'employee_count': dept.employee_count,
                'supervisor_count': dept.supervisor_count,
                'logged_in_count': dept.logged_in_count,
                'attendance_rate': round((dept.logged_in_count / dept.employee_count * 100) if dept.employee_count > 0 else 0, 1),
                'annual_budget': dept.annual_budget,
            }
            for dept in departments
        ]
    
    def get_attendance_trends(self):
        """Tendencias de asistencia de los últimos 7 días"""
        trends = []
        for i in range(7):
            date = timezone.now().date() - timedelta(days=i)
            workdays_count = WorkDay.objects.filter(date=date).count()
            present_count = WorkDay.objects.filter(date=date, status='active').count()
            
            trends.append({
                'date': date,
                'workdays_count': workdays_count,
                'present_count': present_count,
                'attendance_rate': round((present_count / workdays_count * 100) if workdays_count > 0 else 0, 1),
            })
        
        return reversed(trends)  # Más reciente primero
    
    def get_top_performers(self):
        """Top 10 empleados más productivos"""
        from django.db.models import F, FloatField, ExpressionWrapper
        
        # Empleados con mayor promedio de horas productivas
        top_performers = Employee.objects.filter(
            work_days__date__gte=timezone.now().date() - timedelta(days=30)
        ).annotate(
            avg_hours=Avg('work_days__productive_hours'),
            total_hours=Sum('work_days__productive_hours'),
            work_days_count=Count('work_days')
        ).filter(
            avg_hours__gt=0,
            work_days_count__gte=5  # Al menos 5 días de trabajo
        ).order_by('-avg_hours')[:10]
        
        return [
            {
                'employee': emp,
                'avg_hours': round(emp.avg_hours, 2),
                'total_hours': round(emp.total_hours or 0, 2),
                'work_days_count': emp.work_days_count,
                'department': emp.department.name if emp.department else 'N/A',
            }
            for emp in top_performers
        ]
    
    def calculate_campaign_completion(self, campaign):
        """Calcular porcentaje de completitud de campaña"""
        if not campaign.end_date or not campaign.start_date:
            return 0
        
        total_days = (campaign.end_date - campaign.start_date).days
        if total_days <= 0:
            return 100
        
        days_passed = (timezone.now().date() - campaign.start_date).days
        completion = min(100, max(0, (days_passed / total_days) * 100))
        return round(completion, 1)

