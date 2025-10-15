from datetime import datetime, time, timedelta
from django.utils.timezone import now
from django.utils import timezone
from decimal import Decimal

from .models import Attendance, AgentStatus


def timedelta_to_hours(td):
    return Decimal(td.total_seconds()) / Decimal(3600)

def format_timedelta(td):
    total_seconds = int(td.total_seconds())
    hours, remainder = divmod(total_seconds, 3600)
    minutes = (remainder // 60)
    return f"{hours}h {minutes}m"


def calculate_employee_pay(employee, payable_time):
    """
    Calcula el pago del empleado basado en su configuración:
    1. Fixed rate (pago fijo diario)
    2. Hourly rate (pago por hora)
    3. Base salary + hourly (mixto)
    """
    payable_hours = timedelta_to_hours(payable_time)
    
    # 1. Empleado con salario fijo (independiente de horas trabajadas)
    if employee.fixed_rate:
        if employee.custom_base_salary and employee.custom_base_salary > 0:
            # Salario fijo personalizado
            daily_salary = employee.custom_base_salary / 22  # Asumiendo 22 días laborales al mes
            return round(daily_salary, 2), "fixed_custom"
        elif employee.position.base_salary and employee.position.base_salary > 0:
            # Salario fijo basado en posición
            daily_salary = employee.position.base_salary / 22
            return round(daily_salary, 2), "fixed_position"
        else:
            # Salario fijo por defecto
            return round(employee.position.hour_rate * 8, 2), "fixed_default"
    
    # 2. Empleado por horas
    else:
        if employee.custom_base_salary and employee.custom_base_salary > 0:
            # Pago por horas con tarifa personalizada
            return round(employee.custom_base_salary * payable_hours, 2), "hourly_custom"
        else:
            # Pago por horas con tarifa de posición
            return round(employee.position.hour_rate * payable_hours, 2), "hourly_position"



def get_payment_method_display(employee):
    """Retorna la descripción del método de pago"""
    if employee.fixed_rate:
        if employee.custom_base_salary:
            return f"Salario fijo: ${employee.custom_base_salary:,.2f}/mes"
        elif employee.position.base_salary:
            return f"Salario fijo: ${employee.position.base_salary:,.2f}/mes"
        else:
            return f"Salario fijo: ${employee.position.hour_rate * 8 * 22:,.2f}/mes"
    else:
        if employee.custom_base_salary:
            return f"Por horas: ${employee.custom_base_salary:,.2f}/hora"
        else:
            return f"Por horas: ${employee.position.hour_rate:,.2f}/hora"


def get_last_day_of_month(date):
    """Devuelve el último día del mes dado."""
    next_month = date.replace(day=28) + timedelta(days=4)
    return next_month - timedelta(days=next_month.day)

def get_pay_periods(reference_date, periods=6):
    """Genera periodos de pago quincenales hacia atrás desde la fecha de referencia."""
    periods_list = []

    # Determinar si estamos en la primera o segunda quincena
    if reference_date.day <= 15:
        current_start = reference_date.replace(day=1)
        current_end = reference_date.replace(day=15)
    else:
        current_start = reference_date.replace(day=16)
        current_end = get_last_day_of_month(reference_date)

    # Generar los periodos hacia atrás
    for _ in range(periods):
        periods_list.append({
            'start_date': current_start,
            'end_date': current_end,
            'name': f"{current_start.strftime('%b %d')} - {current_end.strftime('%b %d, %Y')}",
            'is_current': len(periods_list) == 0
        })

        # Retroceder una quincena
        if current_start.day == 16:
            # Ir a la primera quincena del mismo mes
            current_end = current_start.replace(day=15)
            current_start = current_start.replace(day=1)
        else:
            # Ir a la segunda quincena del mes anterior
            prev_month = (current_start.replace(day=1) - timedelta(days=1))
            current_start = prev_month.replace(day=16)
            current_end = get_last_day_of_month(prev_month)

    return periods_list

def calculate_pay_period_data(employee, start_date, end_date):
    """Calcula estadísticas para un periodo específico"""
    start_datetime = timezone.make_aware(datetime.combine(start_date, time.min))
    end_datetime = timezone.make_aware(datetime.combine(end_date, time.max))
    
    # Obtener registros del periodo
    records = AgentStatus.objects.filter(
        agent=employee,
        start_time__range=(start_datetime, end_datetime)
    ).order_by('-start_time')
    
    # Calcular tiempos
    total_payable = timedelta()
    total_break = timedelta()
    total_lunch = timedelta()
    
    for record in records:
        end_time = record.end_time or timezone.now()
        if end_time > end_datetime:
            end_time = end_datetime
        if record.start_time < start_datetime:
            start_time = start_datetime
        else:
            start_time = record.start_time
            
        duration = end_time - start_time
        
        if record.status == 'ready':
            total_payable += duration
        elif record.status == 'break':
            total_break += duration
        elif record.status == 'lunch':
            total_lunch += duration
    
    # Calcular pago
    earnings, pay_method = calculate_employee_pay(employee, total_payable)
    
    return {
        'start_date': start_date,
        'end_date': end_date,
        'total_payable': total_payable,
        'total_break': total_break,
        'total_lunch': total_lunch,
        'payable_hours': timedelta_to_hours(total_payable),
        'earnings': earnings,
        'pay_method': pay_method,
        'days_worked': records.dates('start_time', 'day').count(),
    }

def get_recent_daily_stats(employee, days=7):
    """Obtiene estadísticas diarias detectando sesiones de trabajo completas"""
    daily_stats = []
    
    for i in range(days):
        day = timezone.localdate() - timedelta(days=i)
        day_start = timezone.make_aware(datetime.combine(day, time.min))
        day_end = timezone.make_aware(datetime.combine(day, time.max))
        
        records = AgentStatus.objects.filter(
            agent=employee,
            start_time__range=(day_start, day_end)
        ).order_by('start_time')
        
        # Detectar sesiones de trabajo (IN -> OUT)
        work_sessions = []
        current_session_start = None
        
        for record in records:
            if record.status == 'ready' and not current_session_start:
                # Inicio de sesión de trabajo
                current_session_start = record
            elif record.status != 'ready' and current_session_start:
                # Fin de sesión de trabajo
                work_sessions.append({
                    'start': current_session_start,
                    'end': record
                })
                current_session_start = None
        
        # Si hay una sesión sin terminar
        if current_session_start:
            work_sessions.append({
                'start': current_session_start,
                'end': None
            })
        
        # Obtener IN y OUT del día
        first_in = work_sessions[0]['start'] if work_sessions else None
        last_out = None
        
        if work_sessions:
            last_session = work_sessions[-1]
            last_out = last_session['end'] if last_session['end'] else last_session['start']
        
        # Calcular horas trabajadas
        daily_payable = timedelta()
        for session in work_sessions:
            end_time = session['end'].start_time if session['end'] else min(timezone.now(), day_end)
            start_time = session['start'].start_time
            daily_payable += (end_time - start_time)
        
        daily_earnings, _ = calculate_employee_pay(employee, daily_payable)
        
        daily_stats.append({
            'date': day,
            'payable_hours': timedelta_to_hours(daily_payable),
            'earnings': daily_earnings,
            'is_weekend': day.weekday() >= 5,
            'records_count': records.count(),
            'first_in': first_in,
            'last_out': last_out,
            'work_sessions': work_sessions,
        })
    
    return daily_stats