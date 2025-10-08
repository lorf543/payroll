from django.db import models
from django.contrib.auth.models import User
import secrets
import hashlib

class DeviceToken(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='device_token')
    token = models.CharField(max_length=64, unique=True)
    device_fingerprint = models.CharField(max_length=128)
    created_at = models.DateTimeField(auto_now_add=True)
    is_active = models.BooleanField(default=True)
    
    def generate_device_fingerprint(self, request):
        """Generate a fingerprint based on device characteristics"""
        user_agent = request.META.get('HTTP_USER_AGENT', '')
        accept_language = request.META.get('HTTP_ACCEPT_LANGUAGE', '')
        accept_encoding = request.META.get('HTTP_ACCEPT_ENCODING', '')
        
        # Combine various device characteristics
        device_string = f"{user_agent}{accept_language}{accept_encoding}"
        return hashlib.sha256(device_string.encode()).hexdigest()
    
    def generate_token(self):
        """Generate a secure random token"""
        return secrets.token_hex(32)
    
    def save(self, *args, **kwargs):
        if not self.token:
            self.token = self.generate_token()
        super().save(*args, **kwargs)
    
    def __str__(self):
        return f"{self.user.username} - {self.device_fingerprint[:16]}"
    
    class Meta:
        verbose_name = "Device Token"
        verbose_name_plural = "Device Tokens"