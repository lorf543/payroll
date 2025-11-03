# signals.py
from django.db.models.signals import post_save
from django.contrib.auth.signals import user_logged_in, user_logged_out
from django.dispatch import receiver
from .models import Employee
from django.contrib.auth.models import User

@receiver(user_logged_in)
def set_user_logged_in(sender, request, user, **kwargs):
    try:
        employee = Employee.objects.get(user=user)
        employee.is_logged_in = True
        employee.save()
    except Employee.DoesNotExist:
        pass

@receiver(user_logged_out)
def set_user_logged_out(sender, request, user, **kwargs):
    try:
        employee = Employee.objects.get(user=user)
        employee.is_logged_in = False
        employee.save()
    except Employee.DoesNotExist:
        pass

