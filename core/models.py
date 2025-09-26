# models.py
from django.db import models
from django.contrib.auth.models import User
from django.core.validators import MinValueValidator, MaxValueValidator
from decimal import Decimal
from django.db.models.signals import post_save
from django.dispatch import receiver


class Department(models.Model):
    name = models.CharField(max_length=100)
    description = models.TextField(blank=True, null=True)
    annual_budget = models.DecimalField(max_digits=12, decimal_places=2, default=0)

    def __str__(self):
        return self.name

    class Meta:
        verbose_name = "Department"
        verbose_name_plural = "Departments"


class Position(models.Model):
    CONTRACT_TYPE_CHOICES = [
        ('full_time', 'Full Time'),
        ('part_time', 'Part Time'),
        ('temporary', 'Temporary'),
        ('intern', 'Intern'),
    ]

    name = models.CharField(max_length=100)
    department = models.ForeignKey(Department, on_delete=models.CASCADE)
    description = models.TextField(blank=True, null=True)
    base_salary = models.DecimalField(max_digits=10, decimal_places=2)
    contract_type = models.CharField(max_length=20, choices=CONTRACT_TYPE_CHOICES, default='full_time')
    benefits = models.TextField(blank=True, null=True)

    def __str__(self):
        return f"{self.name} - {self.department.name}"

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

    user = models.OneToOneField(User, on_delete=models.CASCADE, null=True, blank=True)
    employee_code = models.CharField(max_length=20, unique=True)
    position = models.ForeignKey(Position, on_delete=models.SET_NULL, null=True)
    department = models.ForeignKey(Department, on_delete=models.SET_NULL, null=True)
    hire_date = models.DateField()
    birth_date = models.DateField()
    gender = models.CharField(max_length=1, choices=GENDER_CHOICES)
    marital_status = models.CharField(max_length=20, choices=MARITAL_STATUS_CHOICES, blank=True, null=True)
    phone = models.CharField(max_length=20, blank=True, null=True)
    address = models.TextField(blank=True, null=True)
    city = models.CharField(max_length=100, blank=True, null=True)
    country = models.CharField(max_length=100, blank=True, null=True)
    postal_code = models.CharField(max_length=10, blank=True, null=True)
    is_active = models.BooleanField(default=True)

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

    class Meta:
        verbose_name = "Employee"
        verbose_name_plural = "Employees"


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
    pay_date = models.DateField()
    gross_salary = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    total_earnings = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    isr = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    afp = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    sfs = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    total_deductions = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    net_salary = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='draft')
    comments = models.TextField(blank=True, null=True)

    def calculate_totals(self):
        details = self.details.all()
        self.total_earnings = sum([d.amount for d in details if d.concept.type == 'earning'], Decimal('0'))
        self.total_deductions = sum([d.amount for d in details if d.concept.type == 'deduction'], Decimal('0'))
        self.net_salary = self.gross_salary + self.total_earnings - self.total_deductions
        self.save()

    def __str__(self):
        return f"Payroll {self.period} - {self.employee}"

    class Meta:
        verbose_name = "Payment"
        verbose_name_plural = "Payments"
        unique_together = ['employee', 'period']


# class PayrollDetail(models.Model):
#     payroll_record = models.ForeignKey(PayrollRecord, on_delete=models.CASCADE, related_name='details')
#     concept = models.ForeignKey(PaymentConcept, on_delete=models.CASCADE)
#     quantity = models.DecimalField(max_digits=10, decimal_places=2, default=1)
#     amount = models.DecimalField(max_digits=10, decimal_places=2)
#     description = models.TextField(blank=True, null=True)

#     def __str__(self):
#         return f"{self.concept.name}: ${self.amount}"

#     class Meta:
#         verbose_name = "Payroll Detail"
#         verbose_name_plural = "Payroll Details"


# class Attendance(models.Model):
#     employee = models.ForeignKey(Employee, on_delete=models.CASCADE)
#     date = models.DateField()
#     check_in = models.TimeField()
#     check_out = models.TimeField()
#     hours_worked = models.DecimalField(max_digits=4, decimal_places=2, default=0)
#     overtime_hours = models.DecimalField(max_digits=4, decimal_places=2, default=0)
#     comments = models.TextField(blank=True, null=True)

#     def save(self, *args, **kwargs):
#         if self.check_in and self.check_out:
#             from datetime import datetime
#             start = datetime.combine(self.date, self.check_in)
#             end = datetime.combine(self.date, self.check_out)
#             if end < start:
#                 end = datetime.combine(self.date, self.check_out)

#             diff = end - start
#             hours = diff.total_seconds() / 3600

#             self.hours_worked = min(hours, 8)
#             self.overtime_hours = max(hours - 8, 0)

#         super().save(*args, **kwargs)

#     def __str__(self):
#         return f"Attendance {self.employee} - {self.date}"

#     class Meta:
#         verbose_name = "Attendance"
#         verbose_name_plural = "Attendances"
#         unique_together = ['employee', 'date']


# class Incident(models.Model):
#     TYPE_CHOICES = [
#         ('late', 'Late'),
#         ('absence', 'Absence'),
#         ('leave', 'Leave'),
#         ('sick_leave', 'Sick Leave'),
#         ('vacation', 'Vacation'),
#     ]

#     employee = models.ForeignKey(Employee, on_delete=models.CASCADE)
#     type = models.CharField(max_length=20, choices=TYPE_CHOICES)
#     date = models.DateField()
#     end_date = models.DateField(null=True, blank=True)
#     justified = models.BooleanField(default=False)
#     comments = models.TextField(blank=True, null=True)
#     evidence = models.FileField(upload_to='incidents/', blank=True, null=True)

#     def __str__(self):
#         return f"{self.get_type_display()} - {self.employee} - {self.date}"

#     class Meta:
#         verbose_name = "Incident"
#         verbose_name_plural = "Incidents"


@receiver(post_save, sender=User)
def create_employee_from_user(sender, instance, created, **kwargs):
    if created and not hasattr(instance, 'employee'):
        from datetime import datetime
        code = f"EMP{datetime.now().strftime('%Y%m%d')}{instance.id:04d}"

        Employee.objects.create(
            user=instance,
            employee_code=code,
            hire_date=datetime.now().date(),
            birth_date=datetime(1990, 1, 1).date(),
            gender='O'
        )
