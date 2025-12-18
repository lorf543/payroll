from django import forms
from .models import EmployeeSchedule, Employee

WEEKDAY_CHOICES = [
    ("monday","Monday"),("tuesday","Tuesday"),("wednesday","Wednesday"),
    ("thursday","Thursday"),("friday","Friday"),("saturday","Saturday"),
    ("sunday","Sunday"),
]

class EmployeeScheduleForm(forms.ModelForm):
    employee = forms.ModelChoiceField(
        queryset=Employee.objects.all(),
        widget=forms.Select(attrs={"class": "form-control"})
    )

    custom_first_break_time = forms.TimeField(
        required=False, 
        widget=forms.TimeInput(attrs={
            "class": "form-control",
            "type": "time"
        })
    )
    
    custom_second_break_time = forms.TimeField(
        required=False,
        widget=forms.TimeInput(attrs={
            "class": "form-control", 
            "type": "time"
        })
    )

    custom_lunch_time = forms.TimeField(
        required=False,
        widget=forms.TimeInput(attrs={
            "class": "form-control",
            "type": "time"
        })
    )

    custom_start_time = forms.TimeField(
        required=False,
        widget=forms.TimeInput(attrs={
            "class": "form-control", 
            "type": "time"
        })
    )

    start_date = forms.DateField(
        widget=forms.DateInput(attrs={
            "class": "form-control", 
            "type": "date"
        })
    )

    primary_weekday = forms.ChoiceField(
        choices=WEEKDAY_CHOICES,
        required=False,
        widget=forms.Select(attrs={"class": "form-control"})
    )

    class Meta:
        model = EmployeeSchedule
        fields = (
            "employee", "start_date", "primary_weekday", "custom_start_time",
            "custom_first_break_time", "custom_second_break_time", "custom_lunch_time"
        )