from django_q.tasks import async_task
from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string
from django.urls import reverse
from django.contrib import messages
from django.shortcuts import render, redirect
from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.templatetags.static import static
from email.mime.image import MIMEImage
from django.templatetags.static import static as get_static_path
import os

MAX_EMAILS = 20
def send_employee_invitation(email, position_id, department_id, supervisor_id, 
    campaign_id, hire_date, custom_identification, base_url):

    from core.models import Employee, User, Position, Department, Campaign
    
    position = Position.objects.get(id=position_id)
    department = Department.objects.get(id=department_id)
    campaign = Campaign.objects.get(id=campaign_id)
    supervisor = Employee.objects.get(id=supervisor_id) if supervisor_id else None
    
    try:
        if Employee.objects.filter(email=email).exists() or User.objects.filter(email=email).exists():
            return {"status": "skipped", "email": email, "reason": "Email already exists"}
        
        employee = Employee.objects.create(
            email=email,
            position=position,
            department=department,
            supervisor=supervisor,
            current_campaign=campaign,
            hire_date=hire_date
        )
        
        if custom_identification:
            employee.identification = custom_identification
            employee.save()
        
        employee.campaigns.add(campaign)
        
        signup_url = f"{base_url}{reverse('account_signup')}?email={email}"
        
        # CAMBIO: Usar Content ID para imagen embebida
        html_content = render_to_string("emails/invitation.html", {
            "email": email,
            "signup_url": signup_url,
            "position": position.name,
            "department": department.name,
            "hire_date": hire_date.strftime("%Y-%m-%d"),
            "supervisor": supervisor.full_name if supervisor else "",
            "logo_url": "cid:company_logo", 
        })
        
        msg = EmailMultiAlternatives(
            subject="Employee Portal Registration Invitation",
            from_email=settings.EMAIL_HOST_USER,
            to=[email]
        )
        msg.attach_alternative(html_content, "text/html")
        
        # Adjuntar imagen como inline
        logo_path = os.path.join(settings.BASE_DIR, 'static', 'img', 'company_logo.png')
        
        if os.path.exists(logo_path):
            with open(logo_path, 'rb') as img:
                logo_img = MIMEImage(img.read())
                logo_img.add_header('Content-ID', '<company_logo>')
                logo_img.add_header('Content-Disposition', 'inline', filename='company_logo.png')
                msg.attach(logo_img)
        
        msg.send()
        
        return {"status": "success", "email": email}
        
    except Exception as e:
        return {"status": "error", "email": email, "error": str(e)}

# Optional: View to check task status
@login_required
def check_invitation_status(request):
    """
    Optional view to check the status of queued invitations
    """
    from django_q.models import Task
    
    # Get recent tasks from the employee_invitations group
    recent_tasks = Task.objects.filter(
        group='employee_invitations'
    ).order_by('-started')[:50]
    
    stats = {
        'total': recent_tasks.count(),
        'success': recent_tasks.filter(success=True).count(),
        'failed': recent_tasks.filter(success=False).count(),
        'pending': Task.objects.filter(group='employee_invitations', success=None).count()
    }
    
    return render(request, 'bulk/invitation_status.html', {
        'tasks': recent_tasks,
        'stats': stats
    })