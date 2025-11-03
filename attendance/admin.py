from django.contrib import admin

from .models import WorkDay,ActivitySession

# Register your models here.

admin.site.register(WorkDay)



@admin.register(ActivitySession)
class ActivitySessionAdmin(admin.ModelAdmin):
    search_fields = ('work_day','session_type')
    list_display = ('work_day','session_type')
    list_filter = ('session_type',)
    
