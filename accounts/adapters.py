from allauth.account.adapter import DefaultAccountAdapter
from django.urls import reverse
from django.contrib.auth import login
from core.models import Employee


class CustomAccountAdapter(DefaultAccountAdapter):
    """
    Adaptador personalizado para flujo rápido:
    Invitación → Crear contraseña → Auto-login → Completar perfil
    """
    
    def is_open_for_signup(self, request):
        """
        Permitir signup solo si hay un email válido en la URL
        que corresponde a un Employee invitado
        """
        email = request.GET.get('email')
        if email:
            # Verificar que existe un Employee con este email sin User asociado
            return Employee.objects.filter(email=email, user__isnull=True).exists()
        return False
    
    def save_user(self, request, user, form, commit=True):
        """
        Vincular el User recién creado con el Employee existente
        y hacer auto-login inmediato
        """
        user = super().save_user(request, user, form, commit=False)
        
        if commit:
            user.save()
        
        # Buscar el Employee que fue invitado con este email
        try:
            employee = Employee.objects.get(email=user.email, user__isnull=True)
            employee.user = user
            employee.save()
            
            # Auto-login del usuario recién registrado
            login(request, user, backend='django.contrib.auth.backends.ModelBackend')
            
        except Employee.DoesNotExist:
            # Si no hay Employee, crear uno básico (backup)
            Employee.objects.create(
                email=user.email,
                user=user,
                employee_code=''
            )
            # Auto-login
            login(request, user, backend='django.contrib.auth.backends.ModelBackend')
        
        return user
    
    def get_signup_redirect_url(self, request):
        """
        Redirigir INMEDIATAMENTE después de crear la contraseña
        al formulario de completar perfil
        """
        employee = Employee.objects.filter(email=request.user.email).first()
        if employee:
            return reverse('edit_employee_profile', kwargs={'employee_id': employee.id})
        return reverse('home')
    
    def get_login_redirect_url(self, request):
        """
        Para logins posteriores (no el primer signup)
        """
        return reverse('home')
    
    def send_confirmation_mail(self, request, emailconfirmation, signup):
        """
        Deshabilitar el envío de email de confirmación
        Ya no necesitamos este paso
        """
        pass  # No enviar email de confirmación