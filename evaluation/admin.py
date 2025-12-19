# admin.py
from django.contrib import admin
from .models import Category, Question, Evaluation

@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ['name', 'description']
    search_fields = ['name']

@admin.register(Question)
class QuestionAdmin(admin.ModelAdmin):
    list_display = ['text', 'category', 'weight']
    list_filter = ['category']
    search_fields = ['text']

@admin.register(Evaluation)
class EvaluationAdmin(admin.ModelAdmin):
    list_display = ['employee', 'evaluator', 'question', 'score', 'date']
    list_filter = ['date', 'employee', 'evaluator']
    search_fields = ['employee__username', 'evaluator__username', 'comments']