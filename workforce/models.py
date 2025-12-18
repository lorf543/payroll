# workforce/models.py
from django.db import models
from django.core.exceptions import ValidationError
from django.utils import timezone
from datetime import time, timedelta, datetime
from core.models import Employee, Campaign
import datetime


class Shift(models.Model):
    """
    Base shifts that can be assigned to employees
    """
    SHIFT_TYPES = [
        ('morning', 'Morning Shift'),
        ('afternoon', 'Afternoon Shift'),
        ('evening', 'Evening Shift'),
        ('night', 'Night Shift'),
        ('rotating', 'Rotating Shift'),
    ]

    name = models.CharField(max_length=100, blank=True, null=True)
    shift_type = models.CharField(max_length=20, choices=SHIFT_TYPES)

    # Shift hours
    start_time = models.TimeField()
    end_time = models.TimeField()

    # Expected duration (calculated or manual)
    expected_hours = models.DecimalField(max_digits=4, decimal_places=2, default=8.0)

    # Break and lunch configuration
    break_duration_minutes = models.IntegerField(
        default=15, help_text="Duration of each break in minutes"
    )
    break_count = models.IntegerField(
        default=2, help_text="Number of allowed breaks"
    )
    lunch_duration_minutes = models.IntegerField(
        default=60, help_text="Lunch duration in minutes"
    )

    # Suggested break/lunch times
    first_break_time = models.TimeField(
        null=True, blank=True, help_text="Suggested time for first break"
    )
    second_break_time = models.TimeField(
        null=True, blank=True, help_text="Suggested time for second break"
    )
    lunch_time = models.TimeField(
        null=True, blank=True, help_text="Suggested lunch time"
    )

    # Configuration
    is_active = models.BooleanField(default=True)
    allow_overtime = models.BooleanField(default=True)
    max_overtime_hours = models.DecimalField(max_digits=4, decimal_places=2, default=2.0)

    # Metadata
    campaign = models.ForeignKey(
        Campaign,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        help_text="Specific campaign for this shift (optional)",
    )
    color_code = models.CharField(
        max_length=7, default="#3B82F6", help_text="Color for calendar display"
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['start_time']

    def __str__(self):
        return f"{self.name} ({self.start_time.strftime('%H:%M')} - {self.end_time.strftime('%H:%M')})"

    def clean(self):
        """Custom validation"""
        if self.start_time and self.end_time:
            start_minutes = self.start_time.hour * 60 + self.start_time.minute
            end_minutes = self.end_time.hour * 60 + self.end_time.minute

            if start_minutes >= end_minutes:
                # Night shift (crosses midnight)
                duration_minutes = (24 * 60 - start_minutes) + end_minutes
            else:
                duration_minutes = end_minutes - start_minutes

            self.expected_hours = round(duration_minutes / 60, 2)

    @property
    def is_night_shift(self):
        """Detect if this is a night shift (crosses midnight)"""
        return self.start_time > self.end_time
    

    @property
    def total_break_time_minutes(self):
        """Total break + lunch time in minutes"""
        return (self.break_duration_minutes * self.break_count) + self.lunch_duration_minutes

    @property
    def formatted_time_range(self):
        """Formatted time range"""
        return f"{self.start_time.strftime('%I:%M %p')} - {self.end_time.strftime('%I:%M %p')}"
    
    def save(self, *args, **kwargs):
        self.name = f"{self.campaign.name } - {self.shift_type.capitalize()}"
        
        super().save(*args, **kwargs)


class EmployeeSchedule(models.Model):
    """
    Specific schedule assigned to an employee for a period of time
    """
    SCHEDULE_STATUS = [
        ('draft', 'Draft'),
        ('published', 'Published'),
        ('active', 'Active'),
        ('completed', 'Completed'),
        ('cancelled', 'Cancelled'),
    ]

    DAYS_OF_WEEK = [
        (0, 'Monday'),
        (1, 'Tuesday'),
        (2, 'Wednesday'),
        (3, 'Thursday'),
        (4, 'Friday'),
        (5, 'Saturday'),
        (6, 'Sunday'),
    ]

    employee = models.ForeignKey(Employee, on_delete=models.CASCADE, related_name='schedules')
    shift = models.ForeignKey(Shift, on_delete=models.PROTECT, related_name='scheduled_employees')

    # Validity period
    start_date = models.DateField()
    end_date = models.DateField(
        null=True, blank=True, help_text="Leave empty for an indefinite schedule"
    )

    # Active weekdays
    monday = models.BooleanField(default=True)
    tuesday = models.BooleanField(default=True)
    wednesday = models.BooleanField(default=True)
    thursday = models.BooleanField(default=True)
    friday = models.BooleanField(default=True)
    saturday = models.BooleanField(default=False)
    sunday = models.BooleanField(default=False)

    # Optional overrides (override shift times)
    custom_start_time = models.TimeField(null=True, blank=True)
    custom_end_time = models.TimeField(null=True, blank=True)
    custom_break_duration = models.IntegerField(null=True, blank=True)
    custom_lunch_duration = models.IntegerField(null=True, blank=True)
    
    custom_break_count = models.IntegerField(null=True, blank=True)
    custom_first_break_time = models.TimeField(null=True, blank=True)
    custom_second_break_time = models.TimeField(null=True, blank=True)
    custom_lunch_time = models.TimeField(null=True, blank=True)
        
    # Status and metadata
    status = models.CharField(max_length=20, choices=SCHEDULE_STATUS, default='draft')
    notes = models.TextField(blank=True, null=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey('auth.User', on_delete=models.SET_NULL, null=True, blank=True)

    class Meta:
        ordering = ['-start_date', 'employee']
        indexes = [
            models.Index(fields=['employee', 'start_date', 'end_date']),
            models.Index(fields=['status', 'start_date']),
        ]

    def __str__(self):
        return f"{self.employee.full_name} - {self.shift.name} ({self.start_date})"

    def clean(self):
        """Validation"""
        if self.end_date and self.start_date > self.end_date:
            raise ValidationError("Start date cannot be later than end date")

        overlapping = EmployeeSchedule.objects.filter(
            employee=self.employee,
            status__in=['published', 'active']
        ).exclude(pk=self.pk)

        if self.end_date:
            overlapping = overlapping.filter(
                start_date__lte=self.end_date,
                end_date__gte=self.start_date
            ) | overlapping.filter(
                start_date__lte=self.end_date,
                end_date__isnull=True
            )
        else:
            overlapping = overlapping.filter(start_date__lte=self.start_date)

        if overlapping.exists():
            raise ValidationError(
                "This employee already has a schedule that overlaps with these dates"
            )

    @property
    def is_active_today(self):
        """Check if this schedule is active today"""
        today = timezone.now().date()

        if self.start_date > today:
            return False
        if self.end_date and self.end_date < today:
            return False

        weekday = today.weekday()
        days_active = [
            self.monday, self.tuesday, self.wednesday, self.thursday,
            self.friday, self.saturday, self.sunday
        ]
        return days_active[weekday]

    @property
    def works_today(self):
        """Alias for is_active_today"""
        return self.is_active_today

    @property
    def active_days(self):
        """List of active days as text"""
        days = []
        day_names = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']
        day_values = [
            self.monday, self.tuesday, self.wednesday, self.thursday,
            self.friday, self.saturday, self.sunday
        ]

        for name, active in zip(day_names, day_values):
            if active:
                days.append(name)
        return ", ".join(days)

    def get_effective_times(self):
        """Return effective times (custom or shift defaults)"""
        return {
            'start_time': self.custom_start_time or self.shift.start_time,
            'end_time': self.custom_end_time or self.shift.end_time,
            'break_duration': self.custom_break_duration or self.shift.break_duration_minutes,
            'lunch_duration': self.custom_lunch_duration or self.shift.lunch_duration_minutes,
            'first_break_time': self.custom_first_break_time or self.shift.first_break_time,
            'second_break_time': self.custom_second_break_time or self.shift.second_break_time,
            'lunch_time': self.custom_lunch_time or self.shift.lunch_time,
        }
    
    def get_schedule_for_date(self, date):
        """Return schedule details for a specific date"""
        if not self.is_valid_for_date(date):
            return None

        times = self.get_effective_times()
        return {
            'date': date,
            'employee': self.employee,
            'shift': self.shift,
            'start_time': times['start_time'],
            'end_time': times['end_time'],
            'break_duration': times['break_duration'],
            'lunch_duration': times['lunch_duration'],
            'expected_hours': self.shift.expected_hours,
        }
    
    def get_schedule_for_date_range(self):
        """Devuelve lista de fechas activas según días de la semana y rango de fechas"""
        start = self.start_date
        end = self.end_date or (self.start_date + timedelta(days=180))  # hasta 6 meses si indefinido
        current = start
        active_dates = []

        weekdays = [
            self.monday, self.tuesday, self.wednesday,
            self.thursday, self.friday, self.saturday, self.sunday
        ]

        while current <= end:
            if weekdays[current.weekday()]:
                active_dates.append(current)
            current += timedelta(days=1)

        return active_dates

    def is_valid_for_date(self, date):
        """Check if schedule applies to a specific date"""
        if date < self.start_date:
            return False
        if self.end_date and date > self.end_date:
            return False

        weekday = date.weekday()
        days_active = [
            self.monday, self.tuesday, self.wednesday, self.thursday,
            self.friday, self.saturday, self.sunday
        ]
        return days_active[weekday]
    
    def get_effective_start_time(self):
        """Get effective start time (custom or shift default)"""
        return self.custom_start_time or self.shift.start_time
    
    def get_effective_end_time(self):
        """Get effective end time (custom or shift default)"""
        return self.custom_end_time or self.shift.end_time
    
    def get_effective_break_duration(self):
        """Get effective break duration"""
        return self.custom_break_duration or self.shift.break_duration_minutes
    
    def get_effective_lunch_duration(self):
        """Get effective lunch duration"""
        return self.custom_lunch_duration or self.shift.lunch_duration_minutes
    
    def get_effective_break_count(self):
        """Get effective break count"""
        return self.custom_break_count or self.shift.break_count
    
    def get_effective_first_break_time(self):
        """Get effective first break time"""
        return self.custom_first_break_time or self.shift.first_break_time
    
    def get_effective_second_break_time(self):
        """Get effective second break time"""
        return self.custom_second_break_time or self.shift.second_break_time
    
    def get_effective_lunch_time(self):
        """Get effective lunch time"""
        return self.custom_lunch_time or self.shift.lunch_time
    
    def get_effective_hours(self):
        """Calculate effective working hours considering custom times"""
        start = self.get_effective_start_time()
        end = self.get_effective_end_time()
        
        if start and end:
            # Handle night shifts (crossing midnight)
            if start > end:
                # Night shift - add 24 hours to end time
                end_dt = datetime.datetime.combine(datetime.date.today(), end)
                end_dt += timedelta(days=1)
                start_dt = datetime.datetime.combine(datetime.date.today(), start)
            else:
                start_dt = datetime.datetime.combine(datetime.date.today(), start)
                end_dt = datetime.datetime.combine(datetime.date.today(), end)
            
            total_minutes = (end_dt - start_dt).total_seconds() / 60
            return round(total_minutes / 60, 2)
        
        return self.shift.expected_hours
    
    def get_break_schedule_details(self):
        """Calculate and return detailed break schedule"""
        start_time = self.get_effective_start_time()
        end_time = self.get_effective_end_time()
        break_count = self.get_effective_break_count()
        break_duration = self.get_effective_break_duration()
        lunch_duration = self.get_effective_lunch_duration()
        
        # Initialize result
        result = {
            'scheduled_breaks': [],
            'lunch_time': None,
            'total_break_time_minutes': 0,
        }
        
        # Get custom times if available
        first_break_time = self.get_effective_first_break_time()
        second_break_time = self.get_effective_second_break_time()
        lunch_time = self.get_effective_lunch_time()
        
        # If custom times are specified, use them
        if first_break_time:
            result['scheduled_breaks'].append({
                'break_number': 1,
                'scheduled_time': first_break_time.strftime('%H:%M'),
                'duration_minutes': break_duration,
                'type': 'break',
                'is_custom': bool(self.custom_first_break_time),
            })
        
        if second_break_time and break_count >= 2:
            result['scheduled_breaks'].append({
                'break_number': 2,
                'scheduled_time': second_break_time.strftime('%H:%M'),
                'duration_minutes': break_duration,
                'type': 'break',
                'is_custom': bool(self.custom_second_break_time),
            })
        
        if lunch_time:
            result['lunch_time'] = {
                'scheduled_time': lunch_time.strftime('%H:%M'),
                'duration_minutes': lunch_duration,
                'type': 'lunch',
                'is_custom': bool(self.custom_lunch_time),
            }
        
        # Calculate total break time
        total_breaks = len(result['scheduled_breaks']) * break_duration
        if result['lunch_time']:
            total_breaks += lunch_duration
        result['total_break_time_minutes'] = total_breaks
        
        # If no custom times, calculate suggested times based on shift duration
        if not result['scheduled_breaks'] and break_count > 0:
            # Calculate suggested break times (spread evenly)
            shift_minutes = (datetime.datetime.combine(datetime.date.today(), end_time) - 
                           datetime.datetime.combine(datetime.date.today(), start_time)).seconds / 60
            
            for i in range(break_count):
                # Break starts after 1/3 of the way through each segment
                break_offset = (shift_minutes / (break_count + 1)) * (i + 1)
                break_time = (datetime.datetime.combine(datetime.date.today(), start_time) + 
                            timedelta(minutes=break_offset)).time()
                
                result['scheduled_breaks'].append({
                    'break_number': i + 1,
                    'scheduled_time': break_time.strftime('%H:%M'),
                    'duration_minutes': break_duration,
                    'type': 'break',
                    'is_custom': False,
                })
        
        return result
    
    def get_daily_schedule_with_breaks(self, date):
        """Get detailed schedule for a specific date including breaks"""
        if not self.is_valid_for_date(date):
            return None
        
        break_details = self.get_break_schedule_details()
        
        return {
            'date': date.strftime('%Y-%m-%d'),
            'day_name': date.strftime('%A'),
            'shift_name': self.shift.name,
            'shift_type': self.shift.shift_type,
            'schedule_id': self.id,
            'times': {
                'start': self.get_effective_start_time().strftime('%H:%M'),
                'end': self.get_effective_end_time().strftime('%H:%M'),
                'working_hours': self.get_effective_hours(),
            },
            'breaks': break_details,
            'notes': self.notes,
            'status': self.status,
        }
    

class TimeOffRequest(models.Model):
    """
    Time off requests (vacation, leave, absence)
    """
    REQUEST_TYPES = [
        ('vacation', 'Vacation'),
        ('sick_leave', 'Sick Leave'),
        ('personal', 'Personal Day'),
        ('unpaid', 'Unpaid Leave'),
        ('bereavement', 'Bereavement'),
        ('other', 'Other'),
    ]

    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected'),
        ('cancelled', 'Cancelled'),
    ]

    employee = models.ForeignKey(Employee, on_delete=models.CASCADE, related_name='time_off_requests')
    request_type = models.CharField(max_length=20, choices=REQUEST_TYPES)

    start_date = models.DateField()
    end_date = models.DateField()

    reason = models.TextField()
    is_paid = models.BooleanField(default=True)

    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    reviewed_by = models.ForeignKey(
        'auth.User',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='reviewed_requests'
    )
    reviewed_at = models.DateTimeField(null=True, blank=True)
    rejection_reason = models.TextField(blank=True, null=True)

    requested_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-requested_at']
        indexes = [
            models.Index(fields=['employee', 'status']),
            models.Index(fields=['start_date', 'end_date']),
        ]

    def __str__(self):
        return f"{self.employee.full_name} - {self.get_request_type_display()} ({self.start_date} to {self.end_date})"

    def clean(self):
        if self.start_date > self.end_date:
            raise ValidationError("Start date cannot be later than end date")

    @property
    def total_days(self):
        """Total requested days"""
        return (self.end_date - self.start_date).days + 1

    @property
    def is_pending(self):
        return self.status == 'pending'

    @property
    def is_approved(self):
        return self.status == 'approved'

    def approve(self, user):
        """Approve request"""
        self.status = 'approved'
        self.reviewed_by = user
        self.reviewed_at = timezone.now()
        self.save()

    def reject(self, user, reason):
        """Reject request"""
        self.status = 'rejected'
        self.reviewed_by = user
        self.reviewed_at = timezone.now()
        self.rejection_reason = reason
        self.save()


class BreakSchedule(models.Model):
    """
    Specific break scheduling per employee/day
    Allows pre-scheduling exact break and lunch times
    """
    BREAK_TYPES = [
        ('break', 'Break'),
        ('lunch', 'Lunch'),
    ]

    employee = models.ForeignKey(Employee, on_delete=models.CASCADE, related_name='break_schedules')
    date = models.DateField()
    break_type = models.CharField(max_length=10, choices=BREAK_TYPES)

    scheduled_start_time = models.TimeField()
    scheduled_end_time = models.TimeField()
    duration_minutes = models.IntegerField()

    was_taken = models.BooleanField(default=False)
    actual_start_time = models.TimeField(null=True, blank=True)
    actual_end_time = models.TimeField(null=True, blank=True)

    created_by = models.ForeignKey('auth.User', on_delete=models.SET_NULL, null=True, blank=True)
    notes = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['date', 'scheduled_start_time']
        unique_together = ['employee', 'date', 'break_type', 'scheduled_start_time']

    def __str__(self):
        return f"{self.employee.full_name} - {self.get_break_type_display()} - {self.date} at {self.scheduled_start_time}"

    @property
    def is_overdue(self):
        """Check if the break was missed"""
        if self.was_taken:
            return False

        now = timezone.now()
        return now.date() == self.date and now.time() > self.scheduled_end_time

    @property
    def compliance_status(self):
        """Compliance status"""
        if not self.was_taken:
            return 'missed' if self.is_overdue else 'scheduled'

        if self.actual_start_time and self.scheduled_start_time:
            scheduled_minutes = self.scheduled_start_time.hour * 60 + self.scheduled_start_time.minute
            actual_minutes = self.actual_start_time.hour * 60 + self.actual_start_time.minute
            diff_minutes = abs(scheduled_minutes - actual_minutes)

            if diff_minutes <= 15:
                return 'on_time'
            elif diff_minutes <= 30:
                return 'delayed'
            else:
                return 'very_late'

        return 'taken'
