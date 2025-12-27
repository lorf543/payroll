from django.contrib import admin

from .models import WorkDay,ActivitySession, Occurrence
from attendance.models import Employee
from django.db.models import Q

# Register your models here.


@admin.register(WorkDay)
class WorkDayAdmin(admin.ModelAdmin):
    list_filter = ('status', 'check_in')
    
    # Busca en first_name y last_name del User vinculado al Employee
    search_fields = (
        'employee__user__first_name',
        'employee__user__last_name',
        'employee__user__username',      # opcional: por si buscan por username
        'employee__employee_code',       # útil buscar por código de empleado
    )
    
    # Opcional: mostrar el nombre completo en la lista
    list_display = ('employee__user__first_name','date', 'status', 'check_in', 'check_out')



@admin.register(Occurrence)
class OccurrenceAdmin(admin.ModelAdmin):
    search_fields = ('employee','occurrence_type')
    list_filter = ('occurrence_type',)


@admin.register(ActivitySession)
class ActivitySessionAdmin(admin.ModelAdmin):
    search_fields = ('work_day','session_type')
    list_display = ('work_day','session_type')
    list_filter = ('session_type',)

    
