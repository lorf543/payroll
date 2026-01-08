import hashlib
import uuid
from django.shortcuts import redirect
from django.contrib import messages
from django.http import HttpResponseForbidden



class DeviceAuthenticationMiddleware:
    """
    Middleware para autenticación por dispositivo
    Ahora permite acceso móvil limitado para ver estado
    """
    
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        return response

    def process_view(self, request, view_func, view_args, view_kwargs):
        # Rutas excluidas de verificación
        excluded_paths = [
            '/admin/',
            '/static/',
            '/media/',
            '/accounts/logout/',
            '/accounts/login/',
            '/account/first-time-setup/',
            '/account/device-not-authorized/',
            '/it-admin/device-management/',
            '/account/account/mobile-status/',
        ]

        if any(request.path.startswith(path) for path in excluded_paths):
            return None

        if request.user.is_authenticated:
            # Detectar si es dispositivo móvil
            is_mobile = self.is_mobile_device(request)
            
            # Si es móvil, solo permitir acceso a vista de estado
            if is_mobile:
                # ⬅️ CRITICAL: Primero verificar si YA está en mobile-status
                if request.path.startswith('/account/mobile-status/'):
                    # Ya está en la vista correcta, permitir acceso
                    return None
                
                # Si está en accounts/logout, permitir
                if request.path.startswith('/accounts/logout/'):
                    return None
                
                # Si está en cualquier otra ruta, redirigir a mobile-status
                return redirect('mobile_status_view')
            
            # Para desktop, verificar dispositivo autorizado
            try:
                from .models import DeviceToken
                device_token = DeviceToken.objects.get(user=request.user)

                if device_token.is_active:
                    current_fingerprint = self.get_device_fingerprint(request)

                    if device_token.device_fingerprint != current_fingerprint:
                        messages.error(
                            request,
                            "Device not authorized. Please contact IT department."
                        )
                        return redirect('device_not_authorized')

            except DeviceToken.DoesNotExist:
                if not request.path.startswith('/account/first-time-setup/'):
                    return redirect('first_time_device_setup')

        return None

    def is_mobile_device(self, request):
        """Detecta si el dispositivo es móvil o tablet"""
        user_agent = request.META.get('HTTP_USER_AGENT', '').lower()
        
        mobile_keywords = [
            'mobile', 'android', 'iphone', 'ipad', 
            'tablet', 'phone', 'ipod'
        ]
        
        return any(keyword in user_agent for keyword in mobile_keywords)

    def get_device_fingerprint(self, request):
        """Genera un fingerprint del dispositivo"""
        user_agent = request.META.get('HTTP_USER_AGENT', '')
        device_uuid = request.COOKIES.get('device_uuid')

        if not device_uuid:
            device_uuid = 'temp-' + str(uuid.uuid4())

        device_string = f"{user_agent}-{device_uuid}"
        return hashlib.sha256(device_string.encode()).hexdigest()