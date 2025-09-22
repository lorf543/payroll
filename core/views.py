from django.shortcuts import render
from django.contrib.auth.decorators import login_required

# Create your views here.

def home_view(request):
    return render(request,'index.html')

@login_required(login_url='home')
def employees_view(request):
    return render(request,'core/employees.html')

@login_required(login_url='home')
@login_required
def employees_detail(request):
    return render(request,'core/employee_detail.html')