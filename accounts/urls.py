# urls.py
from django.urls import path
from . import views

urlpatterns = [
    path('first-time-setup/', views.FirstTimeDeviceSetupView.as_view(), name='first_time_device_setup'),
    path('device-not-authorized/', views.DeviceNotAuthorizedView.as_view(), name='device_not_authorized'),
    path('it-admin/device-management/', views.it_device_management, name='it_device_management'),
    path('it-admin/reset-device/<int:user_id>/', views.reset_user_device, name='reset_user_device'),

    path('accounts/password/change/', views.CustomPasswordChangeView.as_view(), name='account_change_password'),
]