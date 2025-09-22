from django.contrib import admin
from .models import Departamento,Puesto,Empleado,ConceptoPago,PeriodoPago,RegistroPago,DetallePago,Asistencia,Incidencia

# Register your models here.

admin.site.register(Departamento)
admin.site.register(Puesto)
admin.site.register(Empleado)
admin.site.register(ConceptoPago)
admin.site.register(PeriodoPago)
admin.site.register(RegistroPago)
admin.site.register(DetallePago)
admin.site.register(Asistencia)
admin.site.register(Incidencia)