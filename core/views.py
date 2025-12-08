from django.contrib.sessions.models import Session

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import render, get_object_or_404, redirect, HttpResponse
from django.utils import timezone
from django.utils.timezone import now

from django.db.models import (
    Count, Sum, Avg, Prefetch, Q, FloatField
)
from django.db.models.functions import Coalesce
from django.db.models import ExpressionWrapper
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
    
    # ------------------------------------------------------------
    # ACCESS CONTROL
    # ------------------------------------------------------------
    def test_func(self):
        user_employee = getattr(self.request.user, 'employee', None)
        return user_employee and (
            user_employee.is_supervisor or 
            (user_employee.position and user_employee.position.name.lower() in ['ceo', 'manager', 'director', 'executive'])
        )
    
    # ------------------------------------------------------------
    # MAIN CONTEXT
    # ------------------------------------------------------------
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        selected_period = self.request.GET.get('period', '7days')
        context['selected_period'] = selected_period
        
        context.update({
            'total_employees': Employee.objects.filter(is_active=True).count(),
            'active_campaigns': Campaign.objects.filter(is_active=True).count(),
            'total_departments': Department.objects.count(),
            'logged_in_today': Employee.objects.filter(is_logged_in=True).count(),
        })
        
        context.update({
            'avg_productivity': self.calculate_overall_productivity(),
            'productivity_percentage': self.calculate_productivity_percentage(),
            'campaigns_over_budget': self.get_campaigns_needing_attention(),
            'headcount_utilization_rate': self.calculate_overall_headcount_utilization(),
            'optimal_campaigns': self.get_optimal_campaigns_count(),
        })
        
        context['campaigns_data'] = self.get_campaigns_data()
        context['department_stats'] = self.get_department_stats()
        context['attendance_trends'] = self.get_attendance_trends(selected_period)
        context['campaign_alerts'] = self.get_campaign_alerts()
        
        return context

    # ------------------------------------------------------------
    # CAMPAIGNS DATA
    # ------------------------------------------------------------
    def get_campaigns_data(self):
        campaigns = Campaign.objects.filter(is_active=True).prefetch_related(
            Prefetch(
                'active_employees',
                queryset=Employee.objects.filter(is_active=True).select_related('department')
            )
        ).annotate(
            employee_count=Count('active_employees', distinct=True),
            total_work_hours=Coalesce(Sum('active_employees__work_days__productive_hours'), 0.0, output_field=FloatField()),
            avg_productivity=Avg('active_employees__work_days__productive_hours', output_field=FloatField()),
        )
        
        data = []
        for c in campaigns:
            logged = c.active_employees.filter(is_logged_in=True).count()
            emp_count = c.employee_count or 0
            att_rate = (logged / emp_count * 100) if emp_count > 0 else 0
            
            data.append({
                'campaign': c,
                'employee_count': emp_count,
                'logged_in_count': logged,
                'attendance_rate': round(att_rate, 1),
                'total_work_hours': c.total_work_hours or 0,
                'avg_productivity': round(c.avg_productivity or 0, 2),
                'completion_percentage': self.calculate_campaign_completion(c),
                'headcount_utilization': self.calculate_headcount_utilization(c),
            })
        
        return sorted(data, key=lambda x: x['employee_count'], reverse=True)

    # ------------------------------------------------------------
    # DEPARTMENT STATS
    # ------------------------------------------------------------
    def get_department_stats(self):
        departments = Department.objects.annotate(
            employee_count=Count('employee', distinct=True),
            supervisor_count=Count('employee', filter=Q(employee__is_supervisor=True)),
            logged_in_count=Count('employee', filter=Q(employee__is_logged_in=True)),
            avg_productivity=Avg('employee__work_days__productive_hours', output_field=FloatField()),
        )
        
        data = []
        for d in departments:
            emp = d.employee_count or 0
            logged = d.logged_in_count or 0
            rate = (logged / emp * 100) if emp > 0 else 0
            
            data.append({
                'department': d,
                'employee_count': emp,
                'supervisor_count': d.supervisor_count or 0,
                'logged_in_count': logged,
                'attendance_rate': round(rate, 1),
                'avg_productivity': round(d.avg_productivity or 0, 1),
            })
        
        return data

    # ------------------------------------------------------------
    # ATTENDANCE TRENDS
    # ------------------------------------------------------------
    def get_attendance_trends(self, period='7days'):
        today = timezone.now().date()
        trends = []
        
        # -------------- PERÍODO ----------------
        if period == '30days':
            days_range = 30
        elif period == '90days':
            days_range = 90
        elif period == 'current_month':
            start_date = today.replace(day=1)
            days_range = (today - start_date).days + 1
        elif period == 'previous_month':
            first_day_current = today.replace(day=1)
            last_day_prev = first_day_current - timedelta(days=1)
            start_date = last_day_prev.replace(day=1)
            days_range = (last_day_prev - start_date).days + 1
        else:
            days_range = 7

        # -------------- LOOP ----------------
        for i in range(days_range):
            if period == 'current_month':
                date = today.replace(day=1) + timedelta(days=i)
                if date > today:
                    break
            elif period == 'previous_month':
                last_day_prev = today.replace(day=1) - timedelta(days=1)
                start_date = last_day_prev.replace(day=1)
                date = start_date + timedelta(days=i)
                if date > last_day_prev:
                    break
            else:
                date = today - timedelta(days=(days_range - 1 - i))

            wd_count = WorkDay.objects.filter(date=date).count()
            present = WorkDay.objects.filter(date=date, check_in__isnull=False).count()
            rate = (present / wd_count * 100) if wd_count > 0 else 0
            
            direction = "stable"
            if trends:
                prev = trends[-1]["present_count"]
                if present > prev:
                    direction = "up"
                elif present < prev:
                    direction = "down"

            trends.append({
                'date': date,
                'workdays_count': wd_count,
                'present_count': present,
                'attendance_rate': round(rate, 1),
                'trend_direction': direction,
                'is_today': (date == today),
            })
        
        return trends

    # ------------------------------------------------------------
    # CAMPAIGN ALERTS
    # ------------------------------------------------------------
    def get_campaign_alerts(self):
        alerts = []
        campaigns = Campaign.objects.filter(is_active=True).annotate(
            employee_count=Count('active_employees'),
            total_hours=Coalesce(Sum('active_employees__work_days__productive_hours'), 0.0, output_field=FloatField()),
        )
        
        for c in campaigns:
            emp = c.employee_count or 0
            avg = float(c.total_hours / emp) if emp > 0 else 0.0
            
            if c.head_count and emp < c.head_count * 0.7:
                alerts.append({
                    'type': 'warning',
                    'campaign': c,
                    'message': f'Low headcount: {emp}/{c.head_count}',
                    'icon': 'bi-people'
                })
            
            if avg < 4 and emp > 0:
                alerts.append({
                    'type': 'danger',
                    'campaign': c,
                    'message': f'Low productivity: {avg:.1f}h average',
                    'icon': 'bi-speedometer',
                })
        
        return alerts[:5]

    # ------------------------------------------------------------
    # METRICS (NO CAMBIO NOMBRES)
    # ------------------------------------------------------------
    def calculate_headcount_utilization(self, campaign):
        emp = campaign.employee_count or 0
        if campaign.head_count:
            return min((emp / campaign.head_count) * 100, 100)
        return 0

    def calculate_overall_headcount_utilization(self):
        total_hc = sum(c.head_count or 0 for c in Campaign.objects.filter(is_active=True))
        total_emp = Employee.objects.filter(is_active=True, current_campaign__isnull=False).count()
        if total_hc > 0:
            return min((total_emp / total_hc) * 100, 100)
        return 0

    def get_campaigns_needing_attention(self):
        count = 0
        camps = Campaign.objects.filter(is_active=True).annotate(
            employee_count=Count('active_employees'),
            total_hours=Coalesce(Sum('active_employees__work_days__productive_hours'), 0.0, output_field=FloatField()),
        )
        for c in camps:
            emp = c.employee_count or 0
            avg = float(c.total_hours / emp) if emp > 0 else 0.0
            
            if (c.head_count and emp < c.head_count * 0.7) or avg < 4:
                count += 1
        return count

    def get_optimal_campaigns_count(self):
        count = 0
        camps = Campaign.objects.filter(is_active=True).annotate(
            employee_count=Count('active_employees'),
            total_hours=Coalesce(Sum('active_employees__work_days__productive_hours'), 0.0, output_field=FloatField()),
        )
        for c in camps:
            emp = c.employee_count or 0
            avg = float(c.total_hours / emp) if emp > 0 else 0.0
            
            if c.head_count:
                util = (emp / c.head_count) * 100
                if util < 85 or util > 95:
                    continue
            
            if avg < 6:
                continue
            
            count += 1
        
        return count

    def calculate_overall_productivity(self):
        result = WorkDay.objects.aggregate(
            total=Coalesce(Sum('productive_hours'), 0.0, output_field=FloatField()),
            count=Count('id')
        )
        
        total_hours = result['total'] or 0.0
        total_workdays = result['count'] or 0
        
        if total_workdays > 0 and total_hours > 0:
            return float(total_hours) / float(total_workdays)
        return 0.0

    def calculate_productivity_percentage(self):
        avg = self.calculate_overall_productivity()
        return min((avg / 8) * 100, 100) if avg > 0 else 0

    def calculate_campaign_completion(self, campaign):
        if not campaign.start_date or not campaign.end_date:
            return 0
        
        total_days = (campaign.end_date - campaign.start_date).days
        if total_days <= 0:
            return 100
        
        days_passed = (timezone.now().date() - campaign.start_date).days
        return round(min(max(days_passed / total_days * 100, 0), 100), 1)

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
    
    # Obtener período seleccionado
    selected_period = request.GET.get('period', '7days')
    
    # Obtener empleados activos en esta campaña
    campaign_employees = Employee.objects.filter(
        current_campaign=campaign,
        is_active=True
    ).select_related('user', 'position', 'department', 'supervisor')
    
    # Estadísticas de la campaña
    total_employees = campaign_employees.count()
    logged_in_count = campaign_employees.filter(is_logged_in=True).count()
    
    # Métricas de productividad de la campaña
    campaign_metrics = calculate_campaign_productivity_metrics(campaign)
    
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
    
    # Tendencias de asistencia de la campaña con filtro de período
    attendance_trends = get_campaign_attendance_trends(campaign, selected_period)
    
    context = {
        'campaign': campaign,
        'employee_data': employee_data,
        'total_employees': total_employees,
        'logged_in_count': logged_in_count,
        'campaign_metrics': campaign_metrics,
        'attendance_trends': attendance_trends,
        'today': today,
        'selected_period': selected_period,
    }
    
    return render(request, 'management/campaign_detail.html', context)

def calculate_campaign_productivity_metrics(campaign):
    """Calcular métricas de productividad para la campaña"""
    # Obtener estadísticas de workdays de la campaña
    campaign_workdays = WorkDay.objects.filter(
        employee__current_campaign=campaign
    ).aggregate(
        total_hours=Sum('productive_hours'),
        total_work_days=Count('id'),
        avg_productivity=Avg('productive_hours')
    )
    
    # Calcular utilización de headcount
    headcount_utilization = 0
    if campaign.head_count and campaign.active_employees.count() > 0:
        headcount_utilization = min(
            (campaign.active_employees.count() / campaign.head_count) * 100, 
            100
        )
    
    # Calcular tasa de asistencia
    attendance_rate = 0
    total_employees = campaign.active_employees.count()
    if total_employees > 0:
        logged_in_count = campaign.active_employees.filter(is_logged_in=True).count()
        attendance_rate = (logged_in_count / total_employees) * 100
    
    # Calcular porcentaje de completitud
    completion_percentage = 0
    if campaign.end_date and campaign.start_date:
        total_days = (campaign.end_date - campaign.start_date).days
        if total_days > 0:
            days_passed = (timezone.now().date() - campaign.start_date).days
            completion_percentage = min(100, max(0, (days_passed / total_days) * 100))
    
    return {
        'total_hours': campaign_workdays['total_hours'] or 0,
        'total_work_days': campaign_workdays['total_work_days'] or 0,
        'avg_productivity': round(campaign_workdays['avg_productivity'] or 0, 1),
        'headcount_utilization': round(headcount_utilization, 1),
        'attendance_rate': round(attendance_rate, 1),
        'completion_percentage': round(completion_percentage, 1),
    }

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
    
    # Obtener período seleccionado
    selected_period = request.GET.get('period', '7days')
    
    # Obtener empleados activos en esta campaña
    campaign_employees = Employee.objects.filter(
        current_campaign=campaign,
        is_active=True
    ).select_related('user', 'position', 'department', 'supervisor')
    
    # Estadísticas de la campaña
    total_employees = campaign_employees.count()
    logged_in_count = campaign_employees.filter(is_logged_in=True).count()
    
    # Métricas de productividad de la campaña
    campaign_metrics = calculate_campaign_productivity_metrics(campaign)
    
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
    
    # Tendencias de asistencia de la campaña con filtro de período
    attendance_trends = get_campaign_attendance_trends_with_period(campaign, selected_period)
    
    context = {
        'campaign': campaign,
        'employee_data': employee_data,
        'total_employees': total_employees,
        'logged_in_count': logged_in_count,
        'campaign_metrics': campaign_metrics,
        'attendance_trends': attendance_trends,
        'today': today,
        'selected_period': selected_period,
    }
    
    return render(request, 'management/campaign_detail.html', context)

def calculate_campaign_productivity_metrics(campaign):
    """Calcular métricas de productividad para la campaña"""
    # Obtener estadísticas de workdays de la campaña
    campaign_workdays = WorkDay.objects.filter(
        employee__current_campaign=campaign
    ).aggregate(
        total_hours=Sum('productive_hours'),
        total_work_days=Count('id'),
        avg_productivity=Avg('productive_hours')
    )
    
    # Calcular utilización de headcount
    headcount_utilization = 0
    if campaign.head_count and campaign.active_employees.count() > 0:
        headcount_utilization = min(
            (campaign.active_employees.count() / campaign.head_count) * 100, 
            100
        )
    
    # Calcular tasa de asistencia
    attendance_rate = 0
    total_employees = campaign.active_employees.count()
    if total_employees > 0:
        logged_in_count = campaign.active_employees.filter(is_logged_in=True).count()
        attendance_rate = (logged_in_count / total_employees) * 100
    
    # Calcular porcentaje de completitud
    completion_percentage = 0
    if campaign.end_date and campaign.start_date:
        total_days = (campaign.end_date - campaign.start_date).days
        if total_days > 0:
            days_passed = (timezone.now().date() - campaign.start_date).days
            completion_percentage = min(100, max(0, (days_passed / total_days) * 100))
    
    return {
        'total_hours': campaign_workdays['total_hours'] or 0,
        'total_work_days': campaign_workdays['total_work_days'] or 0,
        'avg_productivity': round(campaign_workdays['avg_productivity'] or 0, 1),
        'headcount_utilization': round(headcount_utilization, 1),
        'attendance_rate': round(attendance_rate, 1),
        'completion_percentage': round(completion_percentage, 1),
    }

def get_campaign_attendance_trends_with_period(campaign, period='7days'):
    """Obtener tendencias de asistencia para la campaña con filtro de período"""
    today = timezone.now().date()
    trends = []
    
    # Definir rango de fechas según el período
    if period == '30days':
        days_range = 30
    elif period == '90days':
        days_range = 90
    elif period == 'current_month':
        # Primer día del mes actual hasta hoy
        start_date = today.replace(day=1)
        days_range = (today - start_date).days + 1
    elif period == 'previous_month':
        # Mes completo anterior
        first_day_current = today.replace(day=1)
        last_day_previous = first_day_current - timedelta(days=1)
        start_date = last_day_previous.replace(day=1)
        days_range = (last_day_previous - start_date).days + 1
    else:  # '7days' por defecto
        days_range = 7
    
    # Generar tendencias
    for i in range(days_range):
        if period == 'current_month':
            date = today.replace(day=1) + timedelta(days=i)
            if date > today:
                break
        elif period == 'previous_month':
            first_day_current = today.replace(day=1)
            last_day_previous = first_day_current - timedelta(days=1)
            start_date = last_day_previous.replace(day=1)
            date = start_date + timedelta(days=i)
            if date > last_day_previous:
                break
        else:
            date = today - timedelta(days=(days_range - 1 - i))
        
        # Contar workdays para empleados de esta campaña
        workdays_count = WorkDay.objects.filter(
            employee__current_campaign=campaign,
            date=date
        ).count()
        
        present_count = WorkDay.objects.filter(
            employee__current_campaign=campaign,
            date=date,
            check_in__isnull=False
        ).count()
        
        # Calcular tendencia
        trend_direction = 'stable'
        if len(trends) > 0:
            prev_trend = trends[-1]
            if present_count > prev_trend['present_count']:
                trend_direction = 'up'
            elif present_count < prev_trend['present_count']:
                trend_direction = 'down'
        
        trends.append({
            'date': date,
            'workdays_count': workdays_count,
            'present_count': present_count,
            'attendance_rate': round((present_count / workdays_count * 100) if workdays_count > 0 else 0, 1),
            'trend_direction': trend_direction,
            'is_today': date == today,
        })
    
    return trends


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