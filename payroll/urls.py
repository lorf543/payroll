"""
URL configuration for payroll project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/5.2/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.contrib import admin
from django.urls import path,include
from django.conf import settings
from django.conf.urls.static import static
from django.views.generic import TemplateView
import os

urlpatterns = [
    path('',include('core.urls')),
    path('', include('pwa.urls')),
    path('admin/', admin.site.urls),
    path('employee/', include('attendance.urls')),
    path('account/',include('accounts.urls')),
    path('accounts/', include('allauth.urls')),
    path('hhrr/', include('hhrr.urls')),
    path('payments/', include('payment.urls')),
    path('it_management/', include('it_management.urls')),
]


if settings.DEBUG:
    # Archivos estáticos
    urlpatterns += static(settings.STATIC_URL, document_root=os.path.join(settings.BASE_DIR, 'static'))
    # Archivos media
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
