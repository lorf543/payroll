from django.urls import path

from . import views

app_name = 'qasystem'

urlpatterns = [
    path('',views.dashboard,name='dashboard'),
    path('create-category',views.create_category,name='create_category'),
    path('create-question',views.create_question,name='create_question'),
]
