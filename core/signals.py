# signals.py
from django.db.models.signals import post_save
from django.contrib.auth.signals import user_logged_in, user_logged_out
from django.dispatch import receiver
from django.contrib.auth.models import User
from django.utils import timezone

from .models import Employee
from attendance.models import WorkDay

@receiver(user_logged_in)
def set_user_logged_in(sender, request, user, **kwargs):
    print( "User logged in signal received." )
    try:
        employee = Employee.objects.get(user=user)
        employee.is_logged_in = True
        employee.last_login = timezone.now()
        employee.save()
    except Employee.DoesNotExist:
        pass

@receiver(user_logged_out)
def set_user_logged_out(sender, request, user, **kwargs):
    print("User logged out signal received.")
    try:
        employee = Employee.objects.get(user=user)
        work_day = WorkDay.objects.filter(employee=employee, date=timezone.now().date(), check_out__isnull=True).first()
        
        # Add null check before calling methods
        if work_day:
            work_day.end_current_session()
        
        employee.is_logged_in = False
        employee.last_logout = timezone.now()
        employee.save()
    except Employee.DoesNotExist:
        pass