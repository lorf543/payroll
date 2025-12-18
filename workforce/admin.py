# workforce/admin.py
from django.contrib import admin
from django.contrib import messages
from django.core.exceptions import ValidationError
from .models import Shift, EmployeeSchedule, TimeOffRequest, BreakSchedule


@admin.register(Shift)
class ShiftAdmin(admin.ModelAdmin):
    list_display = ['name', 'shift_type', 'formatted_time_range', 'expected_hours', 
                    'break_count', 'is_active', 'campaign']
    list_filter = ['shift_type', 'is_active', 'campaign']
    search_fields = ['name']
    
    fieldsets = (
        ('Basic information', {
            'fields': ('name', 'shift_type', 'campaign', 'is_active', 'color_code')
        }),
        ('Schudule', {
            'fields': ('start_time', 'end_time', 'expected_hours')
        }),
        ('Breaks and Lunch', {
            'fields': (
                'break_count', 'break_duration_minutes',
                'first_break_time', 'second_break_time',
                'lunch_duration_minutes', 'lunch_time'
            )
        }),
        ('Overtime', {
            'fields': ('allow_overtime', 'max_overtime_hours')
        }),
    )


@admin.register(EmployeeSchedule)
class EmployeeScheduleAdmin(admin.ModelAdmin):
    list_display = ['employee', 'shift', 'start_date', 'end_date', 'active_days', 'status']
    list_filter = ['status', 'shift', 'start_date']
    search_fields = ['employee__full_name', 'employee__employee_id']
    date_hierarchy = 'start_date'
    
    fieldsets = (
        ('Allocation', {
            'fields': ('employee', 'shift', 'status')
        }),
        ('Period', {
            'fields': ('start_date', 'end_date')
        }),
        ('Weekly days', {
            'fields': (
                'monday', 'tuesday', 'wednesday', 'thursday',
                'friday', 'saturday', 'sunday'
            )
        }),
        ('Customized Schedules (Optional)', {
            'fields': (
                'custom_start_time', 'custom_end_time', 
                'custom_break_duration', 'custom_lunch_duration',
                'custom_break_count', 'custom_first_break_time',
                'custom_second_break_time', 'custom_lunch_time'
            ),
            'classes': ('collapse',)
        }),
        ('Notes', {
            'fields': ('notes',)
        }),
    )
    
    def save_model(self, request, obj, form, change):
        """Override save to call clean() and show validation errors"""
        try:
            # Asignar el usuario que está creando/modificando
            if not change:  # Si es nuevo
                obj.created_by = request.user
            
            # Llamar al método clean() para validar
            obj.clean()
            
            # Si pasa la validación, guardar
            super().save_model(request, obj, form, change)
            
            # Mensaje de éxito
            messages.success(request, f'Schedule for {obj.employee.full_name} saved successfully.')
            
        except ValidationError as e:
            # Mostrar el error de validación al usuario
            messages.error(request, f'Validation Error: {e.message}')
            # NO guardar el objeto
            
        except Exception as e:
            # Cualquier otro error
            messages.error(request, f'Error saving schedule: {str(e)}')
            
@admin.register(TimeOffRequest)
class TimeOffRequestAdmin(admin.ModelAdmin):
    list_display = ['employee', 'request_type', 'start_date', 'end_date', 
                    'total_days', 'status', 'requested_at']
    list_filter = ['status', 'request_type', 'is_paid', 'start_date']
    search_fields = ['employee__full_name', 'reason']
    date_hierarchy = 'start_date'
    
    readonly_fields = ['requested_at', 'reviewed_at']
    
    fieldsets = (
        ('Employee', {
            'fields': ('employee',)
        }),
        ('Request', {
            'fields': ('request_type', 'start_date', 'end_date', 'reason', 'is_paid')
        }),
        ('Revision', {
            'fields': ('status', 'reviewed_by', 'reviewed_at', 'rejection_reason')
        }),
    )


@admin.register(BreakSchedule)
class BreakScheduleAdmin(admin.ModelAdmin):
    list_display = ['employee', 'date', 'break_type', 'scheduled_start_time', 
                    'scheduled_end_time', 'was_taken', 'compliance_status']
    list_filter = ['break_type', 'was_taken', 'date']
    search_fields = ['employee__full_name']
    date_hierarchy = 'date'