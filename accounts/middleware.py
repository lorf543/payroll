# middleware.py
from django.shortcuts import redirect
from django.urls import reverse
from django.contrib import messages
from .models import DeviceToken
import hashlib

class DeviceAuthenticationMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        return response

    def process_view(self, request, view_func, view_args, view_kwargs):
        # Skip middleware for static files, admin, and specific URLs
        excluded_paths = [
            '/admin/',
            '/static/',
            '/accounts/logout/',
            '/account/first-time-setup/',  # Add this to prevent redirect loop
            '/account/device-not-authorized/',  # Add this too
            '/it-admin/device-management/',
        ]
        
        if any(request.path.startswith(path) for path in excluded_paths):
            return None
            
        # If user is authenticated
        if request.user.is_authenticated:
            try:
                device_token = DeviceToken.objects.get(user=request.user)
                
                if device_token.is_active:
                    current_fingerprint = self.get_device_fingerprint(request)
                    
                    # Check if device matches
                    if device_token.device_fingerprint != current_fingerprint:
                        messages.error(
                            request, 
                            "Device not authorized. Please contact IT department."
                        )
                        return redirect('device_not_authorized')
                        
            except DeviceToken.DoesNotExist:
                # First time login - only redirect if not already on setup page
                if not request.path.startswith('/first-time-setup/'):
                    return redirect('first_time_device_setup')
        
        return None

    def get_device_fingerprint(self, request):
        """Generate device fingerprint from request"""
        user_agent = request.META.get('HTTP_USER_AGENT', '')
        accept_language = request.META.get('HTTP_ACCEPT_LANGUAGE', '')
        accept_encoding = request.META.get('HTTP_ACCEPT_ENCODING', '')
        
        device_string = f"{user_agent}{accept_language}{accept_encoding}"
        return hashlib.sha256(device_string.encode()).hexdigest()