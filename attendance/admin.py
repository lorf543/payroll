from django.contrib import admin

from .models import Attendance,LeaveType,AgentStatus,StatusSchedule

# Register your models here.

admin.site.register(Attendance)
admin.site.register(LeaveType)
admin.site.register(AgentStatus)
admin.site.register(StatusSchedule)