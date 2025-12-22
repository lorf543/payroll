
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.views.generic import TemplateView

from attendance.models import WorkDay
from django.utils import timezone
from datetime import timedelta
from django.db.models import (
    Count, Sum, Avg, Prefetch, Q, FloatField
)
from django.db.models.functions import Coalesce

from .models import Employee, Payment, Department, Position, Campaign
from workforce.models import Shift, EmployeeSchedule

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
        
        # Basic counts
        context.update({
            'total_employees': Employee.objects.filter(is_active=True).count(),
            'active_campaigns': Campaign.objects.filter(is_active=True).count(),
            'total_departments': Department.objects.count(),
            'logged_in_today': Employee.objects.filter(is_logged_in=True).count(),
        })
        
        # Enhanced metrics with scheduling data
        context.update({
            'avg_productivity': self.calculate_overall_productivity(),
            'productivity_percentage': self.calculate_productivity_percentage(),
            'campaigns_over_budget': self.get_campaigns_needing_attention(),
            'headcount_utilization_rate': self.calculate_overall_headcount_utilization(),
            'optimal_campaigns': self.get_optimal_campaigns_count(),
        })
        
        # NEW: Scheduling metrics
        today = timezone.now().date()
        context.update({
            'scheduled_today': self.get_scheduled_employees_count(today),
            'actual_attendance_today': self.get_actual_attendance_count(today),
            'schedule_compliance_rate': self.calculate_schedule_compliance(today),
            'active_shifts': Shift.objects.filter(is_active=True).count(),
            'employees_with_schedules': EmployeeSchedule.objects.filter(
                status__in=['published', 'active'],
                start_date__lte=today
            ).filter(
                Q(end_date__gte=today) | Q(end_date__isnull=True)
            ).values('employee').distinct().count(),
        })
        
        # Data sections
        context['campaigns_data'] = self.get_campaigns_data()
        context['department_stats'] = self.get_department_stats()
        context['attendance_trends'] = self.get_attendance_trends(selected_period)
        context['campaign_alerts'] = self.get_campaign_alerts()
        
        # NEW: Shift and schedule data
        context['shift_coverage'] = self.get_shift_coverage_today()
        context['schedule_compliance_trends'] = self.get_schedule_compliance_trends(selected_period)
        
        return context

    # ------------------------------------------------------------
    # NEW: SCHEDULING METRICS
    # ------------------------------------------------------------
    def get_scheduled_employees_count(self, date):
        """Count employees scheduled to work on a specific date"""
        weekday = date.weekday()
        day_fields = ['monday', 'tuesday', 'wednesday', 'thursday', 'friday', 'saturday', 'sunday']
        day_filter = {day_fields[weekday]: True}
        
        return EmployeeSchedule.objects.filter(
            status__in=['published', 'active'],
            start_date__lte=date,
            **day_filter
        ).filter(
            Q(end_date__gte=date) | Q(end_date__isnull=True)
        ).count()
    
    def get_actual_attendance_count(self, date):
        """Count employees who actually checked in"""
        return WorkDay.objects.filter(
            date=date,
            check_in__isnull=False
        ).count()
    
    def calculate_schedule_compliance(self, date):
        """Calculate percentage of scheduled employees who showed up"""
        scheduled = self.get_scheduled_employees_count(date)
        actual = self.get_actual_attendance_count(date)
        
        if scheduled > 0:
            return round((actual / scheduled) * 100, 1)
        return 0
    
    def get_shift_coverage_today(self):
        """Get coverage statistics for each shift today"""
        today = timezone.now().date()
        weekday = today.weekday()
        day_fields = ['monday', 'tuesday', 'wednesday', 'thursday', 'friday', 'saturday', 'sunday']
        day_filter = {day_fields[weekday]: True}
        
        shifts = Shift.objects.filter(is_active=True).annotate(
            scheduled_count=Count(
                'scheduled_employees',
                filter=Q(
                    scheduled_employees__status__in=['published', 'active'],
                    scheduled_employees__start_date__lte=today,
                    **{f'scheduled_employees__{day_fields[weekday]}': True}
                ) & (
                    Q(scheduled_employees__end_date__gte=today) | 
                    Q(scheduled_employees__end_date__isnull=True)
                )
            )
        )
        
        data = []
        for shift in shifts:
            # Get employees scheduled for this shift who checked in today
            scheduled_employees = Employee.objects.filter(
                schedules__shift=shift,
                schedules__status__in=['published', 'active'],
                schedules__start_date__lte=today,
                **{f'schedules__{day_fields[weekday]}': True}
            ).filter(
                Q(schedules__end_date__gte=today) | Q(schedules__end_date__isnull=True)
            ).distinct()
            
            checked_in = WorkDay.objects.filter(
                date=today,
                employee__in=scheduled_employees,
                check_in__isnull=False
            ).count()
            
            scheduled = shift.scheduled_count or 0
            coverage_rate = (checked_in / scheduled * 100) if scheduled > 0 else 0
            
            data.append({
                'shift': shift,
                'scheduled_count': scheduled,
                'checked_in_count': checked_in,
                'coverage_rate': round(coverage_rate, 1),
                'is_understaffed': coverage_rate < 80,
            })
        
        return sorted(data, key=lambda x: x['shift'].start_time)
    
    def get_schedule_compliance_trends(self, period='7days'):
        """Track schedule compliance over time"""
        today = timezone.now().date()
        trends = []
        
        # Determine date range
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
            
            scheduled = self.get_scheduled_employees_count(date)
            actual = self.get_actual_attendance_count(date)
            compliance = (actual / scheduled * 100) if scheduled > 0 else 0
            
            trends.append({
                'date': date,
                'scheduled_count': scheduled,
                'actual_count': actual,
                'compliance_rate': round(compliance, 1),
                'is_today': (date == today),
            })
        
        return trends

    # ------------------------------------------------------------
    # ENHANCED CAMPAIGNS DATA (with shift info)
    # ------------------------------------------------------------
    def get_campaigns_data(self):
        today = timezone.now().date()
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
            
            # NEW: Get scheduled count for today for this campaign
            scheduled_today = self.get_campaign_scheduled_count(c, today)
            
            data.append({
                'campaign': c,
                'employee_count': emp_count,
                'logged_in_count': logged,
                'attendance_rate': round(att_rate, 1),
                'total_work_hours': c.total_work_hours or 0,
                'avg_productivity': round(c.avg_productivity or 0, 2),
                'completion_percentage': self.calculate_campaign_completion(c),
                'headcount_utilization': self.calculate_headcount_utilization(c),
                'scheduled_today': scheduled_today,
            })
        
        return sorted(data, key=lambda x: x['employee_count'], reverse=True)
    
    def get_campaign_scheduled_count(self, campaign, date):
        """Get count of employees scheduled for a campaign on a specific date"""
        weekday = date.weekday()
        day_fields = ['monday', 'tuesday', 'wednesday', 'thursday', 'friday', 'saturday', 'sunday']
        day_filter = {day_fields[weekday]: True}
        
        return EmployeeSchedule.objects.filter(
            employee__current_campaign=campaign,
            status__in=['published', 'active'],
            start_date__lte=date,
            **day_filter
        ).filter(
            Q(end_date__gte=date) | Q(end_date__isnull=True)
        ).count()

    # ------------------------------------------------------------
    # ENHANCED DEPARTMENT STATS (with shift info)
    # ------------------------------------------------------------
    def get_department_stats(self):
        today = timezone.now().date()
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
            
            # NEW: Get scheduled count for today for this department
            scheduled_today = self.get_department_scheduled_count(d, today)
            
            data.append({
                'department': d,
                'employee_count': emp,
                'supervisor_count': d.supervisor_count or 0,
                'logged_in_count': logged,
                'attendance_rate': round(rate, 1),
                'avg_productivity': round(d.avg_productivity or 0, 1),
                'scheduled_today': scheduled_today,
            })
        
        return data
    
    def get_department_scheduled_count(self, department, date):
        """Get count of employees scheduled for a department on a specific date"""
        weekday = date.weekday()
        day_fields = ['monday', 'tuesday', 'wednesday', 'thursday', 'friday', 'saturday', 'sunday']
        day_filter = {day_fields[weekday]: True}
        
        return EmployeeSchedule.objects.filter(
            employee__department=department,
            status__in=['published', 'active'],
            start_date__lte=date,
            **day_filter
        ).filter(
            Q(end_date__gte=date) | Q(end_date__isnull=True)
        ).count()

    # ------------------------------------------------------------
    # ATTENDANCE TRENDS (unchanged)
    # ------------------------------------------------------------
    def get_attendance_trends(self, period='7days'):
        today = timezone.now().date()
        trends = []
        
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
    # CAMPAIGN ALERTS (unchanged)
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
    # METRICS (unchanged)
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