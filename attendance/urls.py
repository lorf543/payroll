from django.urls import path
from django.shortcuts import redirect

from . import views

urlpatterns = [
    path('dashboard/', views.agent_dashboard, name='agent_dashboard'),
    path('start-activity/', views.start_activity, name='start_activity'),
    path('end-work-day/', views.end_work_day, name='end_work_day'),
    path('history/', views.attendance_history, name='attendance_history'),
    path('history/<str:date_str>/', views.day_detail, name='day_detail'),

    path('profile/', views.employee_profile, name='employee_profile'),
    path('profile/<int:employee_id>/', views.employee_profile, name='employee_profile_detail'),
    path('profile/<int:employee_id>/edit/', views.edit_employee_profile, name='edit_employee_profile'),

    path('dashboard-supervisor/', views.supervisor_dashboard, name='supervisor_dashboard'),
    path('team/history/', views.team_attendance_history, name='team_attendance_history'),
    path('employee/<int:employee_id>/attendance/', views.employee_attendance_detail, name='employee_attendance_detail'),
    path('employee/<int:employee_id>/day/<str:date_str>/', views.supervisor_day_detail, name='supervisor_day_detail'),

    path('attendance/export-csv/', views.export_attendance_excel, name='export_attendance_excel'),
    path('employee/<int:employee_id>/export-csv/', views.export_employee_attendance_excel, name='export_employee_attendance_excel'),
    path('team/report/export/', views.export_team_report_excel, name='export_team_report_excel'),

    path('edit-session/<int:pk>/', views.edit_session, name='edit_session'), #ojo con esta remover si funiona el drag adjust
    path('force-logout', views.force_logout_all_users, name='force_logout_all_users'),

    path('slider/<int:workday_id>/', views.workday_editor_view, name='workday_editor_view'),
    path('update_session/<int:session_id>/', views.update_session, name='update_session'),


]


