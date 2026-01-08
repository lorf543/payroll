import hashlib
import uuid
from django.shortcuts import redirect
from django.contrib import messages
from django.utils.deprecation import MiddlewareMixin



class DeviceAuthenticationMiddleware(MiddlewareMixin):
    """
    Desktop = requiere dispositivo autorizado
    Móvil / PWA = acceso SOLO a vista read-only
    """

    SAFE_PATHS = (
        '/admin',                    # Admin
        '/static',                   # Static (DEBUG)
        '/staticfiles',              # Whitenoise (PROD)
        '/media',
        '/favicon',
        '/manifest.json',
        '/service-worker.js',
        '/serviceworker.js',      # django-pwa
        '/service-worker.js',  
        '/sw.js',
        '/offline/',
        '/accounts/login',
        '/accounts/logout',
        '/account/first-time-setup',
        '/account/device-not-authorized',
        '/it-admin/device-management',
        '/account/mobile-status',
        '/account/account/mobile-status'
    )

    MOBILE_KEYWORDS = (
        'mobile', 'android', 'iphone', 'ipad', 'tablet', 'phone', 'ipod'
    )

    def process_view(self, request, view_func, view_args, view_kwargs):

        path = request.path.lower()

        # Rutas libres
        if path.startswith(self.SAFE_PATHS):
            return None

        # No autenticado, no hacemos nada todavía
        if not request.user.is_authenticated:
            return None

        # Detectar móvil real
        is_mobile = self.is_mobile_device(request)

        # ============================
        # 🔹 USERS ON MOBILE
        # ============================
        if is_mobile:

            # Si ya está en mobile-status → permitir
            if path.startswith('/account/mobile-status'):
                return None

            # permitir logout
            if path.startswith('/accounts/logout'):
                return None

            # Forzar siempre a vista móvil
            return redirect('mobile_status_view')

        # ============================
        # 🔹 USERS ON DESKTOP
        # ============================
        try:
            from .models import DeviceToken
            device = DeviceToken.objects.get(user=request.user)

            if not device.is_active:
                return redirect('device_not_authorized')

            fingerprint = self.get_device_fingerprint(request)

            if device.device_fingerprint != fingerprint:
                messages.error(request,
                    "Device not authorized. Please contact IT department."
                )
                return redirect('device_not_authorized')

        except DeviceToken.DoesNotExist:
            if not path.startswith('/account/first-time-setup'):
                return redirect('first_time_device_setup')

        return None


    def is_mobile_device(self, request):
        ua = request.META.get('HTTP_USER_AGENT', '').lower()
        return any(k in ua for k in self.MOBILE_KEYWORDS)


    def get_device_fingerprint(self, request):
        user_agent = request.META.get('HTTP_USER_AGENT', '')
        device_uuid = request.COOKIES.get('device_uuid')

        if not device_uuid:
            # NO cambiar fingerprint constantemente
            device_uuid = 'temp-' + str(uuid.uuid4())

        key = f"{user_agent}-{device_uuid}"
        return hashlib.sha256(key.encode()).hexdigest()