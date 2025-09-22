    # models.py
from django.db import models
from django.contrib.auth.models import User
from django.core.validators import MinValueValidator, MaxValueValidator
from decimal import Decimal


    # Signals para automatizar procesos
from django.db.models.signals import post_save
from django.dispatch import receiver

class Departamento(models.Model):
        nombre = models.CharField(max_length=100)
        descripcion = models.TextField(blank=True, null=True)
        presupuesto_anual = models.DecimalField(max_digits=12, decimal_places=2, default=0)
        
        def __str__(self):
            return self.nombre
        
        class Meta:
            verbose_name = "Departamento"
            verbose_name_plural = "Departamentos"

class Puesto(models.Model):
        TIPO_CONTRATO_CHOICES = [
            ('tiempo_completo', 'Tiempo Completo'),
            ('medio_tiempo', 'Medio Tiempo'),
            ('temporal', 'Temporal'),
            ('practicante', 'Practicante'),
        ]
        
        nombre = models.CharField(max_length=100)
        departamento = models.ForeignKey(Departamento, on_delete=models.CASCADE)
        descripcion = models.TextField(blank=True, null=True)
        salario_base = models.DecimalField(max_digits=10, decimal_places=2)
        tipo_contrato = models.CharField(max_length=20, choices=TIPO_CONTRATO_CHOICES, default='tiempo_completo')
        beneficios = models.TextField(blank=True, null=True)
        
        def __str__(self):
            return f"{self.nombre} - {self.departamento.nombre}"
        
        class Meta:
            verbose_name = "Puesto"
            verbose_name_plural = "Puestos"

class Empleado(models.Model):
        GENERO_CHOICES = [
            ('M', 'Masculino'),
            ('F', 'Femenino'),
            ('O', 'Otro'),
        ]
        
        ESTADO_CIVIL_CHOICES = [
            ('soltero', 'Soltero/a'),
            ('casado', 'Casado/a'),
            ('divorciado', 'Divorciado/a'),
            ('viudo', 'Viudo/a'),
            ('union_libre', 'Unión Libre'),
        ]
        
        user = models.OneToOneField(User, on_delete=models.CASCADE, null=True, blank=True)
        codigo_empleado = models.CharField(max_length=20, unique=True)
        puesto = models.ForeignKey(Puesto, on_delete=models.SET_NULL, null=True)
        departamento = models.ForeignKey(Departamento, on_delete=models.SET_NULL, null=True)
        fecha_contratacion = models.DateField()
        fecha_nacimiento = models.DateField()
        genero = models.CharField(max_length=1, choices=GENERO_CHOICES)
        estado_civil = models.CharField(max_length=20, choices=ESTADO_CIVIL_CHOICES, blank=True, null=True)
        telefono = models.CharField(max_length=20, blank=True, null=True)
        direccion = models.TextField(blank=True, null=True)
        ciudad = models.CharField(max_length=100, blank=True, null=True)
        pais = models.CharField(max_length=100, blank=True, null=True)
        codigo_postal = models.CharField(max_length=10, blank=True, null=True)
        # foto = models.ImageField(upload_to='empleados/', blank=True, null=True)
        activo = models.BooleanField(default=True)
        
        # Campos bancarios para nómina
        banco_nombre = models.CharField(max_length=100, blank=True, null=True)
        banco_cuenta = models.CharField(max_length=50, blank=True, null=True)
        
        def __str__(self):
            return f"{self.user.get_full_name() if self.user else 'Sin usuario'} - {self.codigo_empleado}"
        
        @property
        def nombre_completo(self):
            if self.user:
                return self.user.get_full_name()
            return "Empleado sin usuario"
        
        class Meta:
            verbose_name = "Empleado"
            verbose_name_plural = "Empleados"

class ConceptoPago(models.Model):
        TIPO_CHOICES = [
            ('percepcion', 'Percepción'),
            ('deduccion', 'Deducción'),
        ]
        
        CLAVE_CHOICES = [
            ('sueldo', 'Sueldo'),
            ('horas_extra', 'Horas Extras'),
            ('bono', 'Bono'),
            ('comision', 'Comisión'),
            ('isr', 'ISR'),
            ('imss', 'IMSS'),
            ('infonavit', 'Infonavit'),
            ('prestamo', 'Préstamo'),
            ('otro', 'Otro'),
        ]
        
        nombre = models.CharField(max_length=100)
        tipo = models.CharField(max_length=20, choices=TIPO_CHOICES)
        clave = models.CharField(max_length=20, choices=CLAVE_CHOICES, default='otro')
        descripcion = models.TextField(blank=True, null=True)
        monto_fijo = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
        porcentaje = models.DecimalField(
            max_digits=5, 
            decimal_places=2, 
            null=True, 
            blank=True, 
            validators=[MinValueValidator(0), MaxValueValidator(100)]
        )
        aplica_impuestos = models.BooleanField(default=False)
        activo = models.BooleanField(default=True)
        
        def __str__(self):
            return f"{self.get_tipo_display()}: {self.nombre}"
        
        class Meta:
            verbose_name = "Concepto de Pago"
            verbose_name_plural = "Conceptos de Pago"

class PeriodoPago(models.Model):
        FRECUENCIA_CHOICES = [
            ('semanal', 'Semanal'),
            ('quincenal', 'Quincenal'),
            ('mensual', 'Mensual'),
        ]
        
        nombre = models.CharField(max_length=100)
        fecha_inicio = models.DateField()
        fecha_fin = models.DateField()
        fecha_pago = models.DateField()
        frecuencia = models.CharField(max_length=20, choices=FRECUENCIA_CHOICES)
        cerrado = models.BooleanField(default=False)
        
        def __str__(self):
            return f"{self.nombre} ({self.fecha_inicio} - {self.fecha_fin})"
        
        class Meta:
            verbose_name = "Periodo de Pago"
            verbose_name_plural = "Periodos de Pago"
            ordering = ['-fecha_inicio']

class RegistroPago(models.Model):
        ESTADO_CHOICES = [
            ('borrador', 'Borrador'),
            ('calculado', 'Calculado'),
            ('pagado', 'Pagado'),
            ('cancelado', 'Cancelado'),
        ]
        
        empleado = models.ForeignKey(Empleado, on_delete=models.CASCADE)
        periodo = models.ForeignKey(PeriodoPago, on_delete=models.CASCADE)
        fecha_creacion = models.DateTimeField(auto_now_add=True)
        fecha_pago = models.DateField()
        salario_bruto = models.DecimalField(max_digits=12, decimal_places=2, default=0)
        total_percepciones = models.DecimalField(max_digits=12, decimal_places=2, default=0)
        total_deducciones = models.DecimalField(max_digits=12, decimal_places=2, default=0)
        salario_neto = models.DecimalField(max_digits=12, decimal_places=2, default=0)
        estado = models.CharField(max_length=20, choices=ESTADO_CHOICES, default='borrador')
        comentarios = models.TextField(blank=True, null=True)
        
        def calcular_totales(self):
            # Calcular totales basados en los detalles
            detalles = self.detalles.all()
            self.total_percepciones = sum([d.monto for d in detalles if d.concepto.tipo == 'percepcion'], Decimal('0'))
            self.total_deducciones = sum([d.monto for d in detalles if d.concepto.tipo == 'deduccion'], Decimal('0'))
            self.salario_neto = self.salario_bruto + self.total_percepciones - self.total_deducciones
            self.save()
        
        def __str__(self):
            return f"Pago {self.periodo} - {self.empleado}"
        
        class Meta:
            verbose_name = "Registro de Pago"
            verbose_name_plural = "Registros de Pago"
            unique_together = ['empleado', 'periodo']

class DetallePago(models.Model):
        registro_pago = models.ForeignKey(RegistroPago, on_delete=models.CASCADE, related_name='detalles')
        concepto = models.ForeignKey(ConceptoPago, on_delete=models.CASCADE)
        cantidad = models.DecimalField(max_digits=10, decimal_places=2, default=1)
        monto = models.DecimalField(max_digits=10, decimal_places=2)
        descripcion = models.TextField(blank=True, null=True)
        
        def __str__(self):
            return f"{self.concepto.nombre}: ${self.monto}"
        
        class Meta:
            verbose_name = "Detalle de Pago"
            verbose_name_plural = "Detalles de Pago"

class Asistencia(models.Model):
        empleado = models.ForeignKey(Empleado, on_delete=models.CASCADE)
        fecha = models.DateField()
        hora_entrada = models.TimeField()
        hora_salida = models.TimeField()
        horas_trabajadas = models.DecimalField(max_digits=4, decimal_places=2, default=0)
        horas_extra = models.DecimalField(max_digits=4, decimal_places=2, default=0)
        comentarios = models.TextField(blank=True, null=True)
        
        def save(self, *args, **kwargs):
            # Calcular horas trabajadas automáticamente
            if self.hora_entrada and self.hora_salida:
                from datetime import datetime, time
                entrada = datetime.combine(self.fecha, self.hora_entrada)
                salida = datetime.combine(self.fecha, self.hora_salida)
                
                # Si la salida es antes de la entrada, asumimos que es del día siguiente
                if salida < entrada:
                    salida = datetime.combine(self.fecha, self.hora_salida)
                
                diferencia = salida - entrada
                horas = diferencia.total_seconds() / 3600
                
                # Jornada normal de 8 horas
                self.horas_trabajadas = min(horas, 8)
                self.horas_extra = max(horas - 8, 0)
            
            super().save(*args, **kwargs)
        
        def __str__(self):
            return f"Asistencia {self.empleado} - {self.fecha}"
        
        class Meta:
            verbose_name = "Asistencia"
            verbose_name_plural = "Asistencias"
            unique_together = ['empleado', 'fecha']

class Incidencia(models.Model):
        TIPO_CHOICES = [
            ('retardo', 'Retardo'),
            ('falta', 'Falta'),
            ('permiso', 'Permiso'),
            ('incapacidad', 'Incapacidad'),
            ('vacaciones', 'Vacaciones'),
        ]
        
        empleado = models.ForeignKey(Empleado, on_delete=models.CASCADE)
        tipo = models.CharField(max_length=20, choices=TIPO_CHOICES)
        fecha = models.DateField()
        fecha_fin = models.DateField(null=True, blank=True)  # Para incapacidades o vacaciones
        justificada = models.BooleanField(default=False)
        comentarios = models.TextField(blank=True, null=True)
        evidencia = models.FileField(upload_to='incidencias/', blank=True, null=True)
        
        def __str__(self):
            return f"{self.get_tipo_display()} - {self.empleado} - {self.fecha}"
        
        class Meta:
            verbose_name = "Incidencia"
            verbose_name_plural = "Incidencias"
            
            
            
            
@receiver(post_save, sender=User)
def crear_empleado_desde_usuario(sender, instance, created, **kwargs):
        """
        Crear automáticamente un perfil de empleado cuando se crea un usuario
        """
        if created and not hasattr(instance, 'empleado'):
            # Generar código de empleado único
            from datetime import datetime
            codigo = f"EMP{datetime.now().strftime('%Y%m%d')}{instance.id:04d}"
            
            Empleado.objects.create(
                user=instance,
                codigo_empleado=codigo,
                fecha_contratacion=datetime.now().date(),
                fecha_nacimiento=datetime(1990, 1, 1).date(),  # Fecha por defecto
                genero='O'
            )