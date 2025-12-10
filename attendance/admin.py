from django.contrib import admin

from .models import WorkDay,ActivitySession, Occurrence

# Register your models here.

admin.site.register(WorkDay)



@admin.register(Occurrence)
class OccurrenceAdmin(admin.ModelAdmin):
    search_fields = ('employee','occurrence_type')
    list_filter = ('occurrence_type',)


@admin.register(ActivitySession)
class ActivitySessionAdmin(admin.ModelAdmin):
    search_fields = ('work_day','session_type')
    list_display = ('work_day','session_type')
    list_filter = ('session_type',)
    
