# models.py core 
from django.db import models
from django.contrib.auth.models import User
from django.core.validators import MinValueValidator, MaxValueValidator

from django.db.models.signals import pre_save
from django.dispatch import receiver
from decimal import Decimal
from django.utils import timezone
import uuid


class Campaign(models.Model):
    name = models.CharField(max_length=100)
    client_name = models.CharField(max_length=100, blank=True, null=True)
    description = models.TextField(blank=True, null=True)
    start_date = models.DateField()
    end_date = models.DateField(null=True, blank=True)
    is_active = models.BooleanField(default=True)

    break_duraction = models.IntegerField(null=True, blank=True)
    lunch = models.IntegerField(null=True, blank=True)

    head_count = models.IntegerField(null=True, blank=True)
    hours_required = models.IntegerField(null=True, blank=True)
    shutdown_time = models.TimeField(null=True, blank=True)

    hour_rate = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    base_salary = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)

    BONUS_TYPE_CHOICES = [
        ('percent', 'Percentage'),
        ('fixed', 'Fixed Amount'),
    ]
    bonus_type = models.CharField(max_length=10, choices=BONUS_TYPE_CHOICES, blank=True, null=True)
    bonus_value = models.DecimalField(max_digits=10, decimal_places=2, blank=True, null=True)

    def __str__(self):
        return self.name

    class Meta:
        verbose_name = "Campaign"
        verbose_name_plural = "Campaigns"

class Department(models.Model):
    name = models.CharField(max_length=100)
    description = models.TextField(blank=True, null=True)
    annual_budget = models.DecimalField(
        max_digits=12, decimal_places=2, default=0,
        validators=[MinValueValidator(0)]
    )

    def __str__(self):
        return self.name

    class Meta:
        verbose_name = "Department"
        verbose_name_plural = "Departments"
        ordering = ["name"]

class Position(models.Model):
    CONTRACT_TYPE_CHOICES = [
        ('full_time', 'Full Time'),
        ('part_time', 'Part Time'), 
        ('temporary', 'Temporary'),
        ('intern', 'Intern'),
    ]

    name = models.CharField(max_length=100)
    description = models.TextField(blank=True, null=True)
    hour_rate = models.DecimalField(max_digits=10, decimal_places=2,blank=True, null=True)
    base_salary = models.DecimalField(max_digits=10, decimal_places=2,blank=True, null=True)
    contract_type = models.CharField(max_length=20, choices=CONTRACT_TYPE_CHOICES, default='full_time')
    benefits = models.TextField(blank=True, null=True)

    def __str__(self):
        return f"{self.name}"

    class Meta:
        verbose_name = "Position"
        verbose_name_plural = "Positions"


class Employee(models.Model):
    GENDER_CHOICES = [
        ('M', 'Male'),
        ('F', 'Female'),
        ('O', 'Other'),
    ]

    MARITAL_STATUS_CHOICES = [
        ('single', 'Single'),
        ('married', 'Married'),
        ('divorced', 'Divorced'),
        ('widowed', 'Widowed'),
        ('common_law', 'Common Law'),
    ]

    supervisor = models.ForeignKey(
        'self',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='team_members',
        help_text="Direct supervisor"
    )

    is_supervisor = models.BooleanField(default=False)
    is_it = models.BooleanField(default=False)

    position = models.ForeignKey(Position, on_delete=models.SET_NULL, null=True)
    department = models.ForeignKey(Department, on_delete=models.CASCADE, null=True)

    campaigns = models.ManyToManyField('Campaign', related_name='employees', blank=True)
    current_campaign = models.ForeignKey(
        'Campaign',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='active_employees',
        help_text='Campaign where the employee is currently active.'
    )

    is_logged_in = models.BooleanField(default=False)
    last_login = models.DateTimeField(null=True, blank=True)
    last_logout = models.DateTimeField(null=True, blank=True)


    user = models.OneToOneField(User, on_delete=models.CASCADE, null=True, blank=True)
    employee_code = models.CharField(max_length=20, unique=True, null=True, blank=True)
    identification = models.CharField(max_length=50)

    #personal info
    hire_date = models.DateField(blank=True, null=True)
    birth_date = models.DateField(blank=True, null=True)
    gender = models.CharField(max_length=1, choices=GENDER_CHOICES)
    marital_status = models.CharField(max_length=20, choices=MARITAL_STATUS_CHOICES, blank=True, null=True)
    phone = models.CharField(max_length=20, blank=True, null=True)
    address = models.TextField(blank=True, null=True)
    city = models.CharField(max_length=100, blank=True, null=True)
    country = models.CharField(max_length=100, blank=True, null=True)

    is_active = models.BooleanField(default=True)
    
    #Profile
    bio = models.TextField(blank=True)
    education = models.CharField(max_length=50, null=True, blank=True)
    email = models.EmailField(max_length=60, null=True, blank=True)
    skills = models.CharField(max_length=250, null=True, blank=True)

    
    #payment info
    fixed_rate = models.BooleanField(default=False)
    custom_base_salary = models.DecimalField(max_digits=10, decimal_places=2,blank=True, null=True)

    # Banking info for payroll
    bank_name = models.CharField(max_length=100, blank=True, null=True)
    bank_account = models.CharField(max_length=50, blank=True, null=True)

    def __str__(self):
        return f"{self.user.get_full_name() if self.user else 'No user'} - {self.employee_code}"

    @property
    def full_name(self):
        if self.user:
            return self.user.get_full_name()
        return "Employee without user"
    
    @property
    def skills_list(self):
        if not self.skills:
            return ""
        return ', '.join(skill.strip() for skill in self.skills.split(',') if skill.strip())

    @property
    def age(self):
        from datetime import date
        return date.today().year - self.birth_date.year
    
    class Meta:
        verbose_name = "Employee"
        verbose_name_plural = "Employees"

    @property
    def has_registered(self):
        """Check if user has registered (has a linked User account)"""
        return self.user is not None
    
    @property
    def registration_status(self):
        """Get comprehensive registration status"""
        if self.user and self.profile_completed:
            return "Completed"
        elif self.user and not self.profile_completed:
            return "Registered - Profile Pending"
        else:
            return "Invitation Sent"
        
    def save(self, *args, **kwargs):
        # Ensure we have an employee code before saving
        if not self.employee_code:
            # This will be handled by the pre_save signal, but as backup:
            timestamp = timezone.now().strftime('%y%m%d')
            random_part = str(uuid.uuid4().hex[:6].upper())
            self.employee_code = f"EMP{timestamp}{random_part}"
        
        if not self.identification:
            self.identification = self.employee_code
            
        super().save(*args, **kwargs)


class RelatedFamily(models.Model):
    employee = models.ForeignKey(Employee, on_delete=models.CASCADE)

    name = models.CharField(max_length=50, null=True, blank=True)
    phone = models.CharField(max_length=50, null=True, blank=True)
    relationship = models.CharField(max_length=50, null=True, blank=True)

    created_by = models.ForeignKey(User, on_delete=models.CASCADE)
    created_at = models.DateTimeField(auto_now_add=True)

    def __stre__(self):
        return f'{self.employee.full_name} - {self.name}'



class BulkInvitation(models.Model):
    created_by = models.ForeignKey(User, on_delete=models.CASCADE)
    created_at = models.DateTimeField(auto_now_add=True)
    emails_sent = models.PositiveIntegerField(default=0)
    campaign = models.ForeignKey(Campaign, on_delete=models.CASCADE)
    
    def __str__(self):
        return f"Bulk invitation {self.id} - {self.campaign.name}"


class PaymentConcept(models.Model):
    TYPE_CHOICES = [
        ('earning', 'Earning'),
        ('deduction', 'Deduction'),
    ]

    CODE_CHOICES = [
        ('salary', 'Salary'),
        ('overtime', 'Overtime'),
        ('bonus', 'Bonus'),
        ('commission', 'Commission'),
        ('isr', 'ISR'),
        ('afp', 'AFP'),
        ('sfs', 'SFS'),
        ('loan', 'Loan'),
        ('other', 'Other'),
    ]

    name = models.CharField(max_length=100)
    type = models.CharField(max_length=20, choices=TYPE_CHOICES)
    code = models.CharField(max_length=20, choices=CODE_CHOICES, default='other')
    description = models.TextField(blank=True, null=True)
    fixed_amount = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    percentage = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        null=True,
        blank=True,
        validators=[MinValueValidator(0), MaxValueValidator(100)]
    )
    taxable = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)

    def __str__(self):
        return f"{self.get_type_display()}: {self.name}"

    class Meta:
        verbose_name = "Payment Concept"
        verbose_name_plural = "Payment Concepts"


class PayPeriod(models.Model):
    FREQUENCY_CHOICES = [
        ('weekly', 'Weekly'),
        ('biweekly', 'Biweekly'),
        ('monthly', 'Monthly'),
    ]

    name = models.CharField(max_length=100)
    start_date = models.DateField()
    end_date = models.DateField()
    pay_date = models.DateField()
    frequency = models.CharField(max_length=20, choices=FREQUENCY_CHOICES)
    is_closed = models.BooleanField(default=False)
    
    def __str__(self):
        return f"{self.name} ({self.start_date} - {self.end_date})"

    class Meta:
        verbose_name = "Pay Period"
        verbose_name_plural = "Pay Periods"
        ordering = ['-start_date']



class Payment(models.Model):
    STATUS_CHOICES = [
        ('draft', 'Draft'),
        ('pending_employee', 'Pending Employee Approval'),
        ('approved_by_employee', 'Approved by Employee'),
        ('rejected_by_employee', 'Rejected by Employee'),
        ('calculated', 'Calculated'),
        ('pending_payment', 'Pending Payment'),
        ('paid', 'Paid'),
        ('canceled', 'Canceled'),
    ]

    employee = models.ForeignKey(Employee, on_delete=models.CASCADE)
    period = models.ForeignKey(PayPeriod, on_delete=models.CASCADE)
    created_at = models.DateTimeField(auto_now_add=True)
    pay_date = models.DateField(blank=True, null=True)
    
    # Salary breakdown
    gross_salary = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    total_earnings = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    
    # Deductions
    isr = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    afp = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    sfs = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    total_deductions = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    net_salary = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    
    status = models.CharField(max_length=25, choices=STATUS_CHOICES, default='draft')
    comments = models.TextField(blank=True, null=True)
    
    # Employee approval tracking
    employee_approved = models.BooleanField(default=False)
    employee_approved_at = models.DateTimeField(null=True, blank=True)
    employee_rejection_reason = models.TextField(blank=True, null=True)
    
    # Payroll admin tracking
    calculated_by = models.ForeignKey(
        User, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True,
        related_name='calculated_payments'
    )
    calculated_at = models.DateTimeField(null=True, blank=True)
    
    processed_by = models.ForeignKey(
        User, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True,
        related_name='processed_payments'
    )
    processed_at = models.DateTimeField(null=True, blank=True)
    
    # Payment proof
    payment_reference = models.CharField(max_length=100, blank=True, null=True)
    payment_proof = models.FileField(upload_to='payment_proofs/', blank=True, null=True)
        
    def __str__(self):
        return f"Payment {self.period} - {self.employee}"

    class Meta:
        verbose_name = "Payment"
        verbose_name_plural = "Payments"
        unique_together = ['employee', 'period']
        ordering = ['-created_at']
    
    def calculate_totals(self):
        """Calculate all payment totals"""
        from decimal import Decimal
        
        if not self.gross_salary:
            return
        
        # Constants
        AFP_RATE = Decimal('0.0287')
        SFS_RATE = Decimal('0.0304')
        
        # Calculate mandatory deductions
        self.afp = self.gross_salary * AFP_RATE
        self.sfs = self.gross_salary * SFS_RATE
        
        # Calculate ISR
        self.isr = self.calculate_isr()
        
        # Get additional earnings/deductions from details
        additional_earnings = sum(
            detail.amount for detail in self.details.filter(concept__type='earning')
        )
        additional_deductions = sum(
            detail.amount for detail in self.details.filter(concept__type='deduction')
        )
        
        # Update totals
        self.total_earnings = self.gross_salary + Decimal(str(additional_earnings))
        self.total_deductions = self.afp + self.sfs + self.isr + Decimal(str(additional_deductions))
        self.net_salary = self.total_earnings - self.total_deductions
    
    def calculate_isr(self):
        """Calculate ISR based on gross salary"""
        from decimal import Decimal
        
        gross = Decimal(str(self.gross_salary))
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
    
    def approve_by_employee(self):
        """Employee approves their payment"""
        from django.utils import timezone
        self.employee_approved = True
        self.employee_approved_at = timezone.now()
        self.status = 'approved_by_employee'
        self.save()
    
    def reject_by_employee(self, reason):
        """Employee rejects their payment"""
        self.employee_approved = False
        self.status = 'rejected_by_employee'
        self.employee_rejection_reason = reason
        self.save()
    
    def mark_as_paid(self, processed_by, payment_reference=None):
        """Mark payment as paid"""
        from django.utils import timezone
        self.status = 'paid'
        self.processed_by = processed_by
        self.processed_at = timezone.now()
        if payment_reference:
            self.payment_reference = payment_reference
        self.save()
    

class PaymentDetail(models.Model):
    """Detalles de ganancias y deducciones para cada pago"""
    payment = models.ForeignKey(Payment, on_delete=models.CASCADE, related_name='details')
    concept = models.ForeignKey(PaymentConcept, on_delete=models.CASCADE)
    quantity = models.DecimalField(max_digits=10, decimal_places=2, default=1)
    rate = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    comments = models.TextField(blank=True, null=True)
    
    def __str__(self):
        return f"{self.concept.name} - {self.amount}"

    class Meta:
        verbose_name = "Payment Detail"
        verbose_name_plural = "Payment Details"


@receiver(pre_save, sender=Payment)
def calculate_totals_signal(sender, instance, **kwargs):
    if not instance.gross_salary:
        return

    # Constants
    AFP_RATE = Decimal('0.0287')  # 2.87%
    SFS_RATE = Decimal('0.0304')  # 3.04%

    # Calculate mandatory deductions
    instance.afp = instance.gross_salary * AFP_RATE
    instance.sfs = instance.gross_salary * SFS_RATE

    # No details → so no additional earnings/deductions
    additional_earnings = Decimal('0')
    additional_deductions = Decimal('0')

    # Update totals
    instance.total_earnings = additional_earnings
    instance.total_deductions = instance.afp + instance.sfs + additional_deductions
    instance.net_salary = instance.gross_salary + additional_earnings - instance.total_deductions
    

