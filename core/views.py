from django.shortcuts import render

# Create your views here.

def home_view(request):
    return render(request,'index.html')


def employees_view(request):
    return render(request,'core/employees.html')


def employees_detail(request):
    return render(request,'core/employee_detail.html')