# models.py
from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone
from datetime import datetime, time
import humanize
from core.models import Campaign

from core.models import Employee

class Attendance(models.Model):
    ATTENDANCE_STATUS_CHOICES = [
        ('present', 'Present'),
        ('absent', 'Absent'),
        ('late', 'Late'),
        ('half_day', 'Half Day'),
        ('leave', 'On Leave'),
        ('holiday', 'Holiday'),
        ('weekend', 'Weekend'),
    ]
    
    employee = models.ForeignKey(Employee, on_delete=models.CASCADE, related_name='attendance_records')
    date = models.DateField(default=timezone.now)
    check_in = models.TimeField(null=True, blank=True)
    check_out = models.TimeField(null=True, blank=True)
    status = models.CharField(max_length=20, choices=ATTENDANCE_STATUS_CHOICES, default='absent')
    hours_worked = models.DecimalField(max_digits=4, decimal_places=2, default=0)  # in hours
    late_minutes = models.IntegerField(default=0)  # minutes late
    overtime_hours = models.DecimalField(max_digits=4, decimal_places=2, default=0)
    notes = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = "Attendance Record"
        verbose_name_plural = "Attendance Records"
        unique_together = ['employee', 'date']
        ordering = ['-date', 'employee']
        indexes = [
            models.Index(fields=['date', 'status']),
            models.Index(fields=['employee', 'date']),
        ]
    
    def __str__(self):
        return f"{self.employee} - {self.date} - {self.get_status_display()}"
    
    def save(self, *args, **kwargs):
        # Calculate hours worked if both check_in and check_out are present
        if self.check_in and self.check_out:
            check_in_dt = datetime.combine(self.date, self.check_in)
            check_out_dt = datetime.combine(self.date, self.check_out)
            
            # Handle overnight shifts (check_out next day)
            if check_out_dt < check_in_dt:
                check_out_dt = check_out_dt.replace(day=check_out_dt.day + 1)
            
            time_difference = check_out_dt - check_in_dt
            self.hours_worked = round(time_difference.total_seconds() / 3600, 2)
        
        # Calculate late minutes if check_in is after scheduled time
        # if self.check_in and self.employee.position:
        #     scheduled_start = self.employee.position.scheduled_start_time
        #     if scheduled_start and self.check_in > scheduled_start:
        #         check_in_dt = datetime.combine(self.date, self.check_in)
        #         scheduled_dt = datetime.combine(self.date, scheduled_start)
        #         time_difference = check_in_dt - scheduled_dt
        #         self.late_minutes = int(time_difference.total_seconds() / 60)
                
        #         # Auto-set status to late if more than 5 minutes late
        #         if self.late_minutes >= 5 and self.status == 'present':
        #             self.status = 'late'
        
        super().save(*args, **kwargs)
    
    @property
    def is_on_time(self):
        return self.late_minutes == 0 and self.status == 'present'
    
    @property
    def has_overtime(self):
        return self.overtime_hours > 0
    
class LeaveType(models.Model):
    name = models.CharField(max_length=100)
    description = models.TextField(blank=True, null=True)
    max_days_per_year = models.IntegerField(default=20)
    is_paid = models.BooleanField(default=True)
    requires_approval = models.BooleanField(default=True)
    color = models.CharField(max_length=7, default='#3498db')  # Hex color for UI
    
    class Meta:
        verbose_name = "Leave Type"
        verbose_name_plural = "Leave Types"
    
    def __str__(self):
        return self.name
    
class AgentStatus(models.Model):
    STATUS_CHOICES = [
        ('ready', 'Ready'),
        ('break', 'Break'),
        ('lunch', 'Lunch'),
        ('training', 'Training'),
        ('meeting', 'Meeting'),
        ('offline', 'Offline'),
    ]
    
    agent = models.ForeignKey(Employee, on_delete=models.CASCADE, related_name='status_changes')
    campaign = models.ForeignKey(Campaign, on_delete=models.SET_NULL, null=True, blank=True, related_name='campaign_statuses')

    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='offline')
    start_time = models.DateTimeField(null=True, blank=True)
    end_time = models.DateTimeField(null=True, blank=True)
    notes = models.TextField(blank=True, null=True)
    expected_duration = models.IntegerField(null=True, blank=True)  # in minutes
    auto_revert = models.BooleanField(default=False)
    
    class Meta:
        verbose_name = "Agent Status"
        verbose_name_plural = "Agent Statuses"
        ordering = ['end_time']
    
    def __str__(self):
        return f"{self.agent} - {self.status} ({self.start_time})"
    
    @property
    def is_active(self):
        return self.end_time is None
    
    @property
    def duration(self):
        """Calculate duration of the status"""
        if self.end_time:
            return self.end_time - self.start_time
        return timezone.now() - self.start_time
    
    @property
    def natural_duration(self):
        """Retorna la duración en formato humano"""
        duration = self.duration
        if not duration:
            return ""
        
        try:
            return humanize.naturaldelta(duration)
        except:
            # Fallback
            total_seconds = int(duration.total_seconds())
            hours = total_seconds // 3600
            minutes = (total_seconds % 3600) // 60
            
            if hours > 0:
                return f"{hours}h {minutes}m"
            elif minutes > 0:
                return f"{minutes}m"
            else:
                return "Less than 1m"
            

    @classmethod
    def get_current_status(cls, agent):
        return cls.objects.filter(agent=agent, end_time__isnull=True).first()

class StatusSchedule(models.Model):
    agent = models.ForeignKey(Employee, on_delete=models.CASCADE, related_name='status_schedules')
    status = models.CharField(max_length=20, choices=AgentStatus.STATUS_CHOICES)
    scheduled_start = models.DateTimeField()
    scheduled_end = models.DateTimeField()
    recurring = models.BooleanField(default=False)
    recurring_pattern = models.CharField(max_length=50, blank=True, null=True)  # e.g., "daily", "weekly"
    
    class Meta:
        verbose_name = "Status Schedule"
        verbose_name_plural = "Status Schedules"