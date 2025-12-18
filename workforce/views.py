import io
import csv
import json
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import render, redirect, get_object_or_404,get_list_or_404
from django.db import transaction
from datetime import datetime, date
from django.http import HttpResponse
from django.db.models import Q
from django.utils import timezone
from datetime import datetime
from datetime import datetime, timedelta
from django.views.generic import CreateView
from django.views.decorators.http import require_GET

from .models import Employee, Shift, EmployeeSchedule
from .forms import EmployeeScheduleForm
from django.forms import modelformset_factory

@login_required
def bulk_assign_schedule(request):
    days_of_week = [
        ('monday', 'Monday'),
        ('tuesday', 'Tuesday'),
        ('wednesday', 'Wednesday'),
        ('thursday', 'Thursday'),
        ('friday', 'Friday'),
        ('saturday', 'Saturday'),
        ('sunday', 'Sunday'),
    ]

    employees = Employee.objects.filter(is_active=True)
    shifts = Shift.objects.filter(is_active=True).order_by('name')

    if request.method == "POST":
        employee_ids = request.POST.getlist("employees")
        shift_id = request.POST.get("shift")
        start_date_str = request.POST.get("start_date")
        end_date_str = request.POST.get("end_date")

        # Validate required fields
        if not employee_ids:
            messages.error(request, "Please select at least one employee.")
            return redirect("bulk_assign_schedule")
        
        if not shift_id:
            messages.error(request, "Please select a shift.")
            return redirect("bulk_assign_schedule")
        
        if not start_date_str:
            messages.error(request, "Please select a start date.")
            return redirect("bulk_assign_schedule")

        # Parse dates
        try:
            start_date = datetime.strptime(start_date_str, '%Y-%m-%d').date()
            end_date = datetime.strptime(end_date_str, '%Y-%m-%d').date() if end_date_str else None
            
            # Validate date range
            if end_date and end_date < start_date:
                messages.error(request, "End date cannot be earlier than start date.")
                return redirect("bulk_assign_schedule")
                
        except ValueError:
            messages.error(request, "Invalid date format.")
            return redirect("bulk_assign_schedule")

        # Get days selection
        days = {
            "monday": request.POST.get("monday") == "true",
            "tuesday": request.POST.get("tuesday") == "true",
            "wednesday": request.POST.get("wednesday") == "true",
            "thursday": request.POST.get("thursday") == "true",
            "friday": request.POST.get("friday") == "true",
            "saturday": request.POST.get("saturday") == "true",
            "sunday": request.POST.get("sunday") == "true",
        }

        # Check if at least one day is selected
        if not any(days.values()):
            messages.error(request, "Please select at least one day.")
            return redirect("bulk_assign_schedule")

        try:
            shift = Shift.objects.get(id=shift_id, is_active=True)
        except Shift.DoesNotExist:
            messages.error(request, "Selected shift does not exist or is not active.")
            return redirect("bulk_assign_schedule")

        created = 0
        errors = []
        
        # Use transaction for data consistency
        with transaction.atomic():
            for emp_id in employee_ids:
                try:
                    employee = Employee.objects.get(id=emp_id, is_active=True)
                    
                    # Check if schedule already exists for this date range
                    existing_schedules = EmployeeSchedule.objects.filter(
                        employee=employee,
                        start_date__lte=end_date if end_date else start_date,
                        end_date__gte=start_date,
                        shift=shift
                    ).exists()
                    
                    if existing_schedules:
                        errors.append(f"{employee}: Schedule conflict for selected dates")
                        continue
                    
                    EmployeeSchedule.objects.create(
                        employee=employee,
                        shift=shift,
                        start_date=start_date,
                        end_date=end_date,
                        status="published",
                        created_by=request.user,
                        **days
                    )
                    created += 1
                    
                except Employee.DoesNotExist:
                    errors.append(f"Employee ID {emp_id} not found or inactive")
                except Exception as e:
                    errors.append(f"Error creating schedule for employee ID {emp_id}: {str(e)}")

        if created > 0:
            messages.success(
                request,
                f"Successfully created {created} schedule(s)."
            )
        
        if errors:
            messages.warning(
                request,
                f"Some schedules could not be created. {len(errors)} error(s) occurred."
            )
            # Store errors in session for detailed display if needed
            request.session['bulk_schedule_errors'] = errors[:5]  # Store first 5 errors
        
        return redirect("bulk_assign_schedule")

    # Clear any previous errors from session
    if 'bulk_schedule_errors' in request.session:
        del request.session['bulk_schedule_errors']

    context = {
        "employees": employees,
        "shifts": shifts,
        "days_of_week": days_of_week,
        "today": timezone.now().date(),
    }
    
    return render(
        request,
        "workforce/bulk_assign_schedule.html",
        context,
    )


@login_required
def listschedule(request):
    # Get filter parameters
    employee_id = request.GET.get('employee')
    shift_id = request.GET.get('shift')
    status = request.GET.get('status')
    start_date = request.GET.get('start_date')
    end_date = request.GET.get('end_date')
    upcoming = request.GET.get('upcoming')
    
    # Base queryset
    schedules = EmployeeSchedule.objects.select_related(
        'employee', 'shift',
    )
    
    # Apply filters
    if employee_id:
        schedules = schedules.filter(employee_id=employee_id)
    
    if shift_id:
        schedules = schedules.filter(shift_id=shift_id)
    
    
    if status:
        schedules = schedules.filter(status=status)
    
    if start_date:
        try:
            start_date_obj = datetime.strptime(start_date, '%Y-%m-%d').date()
            schedules = schedules.filter(start_date__gte=start_date_obj)
        except ValueError:
            pass
    
    if end_date:
        try:
            end_date_obj = datetime.strptime(end_date, '%Y-%m-%d').date()
            schedules = schedules.filter(
                Q(end_date__lte=end_date_obj) | Q(end_date__isnull=True),
                start_date__lte=end_date_obj
            )
        except ValueError:
            pass
    
    if upcoming == 'true':
        today = date.today()
        schedules = schedules.filter(
            Q(end_date__gte=today) | Q(end_date__isnull=True),
            start_date__gte=today
        )
    
    # Get filter options
    employees = Employee.objects.filter(is_active=True)
    shifts = Shift.objects.filter(is_active=True).order_by('name')
    
    # Status choices
    status_choices = [
        ('draft', 'Draft'),
        ('published', 'Published'),
        ('cancelled', 'Cancelled'),
    ]
    
    context = {
        'schedules': schedules,
        'employees': employees,
        'shifts': shifts,
        'status_choices': status_choices,
        'filter_params': request.GET,
        'today': date.today(),
        'total_schedules': schedules.count(),
    }
    
    return render(request, 'workforce/lists_schedule.html', context)

@login_required
def list_schedule_employee(request):
    employee = request.user.employee  
    
    schedules = EmployeeSchedule.objects.filter(
        employee=employee,
        status__in=['published', 'active']
    ).select_related('shift').order_by('-start_date')
    
    # Prepare JSON-serializable data with all custom overrides
    schedules_data = []
    for schedule in schedules:
        # Get active dates
        active_dates = schedule.get_schedule_for_date_range()
        
        # Calculate break times based on custom overrides or shift defaults
        break_details = schedule.get_break_schedule_details()
        
        schedule_data = {
            'id': schedule.id,
            'shift_name': schedule.shift.name,
            'shift_type': schedule.shift.shift_type,
            'status': schedule.status,
            'active_dates': [date.strftime('%Y-%m-%d') for date in active_dates],
            'start_date': schedule.start_date.strftime('%Y-%m-%d'),
            'end_date': schedule.end_date.strftime('%Y-%m-%d') if schedule.end_date else '',
            'custom_notes': schedule.notes or '',
            'times': {
                'start_time': schedule.get_effective_start_time().strftime('%H:%M'),
                'end_time': schedule.get_effective_end_time().strftime('%H:%M'),
                'total_hours': float(schedule.shift.expected_hours),
                'effective_hours': float(schedule.get_effective_hours()),
            },
            'breaks': {
                'break_count': schedule.get_effective_break_count(),
                'break_duration': schedule.get_effective_break_duration(),
                'lunch_duration': schedule.get_effective_lunch_duration(),
                'scheduled_breaks': break_details['scheduled_breaks'],
                'lunch_time': break_details['lunch_time'],
                'total_break_time_minutes': break_details['total_break_time_minutes'],
            },
            'has_custom_settings': any([
                schedule.custom_start_time,
                schedule.custom_end_time,
                schedule.custom_break_duration,
                schedule.custom_lunch_duration,
                schedule.custom_break_count,
                schedule.custom_first_break_time,
                schedule.custom_second_break_time,
                schedule.custom_lunch_time,
            ]),
        }
        schedules_data.append(schedule_data)
    
    context = {
        'employee': employee,
        'schedules': schedules,
        'schedules_json': json.dumps(schedules_data, default=str),
        'today': timezone.now().date().strftime('%Y-%m-%d'),
    }
    
    return render(request, 'workforce/lists_schedule_employee.html', context)

@login_required
def delete_schedule(request, schedule_id):
    if request.method == 'POST':
        try:
            schedule = EmployeeSchedule.objects.get(id=schedule_id)
            employee_name = schedule.employee
            schedule.delete()
            messages.success(request, f'Schedule for {employee_name} has been deleted successfully.')
        except EmployeeSchedule.DoesNotExist:
            messages.error(request, 'Schedule not found.')
        except Exception as e:
            messages.error(request, f'Error deleting schedule: {str(e)}')
    
    return redirect('list_schedule')

@login_required
def update_schedule_status(request, schedule_id):
    if request.method == 'POST':
        try:
            schedule = EmployeeSchedule.objects.get(id=schedule_id)
            new_status = request.POST.get('status')
            if new_status in ['draft', 'published', 'cancelled']:
                schedule.status = new_status
                schedule.save()
                messages.success(request, f'Schedule status updated to {new_status}.')
            else:
                messages.error(request, 'Invalid status.')
        except EmployeeSchedule.DoesNotExist:
            messages.error(request, 'Schedule not found.')
        except Exception as e:
            messages.error(request, f'Error updating schedule: {str(e)}')
    
    return redirect('listschedule')


#_________________________________

EmployeeScheduleFormSet = modelformset_factory(
    EmployeeSchedule,
    form=EmployeeScheduleForm,
    extra=1,
    can_delete=True
)

def create_schedule(request):
    if request.method == 'POST':
        formset = EmployeeScheduleFormSet(request.POST, queryset=EmployeeSchedule.objects.none())
        if formset.is_valid():
            formset.save()
            return redirect('schedule_success')
    else:
        formset = EmployeeScheduleFormSet(queryset=EmployeeSchedule.objects.none())

    return render(request, 'workforce/schedule_form.html', {
        'formset': formset
    })


def add_schedule_row(request):
    """
    HTMX: devuelve UNA nueva fila del formset
    """
    formset = EmployeeScheduleFormSet(queryset=EmployeeSchedule.objects.none())
    form = formset.empty_form

    return render(request, 'workforce/partials/schedule_row.html', {
        'form': form,
        'index': '__prefix__'
    })