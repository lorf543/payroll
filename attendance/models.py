# models.py
from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone
from datetime import timedelta, datetime
from decimal import Decimal, ROUND_HALF_UP
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


    # NUEVOS CAMPOS PARA HORAS EXTRAS Y NOCTURNAS
    regular_hours = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    overtime_hours_135 = models.DecimalField(max_digits=5, decimal_places=2, default=0, 
    help_text="Horas extras 44-68h (35% premium)")
    overtime_hours_200 = models.DecimalField(max_digits=5, decimal_places=2, default=0,
    help_text="Horas extras >68h (100% premium)")
    night_hours = models.DecimalField(max_digits=5, decimal_places=2, default=0,
    help_text="Horas trabajadas 9PM-7AM (15% premium)")
    
    # PAGOS CALCULADOS
    regular_pay = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    overtime_pay_135 = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    overtime_pay_200 = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    night_pay = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    total_pay = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    
    # TARIFAS APLICADAS
    regular_rate = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    overtime_rate_135 = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    overtime_rate_200 = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    night_rate = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    
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
    
    def calculate_weekly_hours(self):
        """
        Calcula las horas totales trabajadas en la semana para determinar 
        si hay horas extras según la ley dominicana
        """
        # Obtener la semana actual (Lunes a Domingo)
        start_of_week = self.date - timedelta(days=self.date.weekday())
        end_of_week = start_of_week + timedelta(days=6)
        
        # Obtener todos los WorkDays de esta semana para este empleado
        weekly_workdays = WorkDay.objects.filter(
            employee=self.employee,
            date__range=[start_of_week, end_of_week]
        ).exclude(
            status__in=['absent', 'leave']
        )
        
        total_weekly_hours = Decimal('0')
        for wd in weekly_workdays:
            total_weekly_hours += wd.productive_hours
        
        return total_weekly_hours
    
    def is_night_hours(self, time_obj):
        """
        Verifica si una hora específica está en el rango nocturno (9 PM - 7 AM)
        """
        # 9 PM = 21:00, 7 AM = 07:00
        if time_obj.hour >= 21 or time_obj.hour < 7:
            return True
        return False
    
    def calculate_night_hours_from_sessions(self):
        """
        Calcula cuántas horas de trabajo fueron durante horario nocturno
        """
        night_minutes = 0
        sessions = self.sessions.filter(
            session_type='work',
            end_time__isnull=False
        )
        
        for session in sessions:
            current_time = session.start_time
            end_time = session.end_time
            
            # Revisar cada minuto de la sesión
            while current_time < end_time:
                if self.is_night_hours(current_time):
                    night_minutes += 1
                current_time += timedelta(minutes=1)
        
        return Decimal(str(night_minutes / 60))
    
    def calculate_overtime_breakdown(self):
        """
        Calcula el desglose de horas regulares, extras y nocturnas
        según la ley dominicana
        """

        
        # Total de horas trabajadas HOY
        daily_hours = self.productive_hours
        
        # Total de horas trabajadas en la SEMANA
        weekly_hours = self.calculate_weekly_hours()
        
        # Horas nocturnas
        night_hours = self.calculate_night_hours_from_sessions()
        
        # CÁLCULO DE HORAS EXTRAS SEMANALES
        # Hasta 44 horas = regulares
        # 44-68 horas = overtime 135%
        # >68 horas = overtime 200%
        
        regular_hours = Decimal('0')
        overtime_135 = Decimal('0')
        overtime_200 = Decimal('0')
        
        if weekly_hours <= Decimal('44'):
            # Todas las horas de hoy son regulares
            regular_hours = daily_hours
        elif weekly_hours <= Decimal('68'):
            # Hay horas extras al 135%
            # Determinar cuántas horas de HOY caen en overtime
            hours_before_today = weekly_hours - daily_hours
            
            if hours_before_today >= Decimal('44'):
                # Todas las horas de hoy son overtime 135%
                overtime_135 = daily_hours
            else:
                # Parte son regulares, parte son overtime 135%
                regular_hours = Decimal('44') - hours_before_today
                overtime_135 = daily_hours - regular_hours
        else:
            # Hay horas extras al 200%
            hours_before_today = weekly_hours - daily_hours
            
            if hours_before_today >= Decimal('68'):
                # Todas las horas de hoy son overtime 200%
                overtime_200 = daily_hours
            elif hours_before_today >= Decimal('44'):
                # Parte son overtime 135%, parte son overtime 200%
                overtime_135 = Decimal('68') - hours_before_today
                overtime_200 = daily_hours - overtime_135
            else:
                # Parte regulares, parte overtime 135%, parte overtime 200%
                regular_hours = Decimal('44') - hours_before_today
                remaining = daily_hours - regular_hours
                
                if remaining <= (Decimal('68') - Decimal('44')):
                    overtime_135 = remaining
                else:
                    overtime_135 = Decimal('68') - Decimal('44')
                    overtime_200 = remaining - overtime_135
        
        return {
            'regular_hours': regular_hours,
            'overtime_135': overtime_135,
            'overtime_200': overtime_200,
            'night_hours': night_hours,
            'weekly_total': weekly_hours,
            'daily_total': daily_hours
        }
    
    def calculate_pay_with_dominican_law(self):
        """
        Calcula el pago siguiendo las leyes laborales dominicanas:
        - Horas regulares (hasta 44h semanales)
        - Overtime 135% (44-68h semanales) = 35% extra
        - Overtime 200% (>68h semanales) = 100% extra
        - Horas nocturnas 115% (9PM-7AM) = 15% extra
        """
        # Obtener tarifa base
        if self.employee.fixed_rate and self.employee.custom_base_salary:
            custom_salary = Decimal(str(self.employee.custom_base_salary))
            daily_rate = custom_salary / Decimal('30')
            self.regular_rate = daily_rate / Decimal('8')
        elif self.employee.position and self.employee.position.hour_rate:
            self.regular_rate = Decimal(str(self.employee.position.hour_rate))
        elif self.employee.current_campaign and self.employee.current_campaign.hour_rate:
            self.regular_rate = Decimal(str(self.employee.current_campaign.hour_rate))
        else:
            self.regular_rate = Decimal('0.00')

        # Calcular tarifas según ley dominicana
        self.overtime_rate_135 = self.regular_rate * Decimal('1.35')  # 35% extra
        self.overtime_rate_200 = self.regular_rate * Decimal('2.00')  # 100% extra
        self.night_rate = self.regular_rate * Decimal('1.15')  # 15% extra

        # Convertir horas a Decimal
        daily_hours = Decimal(str(self.productive_hours or 0))
        night_hours = Decimal(str(self.calculate_night_hours_from_sessions() or 0))

        # Calcular horas semanales
        weekly_hours = Decimal(str(self.calculate_weekly_hours() or 0))

        # Horas regulares vs overtime según ley dominicana
        regular_hours = Decimal('0')
        overtime_135 = Decimal('0')
        overtime_200 = Decimal('0')

        if weekly_hours <= Decimal('44'):
            regular_hours = daily_hours
        elif weekly_hours <= Decimal('68'):
            hours_before_today = weekly_hours - daily_hours
            if hours_before_today >= Decimal('44'):
                overtime_135 = daily_hours
            else:
                regular_hours = Decimal('44') - hours_before_today
                overtime_135 = daily_hours - regular_hours
        else:
            hours_before_today = weekly_hours - daily_hours
            if hours_before_today >= Decimal('68'):
                overtime_200 = daily_hours
            elif hours_before_today >= Decimal('44'):
                overtime_135 = Decimal('68') - hours_before_today
                overtime_200 = daily_hours - overtime_135
            else:
                regular_hours = Decimal('44') - hours_before_today
                remaining = daily_hours - regular_hours
                if remaining <= (Decimal('68') - Decimal('44')):
                    overtime_135 = remaining
                else:
                    overtime_135 = Decimal('68') - Decimal('44')
                    overtime_200 = remaining - overtime_135

        # Guardar horas calculadas
        self.regular_hours = regular_hours
        self.overtime_hours_135 = overtime_135
        self.overtime_hours_200 = overtime_200
        self.night_hours = night_hours

        # Calcular pagos
        self.regular_pay = regular_hours * self.regular_rate
        self.overtime_pay_135 = overtime_135 * self.overtime_rate_135
        self.overtime_pay_200 = overtime_200 * self.overtime_rate_200
        self.night_pay = night_hours * self.night_rate

        # Total
        self.total_pay = self.regular_pay + self.overtime_pay_135 + self.overtime_pay_200 + self.night_pay

        return {
            'regular_pay': float(self.regular_pay),
            'overtime_pay_135': float(self.overtime_pay_135),
            'overtime_pay_200': float(self.overtime_pay_200),
            'night_pay': float(self.night_pay),
            'total_pay': float(self.total_pay),
            'breakdown': {
                'regular_hours': float(regular_hours),
                'overtime_135': float(overtime_135),
                'overtime_200': float(overtime_200),
                'night_hours': float(night_hours),
                'daily_total': float(daily_hours),
                'weekly_total': float(weekly_hours)
            }
        }
    
    def save(self, *args, **kwargs):
        # Calcular horas automáticamente antes de guardar
        if self.productive_hours > 0:
            self.calculate_pay_with_dominican_law()
        super().save(*args, **kwargs)
    
    # En models.py - método calculate_pay
    def calculate_pay(self):
        """Calcular pagos basado en horas trabajadas"""
        
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
        return int(self.total_break_time.total_seconds() / 60) if self.total_break_time else 0
    
    @property
    def total_lunch_minutes(self):
        return int(self.total_lunch_time.total_seconds() / 60) if self.total_lunch_time else 0
    
    @property
    def is_active(self):
        return self.end_time is None
    
    @property
    def formatted_work_time(self):

        minutes = self.total_work_minutes
        hours = minutes // 60
        mins = minutes % 60
        return f"{hours}h {mins:02d}m"
    
    @property
    def formatted_lunch_time(self):
        minutes = self.total_lunch_minutes
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
        if self.end_time:  # Solo cuando se cierra la sesión
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

    OCCURRENCE_TYPES = [
        ("technical_issues", "Technical Issues"),
        ("call_drop", "Call Drop"),
        ("Bath_room", "Bath room"),
    ]
    
    employee = models.ForeignKey(Employee, on_delete=models.CASCADE)
    occurrence_type = models.CharField(max_length=50, choices=OCCURRENCE_TYPES)
    date = models.DateField()
    start_time = models.TimeField()
    end_time = models.TimeField()
    comment = models.TextField(null=True, blank=True)
    duration = models.DurationField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.employee.full_name}"
    

    def save(self, *args, **kwargs):
        if self.start_time and self.end_time:
            self.duration = (
                datetime.combine(datetime.today(), self.end_time)
                - datetime.combine(datetime.today(), self.start_time)
            )
        super().save(*args, **kwargs)
