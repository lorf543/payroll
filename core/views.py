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
from django.db.models import Prefetch   

from .models import Employee, Payment, Department, Position, Campaign
from attendance.models import WorkDay
from .forms import EmployeeForm, UploadCSVForm


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
        
        # Métricas principales
        context.update({
            'total_employees': Employee.objects.filter(is_active=True).count(),
            'active_campaigns': Campaign.objects.filter(is_active=True).count(),
            'total_departments': Department.objects.count(),
            'logged_in_today': Employee.objects.filter(is_logged_in=True).count(),
        })
        
        # NUEVAS MÉTRICAS FINANCIERAS
        context.update({
            'total_monthly_cost': self.calculate_total_monthly_cost(),
            'budget_utilization_rate': self.calculate_overall_budget_utilization(),
            'campaigns_over_budget': self.get_campaigns_over_budget(),
            'headcount_utilization_rate': self.calculate_overall_headcount_utilization(),
        })
        
        # Datos con alertas
        context['campaigns_data'] = self.get_campaigns_data()
        context['department_stats'] = self.get_department_stats()
        context['attendance_trends'] = self.get_attendance_trends()
        context['campaign_alerts'] = self.get_campaign_alerts()
        
        return context
    
    def get_campaigns_data(self):
        """Obtener estadísticas detalladas por campaña - OPTIMIZADO"""
        campaigns = Campaign.objects.filter(is_active=True).prefetch_related(
            Prefetch('active_employees', 
                    queryset=Employee.objects.filter(is_active=True).select_related('department'))
        ).annotate(
            employee_count=Count('active_employees', distinct=True),
            total_work_hours=Sum('active_employees__work_days__productive_hours'),
            avg_productivity=Avg('active_employees__work_days__productive_hours')
        )
        
        campaigns_data = []
        for campaign in campaigns:
            logged_in_count = campaign.active_employees.filter(is_logged_in=True).count()
            attendance_rate = (logged_in_count / campaign.employee_count * 100) if campaign.employee_count > 0 else 0
            
            total_cost = self.calculate_campaign_cost(campaign)
            budget_utilization = self.calculate_budget_utilization(campaign, total_cost)
            headcount_utilization = self.calculate_headcount_utilization(campaign)
            
            campaigns_data.append({
                'campaign': campaign,
                'employee_count': campaign.employee_count,
                'logged_in_count': logged_in_count,
                'attendance_rate': round(attendance_rate, 1),
                'total_work_hours': campaign.total_work_hours or 0,
                'avg_productivity': round(campaign.avg_productivity or 0, 2),
                'completion_percentage': self.calculate_campaign_completion(campaign),
                'total_cost': total_cost,
                'budget_utilization': budget_utilization,
                'headcount_utilization': headcount_utilization,
            })
        
        return sorted(campaigns_data, key=lambda x: x['employee_count'], reverse=True)
    
    def get_department_stats(self):
        """Estadísticas por departamento con métricas financieras"""
        departments = Department.objects.annotate(
            employee_count=Count('employee', distinct=True),
            supervisor_count=Count('employee', filter=Q(employee__is_supervisor=True)),
            logged_in_count=Count('employee', filter=Q(employee__is_logged_in=True)),
        )
        
        dept_stats = []
        for dept in departments:
            # Calcular costo del departamento
            dept_cost = self.calculate_department_cost(dept)
            budget_used = min(dept_cost, dept.annual_budget)
            
            dept_stats.append({
                'department': dept,
                'employee_count': dept.employee_count,
                'supervisor_count': dept.supervisor_count,
                'logged_in_count': dept.logged_in_count,
                'attendance_rate': round((dept.logged_in_count / dept.employee_count * 100) if dept.employee_count > 0 else 0, 1),
                'annual_budget': dept.annual_budget,
                'budget_used': budget_used,
            })
        
        return dept_stats
    
    def get_attendance_trends(self):
        """Tendencias de asistencia de los últimos 7 días - CORREGIDO"""
        trends = []
        for i in range(7):
            date = timezone.now().date() - timedelta(days=i)
            
            workdays_count = WorkDay.objects.filter(date=date).count()
            present_count = WorkDay.objects.filter(date=date, check_in__isnull=False).count()
            
            trends.append({
                'date': date,
                'workdays_count': workdays_count,
                'present_count': present_count,
                'attendance_rate': round((present_count / workdays_count * 100) if workdays_count > 0 else 0, 1),
            })
        
        return list(reversed(trends))
    
    def get_campaign_alerts(self):
        """Obtener alertas de campañas que necesitan atención"""
        alerts = []
        
        campaigns = Campaign.objects.filter(is_active=True).annotate(
            employee_count=Count('active_employees'),
            total_hours=Sum('active_employees__work_days__productive_hours')
        )
        
        for campaign in campaigns:
            # Alerta por bajo headcount
            if campaign.head_count and campaign.employee_count < (campaign.head_count * 0.7):
                alerts.append({
                    'type': 'warning',
                    'campaign': campaign,
                    'message': f'Low headcount: {campaign.employee_count}/{campaign.head_count}',
                    'icon': 'bi-people'
                })
            
            # Alerta por sobrepresupuesto
            if campaign.base_salary and campaign.total_hours:
                cost = campaign.hour_rate * campaign.total_hours if campaign.hour_rate else 0
                if cost > campaign.base_salary * 0.9:  # 90% del presupuesto
                    alerts.append({
                        'type': 'danger',
                        'campaign': campaign,
                        'message': f'Approaching budget limit: ${cost:.0f}/${campaign.base_salary:.0f}',
                        'icon': 'bi-cash-coin'
                    })
        
        return alerts[:5]
    
    # MÉTODOS DE CÁLCULO
    def calculate_campaign_cost(self, campaign):
        """Calcular costo total de la campaña"""
        if campaign.hour_rate and campaign.total_work_hours:
            return float(campaign.hour_rate) * float(campaign.total_work_hours or 0)
        return 0
    
    def calculate_budget_utilization(self, campaign, total_cost):
        """Calcular utilización del presupuesto"""
        if campaign.base_salary and total_cost > 0:
            utilization = (total_cost / float(campaign.base_salary)) * 100
            return min(utilization, 100)
        return 0
    
    def calculate_headcount_utilization(self, campaign):
        """Calcular utilización de headcount"""
        if campaign.head_count and campaign.employee_count:
            utilization = (campaign.employee_count / campaign.head_count) * 100
            return min(utilization, 100)
        return 0
    
    def calculate_total_monthly_cost(self):
        """Calcular costo mensual total de todas las campañas"""
        total_cost = 0
        campaigns = Campaign.objects.filter(is_active=True).annotate(
            total_hours=Sum('active_employees__work_days__productive_hours')
        )
        
        for campaign in campaigns:
            if campaign.hour_rate and campaign.total_hours:
                total_cost += float(campaign.hour_rate) * float(campaign.total_hours or 0)
        
        return total_cost
    
    def calculate_overall_budget_utilization(self):
        """Calcular utilización general del presupuesto"""
        total_budget = sum(float(camp.base_salary or 0) for camp in Campaign.objects.filter(is_active=True))
        total_cost = self.calculate_total_monthly_cost()
        
        if total_budget > 0:
            return min((total_cost / total_budget) * 100, 100)
        return 0
    
    def calculate_overall_headcount_utilization(self):
        """Calcular utilización general de headcount"""
        total_headcount = sum(camp.head_count or 0 for camp in Campaign.objects.filter(is_active=True))
        total_employees = Employee.objects.filter(is_active=True, current_campaign__isnull=False).count()
        
        if total_headcount > 0:
            return min((total_employees / total_headcount) * 100, 100)
        return 0
    
    def get_campaigns_over_budget(self):
        """Contar campañas que están sobre el 90% del presupuesto"""
        over_budget_count = 0
        campaigns = Campaign.objects.filter(is_active=True).annotate(
            total_hours=Sum('active_employees__work_days__productive_hours')
        )
        
        for campaign in campaigns:
            if campaign.base_salary and campaign.total_hours:
                cost = campaign.hour_rate * campaign.total_hours if campaign.hour_rate else 0
                if cost > campaign.base_salary * 0.9:
                    over_budget_count += 1
        
        return over_budget_count
    
    def calculate_department_cost(self, department):
        """Calcular costo de un departamento"""
        employees = department.employee_set.filter(is_active=True)
        total_cost = 0
        
        for emp in employees:
            if emp.position and emp.position.base_salary:
                total_cost += float(emp.position.base_salary) / 12  # Mensual
        
        return total_cost
    
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
    

@login_required
def campaign_detail_dashboard(request, campaign_id):
    """
    Dashboard detallado para una campaña específica
    """
    try:
        campaign = Campaign.objects.get(id=campaign_id)
    except Campaign.DoesNotExist:
        messages.error(request, "Campaign not found.")
        return redirect('management_dashboard')
    
    # Verificar permisos - solo management puede ver
    user_employee = getattr(request.user, 'employee', None)
    if not user_employee or not (
        user_employee.is_supervisor or 
        user_employee.position.name.lower() in ['ceo', 'manager', 'director', 'executive']
    ):
        messages.error(request, "You don't have permission to view campaign details.")
        return redirect('employee_profile')
    
    # Obtener empleados activos en esta campaña
    campaign_employees = Employee.objects.filter(
        current_campaign=campaign,
        is_active=True
    ).select_related('user', 'position', 'department', 'supervisor')
    
    # Estadísticas de la campaña
    total_employees = campaign_employees.count()
    logged_in_count = campaign_employees.filter(is_logged_in=True).count()
    
    # Métricas financieras de la campaña
    campaign_metrics = calculate_campaign_metrics(campaign)
    
    # Obtener WorkDays de hoy para los empleados de la campaña
    today = timezone.now().date()
    campaign_workdays = WorkDay.objects.filter(
        employee__in=campaign_employees,
        date=today
    ).select_related('employee')
    
    # Preparar datos para cada empleado en la campaña
    employee_data = []
    for employee in campaign_employees:
        try:
            workday_today = campaign_workdays.get(employee=employee)
            current_session = workday_today.get_active_session()
            daily_stats = calculate_daily_stats(workday_today)
        except WorkDay.DoesNotExist:
            workday_today = None
            current_session = None
            daily_stats = None
        
        employee_data.append({
            'employee': employee,
            'workday': workday_today,
            'current_session': current_session,
            'formatted_session': workday_today.get_formatted_session() if workday_today else None,
            'daily_stats': daily_stats,
        })
    
    # Tendencias de asistencia de la campaña (últimos 7 días)
    attendance_trends = get_campaign_attendance_trends(campaign)
    
    context = {
        'campaign': campaign,
        'employee_data': employee_data,
        'total_employees': total_employees,
        'logged_in_count': logged_in_count,
        'campaign_metrics': campaign_metrics,
        'attendance_trends': attendance_trends,
        'today': today,
    }
    
    return render(request, 'management/campaign_detail.html', context)

def calculate_campaign_metrics(campaign):
    """Calcular métricas financieras y de performance de la campaña"""
    # Obtener workdays de los últimos 30 días para esta campaña
    thirty_days_ago = timezone.now().date() - timedelta(days=30)
    
    campaign_workdays = WorkDay.objects.filter(
        employee__current_campaign=campaign,
        date__gte=thirty_days_ago
    ).aggregate(
        total_hours=Sum('productive_hours'),
        total_work_days=Count('id'),
        avg_productivity=Avg('productive_hours')
    )
    
    # Calcular costos
    total_cost = 0
    if campaign.hour_rate and campaign_workdays['total_hours']:
        total_cost = float(campaign.hour_rate) * float(campaign_workdays['total_hours'])
    
    budget_utilization = 0
    if campaign.base_salary and total_cost > 0:
        budget_utilization = min((total_cost / float(campaign.base_salary)) * 100, 100)
    
    # Calcular completion rate basado en tiempo
    completion_percentage = 0
    if campaign.end_date and campaign.start_date:
        total_days = (campaign.end_date - campaign.start_date).days
        if total_days > 0:
            days_passed = (timezone.now().date() - campaign.start_date).days
            completion_percentage = min(100, max(0, (days_passed / total_days) * 100))
    
    return {
        'total_hours': campaign_workdays['total_hours'] or 0,
        'total_work_days': campaign_workdays['total_work_days'] or 0,
        'avg_productivity': round(campaign_workdays['avg_productivity'] or 0, 2),
        'total_cost': total_cost,
        'budget_utilization': round(budget_utilization, 1),
        'completion_percentage': round(completion_percentage, 1),
        'headcount_utilization': calculate_headcount_utilization(campaign),
    }

def get_campaign_attendance_trends(campaign):
    """Obtener tendencias de asistencia para la campaña"""
    trends = []
    for i in range(7):
        date = timezone.now().date() - timedelta(days=i)
        
        workdays_count = WorkDay.objects.filter(
            employee__current_campaign=campaign,
            date=date
        ).count()
        
        present_count = WorkDay.objects.filter(
            employee__current_campaign=campaign,
            date=date,
            check_in__isnull=False
        ).count()
        
        trends.append({
            'date': date,
            'workdays_count': workdays_count,
            'present_count': present_count,
            'attendance_rate': round((present_count / workdays_count * 100) if workdays_count > 0 else 0, 1),
        })
    
    return list(reversed(trends))

def calculate_headcount_utilization(campaign):
    """Calcular utilización de headcount para la campaña"""
    if campaign.head_count:
        current_count = Employee.objects.filter(current_campaign=campaign, is_active=True).count()
        utilization = (current_count / campaign.head_count) * 100
        return min(utilization, 100)
    return 0