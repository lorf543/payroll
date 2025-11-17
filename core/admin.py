from django.contrib import admin
from django import forms

from .models import (
    Department, Position, Employee,
    PaymentConcept, PayPeriod,Payment,
    Campaign,BulkInvitation
)


admin.site.site_header = "Payroll Administration"
admin.site.site_title = "Payroll Admin Portal"
admin.site.index_title = "Payroll Administration"


admin.site.register(BulkInvitation)


@admin.register(Campaign)
class CampaignAdmin(admin.ModelAdmin):
    list_display = ("name", "client_name")
    # filter_horizontal = ("employees",) 
    
@admin.register(Department)
class DepartmentAdmin(admin.ModelAdmin):
    list_display = ("name", "annual_budget", "description")
    search_fields = ("name",)
    ordering = ("name",)


@admin.register(Position)
class PositionAdmin(admin.ModelAdmin):
    list_display = ("name", "contract_type", "base_salary")
    search_fields = ("name",)
    list_filter = ( "contract_type",)
    ordering = ("name",)


class SupervisorForm(forms.ModelForm):
    team_members = forms.ModelMultipleChoiceField(
        queryset=Employee.objects.filter(is_supervisor=False),
        required=False,
        widget=admin.widgets.FilteredSelectMultiple('Team Members', is_stacked=False)
    )

    class Meta:
        model = Employee
        fields = '__all__'

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance.pk:
            # Mostrar solo los empleados que no son supervisores y que no tienen supervisor asignado
            self.fields['team_members'].initial = Employee.objects.filter(supervisor=self.instance)

    def save(self, commit=True):
        instance = super().save(commit=False)
        if commit:
            instance.save()
            self.save_m2m()

        # # Primero quitamos a los empleados que antes estaban bajo este supervisor
        # Employee.objects.filter(supervisor=instance).update(supervisor=None)

        # Asignamos los seleccionados como subordinados
        for emp in self.cleaned_data['team_members']:
            emp.supervisor = instance
            emp.save()

        return instance


@admin.register(Employee)
class EmployeeAdmin(admin.ModelAdmin):
    form = SupervisorForm

    list_display = (
        'employee_code', 'identification', 'user', 'position',
        'is_active', 'department', 'supervisor', 'is_logged_in'
    )
    list_filter = ('is_active', 'position', 'gender', 'marital_status', 'supervisor')
    search_fields = (
        'employee_code', 'identification', 'user__username',
        'user__email', 'supervisor__user__username'
    )
    raw_id_fields = ('user', 'supervisor')

    filter_horizontal = ('campaigns',)

    # Fieldsets originales con supervisor y nueva sección de team_members
    fieldsets = (
        ('Authentication & Basic Information', {
            'fields': (
                'user',
                'employee_code',
                'identification',
                'is_active',
                'is_logged_in'
            )
        }),
        ('Campaign Settings', {
            'fields': (
                'campaigns',
                'current_campaign',
                'last_login',
                'last_logout',
            ),
            'classes': ('collapse',)
        }),
        ('Employment Details', {
            'fields': (
                'position',
                'department',
                'hire_date',
                'is_supervisor',
                'is_it',
                'supervisor',
                'team_members', 
            )
        }),
        ('Personal Information', {
            'fields': (
                'birth_date',
                'gender',
                'marital_status',
            ),
            'classes': ('collapse',)
        }),
        ('Contact Information', {
            'fields': (
                'phone',
                'email',
                'address',
                'city',
                'country'
            ),
            'classes': ('collapse',)
        }),
        ('Profile & Professional Details', {
            'fields': (
                'bio',
                'education',
                'skills'
            ),
            'classes': ('collapse',)
        }),
        ('Salary Information', {
            'fields': (
                'fixed_rate',
                'custom_base_salary'
            ),
            'classes': ('collapse',)
        }),
        ('Banking Information', {
            'fields': (
                'bank_name',
                'bank_account'
            ),
            'classes': ('collapse',)
        }),
    )

    add_fieldsets = (
        ('Required Information', {
            'fields': (
                'user',
                'employee_code',
                'identification',
                'position',
                'department',
                'hire_date',
                'birth_date',
                'gender'
            )
        }),
    )




@admin.register(PaymentConcept)
class PaymentConceptAdmin(admin.ModelAdmin):
    list_display = ("name", "type", "code", "fixed_amount", "percentage", "taxable", "is_active")
    search_fields = ("name", "code")
    list_filter = ("type", "taxable", "is_active")
    ordering = ("type", "name")


@admin.register(PayPeriod)
class PayPeriodAdmin(admin.ModelAdmin):
    list_display = ("name", "start_date", "end_date", "pay_date", "frequency", "is_closed")
    list_filter = ("frequency", "is_closed")
    search_fields = ("name",)
    ordering = ("-start_date",)




@admin.register(Payment)
class PayrollRecordAdmin(admin.ModelAdmin):
    list_display = ("employee", "period", "pay_date", "gross_salary", "net_salary", "status")
    search_fields = ("employee__user__first_name", "employee__user__last_name", "period__name")
    list_filter = ("status", "period",)
    ordering = ("-pay_date",)
    date_hierarchy = "pay_date"

