# payroll/views.py
from django.db.models import Sum, Q, Count
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render, get_object_or_404, HttpResponse
from django.utils import timezone
from datetime import timedelta
from decimal import Decimal
from django.db import IntegrityError
from datetime import datetime
from django.http import JsonResponse
from collections import defaultdict
from django.views.generic import ListView, DetailView, UpdateView
from django.contrib.auth.mixins import LoginRequiredMixin

from core.models import Employee, Payment, PaymentConcept,PaymentDetail, PayPeriod, Campaign
from attendance.models import WorkDay

from decimal import Decimal, InvalidOperation

from django import forms
from django.views.generic.edit import FormView

class PaymentRejectionForm(forms.Form):
    rejection_reason = forms.CharField(
        label='Reason for Rejection',
        widget=forms.Textarea(attrs={
            'rows': 4,
            'placeholder': 'Please explain why you are rejecting this payment...',
            'class': 'form-control'
        }),
        required=True,
        max_length=500
    )

def to_decimal(value, default=0):
    """Safely convert any value to Decimal"""
    if value is None:
        return Decimal(str(default))
    if isinstance(value, Decimal):
        return value
    try:
        return Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError):
        return Decimal(str(default))

def to_float(value, default=0):
    """Safely convert any value to float"""
    if value is None:
        return float(default)
    if isinstance(value, (int, float)):
        return float(value)
    try:
        return float(value)
    except (TypeError, ValueError):
        return float(default)


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
        'campaigns': "Campaign.objects.all()"
    }
    
    return render(request, 'nomina/dashboard.html', context)


@login_required
def create_pay_period(request):
    """Create new pay period and automatically create payment records"""
    if request.method == 'POST':
        try:
            # Get form data
            name = request.POST.get('name', '').strip()
            start_date_str = request.POST.get('start_date')
            end_date_str = request.POST.get('end_date')
            pay_date_str = request.POST.get('pay_date')
            frequency = request.POST.get('frequency')

            # Validate required fields
            if not all([name, start_date_str, end_date_str, pay_date_str, frequency]):
                messages.error(request, "All fields are required.")
                return render(request, 'nomina/create_period.html')

            # Convert dates
            try:
                start_date = datetime.strptime(start_date_str, '%Y-%m-%d').date()
                end_date = datetime.strptime(end_date_str, '%Y-%m-%d').date()
                pay_date = datetime.strptime(pay_date_str, '%Y-%m-%d').date()
            except ValueError:
                messages.error(request, "Invalid date format. Please use YYYY-MM-DD format.")
                return render(request, 'nomina/create_period.html')

            # Create period
            period = PayPeriod.objects.create(
                name=name,
                start_date=start_date,
                end_date=end_date,
                pay_date=pay_date,
                frequency=frequency
            )

            # Get active employees
            active_employees = Employee.objects.filter(is_active=True)
            active_count = active_employees.count()
            payments_created = 0

            # Create payment records for each employee
            for employee in active_employees:
                # Calculate total from workdays
                workdays = WorkDay.objects.filter(
                    employee=employee,
                    date__range=[start_date, end_date]
                )
                
                total_gross = Decimal('0.00')
                for workday in workdays:
                    if workday.total_pay == 0 and workday.productive_hours > 0:
                        workday.calculate_pay()
                        workday.save()
                    total_gross += Decimal(str(workday.total_pay))
                
                # Only create payment if there are workdays OR if employee has fixed salary
                if workdays.exists() or (employee.fixed_rate and employee.custom_base_salary):
                    if employee.fixed_rate and employee.custom_base_salary:
                        # Use fixed salary if employee has fixed rate
                        total_gross = employee.custom_base_salary
                    
                    # Calculate net salary
                    employee_net = calculate_employee_net_salary(employee, total_gross)
                    
                    # Create payment record with status 'pending_employee'
                    payment = Payment.objects.create(
                        employee=employee,
                        period=period,
                        gross_salary=total_gross,
                        net_salary=employee_net,
                        pay_date=pay_date,
                        status='pending_employee'  # IMPORTANTE: para que el empleado lo vea
                    )
                    
                    # Calculate and update deductions
                    payment.calculate_totals()
                    payment.save()
                    
                    payments_created += 1

            # Find existing workdays in this range
            workdays_count = WorkDay.objects.filter(
                date__range=[start_date, end_date],
                employee__in=active_employees
            ).count()

            messages.success(
                request, 
                f"Pay period '{period.name}' created successfully! "
                f"Created {payments_created} payment records for employee review. "
                f"Found {workdays_count} work days for {active_count} active employees."
            )

            return redirect('nomina:review_pay_period', period_id=period.id)

        except IntegrityError:
            messages.error(request, "A pay period with similar dates already exists.")
        except Exception as e:
            messages.error(request, f"Error creating pay period: {str(e)}")
            import logging
            logger = logging.getLogger(__name__)
            logger.error(f"Error creating pay period: {str(e)}", exc_info=True)

    context = {
        'today': timezone.now().date(),
    }
    return render(request, 'nomina/create_period.html', context)



@login_required
def review_pay_period(request, period_id):
    """Review and manage a complete pay period"""
    period = get_object_or_404(PayPeriod, id=period_id)
    
    # Get all active employees
    active_employees = Employee.objects.filter(is_active=True)
    
    # Prepare data for each employee
    employees_data = []
    total_gross = Decimal('0.00')
    total_net = Decimal('0.00')
    
    for employee in active_employees:
        # Get employee workdays in the period
        workdays = WorkDay.objects.filter(
            employee=employee,
            date__range=[period.start_date, period.end_date]
        ).order_by('date')
        
        # Calculate totals
        workdays_data = []
        employee_gross = Decimal('0.00')
        employee_approved = True
        
        for workday in workdays:
            # Calculate pay if not calculated
            if workday.total_pay == 0 and workday.productive_hours > 0:
                workday.calculate_pay()
                workday.save()
            
            workdays_data.append(workday)
            employee_gross += Decimal(str(workday.total_pay))
            
            # Check if all are approved
            if not workday.is_approved:
                employee_approved = False
        
        # Calculate deductions and net
        employee_net = calculate_employee_net_salary(employee, employee_gross)
        
        # Convert to float for template display
        employees_data.append({
            'employee': employee,
            'workdays': workdays_data,
            'workdays_count': len(workdays_data),
            'approved_count': sum(1 for w in workdays_data if w.is_approved),
            'total_gross': float(employee_gross),  # Convert to float for template
            'total_net': float(employee_net),      # Convert to float for template
            'fully_approved': employee_approved,
            'has_workdays': len(workdays_data) > 0,
        })
        
        total_gross += employee_gross
        total_net += employee_net
    
    # Period statistics
    all_workdays = WorkDay.objects.filter(
        date__range=[period.start_date, period.end_date],
        employee__is_active=True
    )
    
    # Group employees by campaign
    grouped_employees = {}
    
    for emp_data in employees_data:
        employee = emp_data["employee"]
        campaign_name = (
            employee.current_campaign.name
            if employee.current_campaign
            else "No Campaign"
        )
        
        if campaign_name not in grouped_employees:
            grouped_employees[campaign_name] = []
        
        grouped_employees[campaign_name].append(emp_data)
    
    # Get all campaigns for the tabs
    campaigns = Campaign.objects.all()

    stats = {
        'total_employees': active_employees.count(),
        'employees_with_workdays': sum(1 for ed in employees_data if ed['has_workdays']),
        'total_workdays': all_workdays.count(),
        'approved_workdays': all_workdays.filter(is_approved=True).count(),
        'total_gross': float(total_gross),  # Convert to float for template
        'total_net': float(total_net),      # Convert to float for template
        'all_approved': all(ed['fully_approved'] for ed in employees_data if ed['has_workdays']),
    }
    
    context = {
        'period': period,
        'stats': stats,
        'campaigns': campaigns,
        'grouped_employees': grouped_employees,
        'employees_data': employees_data,  # También pasamos esto por si acaso
    }
    
    return render(request, 'nomina/period_review.html', context)


def calculate_employee_net_salary(employee, gross_salary):
    """Calculate net salary with deductions"""
    from decimal import Decimal
    
    # Convertir gross_salary a Decimal si es necesario
    if isinstance(gross_salary, Decimal):
        gross = gross_salary
    else:
        gross = Decimal(str(gross_salary))
    
    if gross == Decimal('0.00'):
        return Decimal('0.00')
    
    # Usar Decimal para todos los cálculos
    afp = gross * Decimal('0.0287')  # AFP (2.87%)
    sfs = gross * Decimal('0.0304')  # SFS (3.04%)
    isr = calculate_isr(gross)       # ISR
    
    total_deductions = afp + sfs + isr
    return gross - total_deductions

def calculate_isr(gross_salary):
    """Simplified ISR calculation with Decimal"""
    from decimal import Decimal
    
    # Convertir a Decimal si es necesario
    if isinstance(gross_salary, Decimal):
        gross = gross_salary
    else:
        gross = Decimal(str(gross_salary))
    
    # Límites en Decimal
    exemption_limit = Decimal('416220.00')
    bracket_limit = Decimal('624329.00')
    
    if gross <= exemption_limit:
        return Decimal('0.00')
    elif gross <= bracket_limit:
        return (gross - exemption_limit) * Decimal('0.15')
    else:
        excess = gross - bracket_limit
        base_bracket = bracket_limit - exemption_limit
        return (base_bracket * Decimal('0.15')) + (excess * Decimal('0.20'))

@login_required
def approve_all_workdays(request, period_id):
    """Approve all workdays in the period"""
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
    
    messages.success(request, f"{approved_count} work days approved.")
    return redirect('nomina:review_period', period_id=period_id)

@login_required
def generate_payroll(request, period_id):
    """Generate complete payroll for the period"""
    period = get_object_or_404(PayPeriod, id=period_id)
    
    # Verify all workdays are approved
    unapproved_count = WorkDay.objects.filter(
        date__range=[period.start_date, period.end_date],
        employee__is_active=True,
        is_approved=False
    ).count()
    
    if unapproved_count > 0:
        messages.warning(request, 
            f"There are {unapproved_count} unapproved work days. "
            f"Please approve all days before generating payroll."
        )
        return redirect('nomina:review_period', period_id=period_id)
    
    # Generate payments for each employee
    created_count = 0
    active_employees = Employee.objects.filter(is_active=True)
    
    for employee in active_employees:
        workdays = WorkDay.objects.filter(
            employee=employee,
            date__range=[period.start_date, period.end_date],
            is_approved=True
        )
        
        # Use Decimal for calculation
        total_gross = Decimal('0.00')
        for workday in workdays:
            total_gross += Decimal(str(workday.total_pay))
        
        if total_gross > Decimal('0.00'):
            # Create or update payment
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
    
    # Calculate total using aggregation
    from django.db.models import Sum
    total_period_result = Payment.objects.filter(period=period).aggregate(
        total=Sum('gross_salary')
    )
    total_period = total_period_result['total'] or Decimal('0.00')
    
    messages.success(request, 
        f"Payroll generated successfully for {created_count} employees. "
        f"Period total: ${float(total_period):,.2f}"  # Convert to float for display
    )
    
    return redirect('nomina:review_period', period_id=period_id)

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



class EmployeePaymentListView(LoginRequiredMixin, ListView):
    model = Payment
    template_name = 'nomina/employee_payments.html'
    context_object_name = 'payments'
    paginate_by = 10
    
    def get_queryset(self):
        # Solo mostrar pagos del empleado actual
        employee = get_object_or_404(Employee, user=self.request.user)
        return Payment.objects.filter(employee=employee).order_by('-created_at')
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        employee = get_object_or_404(Employee, user=self.request.user)
        
        # Estadísticas para el dashboard
        context['total_payments'] = self.get_queryset().count()
        context['pending_approval'] = self.get_queryset().filter(
            status='pending_employee'
        ).count()
        context['approved_payments'] = self.get_queryset().filter(
            status='approved_by_employee'
        ).count()
        
        return context

class PaymentDetailView(LoginRequiredMixin, DetailView):
    model = Payment
    template_name = 'nomina/payment_detail.html'
    context_object_name = 'payment'
    
    def get_queryset(self):
        # Employees can only see their own payments
        employee = get_object_or_404(Employee, user=self.request.user)
        return Payment.objects.filter(employee=employee)
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        payment = self.get_object()
        
        # Calculate detailed breakdown
        context['earnings_breakdown'] = self.get_earnings_breakdown(payment)
        context['deductions_breakdown'] = self.get_deductions_breakdown(payment)
        context['can_approve'] = payment.status == 'pending_employee'
        
        return context
    
    def get_earnings_breakdown(self, payment):
        """Earnings breakdown"""
        earnings = [
            {
                'name': 'Base Salary',
                'amount': payment.gross_salary,
                'type': 'salary'
            }
        ]
        return earnings
    
    def get_deductions_breakdown(self, payment):
        """Deductions breakdown"""
        deductions = [
            {
                'name': 'AFP (2.87%)',
                'amount': payment.afp,
                'type': 'afp'
            },
            {
                'name': 'SFS (3.04%)',
                'amount': payment.sfs,
                'type': 'sfs'
            },
            {
                'name': 'ISR',
                'amount': payment.isr,
                'type': 'isr'
            }
        ]
        return deductions

class PaymentApprovalView(LoginRequiredMixin, UpdateView):
    model = Payment
    template_name = 'nomina/payment_approval.html'
    fields = []  # No necesitamos campos del formulario para aprobación
    
    def get_queryset(self):
        employee = get_object_or_404(Employee, user=self.request.user)
        return Payment.objects.filter(employee=employee, status='pending_employee')
    
    def form_valid(self, form):
        payment = form.save(commit=False)
        payment.approve_by_employee()
        
        messages.success(
            self.request, 
            f'Payment for period {payment.period} has been approved successfully!'
        )
        
        return redirect('employee_payments')

class PaymentRejectionView(LoginRequiredMixin, FormView):
    template_name = 'nomina/payment_rejection.html'
    form_class = PaymentRejectionForm
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['payment'] = get_object_or_404(
            Payment, 
            id=self.kwargs['pk'],
            employee__user=self.request.user,
            status='pending_employee'
        )
        return context
    
    def form_valid(self, form):
        payment = get_object_or_404(
            Payment, 
            id=self.kwargs['pk'],
            employee__user=self.request.user,
            status='pending_employee'
        )
        
        reason = form.cleaned_data['rejection_reason']
        payment.reject_by_employee(reason)
        
        messages.warning(
            self.request, 
            f'Payment for period {payment.period} has been rejected. HR will review your concerns.'
        )
        
        return redirect('employee_payments')