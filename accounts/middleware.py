import hashlib
import uuid
from django.shortcuts import redirect, get_object_or_404, render
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.views import View
from .models import DeviceToken


class DeviceAuthenticationMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        return response

    def process_view(self, request, view_func, view_args, view_kwargs):
        excluded_paths = [
            '/admin/',
            '/static/',
            '/accounts/logout/',
            '/account/first-time-setup/',
            '/account/device-not-authorized/',
            '/it-admin/device-management/',
        ]

        if any(request.path.startswith(path) for path in excluded_paths):
            return None

        if request.user.is_authenticated:
            try:
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

    def get_device_fingerprint(self, request):
        """Genera un fingerprint estable combinando User-Agent y cookie persistente"""
        user_agent = request.META.get('HTTP_USER_AGENT', '')
        device_uuid = request.COOKIES.get('device_uuid')

        # Si no existe la cookie, se genera un nuevo UUID temporal
        # (solo se usará para crear el token en el primer registro)
        if not device_uuid:
            device_uuid = 'temp-' + str(uuid.uuid4())

        device_string = f"{user_agent}-{device_uuid}"
        return hashlib.sha256(device_string.encode()).hexdigest()