from django.contrib import admin
from import_export import resources
from .models import (
    Department, Position, Employee,
    PaymentConcept, PayPeriod,Payment
)


@admin.register(Department)
class DepartmentAdmin(admin.ModelAdmin):
    list_display = ("name", "annual_budget", "description")
    search_fields = ("name",)
    ordering = ("name",)


@admin.register(Position)
class PositionAdmin(admin.ModelAdmin):
    list_display = ("name", "department", "contract_type", "base_salary")
    search_fields = ("name", "department__name")
    list_filter = ("department", "contract_type")
    ordering = ("department", "name")


@admin.register(Employee)
class EmployeeAdmin(admin.ModelAdmin):
    list_display = ("employee_code", "full_name", "position", "department", "hire_date", "is_active","identification")
    search_fields = ("employee_code", "user__first_name", "user__last_name", "position__name", "department__name")
    list_filter = ("department", "position", "is_active", "gender", "marital_status")
    ordering = ("employee_code",)
    readonly_fields = ("full_name",)


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


# class PayrollDetailInline(admin.TabularInline):
#     model = PayrollDetail
#     extra = 1



@admin.register(Payment)
class PayrollRecordAdmin(admin.ModelAdmin):
    list_display = ("employee", "period", "pay_date", "gross_salary", "net_salary", "status")
    search_fields = ("employee__user__first_name", "employee__user__last_name", "period__name")
    list_filter = ("status", "period", "employee__department")
    ordering = ("-pay_date",)
    date_hierarchy = "pay_date"


# @admin.register(PayrollDetail)
# class PayrollDetailAdmin(admin.ModelAdmin):
#     list_display = ("payroll_record", "concept", "quantity", "amount")
#     search_fields = ("concept__name", "payroll_record__employee__user__first_name", "payroll_record__employee__user__last_name")
#     list_filter = ("concept",)


# @admin.register(Attendance)
# class AttendanceAdmin(admin.ModelAdmin):
#     list_display = ("employee", "date", "check_in", "check_out", "hours_worked", "overtime_hours")
#     search_fields = ("employee__user__first_name", "employee__user__last_name")
#     list_filter = ("date", "employee__department")
#     ordering = ("-date",)


# @admin.register(Incident)
# class IncidentAdmin(admin.ModelAdmin):
#     list_display = ("employee", "type", "date", "end_date", "justified")
#     search_fields = ("employee__user__first_name", "employee__user__last_name", "type")
#     list_filter = ("type", "justified", "date")
#     ordering = ("-date",)
