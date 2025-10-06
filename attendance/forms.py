from django import forms
from .models import AgentStatus

class AgentStatusForm(forms.ModelForm):

    status = forms.ChoiceField(
        choices=AgentStatus.STATUS_CHOICES,
        widget=forms.Select(attrs={
            'class': 'form-select form-select',
        }),
        label='Select New Status'
    )
    class Meta:
        model = AgentStatus
        fields = ['status']
