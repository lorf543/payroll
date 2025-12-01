# it/urls.py
from django.urls import path
from . import views

app_name = 'it'

urlpatterns = [
    path('dashboard/', views.it_dashboard, name='dashboard'),
    # path('device-tokens/', views.device_token_management, name='device_tokens'),
    # path('bulk-invite/', views.bulk_employee_invitation, name='bulk_invite'),
    # path('tickets/', views.ticket_system, name='ticket_system'),
    # path('inventory/', views.inventory_management, name='inventory'),
    # path('user-management/', views.user_management, name='user_management'),
    # path('security-center/', views.security_center, name='security_center'),
    # ... más URLs para las otras herramientas
]