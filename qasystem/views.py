from django.shortcuts import render,redirect
from django.contrib import messages
from django.db import IntegrityError

from .models import (
    QAConfig, Category, Question, Call, Evaluation, 
    QuestionResponse, EvaluationTemplate, AgentMetrics, 
    Dispute, CalibrationSession, QualityStandard
)

from .forms import QAConfigForm, CategoryForm, QuestionForm, ScorecardForm
from core.models import Campaign, Employee
# Create your views here.


def dashboard(request):

    context = {}
    return render(request,'qasystem/dashboard.html',context)



def create_category(request):
    if request.method == "POST":
        form = CategoryForm(request.POST)
        if form.is_valid():
            try:
                category = form.save()
                messages.success(request, f'Category "{category.name}" created successfully!')
                return redirect('qasystem:create_category')  
            except IntegrityError:
                messages.error(request, 'A category with this name already exists.')
        
    else:
        form = CategoryForm()

    context = {"form": form}
    return render(request, 'qasystem/create_category.html', context)

def create_question(request):
    if request.method == "POST":
        form = QuestionForm(request.POST)
        if form.is_valid():
            try:
                category = form.save()
                messages.success(request, f'Category "{category.text}" created successfully!')
                return redirect('qasystem:create_category')  
            except IntegrityError:
                messages.error(request, 'A category with this name already exists.')
        
    else:
        form = QuestionForm()

    context = {"form": form}
    return render(request, 'qasystem/create_question.html', context)


def create_scorecard(request):
    if request.method == 'POST':
        form = ScorecardForm(request.POST)
        if form.is_valid():
            scorecard = form.save(commit=False)
            scorecard.created_by = request.user
            scorecard.save()

            # Guardar preguntas
            form.save_m2m()

            # 🔥 Asignar categorías automáticamente
            categories = Category.objects.filter(
                questions__in=scorecard.questions.all()
            ).distinct()

            scorecard.categories.set(categories)

            messages.success(request, "Scorecard created successfully!")
            return redirect('qasystem:scorecard_list')
    else:
        form = ScorecardForm()

    return render(request, 'qasystem/create_scorecard.html', {'form': form})