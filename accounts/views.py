from django_q.tasks import async_task
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required, user_passes_test
from allauth.account.views import PasswordChangeView
from django.contrib.messages.views import SuccessMessageMixin
from django.contrib.auth.models import User
from django.urls import reverse_lazy, reverse
from django.contrib import messages
from django.views import View
from django.db.models import Q
from django.core.mail import EmailMultiAlternatives, send_mail
from django.template.loader import render_to_string
from .models import DeviceToken
import hashlib
import uuid

from django.contrib.sites.shortcuts import get_current_site
from django.template.loader import render_to_string
from django.utils.http import urlsafe_base64_encode
from django.utils.encoding import force_bytes
from django.contrib.auth.tokens import default_token_generator
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST
from django.template.loader import render_to_string
from django.http import HttpResponse
from .forms import EmailForm 
from .forms import EmployeeInvitationForm, EmployeeEmailForm


from core.models import Employee, BulkInvitation
from django.utils import timezone

def test_view(request):
    return render(request,'emails/invitation.html')

class CustomPasswordChangeView(SuccessMessageMixin, PasswordChangeView):
    template_name = 'account/password_change.html'
    success_url = reverse_lazy('home')
    success_message = "Your password has been changed successfully!"
    
    def form_valid(self, form):
        response = super().form_valid(form)
        return response



class DeviceAuthenticationMiddleware:
    """
    Middleware para validar el dispositivo del usuario autenticado.
    Se salta rutas estáticas, de medios, PWA y ciertas rutas de cuenta.
    """

    def __init__(self, get_response):
        self.get_response = get_response

        # Prefijos o rutas a excluir
        self.excluded_prefixes = [
            '/admin/',
            '/static/',
            '/media/',
            '/accounts/logout/',
            '/account/first-time-setup/',
            '/account/device-not-authorized/',
            '/it-admin/device-management/',
            '/manifest.json',
            '/serviceworker.js',
            '/sw.js',
            '/offline/',
        ]

    def __call__(self, request):
        response = self.get_response(request)
        return response

    def process_view(self, request, view_func, view_args, view_kwargs):
        # Excluir rutas definidas
        if any(request.path.startswith(prefix) for prefix in self.excluded_prefixes):
            return None

        # Si el usuario no está autenticado, no hacer nada
        if not request.user.is_authenticated:
            return None

        # Intentar obtener el DeviceToken
        try:
            device_token = DeviceToken.objects.get(user=request.user)
        except DeviceToken.DoesNotExist:
            # Redirigir solo si no está en el flujo de configuración
            if not request.path.startswith('/account/first-time-setup/'):
                return redirect('first_time_device_setup')
            return None

        # Validar el dispositivo
        if device_token.is_active:
            current_fingerprint = self.get_device_fingerprint(request)

            if device_token.device_fingerprint != current_fingerprint:
                messages.error(
                    request,
                    "Device not authorized. Please contact IT department."
                )
                return redirect('device_not_authorized')

        return None

    def get_device_fingerprint(self, request):
        """Genera un fingerprint estable combinando User-Agent y cookie persistente"""
        user_agent = request.META.get('HTTP_USER_AGENT', '')
        device_uuid = request.COOKIES.get('device_uuid')

        if not device_uuid:
            device_uuid = 'temp-' + str(uuid.uuid4())

        device_string = f"{user_agent}-{device_uuid}"
        return hashlib.sha256(device_string.encode()).hexdigest()

class FirstTimeDeviceSetupView(View):
    def get(self, request):
        if not request.user.is_authenticated:
            return redirect('account_login')

        if hasattr(request.user, 'device_token'):
            return redirect('home')

        return render(request, 'device_auth/first_time_setup.html')

    def post(self, request):
        if not request.user.is_authenticated:
            return redirect('account_login')

        # Crear nuevo UUID persistente
        device_uuid = str(uuid.uuid4())

        # Crear token de dispositivo
        device_token = DeviceToken(user=request.user)
        device_fingerprint = hashlib.sha256(
            f"{request.META.get('HTTP_USER_AGENT', '')}-{device_uuid}".encode()
        ).hexdigest()

        device_token.device_fingerprint = device_fingerprint
        device_token.save()

        messages.success(request, "Device registered successfully!")

        # Crear cookie persistente (1 año)
        response = redirect('home')
        response.set_cookie(
            'device_uuid',
            device_uuid,
            max_age=60 * 60 * 24 * 365,  # 1 año
            httponly=True,
            secure=True,  # Cambia a False si no usas HTTPS en desarrollo
            samesite='Lax'
        )
        return response


class DeviceNotAuthorizedView(View):
    def get(self, request):
        if not request.user.is_authenticated:
            return redirect('account_login')
        return render(request, 'device_auth/device_not_authorized.html')


@login_required
def it_device_management(request):
    query = request.GET.get('q', '').strip()
    device_tokens = DeviceToken.objects.select_related('user').all()

    if query:
        device_tokens = device_tokens.filter(
            Q(user__username__icontains=query)
        )

    if request.method == 'POST':
        token_id = request.POST.get('token_id')
        action = request.POST.get('action')
        device_token = get_object_or_404(DeviceToken, id=token_id)

        if action == 'deactivate':
            device_token.is_active = False
            device_token.save()
            messages.success(request, f"Device token for {device_token.user.username} has been deactivated.")
        elif action == 'activate':
            device_token.is_active = True
            device_token.save()
            messages.success(request, f"Device token for {device_token.user.username} has been activated.")
        elif action == 'delete':
            username = device_token.user.username
            device_token.delete()
            messages.success(request, f"Device token for {username} has been deleted.")

        return redirect('it_device_management')

    return render(request, 'device_auth/it_device_management.html', {
        'device_tokens': device_tokens
    })

@login_required
def reset_user_device(request, user_id):
    from django.contrib.auth.models import User

    user = get_object_or_404(User, id=user_id)

    DeviceToken.objects.filter(user=user).delete()

    messages.success(
        request,
        f"Device token for {user.username} has been reset. They can now register a new device on next login."
    )
    return redirect('it_device_management')


def add_email_field(request):
    index = int(request.POST.get("index", 0))
    form = EmailForm(prefix=str(index))  # important: use prefix to separate forms

    html = render_to_string("bulk/email_row.html", {"form": form, "index": index})
    return HttpResponse(html)

MAX_EMAILS = 20
@login_required
def bulk_employee_invitation(request):
    initial_forms = 1
    email_forms = [EmployeeEmailForm(prefix=str(i)) for i in range(initial_forms)]
    
    if request.method == 'POST':
        main_form = EmployeeInvitationForm(request.POST)
        
        if main_form.is_valid():
            campaign = main_form.cleaned_data['campaign']
            position = main_form.cleaned_data['position']
            department = main_form.cleaned_data['department']
            supervisor = main_form.cleaned_data['supervisor']
            hire_date = main_form.cleaned_data['hire_date']
            
            # Collect valid email forms
            valid_emails = []
            for i in range(MAX_EMAILS):
                email_form = EmployeeEmailForm(request.POST, prefix=str(i))
                if email_form.is_valid() and email_form.cleaned_data.get('email'):
                    valid_emails.append(email_form.cleaned_data)
            
            if not valid_emails:
                messages.error(request, "Please enter at least one email address.")
                return render(request, 'bulk/bulk_invitation.html', {
                    'main_form': main_form,
                    'email_forms': email_forms
                })
            
            base_url = request.build_absolute_uri('/').rstrip('/')
            
            # Generar links de invitación
            links = []
            for email_data in valid_emails:
                email = email_data['email']
                custom_id = email_data.get('identification', '')
                
                # Aquí el link apunta a la signup page de Allauth con el email
                signup_url = f"{base_url}{reverse('account_signup')}?email={email}"
                if custom_id:
                    signup_url += f"&id={custom_id}"
                
                links.append(f"{email}: {signup_url}")
                
                # Crear Employee INVITADO en la base si no existe aún
                from core.models import Employee
                Employee.objects.get_or_create(
                    email=email,
                    defaults={
                        'position': position,
                        'department': department,
                        'supervisor': supervisor,
                        'current_campaign': campaign,
                        'hire_date': hire_date,
                        'identification': custom_id
                    }
                )
            
            # Descargar archivo .txt con todos los links
            response = HttpResponse("\n".join(links), content_type="text/plain")
            response['Content-Disposition'] = 'attachment; filename="employee_invites.txt"'
            return response
    
    else:
        main_form = EmployeeInvitationForm()
    
    return render(request, 'bulk/bulk_invitation.html', {
        'main_form': main_form,
        'email_forms': email_forms
    })