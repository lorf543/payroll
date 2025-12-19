# urls.py
from django.urls import path
from . import views

app_name = 'evaluation'

urlpatterns = [
    # Dashboard
    path('', views.evaluation_dashboard, name='dashboard'),
    
    # Category URLs
    path('categories/', views.category_list, name='category_list'),
    path('categories/new/', views.category_create, name='category_create'),
    path('categories/<int:pk>/edit/', views.category_update, name='category_update'),
    path('categories/<int:pk>/delete/', views.category_delete, name='category_delete'),
    
    # Question URLs
    path('questions/', views.question_list, name='question_list'),
    path('questions/new/', views.question_create, name='question_create'),
    path('questions/<int:pk>/edit/', views.question_update, name='question_update'),
    path('questions/<int:pk>/delete/', views.question_delete, name='question_delete'),
    
    # Evaluation URLs
    path('evaluations/', views.evaluation_list, name='evaluation_list'),
    path('evaluations/new/', views.evaluation_create, name='evaluation_create'),
    path('evaluations/<int:pk>/edit/', views.evaluation_update, name='evaluation_update'),
    path('evaluations/<int:pk>/delete/', views.evaluation_delete, name='evaluation_delete'),
]