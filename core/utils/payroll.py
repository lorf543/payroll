from decimal import Decimal

def get_effective_pay_rate(employee, total_hours=None):
    """
    Simplified version without campaign logic
    """
    # Safe defaults
    base_rate = Decimal('0.00')
    pay_type = 'hourly'
    
    # Determine base rate
    if employee.custom_base_salary is not None:
        base_rate = employee.custom_base_salary
        pay_type = 'fixed' if employee.fixed_rate else 'hourly'
    elif employee.fixed_rate and employee.position and employee.position.base_salary:
        base_rate = employee.position.base_salary
        pay_type = 'fixed'
    elif not employee.fixed_rate and employee.position and employee.position.hour_rate:
        base_rate = employee.position.hour_rate
        pay_type = 'hourly'
    
    # Handle total_hours
    if total_hours is None:
        total_hours = Decimal('0')
    elif not isinstance(total_hours, Decimal):
        total_hours = Decimal(str(total_hours))
    
    # Calculate net salary
    if pay_type == 'hourly':
        # Simple calculation without overtime for now
        net_salary = total_hours * base_rate
    else:
        # Fixed monthly salary
        net_salary = base_rate
    
    return {
        'pay_rate': base_rate,
        'base_rate': base_rate,
        'overtime_rate': Decimal('0.00'),
        'bonus': Decimal('0.00'),
        'pay_type': pay_type,
        'net_salary': net_salary,
    }