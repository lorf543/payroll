# models.py
from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone
from datetime import datetime, timedelta
import humanize
import logging


from core.models import Campaign, Employee

logger = logging.getLogger(__name__)

class WorkDay(models.Model):
    STATUS_CHOICES = [
        ('active', 'Active'),
        ('completed', 'Completed'),
        ('absent', 'Absent'), 
        ('leave', 'On Leave'),        
    ]
    
    employee = models.ForeignKey(Employee, on_delete=models.CASCADE, related_name='work_days')
    date = models.DateField(default=timezone.now)
    
    # Timestamps principales
    check_in = models.DateTimeField(null=True, blank=True)
    check_out = models.DateTimeField(null=True, blank=True)
    
    # Estado del día
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='active')
    
    # Cálculos automáticos
    total_work_time = models.DurationField(default=timedelta(0))
    total_break_time = models.DurationField(default=timedelta(0))
    total_lunch_time = models.DurationField(default=timedelta(0))
    
    # Métricas
    productive_hours = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    break_count = models.IntegerField(default=0)
    
    notes = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        unique_together = ['employee', 'date']
        ordering = ['-date', 'employee']
        indexes = [
            models.Index(fields=['date', 'status']),
            models.Index(fields=['employee', 'date']),
        ]

    def __str__(self):
        return f"{self.employee} - {self.date} - {self.status}"
    

    def start_work_session(self, session_type='work', notes=None):
        """Iniciar una nueva sesión de trabajo"""
        # Si es "end_of_day", manejar de forma especial
        if session_type == 'end_of_day':
            return self.end_work_day()
        
        # Cerrar sesión anterior si existe
        self.end_current_session()
        
        session = ActivitySession.objects.create(
            work_day=self,
            session_type=session_type,
            start_time=timezone.now(),
            notes=notes
        )
        
        # Si es la primera sesión y es de trabajo, establecer check_in
        if session_type == 'work' and not self.check_in:
            self.check_in = timezone.now()
            self.save()
        
        return session
    
    def end_current_session(self):
        """Finalizar la sesión activa actual"""
        active_session = self.get_active_session()
        if active_session:
            active_session.end_time = timezone.now()
            active_session.save()
            logger.info(f"⏹️ Sesión {active_session.session_type} finalizada")
            return active_session
        return None
    
    def get_active_session(self):
        """Obtener la sesión activa actual"""
        return self.sessions.filter(end_time__isnull=True).first()
    
    def calculate_metrics(self):
        """Calcular todas las métricas automáticamente"""
        sessions = self.sessions.filter(end_time__isnull=False)
        
        total_work = timedelta(0)
        total_break = timedelta(0)
        total_lunch = timedelta(0)
        break_count = 0
        
        for session in sessions:
            # Ensure that session.duration is a timedelta
            if isinstance(session.duration, timedelta):
                if session.session_type == 'work':
                    total_work += session.duration
                elif session.session_type == 'break':
                    total_break += session.duration
                    break_count += 1
                elif session.session_type == 'lunch':
                    total_lunch += session.duration
            else:
                # Handle cases where session.duration is not a timedelta
                print(f"Unexpected duration type: {type(session.duration)} for session: {session}")

        self.total_work_time = total_work
        self.total_break_time = total_break
        self.total_lunch_time = total_lunch
        self.break_count = break_count
        self.productive_hours = round(total_work.total_seconds() / 3600, 2)
        
        self.save()
        return self.productive_hours
        # logger.info(self.productive_hours)
    
    @property
    def current_status(self):
        """Estado actual del empleado"""
        active_session = self.get_active_session()
        if active_session:
            return active_session.session_type
        return 'inactive'
    
    @property
    def hours_worked_decimal(self):
        """Horas trabajadas en formato decimal para compatibilidad"""
        return float(self.productive_hours)
    
    def end_work_day(self):
        """Finalizar el día de trabajo"""
        # Cerrar sesión activa
        self.end_current_session()
        
        # Establecer check_out
        self.check_out = timezone.now()
        self.status = 'completed'
        
        # Calcular métricas finales
        self.calculate_metrics()
        
        self.save()
        logger.info(f"🏁 Día laboral finalizado para {self.employee}")



    def get_formatted_session(self):
        """Obtener sesión formateada para display"""
        session = self.get_active_session()
        if not session:
            return None
            
        # Si es un objeto ActivitySession
        if hasattr(session, 'start_time'):
            return session.start_time.strftime("%H:%M:%S")
        
        # Si es un string
        session_str = str(session)
        if ' - ' in session_str:
            return session_str.split(' - ')[-1]
        
        return session_str

class ActivitySession(models.Model):
    SESSION_TYPES = [
        ('work', 'Working'),
        ('break', 'Break'),
        ('lunch', 'Almuerzo'),
        ('training', 'Training'),
        ('meeting', 'Meeting'),
        ('technical', 'Technical'),
    ]
    
    work_day = models.ForeignKey(WorkDay, on_delete=models.CASCADE, related_name='sessions')
    session_type = models.CharField(max_length=20, choices=SESSION_TYPES)
    
    # Timestamps
    start_time = models.DateTimeField()
    end_time = models.DateTimeField(null=True, blank=True)
    
    # Duración calculada automáticamente
    duration = models.DurationField(null=True, blank=True)
    
    # Metadata
    campaign = models.ForeignKey(Campaign, on_delete=models.SET_NULL, null=True, blank=True)
    notes = models.TextField(blank=True, null=True)
    auto_created = models.BooleanField(default=False)

    class Meta:
        ordering = ['start_time']

    def __str__(self):
        return f"{self.work_day.employee} - {self.session_type} - {self.start_time.time()}"

    def save(self, *args, **kwargs):
        # Calcular duración automáticamente
        if self.start_time and self.end_time:
            self.duration = self.end_time - self.start_time
        
        super().save(*args, **kwargs)
        
        # Actualizar métricas del WorkDay
        if self.end_time:
            self.work_day.calculate_metrics()


    @property
    def formatted_duration(self):
        """Devuelve la duración formateada de manera legible"""
        if not self.duration:
            return "—"
        
        total_seconds = int(self.duration.total_seconds())
        hours = total_seconds // 3600
        minutes = (total_seconds % 3600) // 60
        seconds = total_seconds % 60
        
        if hours > 0:
            return f"{hours}h {minutes:02d}m {seconds:02d}s"
        elif minutes > 0:
            return f"{minutes}m {seconds:02d}s"
        else:
            return f"{seconds}s"