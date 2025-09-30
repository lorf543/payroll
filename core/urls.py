from django.urls import path

from . import views

urlpatterns = [
    path('',views.home_view,name='home'),
    path('employees/',views.employees_view,name='employees'),
    path('admin_dashboard/',views.admin_dashboard,name='admin_dashboard'),
    
    path('employees/<int:employee_id>/',views.employees_detail,name='employees_detail'),
    path('perfil-edit/<int:employee_id>/',views.perfil_edit,name='perfil_edit'),
    
]
