# urls.py
from django.urls import path
from . import views

urlpatterns = [
    path('hhrr/id-cards/', views.employee_id_cards_list, name='employee_id_cards_list'),
    path('hhrr/id-cards/toggle/<int:employee_id>/', views.toggle_employee_selection, name='toggle_employee_selection'),
    path('hhrr/id-cards/clear/', views.clear_selection, name='clear_id_cards_selection'),

]