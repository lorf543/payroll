from django.urls import path

from . import views

urlpatterns = [
    path('',views.home_view,name='home'),
    path('employees/',views.employees_view,name='employees'),
    path('employees-detail/',views.employees_detail,name='employees_detail'),
]
