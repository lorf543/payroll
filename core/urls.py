from django.urls import path

from . import views

urlpatterns = [
    path('',views.home_view,name='home'),
    path('list-employees',views.list_employees,name='list_employees'),
    path('log-all',views.logout_all_users,name='logout_all_users'),


    path('management/dashboard/', views.ManagementDashboardView.as_view(), name='management_dashboard'),
    path('management/campaign/<int:campaign_id>/', views.campaign_detail_dashboard, name='campaign_detail'),
    #path('management/export-campaign/<int:campaign_id>/', views.export_campaign_report, name='export_campaign_report'),

]
