# models.py
from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone
from datetime import timedelta
from decimal import Decimal
import logging


from core.models import Campaign, Employee

logger = logging.getLogger(__name__)

class WorkDay(models.Model):
    STATUS_CHOICES = [
        ('active', 'Active'),
        ('completed', 'Completed'),
        ('absent', 'Absent'), 
        ('leave', 'On Leave'),  
        ('regular_hours','Regular hours'),
        ('holyday','Holy Day')      
    ]
    
    employee = models.ForeignKey(Employee, on_delete=models.CASCADE, related_name='work_days')
    date = models.DateField(default=timezone.now)
    
    # Timestamps principales
    check_in = models.DateTimeField(null=True, blank=True)
    check_out = models.DateTimeField(null=True, blank=True)
    
    # Estado del día
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='regular_hours')
    
    # Cálculos automáticos
    total_work_time = models.DurationField(default=timedelta(0))
    total_break_time = models.DurationField(default=timedelta(0))
    total_lunch_time = models.DurationField(default=timedelta(0))
    
    # Métricas
    productive_hours = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    break_count = models.IntegerField(default=0)
    
    # NUEVOS CAMPOS PARA NÓMINA
    is_approved = models.BooleanField(default=False)
    approved_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='approved_workdays')
    approved_at = models.DateTimeField(null=True, blank=True)
    
    # Cálculos de pago
    regular_hours = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    overtime_hours = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    night_hours = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    holiday_hours = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    
    regular_pay = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    overtime_pay = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    total_pay = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    
    # Tarifas aplicadas (para auditoría)
    regular_rate = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    overtime_rate = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    
    notes = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    # Adjustment fields
    last_adjustment_reason = models.TextField(blank=True, null=True)
    adjustment_history = models.JSONField(default=list, blank=True) 
    last_adjusted_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    last_adjustment_date = models.DateTimeField(null=True, blank=True)
    adjustment_count_field = models.IntegerField(default=0)
    
    class Meta:
        unique_together = ['employee', 'date']
        ordering = ['-date', 'employee']
        indexes = [
            models.Index(fields=['date', 'status']),
            models.Index(fields=['employee', 'date']),
            models.Index(fields=['is_approved', 'date']),  # Nuevo índice
        ]

    def __str__(self):
        return f"{self.employee} - {self.date} - {self.status}"
    
    def save(self, *args, **kwargs):
        # Calcular horas automáticamente antes de guardar
        if self.productive_hours > 0:
            self.calculate_pay()
        super().save(*args, **kwargs)
    
    # En models.py - método calculate_pay
    def calculate_pay(self):
        """Calcular pagos basado en horas trabajadas"""
        from decimal import Decimal
        
        # Convertir productive_hours a Decimal de forma segura
        if isinstance(self.productive_hours, (int, float)):
            productive_hours = Decimal(str(self.productive_hours))
        else:
            # Si ya es Decimal o otro tipo
            productive_hours = Decimal(str(self.productive_hours))
        
        # Determinar tarifas - convertir todo a Decimal
        if self.employee.fixed_rate and self.employee.custom_base_salary:
            # Convertir a Decimal
            custom_salary = Decimal(str(self.employee.custom_base_salary))
            daily_rate = custom_salary / Decimal('30')
            self.regular_rate = daily_rate / Decimal('8') if productive_hours > Decimal('0') else Decimal('0')
        
        elif self.employee.position and self.employee.position.hour_rate:
            self.regular_rate = Decimal(str(self.employee.position.hour_rate))
        
        elif self.employee.current_campaign and self.employee.current_campaign.hour_rate:
            self.regular_rate = Decimal(str(self.employee.current_campaign.hour_rate))
        
        else:
            self.regular_rate = Decimal('0.00')
        
        # Calcular horas regulares vs overtime
        if productive_hours <= Decimal('8'):
            self.regular_hours = productive_hours
            self.overtime_hours = Decimal('0.00')
        else:
            self.regular_hours = Decimal('8.00')
            self.overtime_hours = productive_hours - Decimal('8.00')
        
        # Calcular overtime rate (1.5x regular rate)
        self.overtime_rate = self.regular_rate * Decimal('1.5')
        
        # Calcular pagos
        self.regular_pay = self.regular_hours * self.regular_rate
        self.overtime_pay = self.overtime_hours * self.overtime_rate
        self.total_pay = self.regular_pay + self.overtime_pay
        
        # Asegurar que todos los campos sean Decimal
        self.regular_hours = Decimal(str(self.regular_hours))
        self.overtime_hours = Decimal(str(self.overtime_hours))
        self.regular_pay = Decimal(str(self.regular_pay))
        self.overtime_pay = Decimal(str(self.overtime_pay))
        self.total_pay = Decimal(str(self.total_pay))
        
    def approve(self, approved_by_user):
        """Aprobar día para nómina"""
        self.is_approved = True
        self.approved_by = approved_by_user
        self.approved_at = timezone.now()
        self.save()
    
    def unapprove(self):
        """Desaprobar día"""
        self.is_approved = False
        self.approved_by = None
        self.approved_at = None
        self.save()

    # Tus métodos existentes se mantienen...
    def add_adjustment_record(self, adjusted_by, reason="", sessions_affected=None):
        """Agregar registro al historial de ajustes"""
        adjustment_record = {
            'timestamp': timezone.now().isoformat(),
            'adjusted_by': adjusted_by.username if adjusted_by else 'System',
            'adjusted_by_id': adjusted_by.id if adjusted_by else None,
            'reason': reason,
            'sessions_affected': sessions_affected or [],
            'before_state': {
                'total_work_time': str(self.total_work_time),
                'total_break_time': str(self.total_break_time),
                'total_lunch_time': str(self.total_lunch_time),
                'productive_hours': float(self.productive_hours)
            }
        }
        
        self.adjustment_history.append(adjustment_record)
        self.last_adjustment_reason = reason
        self.last_adjusted_by = adjusted_by
        self.last_adjustment_date = timezone.now()
        self.adjustment_count_field += 1
        self.save()

    def update_adjustment_info(self, adjusted_by):
        """Actualizar información de ajustes"""
        self.last_adjusted_by = adjusted_by
        self.last_adjustment_date = timezone.now()
        self.adjustment_count_field += 1
        self.save()

    def get_day_status(self):
        status_dict = dict(self.STATUS_CHOICES)
        return status_dict.get(self.status, self.status)

    @property
    def adjusted_sessions(self):
        """Sesiones que han sido ajustadas - para usar en templates"""
        return self.sessions.filter(is_adjusted=True).order_by('-adjustment_date')
    
    @property
    def adjustment_count(self):
        """Contar sesiones ajustadas - para usar en templates"""
        return self.sessions.filter(is_adjusted=True).count()
    
    @property
    def has_adjustments(self):
        """Verificar si hay ajustes - para condicionales en templates"""
        return self.sessions.filter(is_adjusted=True).exists()
    
    @property
    def total_work_minutes(self):
        """Total de minutos trabajados"""
        return int(self.total_work_time.total_seconds() / 60) if self.total_work_time else 0
    
    @property
    def total_break_minutes(self):
        """Total de minutos de break"""
        return int(self.total_break_time.total_seconds() / 60) if self.total_break_time else 0
    
    @property
    def total_lunch_minutes(self):
        """Total lunch minutes for easy display"""
        return int(self.total_lunch_time.total_seconds() / 60) if self.total_lunch_time else 0
    
    @property
    def formatted_work_time(self):
        """Tiempo de trabajo formateado (ej: 8h 30m)"""
        minutes = self.total_work_minutes
        hours = minutes // 60
        mins = minutes % 60
        return f"{hours}h {mins:02d}m"
    
    @property
    def formatted_break_time(self):
        """Tiempo de break formateado"""
        minutes = self.total_break_minutes
        hours = minutes // 60
        mins = minutes % 60
        if hours > 0:
            return f"{hours}h {mins:02d}m"
        return f"{mins}m"

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
    
    def calculate_daily_totals(self):
        """Calcular totales del día - RENOMBRADO desde calculate_metrics para ser más claro"""
        sessions = self.sessions.filter(end_time__isnull=False)
        
        total_work = timedelta(0)
        total_break = timedelta(0)
        total_lunch = timedelta(0)
        break_count = 0
        
        for session in sessions:
            if isinstance(session.duration, timedelta):
                if session.session_type == 'work':
                    total_work += session.duration
                elif session.session_type == 'break':
                    total_break += session.duration
                    break_count += 1
                elif session.session_type == 'lunch':
                    total_lunch += session.duration
            else:
                logger.warning(f"Unexpected duration type: {type(session.duration)} for session: {session}")

        self.total_work_time = total_work
        self.total_break_time = total_break
        self.total_lunch_time = total_lunch
        self.break_count = break_count
        self.productive_hours = round(total_work.total_seconds() / 3600, 2)
        
        self.save()
        return self.productive_hours
    
    # Mantener compatibilidad con código existente
    calculate_metrics = calculate_daily_totals
    
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
        self.calculate_daily_totals()
        
        self.save()
        logger.info(f"🏁 Día laboral finalizado para {self.employee}")

    def get_formatted_session(self):
        """Obtener sesión formateada para display"""
        session = self.get_active_session()
        if not session:
            return None
            
        if hasattr(session, 'start_time'):
            return session.start_time.strftime("%H:%M:%S")
        
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

    # CAMPOS PARA AUDITORÍA Y AJUSTES
    original_start_time = models.DateTimeField(null=True, blank=True)
    original_end_time = models.DateTimeField(null=True, blank=True)
    adjusted_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    adjustment_notes = models.TextField(blank=True, null=True)
    is_adjusted = models.BooleanField(default=False)
    adjustment_date = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['start_time']

    def __str__(self):
        return f"{self.work_day.employee} - {self.session_type} - {self.start_time.time()}"

    def save(self, *args, **kwargs):
        # Guardar tiempos originales en el primer save
        if not self.pk:
            self.original_start_time = self.start_time
            if self.end_time:
                self.original_end_time = self.end_time
        
        # Calcular duración automáticamente
        if self.start_time and self.end_time:
            self.duration = self.end_time - self.start_time
        
        super().save(*args, **kwargs)
        
        # Actualizar métricas del WorkDay
        if self.end_time:
            self.work_day.calculate_daily_totals()

    def adjust_times(self, new_start_time, new_end_time, adjusted_by, notes=""):
        """Método para ajustar tiempos de sesión"""
        self.start_time = new_start_time
        self.end_time = new_end_time
        self.adjusted_by = adjusted_by
        self.adjustment_notes = notes
        self.is_adjusted = True
        self.adjustment_date = timezone.now()
        self.save()

    @property
    def duration_minutes(self):
        """Duración en minutos - PROPIEDAD FALTANTE"""
        if not self.duration:
            return 0
        return int(self.duration.total_seconds() / 60)
    
    @property
    def duration_hours(self):
        """Duración en horas (decimal)"""
        if not self.duration:
            return 0.0
        return round(self.duration.total_seconds() / 3600, 2)

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
    
    @property
    def formatted_time_range(self):
        """Rango de tiempo formateado (ej: 09:00 - 10:30)"""
        start = self.start_time.strftime("%H:%M")
        end = self.end_time.strftime("%H:%M") if self.end_time else "En curso"
        return f"{start} - {end}"
    
    @property
    def was_adjusted(self):
        """Alias para is_adjusted (más legible)"""
        return self.is_adjusted
    
    @property
    def has_original_times(self):
        """Verificar si existen tiempos originales guardados"""
        return self.original_start_time is not None and self.original_end_time is not None
    
    @property
    def time_adjustment_delta(self):
        """Calcular cuánto tiempo se ajustó (en minutos)"""
        if not self.has_original_times or not self.end_time:
            return 0
        
        original_duration = (self.original_end_time - self.original_start_time).total_seconds() / 60
        current_duration = self.duration_minutes
        return int(current_duration - original_duration)
    

class Occurrence(models.Model):
    employee = models.ForeignKey(User, on_delete=models.CASCADE)

    duration = models.DurationField(null=True, blank=True)
    start_time = models.TimeField(null=True, blank=True)
    end_time = models.TimeField(null=True, blank=True)
    comment = models.TextField(null=True, blank=True)

    def save(self, *args, **kwargs):

        if self.start_time and self.end_time:
            self.duration = self.end_time - self.start_time
        
        super().save(*args, **kwargs)
