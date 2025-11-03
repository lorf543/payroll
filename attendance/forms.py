from django import forms
from .models import Employee
from django.contrib.auth.models import User

class EmployeeProfileForm(forms.ModelForm):
    # Campos del User model
    first_name = forms.CharField(
        max_length=30, 
        required=True,
        widget=forms.TextInput(attrs={'class': 'form-control'})
    )
    last_name = forms.CharField(
        max_length=30, 
        required=True,
        widget=forms.TextInput(attrs={'class': 'form-control'})
    )

    class Meta:
        model = Employee
        fields = [
            # Personal Info
            'identification', 'gender', 'marital_status', 'birth_date', 'phone',
            'address', 'city', 'country',
            # Profile  
            'education', 'email', 'skills', 'bio',
            # Banking
            # 'bank_name', 'bank_account'
        ]
        widgets = {
            # Personal Info
            'identification': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Enter identification number'
            }),
            'gender': forms.Select(attrs={'class': 'form-control'}),
            'marital_status': forms.Select(attrs={'class': 'form-control'}),
            'birth_date': forms.DateInput(attrs={
                'class': 'form-control',
                'type': 'date'
            }),
            'phone': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Enter phone number'
            }),
            'address': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 3,
                'placeholder': 'Enter full address'
            }),
            'city': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Enter city'
            }),
            'country': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Enter country'
            }),
            # Profile
            'education': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Enter education level'
            }),
            'email': forms.EmailInput(attrs={
                'class': 'form-control',
                'placeholder': 'Enter email address'
            }),
            'skills': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 3,
                'placeholder': 'Enter skills separated by commas'
            }),
            'bio': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 4,
                'placeholder': 'Enter a brief biography'
            }),
            # Banking
            # 'bank_name': forms.TextInput(attrs={
            #     'class': 'form-control',
            #     'placeholder': 'Enter bank name'
            # }),
            # 'bank_account': forms.TextInput(attrs={
            #     'class': 'form-control', 
            #     'placeholder': 'Enter bank account number'
            # }),
        }
        labels = {
            # Personal Info
            'identification': 'Identification Number',
            'gender': 'Gender',
            'marital_status': 'Marital Status',
            'birth_date': 'Birth Date',
            'phone': 'Phone Number',
            'address': 'Address',
            'city': 'City',
            'country': 'Country',
            # Profile
            'education': 'Education',
            'email': 'Email Address',
            'skills': 'Skills',
            'bio': 'Biography',
            # Banking
            'bank_name': 'Bank Name',
            'bank_account': 'Bank Account Number',
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance and self.instance.user:
            self.fields['first_name'].initial = self.instance.user.first_name
            self.fields['last_name'].initial = self.instance.user.last_name

    def clean_email(self):
        email = self.cleaned_data.get('email')
        if email:
            # Verificar que el email no esté en uso por otro empleado
            employees_with_email = Employee.objects.filter(email=email)
            if self.instance and self.instance.pk:
                employees_with_email = employees_with_email.exclude(pk=self.instance.pk)
            
            if employees_with_email.exists():
                raise forms.ValidationError("This email is already in use by another employee.")
        return email

    def save(self, commit=True):
        employee = super().save(commit=False)
        
        # Actualizar el usuario relacionado
        if employee.user:
            employee.user.first_name = self.cleaned_data['first_name']
            employee.user.last_name = self.cleaned_data['last_name']
            if commit:
                employee.user.save()
        
        if commit:
            employee.save()
        
        return employee