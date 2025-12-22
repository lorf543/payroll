from django import forms
from core.models import Employee

from .models import (
    QAConfig, Category, Question, Call, Evaluation, 
    QuestionResponse, EvaluationTemplate, AgentMetrics, 
    Dispute, CalibrationSession, QualityStandard
)


class QAConfigForm(forms.ModelForm):
    
    class Meta:
        model = QAConfig
        fields = "__all__"


class CategoryForm(forms.ModelForm):
    class Meta:
        model = Category
        fields = ("name", "description",)

        widgets = {
            'description': forms.Textarea(attrs={'rows': 3}),
            'weight': forms.NumberInput(attrs={
                'step': '0.01',
                'min': '0',
                'max': '1'
            }),
        }
    
    def clean_weight(self):
        weight = self.cleaned_data.get('weight')
        if weight < 0 or weight > 1:
            raise forms.ValidationError("Weight must be between 0 and 1")
        return weight
    

class QuestionForm(forms.ModelForm):
    class Meta:
        model = Question
        fields = [
            'text',
            'category',
            'category_type',
            'score_type',
            'weight',
            'max_score',
            'is_required',
            'is_active',
            'order',
            'critical'
        ]
        
        widgets = {
            'text': forms.Textarea(attrs={'rows': 3}),
            'category': forms.Select(attrs={'class': 'form-select'}),
            'category_type': forms.Select(attrs={'class': 'form-select'}),
            'score_type': forms.Select(attrs={'class': 'form-select'}),
            'weight': forms.NumberInput(attrs={'step': '0.01'}),
            'max_score': forms.NumberInput(attrs={'step': '0.01'}),
        }


    def clean_weight(self):
        weight = self.cleaned_data.get('weight')
        if weight <= 0:
            raise forms.ValidationError("Weight must be greater than 0")
        return weight
    
    def clean_max_score(self):
        max_score = self.cleaned_data.get('max_score')
        if max_score <= 0:
            raise forms.ValidationError("Max score must be greater than 0")
        return max_score
