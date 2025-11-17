# views.py
from django.db.models import Q
from django.core.paginator import Paginator
from django.shortcuts import render, get_object_or_404,redirect
from django.contrib.auth.decorators import login_required, user_passes_test
from django.http import JsonResponse, HttpResponse
from django.template.loader import render_to_string

import tempfile
import os



from core.models import Employee, Position, Campaign, Department

def is_hr_user(user):
    """Check if user is HR staff or superuser"""
    return user.is_superuser or user.groups.filter(name='HR').exists()

@login_required
def employee_id_cards_list(request):
    employees = Employee.objects.select_related(
        'user', 'position', 'department', 'current_campaign'
    ).filter(is_active=True)

    # filtros
    department_filter = request.GET.get('department')
    position_filter = request.GET.get('position')
    campaign_filter = request.GET.get('campaign')
    search_query = request.GET.get('search')
    status_filter = request.GET.get('status')

    if department_filter:
        employees = employees.filter(department_id=department_filter)
    if position_filter:
        employees = employees.filter(position_id=position_filter)
    if campaign_filter:
        employees = employees.filter(current_campaign_id=campaign_filter)
    if status_filter:
        if status_filter == 'logged_in':
            employees = employees.filter(is_logged_in=True)
        elif status_filter == 'logged_out':
            employees = employees.filter(is_logged_in=False)
    if search_query:
        employees = employees.filter(
            Q(user__first_name__icontains=search_query) |
            Q(user__last_name__icontains=search_query) |
            Q(employee_code__icontains=search_query) |
            Q(user__email__icontains=search_query)
        )

    paginator = Paginator(employees, 20)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    departments = Department.objects.all()
    positions = Position.objects.all()
    campaigns = Campaign.objects.filter(is_active=True)

    selected_employees = request.session.get('selected_employees', [])
    # asegurar que la lista en sesión tiene ints
    selected_employees = [int(x) for x in selected_employees]

    context = {
        'page_obj': page_obj,
        'departments': departments,
        'positions': positions,
        'campaigns': campaigns,
        'selected_count': len(selected_employees),
        'selected_employees': selected_employees, 
        'search_query': search_query or '',
        'filters': {
            'department': department_filter,
            'position': position_filter,
            'campaign': campaign_filter,
            'status': status_filter,
        }
    }
    return render(request, 'hhrr/employee_id_cards_list.html', context)


@login_required
def toggle_employee_selection(request, employee_id):
    if request.method == 'POST' and request.headers.get('x-requested-with') == 'XMLHttpRequest':
        employee = get_object_or_404(Employee, id=employee_id, is_active=True)
        selected_employees = request.session.get('selected_employees', [])
        # normalizar a ints
        selected_employees = [int(x) for x in selected_employees]

        eid = int(employee_id)
        if eid in selected_employees:
            selected_employees.remove(eid)
            action = 'removed'
        else:
            selected_employees.append(eid)
            action = 'added'

        request.session['selected_employees'] = selected_employees
        request.session.modified = True

        return JsonResponse({
            'success': True,
            'action': action,
            'selected_count': len(selected_employees),
            'employee_id': eid
        })
    return JsonResponse({'success': False, 'error': 'Invalid request'})


@login_required
def clear_selection(request):
    if request.method == 'POST':
        request.session['selected_employees'] = []
        request.session.modified = True
        if request.headers.get('x-requested-with') == 'XMLHttpRequest':
            return JsonResponse({'success': True, 'selected_count': 0})
        return redirect('employee_id_cards_list')
    return JsonResponse({'success': False})