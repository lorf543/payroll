# it/views.py
from django.contrib.auth.decorators import login_required
from django.shortcuts import render

@login_required
def it_dashboard(request):
    """IT Administration Dashboard"""
    # Aquí iría la lógica para obtener estadísticas del sistema
    # Por ahora, retornamos datos de ejemplo para el template
    
    context = {
        'active_users_count': 145,
        'pending_tickets_count': 8,
        'online_devices_count': 89,
        'laptops_count': 45,
        'desktops_count': 32,
        'mobiles_count': 12,
        'accessories_count': 67,
        'recent_tickets': [
            {'id': 101, 'subject': 'Cannot access payroll system', 'priority': 'high', 'status': 'open'},
            {'id': 102, 'subject': 'Printer not working in accounting', 'priority': 'medium', 'status': 'in_progress'},
            {'id': 103, 'subject': 'Email configuration issue', 'priority': 'low', 'status': 'open'},
        ],
        'system_alerts': [
            {'message': 'Backup scheduled for tonight at 2:00 AM'},
            {'message': 'System update available for deployment'},
        ],
        'recent_activity': [
            {'icon': 'person-plus', 'description': 'New user account created for John Doe', 'timestamp': '2 hours'},
            {'icon': 'key', 'description': 'Device token regenerated for Sales Department', 'timestamp': '4 hours'},
            {'icon': 'shield-check', 'description': 'Security policy updated', 'timestamp': '1 day'},
        ]
    }
    return render(request, 'it_management/dashboard.html', context)