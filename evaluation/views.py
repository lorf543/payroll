# views.py
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from .models import Category, Question, Evaluation
from .forms import CategoryForm, QuestionForm, EvaluationForm

# ========== CATEGORY CRUD ==========
@login_required
def category_list(request):
    categories = Category.objects.all()
    return render(request, 'evaluation/category_list.html', {'categories': categories})

@login_required
def category_create(request):
    if request.method == 'POST':
        form = CategoryForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, 'Categoría creada exitosamente.')
            return redirect('evaluation:category_list')
    else:
        form = CategoryForm()
    return render(request, 'evaluation/category_form.html', {'form': form, 'title': 'New Category'})

@login_required
def category_update(request, pk):
    category = get_object_or_404(Category, pk=pk)
    if request.method == 'POST':
        form = CategoryForm(request.POST, instance=category)
        if form.is_valid():
            form.save()
            messages.success(request, 'Categoría actualizada exitosamente.')
            return redirect('evaluation:category_list')
    else:
        form = CategoryForm(instance=category)
    return render(request, 'evaluation/category_form.html', {'form': form, 'title': 'Edit Category'})

@login_required
def category_delete(request, pk):
    category = get_object_or_404(Category, pk=pk)
    if request.method == 'POST':
        category.delete()
        messages.success(request, 'Categoría eliminada exitosamente.')
        return redirect('evaluation:category_list')
    return render(request, 'evaluation/category_confirm_delete.html', {'category': category})

# ========== QUESTION CRUD ==========
@login_required
def question_list(request):
    questions = Question.objects.select_related('category').all()
    return render(request, 'evaluation/question_list.html', {'questions': questions})

@login_required
def question_create(request):
    if request.method == 'POST':
        form = QuestionForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, 'Pregunta creada exitosamente.')
            return redirect('evaluation:question_list')
    else:
        form = QuestionForm()
    return render(request, 'evaluation/question_form.html', {'form': form, 'title': 'New Question'})

@login_required
def question_update(request, pk):
    question = get_object_or_404(Question, pk=pk)
    if request.method == 'POST':
        form = QuestionForm(request.POST, instance=question)
        if form.is_valid():
            form.save()
            messages.success(request, 'Pregunta actualizada exitosamente.')
            return redirect('evaluation:question_list')
    else:
        form = QuestionForm(instance=question)
    return render(request, 'evaluation/question_form.html', {'form': form, 'title': 'Edit Question'})

@login_required
def question_delete(request, pk):
    question = get_object_or_404(Question, pk=pk)
    if request.method == 'POST':
        question.delete()
        messages.success(request, 'Pregunta eliminada exitosamente.')
        return redirect('evaluation:question_list')
    return render(request, 'evaluation/question_confirm_delete.html', {'question': question})

# ========== EVALUATION CRUD ==========
@login_required
def evaluation_list(request):
    evaluations = Evaluation.objects.select_related('employee', 'evaluator', 'question').all()
    return render(request, 'evaluation/evaluation_list.html', {'evaluations': evaluations})

@login_required
def evaluation_create(request):
    if request.method == 'POST':
        form = EvaluationForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, 'Evaluación creada exitosamente.')
            return redirect('evaluation:evaluation_list')
    else:
        form = EvaluationForm()
    return render(request, 'evaluation/evaluation_form.html', {'form': form, 'title': 'New Evaluation'})

@login_required
def evaluation_update(request, pk):
    evaluation = get_object_or_404(Evaluation, pk=pk)
    if request.method == 'POST':
        form = EvaluationForm(request.POST, instance=evaluation)
        if form.is_valid():
            form.save()
            messages.success(request, 'Evaluación actualizada exitosamente.')
            return redirect('evaluation:evaluation_list')
    else:
        form = EvaluationForm(instance=evaluation)
    return render(request, 'evaluation/evaluation_form.html', {'form': form, 'title': 'Edit Evaluation'})

@login_required
def evaluation_delete(request, pk):
    evaluation = get_object_or_404(Evaluation, pk=pk)
    if request.method == 'POST':
        evaluation.delete()
        messages.success(request, 'Evaluación eliminada exitosamente.')
        return redirect('evaluation:evaluation_list')
    return render(request, 'evaluation/evaluation_confirm_delete.html', {'evaluation': evaluation})

# ========== DASHBOARD ==========
@login_required
def evaluation_dashboard(request):
    total_evaluations = Evaluation.objects.count()
    total_questions = Question.objects.count()
    total_categories = Category.objects.count()
    
    # Promedio de calificaciones
    from django.db.models import Avg
    avg_score = Evaluation.objects.aggregate(Avg('score'))['score__avg'] or 0
    
    # Últimas evaluaciones
    recent_evaluations = Evaluation.objects.select_related(
        'employee', 'evaluator', 'question'
    ).order_by('-date')[:5]
    
    context = {
        'total_evaluations': total_evaluations,
        'total_questions': total_questions,
        'total_categories': total_categories,
        'avg_score': round(avg_score, 2),
        'recent_evaluations': recent_evaluations,
    }
    
    return render(request, 'evaluation/dashboard.html', context)