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
    
    path('my-payments/', views.EmployeePaymentListView.as_view(), name='employee_payments'),
    path('payment/<int:pk>/', views.PaymentDetailView.as_view(), name='payment_detail'),
    path('payment/<int:pk>/approve/', views.PaymentApprovalView.as_view(), name='payment_approve'),
    path('payment/<int:pk>/reject/', views.PaymentRejectionView.as_view(), name='payment_reject'),
    
    path('payment/<int:payment_id>/confirm-isr/', views.confirm_isr, name='confirm_isr'),
    path('payment/<int:payment_id>/unlock-isr/', views.unlock_isr, name='unlock_isr'),
]