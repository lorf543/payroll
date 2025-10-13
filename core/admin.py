from django.contrib import admin
from import_export import resources
from .models import (
    Department, Position, Employee,
    PaymentConcept, PayPeriod,Payment,
    Campaign
)




@admin.register(Campaign)
class CampaignAdmin(admin.ModelAdmin):
    list_display = ("name", "client_name")
    filter_horizontal = ("employees",) 
    
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


class TeamMemberInline(admin.TabularInline):
    model = Employee
    fk_name = 'supervisor'
    extra = 1
    fields = ('employee_code', 'user', 'department', 'position', 'is_active')
    show_change_link = True




class TeamMemberInline(admin.TabularInline):
    model = Employee
    fk_name = 'supervisor'
    extra = 1
    fields = ('employee_code', 'user', 'department', 'position', 'is_active')
    show_change_link = True

class EmployeeAdmin(admin.ModelAdmin):
    list_display = ('employee_code', 'identification', 'user', 'position', 'is_active','department')
    list_filter = ('is_active', 'position', 'gender', 'marital_status')
    search_fields = ('employee_code', 'identification', 'user__username', 'user__email')
    raw_id_fields = ('user', 'supervisor')
    
    fieldsets = (
        # Authentication & Basic Info
        ('Authentication & Basic Information', {
            'fields': (
                'user',
                'employee_code', 
                'identification',
                'is_active'
            ),
            'classes': ('collapse',)  # Makes this section collapsible
        }),
        
        # Employment Details
        ('Employment Details', {
            'fields': (
                'position',
                'hire_date',
                'is_supervisor',
                'is_it',
                'department'
            )
        }),
        
        # Personal Information
        ('Personal Information', {
            'fields': (
                'birth_date',
                'gender', 
                'marital_status',
            )
        }),
        
        # Contact Information
        ('Contact Information', {
            'fields': (
                'phone',
                'email',
                'address',
                'city',
                'country'
            )
        }),
        
        # Profile & Professional Details
        ('Profile & Professional Details', {
            'fields': (
                'bio',
                'education',
                'skills'
            ),
            'classes': ('collapse',)  # Makes this section collapsible
        }),
        
        # Salary Information
        ('Salary Information', {
            'fields': (
                'fixed_rate',
                'custom_base_salary'
            ),
            'classes': ('collapse',)  # Makes this section collapsible
        }),
        
        # Banking Information
        ('Banking Information', {
            'fields': (
                'bank_name',
                'bank_account'
            ),
            'classes': ('collapse',)  # Makes this section collapsible
        }),
    )
    
    # You can also group fields in the add form differently if needed
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
                'deparment'
            )
        }),
    )


    inlines = [TeamMemberInline]

    def get_inlines(self, request, obj):
        # Mostrar el inline solo si el empleado es un supervisor
        if obj and obj.is_supervisor:
            return [TeamMemberInline]
        return []
    
admin.site.register(Employee, EmployeeAdmin)


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

