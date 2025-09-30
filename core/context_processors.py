# core/context_processors.py
from .models import Employee

def employee_context(request):
    context = {}
    if request.user.is_authenticated:
        try:
            employee = Employee.objects.get(user=request.user)
            context['employee'] = employee
        except Employee.DoesNotExist:
            # Si el usuario no tiene empleado asociado
            context['employee'] = None
    else:
        context['employee'] = None
    
    return context