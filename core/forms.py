# forms.py
from django import forms
from .models import Employee
from django.contrib.auth.models import User


class UploadCSVForm(forms.Form):
    file = forms.FileField()

class EmployeeForm(forms.ModelForm):
    # Campos del User model que quieras incluir
    first_name = forms.CharField(
        max_length=30, 
        required=True,
        label='Nombre'
    )
    last_name = forms.CharField(
        max_length=30, 
        required=True,
        label='Apellido'
    )
    email = forms.EmailField(
        required=True,
        label='Correo Electrónico'
    )
    
    phone = forms.CharField(
        max_length=20,
        required=False,
        label='Phone Number',
        widget=forms.TextInput(attrs={
            'placeholder': '(123) 456-7890',
        })
    )

        # Education choices dropdown
    EDUCATION_CHOICES = [
        ('', 'Select Education Level'),
        ('high_school', 'High School'),
        ('associate', 'Associate Degree'),
        ('bachelor', 'Bachelor\'s Degree'),
        ('master', 'Master\'s Degree'),
        ('phd', 'PhD'),
        ('professional', 'Professional Certification'),
        ('other', 'Other'),
    ]
    
    education = forms.ChoiceField(
        choices=EDUCATION_CHOICES,
        required=False,
        label='Education Level',
        widget=forms.Select(attrs={'class': 'form-select'})
    )
    class Meta:
        model = Employee
        fields = [
            'first_name', 'last_name', 'email', 
            'birth_date', 'gender', 'marital_status',
            'phone', 'address', 'city', 'country', 'is_active',
            'bio', 'education', 'skills',
        ]
        widgets = {
            'birth_date': forms.DateInput(attrs={'type': 'date'}),
            'bio': forms.Textarea(attrs={'rows': 3}),
            'address': forms.Textarea(attrs={'rows': 2}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance and self.instance.user:
            self.fields['first_name'].initial = self.instance.user.first_name
            self.fields['last_name'].initial = self.instance.user.last_name
            self.fields['email'].initial = self.instance.user.email

    def save(self, commit=True):
        employee = super().save(commit=False)
        if employee.user:
            user = employee.user
            user.first_name = self.cleaned_data['first_name']
            user.last_name = self.cleaned_data['last_name']
            user.email = self.cleaned_data['email']
            if commit:
                user.save()
                employee.save()
        return employee
