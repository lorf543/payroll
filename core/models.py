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
    employee_code = models.CharField(max_length=20, unique=True)
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
        ('calculated', 'Calculated'),
        ('paid', 'Paid'),
        ('canceled', 'Canceled'),
    ]

    employee = models.ForeignKey(Employee, on_delete=models.CASCADE)
    period = models.ForeignKey(PayPeriod, on_delete=models.CASCADE)
    created_at = models.DateTimeField(auto_now_add=True)
    pay_date = models.DateField(blank=True, null=True)
    

    gross_salary = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    total_earnings = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    isr = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    afp = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    sfs = models.DecimalField(max_digits=12, decimal_places=2, default=0)

    
    total_deductions = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    net_salary = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='draft')
    comments = models.TextField(blank=True, null=True)
        
    def __str__(self):
        return f"Payroll {self.period} - {self.employee}"

    class Meta:
        verbose_name = "Payment"
        verbose_name_plural = "Payments"
        unique_together = ['employee', 'period']
    


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
    

