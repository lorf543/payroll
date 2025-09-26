from django.shortcuts import render
from django.contrib.auth.decorators import login_required

from django.shortcuts import render, get_object_or_404
from django.utils.timezone import now
from django.db.models import Sum, Count, Avg
from .models import Employee, Payment
# Create your views here.


@login_required(login_url='account_login')
def home_view(request):
    employee = get_object_or_404(Employee, user=request.user)
    payments = Payment.objects.filter(employee=employee)


    # Latest payment
    last_payment = payments.first()

    # Totals for the current year
    current_year = now().year
    year_payments = payments.filter(pay_date__year=current_year)
    total_year = year_payments.aggregate(total=Sum("net_salary"))["total"] or 0
    total_payments = year_payments.count()
    avg_monthly = total_year / 12 if total_year else 0

    context = {
        "employee": employee,
        "payments": payments,
        "last_payment": last_payment,
        "total_year": total_year,
        "total_payments": total_payments,
        "avg_monthly": avg_monthly,
    }
    return render(request, "index.html", context)

@login_required(login_url='account_login')
def employees_view(request):
    empleados = Employee.objects.all()

    context = {'empleados':empleados}
    return render(request,'core/employees.html', context)

@login_required(login_url='account_login')
@login_required
def employees_detail(request):
    return render(request,'core/employee_detail.html')