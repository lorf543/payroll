from django.urls import path
from . import views


urlpatterns = [
    path('bulk-assign-schedule',views.bulk_assign_schedule,name='bulk_assign_schedule'),
    path('lists-chedule',views.listschedule,name='list_schedule'),
    path('lists-chedule-eemployee',views.list_schedule_employee,name='list_schedule_eemployee'),

    path('schedule/create/', views.create_schedule, name='create_schedule'),
    path('schedule/add-row/', views.add_schedule_row, name='add_schedule_row'),
]

