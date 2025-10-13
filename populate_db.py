# populate_db.py
import os
import django
import random
from datetime import date, timedelta
from decimal import Decimal

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'payroll.settings')
django.setup()

from django.contrib.auth.models import User
from core.models import Department, Position, Employee, Campaign, PaymentConcept, PayPeriod, Payment

def clear_data():
    """Limpia toda la data existente"""
    print("Limpiando datos existentes...")
    Payment.objects.all().delete()
    PayPeriod.objects.all().delete()
    PaymentConcept.objects.all().delete()
    Campaign.objects.all().delete()
    Employee.objects.all().delete()
    Position.objects.all().delete()
    Department.objects.all().delete()
    User.objects.exclude(is_superuser=True).delete()
    print("✓ Datos limpiados")

def create_departments():
    """Crea departamentos de call center"""
    print("\nCreando departamentos...")
    departments_data = [
        {'name': 'Atención al Cliente', 'description': 'Soporte y servicio al cliente', 'annual_budget': 600000},
        {'name': 'Ventas Inbound', 'description': 'Ventas por llamadas entrantes', 'annual_budget': 750000},
        {'name': 'Ventas Outbound', 'description': 'Ventas por llamadas salientes', 'annual_budget': 700000},
        {'name': 'Soporte Técnico', 'description': 'Asistencia técnica especializada', 'annual_budget': 650000},
        {'name': 'Retención', 'description': 'Retención de clientes', 'annual_budget': 550000},
        {'name': 'Cobranzas', 'description': 'Gestión de cobranzas', 'annual_budget': 500000},
        {'name': 'Back Office', 'description': 'Procesamiento y administración', 'annual_budget': 450000},
        {'name': 'Quality Assurance', 'description': 'Control de calidad', 'annual_budget': 400000},
        {'name': 'Capacitación', 'description': 'Entrenamiento y desarrollo', 'annual_budget': 350000},
        {'name': 'Workforce Management', 'description': 'Gestión de fuerza laboral', 'annual_budget': 380000},
    ]
    
    departments = []
    for dept_data in departments_data:
        dept = Department.objects.create(**dept_data)
        departments.append(dept)
        print(f"  ✓ {dept.name}")
    
    return departments

def create_positions():
    """Crea posiciones de call center"""
    print("\nCreando posiciones...")
    positions_data = [
        # Gestión
        {'name': 'Director de Operaciones', 'contract_type': 'full_time', 'base_salary': Decimal('120000'), 'benefits': 'Seguro médico premium, bono anual, vehículo'},
        {'name': 'Gerente de Call Center', 'contract_type': 'full_time', 'base_salary': Decimal('85000'), 'benefits': 'Seguro médico, bono trimestral'},
        {'name': 'Gerente de Cuenta', 'contract_type': 'full_time', 'base_salary': Decimal('75000'), 'benefits': 'Seguro médico, bono por resultados'},
        
        # Supervisión
        {'name': 'Supervisor de Operaciones', 'contract_type': 'full_time', 'base_salary': Decimal('55000'), 'benefits': 'Seguro médico, bono mensual'},
        {'name': 'Team Leader', 'contract_type': 'full_time', 'base_salary': Decimal('48000'), 'benefits': 'Seguro médico'},
        {'name': 'Supervisor de Calidad', 'contract_type': 'full_time', 'base_salary': Decimal('50000'), 'benefits': 'Seguro médico'},
        
        # Agentes
        {'name': 'Agente de Atención al Cliente', 'contract_type': 'full_time', 'base_salary': Decimal('28000'), 'benefits': 'Seguro básico'},
        {'name': 'Agente de Ventas', 'contract_type': 'full_time', 'base_salary': Decimal('25000'), 'benefits': 'Seguro básico, comisiones'},
        {'name': 'Agente de Soporte Técnico', 'contract_type': 'full_time', 'base_salary': Decimal('32000'), 'benefits': 'Seguro médico'},
        {'name': 'Agente de Retención', 'contract_type': 'full_time', 'base_salary': Decimal('30000'), 'benefits': 'Seguro básico, bonos por retención'},
        {'name': 'Agente de Cobranzas', 'contract_type': 'full_time', 'base_salary': Decimal('27000'), 'benefits': 'Seguro básico, comisiones'},
        {'name': 'Agente Bilingüe', 'contract_type': 'full_time', 'base_salary': Decimal('35000'), 'benefits': 'Seguro médico, bono de idioma'},
        
        # Especialistas
        {'name': 'Analista de Calidad', 'contract_type': 'full_time', 'base_salary': Decimal('38000'), 'benefits': 'Seguro médico'},
        {'name': 'Especialista en Capacitación', 'contract_type': 'full_time', 'base_salary': Decimal('42000'), 'benefits': 'Seguro médico'},
        {'name': 'Workforce Analyst', 'contract_type': 'full_time', 'base_salary': Decimal('45000'), 'benefits': 'Seguro médico'},
        {'name': 'Analista de Reportes', 'contract_type': 'full_time', 'base_salary': Decimal('40000'), 'benefits': 'Seguro médico'},
        
        # Back Office
        {'name': 'Coordinador de Back Office', 'contract_type': 'full_time', 'base_salary': Decimal('44000'), 'benefits': 'Seguro médico'},
        {'name': 'Especialista de Back Office', 'contract_type': 'full_time', 'base_salary': Decimal('33000'), 'benefits': 'Seguro básico'},
        {'name': 'Asistente Administrativo', 'contract_type': 'full_time', 'base_salary': Decimal('26000')},
        
        # Tiempo parcial y temporales
        {'name': 'Agente Part-Time', 'contract_type': 'part_time', 'hour_rate': Decimal('175')},
        {'name': 'Agente Temporal', 'contract_type': 'temporary', 'base_salary': Decimal('24000')},
        {'name': 'Pasante de Call Center', 'contract_type': 'intern', 'hour_rate': Decimal('120')},
    ]
    
    positions = []
    for pos_data in positions_data:
        pos = Position.objects.create(**pos_data)
        positions.append(pos)
        print(f"  ✓ {pos.name}")
    
    return positions

def create_employees(departments, positions):
    """Crea empleados"""
    print("\nCreando empleados...")
    
    first_names = ['Juan', 'María', 'Carlos', 'Ana', 'Luis', 'Carmen', 'Pedro', 'Lucía', 
                   'Miguel', 'Isabel', 'José', 'Rosa', 'Antonio', 'Patricia', 'Francisco',
                   'Laura', 'Manuel', 'Sofía', 'Diego', 'Elena', 'Rafael', 'Valentina',
                   'Roberto', 'Camila', 'Fernando', 'Isabella', 'Jorge', 'Daniela',
                   'Ricardo', 'Andrea', 'Alberto', 'Gabriela', 'Sergio', 'Natalia',
                   'Alejandro', 'Victoria', 'Raúl', 'Carolina', 'Ernesto', 'Mariana']
    
    last_names = ['García', 'Rodríguez', 'Martínez', 'López', 'González', 'Pérez', 
                  'Sánchez', 'Ramírez', 'Torres', 'Flores', 'Rivera', 'Gómez',
                  'Díaz', 'Cruz', 'Morales', 'Reyes', 'Jiménez', 'Hernández',
                  'Castillo', 'Vargas', 'Méndez', 'Ortiz', 'Ruiz', 'Guzmán']
    
    cities = ['Santo Domingo', 'Santiago', 'La Vega', 'San Pedro de Macorís', 
              'San Cristóbal', 'Puerto Plata', 'La Romana', 'San Francisco de Macorís']
    
    education_levels = ['Bachillerato', 'Técnico en Call Center', 'Licenciatura en Comunicación', 
                       'Licenciatura en Administración', 'Licenciatura en Marketing', 'Maestría en Gestión']
    
    skills_options = [
        'Atención al cliente, Comunicación efectiva, Manejo de CRM',
        'Ventas, Persuasión, Cierre de ventas, Negotiación',
        'Soporte técnico, Troubleshooting, Sistemas operativos',
        'Inglés avanzado, Español nativo, Atención bilingüe',
        'Manejo de quejas, Resolución de conflictos, Empatía',
        'Cobranzas, Negociación de deudas, Análisis financiero',
        'Excel avanzado, Reportes, Análisis de datos',
        'Capacitación, Desarrollo de personal, Presentaciones',
        'Quality monitoring, Call scoring, Feedback efectivo',
        'Multitasking, Trabajo bajo presión, Orientación a resultados',
    ]
    
    employees = []
    
    for i in range(50):
        # Crear usuario
        first_name = random.choice(first_names)
        last_name = random.choice(last_names)
        username = f"{first_name.lower()}.{last_name.lower()}{i}"
        email = f"{username}@callcenter.com"
        
        user = User.objects.create_user(
            username=username,
            email=email,
            first_name=first_name,
            last_name=last_name,
            password='password123'
        )
        
        # Datos del empleado
        hire_date = date.today() - timedelta(days=random.randint(30, 2190))
        birth_date = date.today() - timedelta(days=random.randint(7300, 18250))
        
        department = random.choice(departments)
        position = random.choice(positions)
        
        # Salario personalizado en algunos casos (20% de probabilidad)
        custom_salary = None
        fixed_rate = False
        if random.random() > 0.8:
            fixed_rate = True
            if position.base_salary:
                custom_salary = position.base_salary * Decimal(str(random.uniform(0.95, 1.15)))
        
        employee = Employee.objects.create(
            user=user,
            identification=f"001-{random.randint(1000000, 9999999)}-{random.randint(1, 9)}",
            employee_code=f"CC{str(i+1).zfill(4)}",
            hire_date=hire_date,
            birth_date=birth_date,
            gender=random.choice(['M', 'F']),
            marital_status=random.choice(['single', 'married', 'divorced', 'common_law']),
            phone=f"809-{random.randint(200, 999)}-{random.randint(1000, 9999)}",
            address=f"Calle {random.randint(1, 50)} #{random.randint(1, 200)}, Sector {random.choice(['Los Ríos', 'Villa Mella', 'Los Mina', 'Cristo Rey'])}",
            city=random.choice(cities),
            country='República Dominicana',
            is_active=random.choice([True, True, True, True, False]),  # 80% activos
            position=position,
            department=department,
            bio=f"Profesional dedicado con experiencia en {department.name}. Comprometido con la excelencia en el servicio.",
            education=random.choice(education_levels),
            email=email,
            skills=random.choice(skills_options),
            fixed_rate=fixed_rate,
            custom_base_salary=custom_salary,
            bank_name=random.choice(['Banco Popular', 'Banco BHD León', 'Banreservas', 'Banco López de Haro', 'ScotiaBank']),
            bank_account=f"{random.randint(1000000000, 9999999999)}"
        )
        
        employees.append(employee)
        print(f"  ✓ {employee.full_name} - {position.name} ({department.name})")
    
    return employees

def create_campaigns(employees):
    """Crea campañas de call center"""
    print("\nCreando campañas...")
    
    campaigns_data = [
        {'name': 'Campaña Telefonía Móvil', 'client_name': 'TelcoMax', 'description': 'Ventas y retención de servicios móviles'},
        {'name': 'Soporte Técnico Banking', 'client_name': 'MegaBank', 'description': 'Soporte técnico para banca en línea'},
        {'name': 'Ventas Seguros', 'client_name': 'SecureLife', 'description': 'Venta de seguros de vida y salud'},
        {'name': 'Atención Cliente E-commerce', 'client_name': 'ShopNow', 'description': 'Atención al cliente para plataforma de ventas online'},
        {'name': 'Cobranzas Tarjetas', 'client_name': 'CreditCard Plus', 'description': 'Gestión de cobranzas para tarjetas de crédito'},
        {'name': 'Retención Cable/Internet', 'client_name': 'NetConnect', 'description': 'Retención de clientes de servicios de cable e internet'},
    ]
    
    campaigns = []
    for campaign_data in campaigns_data:
        start_date = date.today() - timedelta(days=random.randint(60, 365))
        end_date = start_date + timedelta(days=random.randint(90, 180))
        
        campaign = Campaign.objects.create(
            **campaign_data,
            start_date=start_date,
            end_date=end_date,
            is_active=random.choice([True, True, True, False])  # 75% activas
        )
        
        # Asignar empleados aleatorios (entre 5 y 15 por campaña)
        campaign_employees = random.sample(employees, k=random.randint(5, min(15, len(employees))))
        campaign.employees.set(campaign_employees)
        
        campaigns.append(campaign)
        print(f"  ✓ {campaign.name} ({len(campaign_employees)} empleados)")
    
    return campaigns

def create_payment_concepts():
    """Crea conceptos de pago"""
    print("\nCreando conceptos de pago...")
    
    concepts_data = [
        {'name': 'Salario Base', 'type': 'earning', 'code': 'salary', 'taxable': True},
        {'name': 'Horas Extra', 'type': 'earning', 'code': 'overtime', 'taxable': True, 'percentage': Decimal('50')},
        {'name': 'Bono de Productividad', 'type': 'earning', 'code': 'bonus', 'taxable': True},
        {'name': 'Comisión de Ventas', 'type': 'earning', 'code': 'commission', 'taxable': True, 'percentage': Decimal('5')},
        {'name': 'Bono de Calidad', 'type': 'earning', 'code': 'bonus', 'taxable': True, 'fixed_amount': Decimal('2000')},
        {'name': 'ISR', 'type': 'deduction', 'code': 'isr', 'taxable': False},
        {'name': 'AFP', 'type': 'deduction', 'code': 'afp', 'percentage': Decimal('2.87')},
        {'name': 'SFS', 'type': 'deduction', 'code': 'sfs', 'percentage': Decimal('3.04')},
        {'name': 'Préstamo Personal', 'type': 'deduction', 'code': 'loan', 'fixed_amount': Decimal('3000')},
        {'name': 'Descuento por Ausencia', 'type': 'deduction', 'code': 'other'},
    ]
    
    concepts = []
    for concept_data in concepts_data:
        concept = PaymentConcept.objects.create(**concept_data)
        concepts.append(concept)
        print(f"  ✓ {concept.name}")
    
    return concepts

def create_pay_periods():
    """Crea períodos de pago"""
    print("\nCreando períodos de pago...")
    
    periods = []
    start = date(2024, 1, 1)
    
    for i in range(24):  # 24 quincenas (1 año)
        end = start + timedelta(days=14)
        pay_date = end + timedelta(days=3)
        
        period = PayPeriod.objects.create(
            name=f"Quincena {(i % 24) + 1}/2024",
            start_date=start,
            end_date=end,
            pay_date=pay_date,
            frequency='biweekly',
            is_closed=i < 20  # Las primeras 20 quincenas están cerradas
        )
        
        periods.append(period)
        print(f"  ✓ {period.name}")
        
        start = end + timedelta(days=1)
    
    return periods

def create_payments(employees, periods):
    """Crea pagos de ejemplo"""
    print("\nCreando pagos...")
    
    payment_count = 0
    
    # Crear pagos para los períodos cerrados
    for period in periods[:15]:  # Primeros 15 períodos
        active_employees = [e for e in employees if e.is_active]
        
        # Seleccionar empleados aleatorios para este período
        employees_for_period = random.sample(active_employees, k=min(30, len(active_employees)))
        
        for employee in employees_for_period:
            # Calcular salario bruto basado en el tipo de contrato
            gross_salary = None
            
            if employee.fixed_rate and employee.custom_base_salary:
                gross_salary = Decimal(str(employee.custom_base_salary)) / Decimal('24')
            elif employee.position.base_salary:
                gross_salary = Decimal(str(employee.position.base_salary)) / Decimal('24')
            elif employee.position.hour_rate:
                # Para trabajadores por hora, asumir 80 horas por quincena
                hours_worked = Decimal(str(random.randint(60, 80)))
                gross_salary = Decimal(str(employee.position.hour_rate)) * hours_worked
            else:
                continue
            
            # Redondear a 2 decimales
            gross_salary = gross_salary.quantize(Decimal('0.01'))
            
            payment = Payment.objects.create(
                employee=employee,
                period=period,
                pay_date=period.pay_date,
                gross_salary=gross_salary,
                status='paid' if period.is_closed else 'calculated',
                comments='Pago generado automáticamente'
            )
            
            payment_count += 1
    
    print(f"  ✓ {payment_count} pagos creados")

def main():
    print("=" * 60)
    print("GENERADOR DE DATOS DE PRUEBA - SISTEMA DE CALL CENTER")
    print("=" * 60)
    
    clear_data()
    
    departments = create_departments()
    positions = create_positions()
    employees = create_employees(departments, positions)
    campaigns = create_campaigns(employees)
    concepts = create_payment_concepts()
    periods = create_pay_periods()
    create_payments(employees, periods)
    
    print("\n" + "=" * 60)
    print("✓ DATOS GENERADOS EXITOSAMENTE")
    print("=" * 60)
    print(f"Departamentos: {len(departments)}")
    print(f"Posiciones: {len(positions)}")
    print(f"Empleados: {len(employees)}")
    print(f"Campañas: {len(campaigns)}")
    print(f"Conceptos de Pago: {len(concepts)}")
    print(f"Períodos de Pago: {len(periods)}")
    print("\nUsuarios creados con:")
    print("  Username: [nombre].[apellido][numero]")
    print("  Password: password123")
    print("  Email: [username]@callcenter.com")
    print("\n⚠ IMPORTANTE:")
    print("  - Ningún empleado está marcado como supervisor o IT")
    print("  - Puedes asignar estos roles desde el admin de Django")
    print("  - Aproximadamente 80% de empleados están activos")

if __name__ == '__main__':
    main()