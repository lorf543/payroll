# populate_data.py
import os
import sys
import random
from datetime import datetime, timedelta
from decimal import Decimal

# Configuración para poder ejecutar el script como standalone
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'payroll.settings')
import django
django.setup()

from django.contrib.auth.models import User
from core.models import (Departamento, Puesto, Empleado, ConceptoPago, 
                          PeriodoPago, RegistroPago, DetallePago)

def crear_departamentos():
    print("Creando departamentos...")
    departamentos = [
        {'nombre': 'Desarrollo', 'descripcion': 'Departamento de desarrollo de software', 'presupuesto_anual': 5000000},
        {'nombre': 'Recursos Humanos', 'descripcion': 'Gestión de personal', 'presupuesto_anual': 1500000},
        {'nombre': 'Ventas', 'descripcion': 'Departamento comercial', 'presupuesto_anual': 3000000},
        {'nombre': 'Soporte Técnico', 'descripcion': 'Atención a clientes', 'presupuesto_anual': 2000000},
        {'nombre': 'Administración', 'descripcion': 'Gestión administrativa', 'presupuesto_anual': 2500000},
    ]
    
    for depto in departamentos:
        Departamento.objects.get_or_create(
            nombre=depto['nombre'],
            defaults={
                'descripcion': depto['descripcion'],
                'presupuesto_anual': depto['presupuesto_anual']
            }
        )
    
    return Departamento.objects.all()

def crear_puestos(departamentos):
    print("Creando puestos...")
    puestos = [
        {'nombre': 'Desarrollador Senior', 'departamento': departamentos[0], 'salario_base': 35000, 'tipo_contrato': 'tiempo_completo'},
        {'nombre': 'Desarrollador Junior', 'departamento': departamentos[0], 'salario_base': 20000, 'tipo_contrato': 'tiempo_completo'},
        {'nombre': 'Analista de RH', 'departamento': departamentos[1], 'salario_base': 18000, 'tipo_contrato': 'tiempo_completo'},
        {'nombre': 'Ejecutivo de Ventas', 'departamento': departamentos[2], 'salario_base': 15000, 'tipo_contrato': 'tiempo_completo'},
        {'nombre': 'Soporte Técnico', 'departamento': departamentos[3], 'salario_base': 12000, 'tipo_contrato': 'tiempo_completo'},
        {'nombre': 'Contador', 'departamento': departamentos[4], 'salario_base': 22000, 'tipo_contrato': 'tiempo_completo'},
        {'nombre': 'Practicante Desarrollo', 'departamento': departamentos[0], 'salario_base': 8000, 'tipo_contrato': 'practicante'},
    ]
    
    for puesto_data in puestos:
        Puesto.objects.get_or_create(
            nombre=puesto_data['nombre'],
            departamento=puesto_data['departamento'],
            defaults={
                'salario_base': puesto_data['salario_base'],
                'tipo_contrato': puesto_data['tipo_contrato']
            }
        )
    
    return Puesto.objects.all()

def crear_conceptos_pago():
    print("Creando conceptos de pago...")
    conceptos = [
        # Percepciones
        {'nombre': 'Sueldo', 'tipo': 'percepcion', 'clave': 'sueldo'},
        {'nombre': 'Horas Extras', 'tipo': 'percepcion', 'clave': 'horas_extra', 'porcentaje': None, 'monto_fijo': None},
        {'nombre': 'Bono por Productividad', 'tipo': 'percepcion', 'clave': 'bono', 'porcentaje': 5, 'monto_fijo': None},
        {'nombre': 'Vales de Despensa', 'tipo': 'percepcion', 'clave': 'otro', 'monto_fijo': 1500},
        {'nombre': 'Ayuda para Transporte', 'tipo': 'percepcion', 'clave': 'otro', 'monto_fijo': 800},
        
        # Deducciones
        {'nombre': 'ISR', 'tipo': 'deduccion', 'clave': 'isr', 'porcentaje': 15, 'monto_fijo': None, 'aplica_impuestos': False},
        {'nombre': 'IMSS', 'tipo': 'deduccion', 'clave': 'imss', 'porcentaje': 5, 'monto_fijo': None, 'aplica_impuestos': False},
        {'nombre': 'Ahorro Voluntario', 'tipo': 'deduccion', 'clave': 'otro', 'monto_fijo': 500, 'aplica_impuestos': False},
        {'nombre': 'Préstamo Personal', 'tipo': 'deduccion', 'clave': 'prestamo', 'monto_fijo': 1000, 'aplica_impuestos': False},
    ]
    
    for concepto_data in conceptos:
        ConceptoPago.objects.get_or_create(
            nombre=concepto_data['nombre'],
            tipo=concepto_data['tipo'],
            defaults={
                'clave': concepto_data.get('clave', 'otro'),
                'porcentaje': concepto_data.get('porcentaje', None),
                'monto_fijo': concepto_data.get('monto_fijo', None),
                'aplica_impuestos': concepto_data.get('aplica_impuestos', False)
            }
        )
    
    return ConceptoPago.objects.all()

def crear_empleados_y_usuarios(puestos):
    print("Creando empleados y usuarios...")
    empleados_data = [
        {
            'username': 'juan.perez', 
            'first_name': 'Juan', 
            'last_name': 'Pérez', 
            'email': 'juan.perez@empresa.com',
            'puesto': puestos[0],  # Desarrollador Senior
            'departamento': puestos[0].departamento,
            'fecha_contratacion': datetime(2020, 3, 15).date(),
            'fecha_nacimiento': datetime(1985, 7, 22).date(),
            'genero': 'M',
            'salario_base': 35000
        },
        {
            'username': 'maria.garcia', 
            'first_name': 'María', 
            'last_name': 'García', 
            'email': 'maria.garcia@empresa.com',
            'puesto': puestos[1],  # Desarrollador Junior
            'departamento': puestos[1].departamento,
            'fecha_contratacion': datetime(2021, 6, 10).date(),
            'fecha_nacimiento': datetime(1992, 11, 5).date(),
            'genero': 'F',
            'salario_base': 20000
        },
        {
            'username': 'carlos.lopez', 
            'first_name': 'Carlos', 
            'last_name': 'López', 
            'email': 'carlos.lopez@empresa.com',
            'puesto': puestos[2],  # Analista de RH
            'departamento': puestos[2].departamento,
            'fecha_contratacion': datetime(2019, 1, 8).date(),
            'fecha_nacimiento': datetime(1988, 4, 17).date(),
            'genero': 'M',
            'salario_base': 18000
        },
        {
            'username': 'ana.martinez', 
            'first_name': 'Ana', 
            'last_name': 'Martínez', 
            'email': 'ana.martinez@empresa.com',
            'puesto': puestos[3],  # Ejecutivo de Ventas
            'departamento': puestos[3].departamento,
            'fecha_contratacion': datetime(2022, 2, 20).date(),
            'fecha_nacimiento': datetime(1995, 9, 12).date(),
            'genero': 'F',
            'salario_base': 15000
        },
        {
            'username': 'luis.rodriguez', 
            'first_name': 'Luis', 
            'last_name': 'Rodríguez', 
            'email': 'luis.rodriguez@empresa.com',
            'puesto': puestos[5],  # Contador
            'departamento': puestos[5].departamento,
            'fecha_contratacion': datetime(2018, 8, 5).date(),
            'fecha_nacimiento': datetime(1987, 12, 30).date(),
            'genero': 'M',
            'salario_base': 22000
        }
    ]
    
    empleados = []
    for emp_data in empleados_data:
        # Crear usuario
        user, created = User.objects.get_or_create(
            username=emp_data['username'],
            defaults={
                'first_name': emp_data['first_name'],
                'last_name': emp_data['last_name'],
                'email': emp_data['email'],
                'password': 'password123'  # En un caso real, usaríamos set_password()
            }
        )
        
        # Crear empleado
        codigo_empleado = f"EMP{user.id:04d}"
        empleado, created = Empleado.objects.get_or_create(
            user=user,
            defaults={
                'codigo_empleado': codigo_empleado,
                'puesto': emp_data['puesto'],
                'departamento': emp_data['departamento'],
                'fecha_contratacion': emp_data['fecha_contratacion'],
                'fecha_nacimiento': emp_data['fecha_nacimiento'],
                'genero': emp_data['genero'],
                'telefono': f"55{random.randint(1000, 9999)}{random.randint(1000, 9999)}",
                'direccion': f"Calle {random.randint(1, 100)} # {random.randint(100, 999)}",
                'ciudad': "Ciudad de México",
                'pais': "México",
                'banco_nombre': "Banco Ejemplo",
                'banco_cuenta': f"{random.randint(1000000000, 9999999999)}",
                'banco_clabe': f"{random.randint(100000000000000000, 999999999999999999)}"
            }
        )
        empleados.append(empleado)
    
    return empleados

def crear_periodos_pago():
    print("Creando periodos de pago...")
    # Crear 10 periodos de pago (quincenales)
    periodos = []
    fecha_inicio = datetime(2023, 1, 1).date()
    
    for i in range(10):
        fecha_fin = fecha_inicio + timedelta(days=14)
        fecha_pago = fecha_fin + timedelta(days=1)
        
        periodo, created = PeriodoPago.objects.get_or_create(
            nombre=f"Quincena {i+1} - {fecha_inicio.month}/{fecha_inicio.year}",
            defaults={
                'fecha_inicio': fecha_inicio,
                'fecha_fin': fecha_fin,
                'fecha_pago': fecha_pago,
                'frecuencia': 'quincenal',
                'cerrado': True
            }
        )
        periodos.append(periodo)
        fecha_inicio = fecha_fin + timedelta(days=1)
    
    return periodos

def crear_registros_pagos(empleados, periodos, conceptos):
    print("Creando registros de pago...")
    
    # Separar conceptos en percepciones y deducciones
    percepciones = [c for c in conceptos if c.tipo == 'percepcion']
    deducciones = [c for c in conceptos if c.tipo == 'deduccion']
    
    for empleado in empleados:
        salario_base = empleado.puesto.salario_base
        
        for periodo in periodos:
            # Crear registro de pago
            registro, created = RegistroPago.objects.get_or_create(
                empleado=empleado,
                periodo=periodo,
                defaults={
                    'fecha_pago': periodo.fecha_pago,
                    'salario_bruto': salario_base,
                    'estado': 'pagado'
                }
            )
            
            # Agregar detalles de percepciones
            for percepcion in percepciones:
                monto = 0
                if percepcion.nombre == 'Sueldo':
                    monto = salario_base / 2  # Mitad del salario mensual por quincena
                elif percepcion.nombre == 'Horas Extras' and random.random() > 0.7:  # 30% de probabilidad
                    monto = random.randint(500, 2000)
                elif percepcion.nombre == 'Bono por Productividad' and random.random() > 0.5:  # 50% de probabilidad
                    monto = salario_base * Decimal(percepcion.porcentaje / 100) / 2
                elif percepcion.monto_fijo:
                    monto = percepcion.monto_fijo
                
                if monto > 0:
                    DetallePago.objects.get_or_create(
                        registro_pago=registro,
                        concepto=percepcion,
                        defaults={
                            'monto': monto
                        }
                    )
            
            # Agregar detalles de deducciones
            for deduccion in deducciones:
                monto = 0
                if deduccion.nombre == 'ISR':
                    monto = salario_base * Decimal(deduccion.porcentaje / 100) / 2
                elif deduccion.nombre == 'IMSS':
                    monto = salario_base * Decimal(deduccion.porcentaje / 100) / 2
                elif deduccion.monto_fijo:
                    monto = deduccion.monto_fijo
                
                if monto > 0:
                    DetallePago.objects.get_or_create(
                        registro_pago=registro,
                        concepto=deduccion,
                        defaults={
                            'monto': monto
                        }
                    )
            
            # Calcular totales
            registro.calcular_totales()
    
    print("Registros de pago creados exitosamente!")

def main():
    print("Iniciando población de datos...")
    
    # Limpiar datos existentes (opcional, tener cuidado en producción)
    # RegistroPago.objects.all().delete()
    # Empleado.objects.all().delete()
    # Puesto.objects.all().delete()
    # Departamento.objects.all().delete()
    # ConceptoPago.objects.all().delete()
    # PeriodoPago.objects.all().delete()
    
    # Crear datos
    departamentos = crear_departamentos()
    puestos = crear_puestos(departamentos)
    conceptos = crear_conceptos_pago()
    empleados = crear_empleados_y_usuarios(puestos)
    periodos = crear_periodos_pago()
    crear_registros_pagos(empleados, periodos, conceptos)
    
    print("¡Datos poblados exitosamente!")
    print(f"- Departamentos creados: {departamentos.count()}")
    print(f"- Puestos creados: {puestos.count()}")
    print(f"- Conceptos de pago creados: {conceptos.count()}")
    print(f"- Empleados creados: {len(empleados)}")
    print(f"- Periodos de pago creados: {len(periodos)}")
    print(f"- Registros de pago creados: {RegistroPago.objects.count()}")
    print(f"- Detalles de pago creados: {DetallePago.objects.count()}")

if __name__ == '__main__':
    main()