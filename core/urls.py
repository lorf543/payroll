from django.urls import path

from . import views
from . import class_view

urlpatterns = [
    path('',views.home_view,name='home'),
    path('list-employees',views.list_employees,name='list_employees'),
    path('log-all',views.logout_all_users,name='logout_all_users'),


    path('management/dashboard/', class_view.ManagementDashboardView.as_view(), name='management_dashboard'),
    path('management/campaign/<int:campaign_id>/', views.campaign_detail_dashboard, name='campaign_detail'),
    path('info-payment',views.info_payment,name='info_payment')

]
