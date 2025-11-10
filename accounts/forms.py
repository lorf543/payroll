# forms.py
from django import forms
from django.core.validators import validate_email
from core.models import Employee, Position, Department, Campaign
from django.utils import timezone

from allauth.account.forms import SignupForm


class EmailForm(forms.Form):
    email = forms.EmailField(widget=forms.EmailInput(attrs={'class': 'form-control'}))
    identification = forms.CharField(
        required=False,
        widget=forms.TextInput(attrs={'class': 'form-control'})
    )


class CustomSignupForm(SignupForm):
    """
    Formulario de registro simplificado que solo pide contraseña
    cuando el usuario viene de una invitación por email
    """
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        # Email es read-only y viene pre-llenado desde la URL
        if 'email' in self.fields:
            self.fields['email'].widget.attrs.update({
                'readonly': True,
                'class': 'form-control bg-light'
            })
        
        # Eliminar username si usas autenticación por email
        if 'username' in self.fields:
            del self.fields['username']
        
        # Solo mostrar password1 (crear contraseña)
        if 'password1' in self.fields:
            self.fields['password1'].widget.attrs['class'] = 'form-control'
            self.fields['password1'].label = "Crear Contraseña"
            self.fields['password1'].help_text = "Tu contraseña debe tener al menos 8 caracteres"
        
        # Eliminar password2 para simplificar (opcional)
        # Si quieres mantener la confirmación, descomenta las siguientes líneas:
        if 'password2' in self.fields:
            self.fields['password2'].widget.attrs['class'] = 'form-control'
            self.fields['password2'].label = "Confirmar Contraseña"
    
    def clean_email(self):
        """
        Prevenir que el email sea modificado
        Verificar que el email existe en Employee
        """
        email = self.cleaned_data.get('email')
        
        # Si hay un email inicial (de la URL), usarlo
        initial_email = self.initial.get('email')
        if initial_email:
            email = initial_email
        
        # Verificar que existe un Employee con este email
        if not Employee.objects.filter(email=email).exists():
            raise forms.ValidationError(
                "No se encontró una invitación válida para este email. "
                "Por favor contacta a Recursos Humanos."
            )
        
        return email


class EmployeeInvitationForm(forms.Form):
    campaign = forms.ModelChoiceField(
        queryset=Campaign.objects.all(),
        widget=forms.Select(attrs={'class': 'form-control'}),
        required=True,
        label="Campaña"
    )
    position = forms.ModelChoiceField(
        queryset=Position.objects.all(),
        widget=forms.Select(attrs={'class': 'form-control'}),
        required=True,
        label="Posición"
    )
    department = forms.ModelChoiceField(
        queryset=Department.objects.all(),
        widget=forms.Select(attrs={'class': 'form-control'}),
        required=True,
        label="Departamento"
    )
    supervisor = forms.ModelChoiceField(
        queryset=Employee.objects.filter(is_supervisor=True),
        required=False,
        widget=forms.Select(attrs={'class': 'form-control'}),
        label="Supervisor"
    )
    hire_date = forms.DateField(
        widget=forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
        initial=timezone.now().date(),
        required=True,
        label="Fecha de Contratación"
    )


class EmployeeEmailForm(forms.Form):
    email = forms.EmailField(
        required=False,
        widget=forms.EmailInput(attrs={
            'class': 'form-control',
            'placeholder': 'empleado@empresa.com'
        }),
        label="Email"
    )
    identification = forms.CharField(
        max_length=50,
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Identificación personalizada (opcional)'
        }),
        help_text="Dejar en blanco para auto-generación",
        label="Identificación"
    )