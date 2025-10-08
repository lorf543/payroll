from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib import messages
from django.views import View
from .models import DeviceToken
import hashlib



class FirstTimeDeviceSetupView(View):
    def get(self, request):
        if not request.user.is_authenticated:
            return redirect('account_login')
            
        # Check if user already has a device token
        if hasattr(request.user, 'device_token'):
            return redirect('home')
            
        return render(request, 'device_auth/first_time_setup.html')
    
    def post(self, request):
        if not request.user.is_authenticated:
            return redirect('account_login')
            
        # Create device token
        device_token = DeviceToken(user=request.user)
        device_fingerprint = device_token.generate_device_fingerprint(request)
        
        device_token.device_fingerprint = device_fingerprint
        device_token.save()
        
        messages.success(request, "Device registered successfully!")
        return redirect('home')

class DeviceNotAuthorizedView(View):
    def get(self, request):
        if not request.user.is_authenticated:
            return redirect('account_login')
        return render(request, 'device_auth/device_not_authorized.html')

def is_it_staff(user):
    return user.is_staff or user.is_superuser

@login_required
@user_passes_test(is_it_staff)
def it_device_management(request):
    device_tokens = DeviceToken.objects.select_related('user').all()
    
    if request.method == 'POST':
        token_id = request.POST.get('token_id')
        action = request.POST.get('action')
        
        device_token = get_object_or_404(DeviceToken, id=token_id)
        
        if action == 'deactivate':
            device_token.is_active = False
            device_token.save()
            messages.success(request, f"Device token for {device_token.user.username} has been deactivated.")
        elif action == 'activate':
            device_token.is_active = True
            device_token.save()
            messages.success(request, f"Device token for {device_token.user.username} has been activated.")
        elif action == 'delete':
            username = device_token.user.username
            device_token.delete()
            messages.success(request, f"Device token for {username} has been deleted.")
            
        return redirect('it_device_management')
    
    return render(request, 'device_auth/it_device_management.html', {
        'device_tokens': device_tokens
    })

@login_required
@user_passes_test(is_it_staff)
def reset_user_device(request, user_id):
    from django.contrib.auth.models import User
    
    user = get_object_or_404(User, id=user_id)
    
    # Delete existing device token
    DeviceToken.objects.filter(user=user).delete()
    
    messages.success(
        request, 
        f"Device token for {user.username} has been reset. They can now register a new device on next login."
    )
    return redirect('it_device_management')