# signals.py
from django.db.models.signals import pre_save, post_save
from django.dispatch import receiver
from django.utils import timezone
from core.models import Employee, BulkInvitation
from django.contrib.auth.models import User
import uuid

@receiver(pre_save, sender=Employee)
def generate_employee_code(sender, instance, **kwargs):
    """
    Automatically generate employee code if not provided
    """
    if not instance.employee_code:
        # Generate a unique employee code
        timestamp = timezone.now().strftime('%y%m%d')
        random_part = str(uuid.uuid4().hex[:6].upper())
        instance.employee_code = f"EMP{timestamp}{random_part}"
    
    # Ensure identification is set if empty
    if not instance.identification:
        instance.identification = instance.employee_code

@receiver(post_save, sender=User)
def activate_new_user(sender, instance, created, **kwargs):
    if not created and not instance.is_active:
        # User just set password for first time (optional logic)
        instance.is_active = True
        instance.save()