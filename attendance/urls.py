from django.urls import path

from . import views

urlpatterns = [ 

    
    path('', views.agent_status_dashboard, name='agent_status_dashboard'),
    path('agent/<int:agent_id>/change-status/', views.change_agent_status, name='change_agent_status'),

    path('payroll-dashboard/', views.employee_payroll_dashboard, name='payroll_dashboard'),

    path('supervisor-dashboard/', views.supervisor_dashboard, name='supervisor_dashboard'),
]
