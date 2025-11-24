from django.urls import path

from . import views

app_name = 'nomina'

urlpatterns = [
    path('', views.nomina_dashboard, name='dashboard'),
    path('periodos/crear/', views.create_pay_period, name='create_period'),
    path('periodos/<int:period_id>/revisar/', views.review_pay_period, name='review_period'),
    path('periodos/<int:period_id>/aprobar-todos/', views.approve_all_workdays, name='approve_all'),
    path('periodos/<int:period_id>/generar-nomina/', views.generate_payroll, name='generate_payroll'),
    path('workday/<int:workday_id>/toggle-aprobar/', views.toggle_workday_approval, name='toggle_approval'),
]