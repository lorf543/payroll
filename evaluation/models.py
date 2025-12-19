from django.db import models
from django.conf import settings
from django.core.validators import MinValueValidator, MaxValueValidator
# Create your models here.  

class Category(models.Model):
    name = models.CharField(max_length=100, unique=True)
    description = models.TextField(blank=True)
    
    def __str__(self):
        return self.name 
    
    class Meta:
        verbose_name_plural = "Categories"
        ordering = ['name']

class Question(models.Model): 
    text = models.TextField()
    category = models.ForeignKey(Category, on_delete=models.CASCADE, related_name='questions')
    weight = models.DecimalField(max_digits=5, decimal_places=2, default=1.0)

    def __str__(self):
        return self.text[:50] + "..." if len(self.text) > 50 else self.text

class Evaluation(models.Model):
    employee = models.ForeignKey(
        settings.AUTH_USER_MODEL, 
        on_delete=models.CASCADE, 
        related_name='evaluations_received'
    )
    evaluator = models.ForeignKey(
        settings.AUTH_USER_MODEL, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True, 
        related_name='evaluations_given'
    )
    question = models.ForeignKey(
        Question, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True, 
        related_name='evaluations'
    )
    score = models.DecimalField(
        max_digits=5, 
        decimal_places=2,
        validators=[MinValueValidator(0), MaxValueValidator(10)]
    )
    comments = models.TextField(blank=True)
    date = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f'Evaluación para {self.employee} - {self.score}'
    
    class Meta:
        ordering = ['-date']
        verbose_name_plural = "Evaluations"

