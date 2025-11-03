from django.urls import path

from . import views

urlpatterns = [
    path('',views.home_view,name='home'),
    path('list-employees',views.list_employees,name='list_employees'),
    path('log-all',views.logout_all_users,name='logout_all_users'),
]
