from django.urls import path

from . import views

urlpatterns = [ 

    
    path('', views.agent_status_dashboard, name='agent_status_dashboard'),
    path('agent/<int:agent_id>/change-status/', views.change_agent_status, name='change_agent_status'),

    path('payroll-dashboard/', views.employee_payroll_dashboard, name='payroll_dashboard'),

    path('supervisor/dashboard/', views.supervisor_dashboard, name='supervisor_dashboard'),
    path('supervisor/stats-api/', views.supervisor_stats_api, name='supervisor_stats_api'),
    path('supervisor/agents-api/', views.supervisor_agents_api, name='supervisor_agents_api'),
    path('supervisor/activity-api/', views.supervisor_activity_api, name='supervisor_activity_api'),
    path('supervisor/dashboard/partial/', views.supervisor_dashboard_partial, name='supervisor_dashboard_partial'),

    path('employee/<int:id_employee>/statuses/', views.employee_status_list, name='employee_status_list'),
    path('employee/<int:employee_id>/force-logout/', views.employee_force_logout, name='employee_force_logout'),
    path('status/<int:status_id>/add-note/', views.add_status_note, name='add_status_note'),

    path('employee/status-history/', views.employee_status_history, name='employee_status_history'),
    
    path('employees/export/excel/', views.export_employees_excel, name='export_employees_excel'),

]
