from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
from core.models import Employee, Department, Position, Campaign
from attendance.models import WorkDay, ActivitySession
from django.utils import timezone
from datetime import datetime, timedelta
import random
from decimal import Decimal

class Command(BaseCommand):
    help = 'Create dummy data for testing the supervisor dashboard'

    def handle(self, *args, **options):
        self.stdout.write('🚀 Creating dummy data...')
        
        # Limpiar datos existentes (opcional - ten cuidado en producción)
        # self.cleanup_data()
        
        # Crear departamentos
        departments = self.create_departments()
        
        # Crear posiciones
        positions = self.create_positions()
        
        # Crear campañas
        campaigns = self.create_campaigns()
        
        # Crear supervisores
        supervisors = self.create_supervisors(departments, positions)
        
        # Crear empleados regulares
        employees = self.create_employees(departments, positions, supervisors)
        
        # Asignar campañas a empleados
        self.assign_campaigns(employees, campaigns)
        
        # Crear datos de attendance
        self.create_attendance_data(employees, campaigns)
        
        self.stdout.write(
            self.style.SUCCESS('✅ Dummy data created successfully!')
        )
        
        self.show_summary(supervisors, employees, campaigns)

    def create_departments(self):
        """Crear departamentos dummy"""
        departments_data = [
            {'name': 'Sales', 'description': 'Sales Department'},
            {'name': 'Support', 'description': 'Customer Support Department'},
            {'name': 'Technical', 'description': 'Technical Support Department'},
            {'name': 'Operations', 'description': 'Operations Department'},
        ]
        
        departments = []
        for data in departments_data:
            dept, created = Department.objects.get_or_create(
                name=data['name'],
                defaults=data
            )
            departments.append(dept)
            if created:
                self.stdout.write(f'✅ Created department: {dept.name}')
        
        return departments

    def create_positions(self):
        """Crear posiciones dummy"""
        positions_data = [
            {'name': 'Sales Agent', 'description': 'Sales Representative', 'hour_rate': Decimal('18.50')},
            {'name': 'Support Agent', 'description': 'Customer Support', 'hour_rate': Decimal('16.75')},
            {'name': 'Technical Support', 'description': 'Technical Support Specialist', 'hour_rate': Decimal('20.00')},
            {'name': 'Team Lead', 'description': 'Team Leader', 'hour_rate': Decimal('22.50')},
            {'name': 'Senior Agent', 'description': 'Senior Customer Service', 'hour_rate': Decimal('19.25')},
        ]
        
        positions = []
        for data in positions_data:
            pos, created = Position.objects.get_or_create(
                name=data['name'],  # Changed from 'title' to 'name'
                defaults=data
            )
            positions.append(pos)
            if created:
                self.stdout.write(f'✅ Created position: {pos.name} (${pos.hour_rate}/hr)')  # Changed from title to name
        
        return positions

    def create_campaigns(self):
        """Crear campañas dummy"""
        campaigns_data = [
            {
                'name': 'Premium Sales Campaign',
                'client_name': 'TechCorp Inc.',
                'description': 'High-value sales campaign for enterprise clients',
                'start_date': timezone.now().date() - timedelta(days=30),
                'end_date': timezone.now().date() + timedelta(days=30),
                'is_active': True,
                'hour_rate': Decimal('22.00'),
                'shutdown_time': datetime.strptime('18:00', '%H:%M').time(),
            },
            {
                'name': 'Customer Support 24/7',
                'client_name': 'Global Services',
                'description': '24/7 customer support campaign',
                'start_date': timezone.now().date() - timedelta(days=15),
                'end_date': timezone.now().date() + timedelta(days=45),
                'is_active': True,
                'hour_rate': Decimal('18.50'),
                'shutdown_time': datetime.strptime('17:30', '%H:%M').time(),
            },
            {
                'name': 'Technical Support',
                'client_name': 'Software Solutions',
                'description': 'Technical support for software products',
                'start_date': timezone.now().date() - timedelta(days=10),
                'end_date': timezone.now().date() + timedelta(days=20),
                'is_active': True,
                'hour_rate': Decimal('21.00'),
                'shutdown_time': datetime.strptime('19:00', '%H:%M').time(),
            },
        ]
        
        campaigns = []
        for data in campaigns_data:
            campaign, created = Campaign.objects.get_or_create(
                name=data['name'],
                defaults=data
            )
            campaigns.append(campaign)
            if created:
                self.stdout.write(f'✅ Created campaign: {campaign.name}')
        
        return campaigns

    def create_supervisors(self, departments, positions):
        """Crear supervisores dummy"""
        supervisors_data = [
            {
                'username': 'supervisor1',
                'email': 'supervisor1@company.com',
                'first_name': 'Maria',
                'last_name': 'Gonzalez',
                'employee_code': 'SUP001',
                'department': departments[0],  # Sales
                'position': positions[3],  # Team Lead
                'is_supervisor': True,
            },
            {
                'username': 'supervisor2', 
                'email': 'supervisor2@company.com',
                'first_name': 'James',
                'last_name': 'Wilson',
                'employee_code': 'SUP002',
                'department': departments[1],  # Support
                'position': positions[3],  # Team Lead
                'is_supervisor': True,
            },
        ]
        
        supervisors = []
        for data in supervisors_data:
            user, created = User.objects.get_or_create(
                username=data['username'],
                defaults={
                    'email': data['email'],
                    'first_name': data['first_name'],
                    'last_name': data['last_name'],
                }
            )
            
            if created:
                user.set_password('password123')
                user.save()
            
            emp, emp_created = Employee.objects.get_or_create(
                user=user,
                defaults={
                    'employee_code': data['employee_code'],
                    'department': data['department'],
                    'position': data['position'],
                    'is_supervisor': data['is_supervisor'],
                    'hire_date': timezone.now().date() - timedelta(days=365),
                    'birth_date': datetime(1985, 6, 15).date(),
                    'gender': 'F' if data['first_name'] == 'Maria' else 'M',
                    'phone': '+1-555-0100',
                    'address': '123 Main St, City, State',
                    'city': 'New York',
                    'country': 'USA',
                    'education': 'Bachelor Degree',
                    'email': data['email'],
                    'skills': 'Leadership,Management,Communication,Training',
                    'bio': f"Experienced supervisor with 5+ years in team management.",
                }
            )
            
            supervisors.append(emp)
            if emp_created:
                self.stdout.write(f'✅ Created supervisor: {emp.user.get_full_name()}')

        return supervisors

    def create_employees(self, departments, positions, supervisors):
        """Crear empleados regulares dummy"""
        employees_data = [
            # Sales Team (Supervisor 1)
            {'first_name': 'John', 'last_name': 'Smith', 'code': 'EMP001', 'dept': 0, 'pos': 0, 'sup': 0},
            {'first_name': 'Sarah', 'last_name': 'Johnson', 'code': 'EMP002', 'dept': 0, 'pos': 0, 'sup': 0},
            {'first_name': 'Mike', 'last_name': 'Davis', 'code': 'EMP003', 'dept': 0, 'pos': 0, 'sup': 0},
            {'first_name': 'Emily', 'last_name': 'Brown', 'code': 'EMP004', 'dept': 0, 'pos': 4, 'sup': 0},
            
            # Support Team (Supervisor 2)
            {'first_name': 'David', 'last_name': 'Wilson', 'code': 'EMP005', 'dept': 1, 'pos': 1, 'sup': 1},
            {'first_name': 'Lisa', 'last_name': 'Miller', 'code': 'EMP006', 'dept': 1, 'pos': 1, 'sup': 1},
            {'first_name': 'Robert', 'last_name': 'Taylor', 'code': 'EMP007', 'dept': 1, 'pos': 2, 'sup': 1},
            {'first_name': 'Jennifer', 'last_name': 'Anderson', 'code': 'EMP008', 'dept': 1, 'pos': 4, 'sup': 1},
            
            # Technical Team (Supervisor 1)
            {'first_name': 'Kevin', 'last_name': 'Thomas', 'code': 'EMP009', 'dept': 2, 'pos': 2, 'sup': 0},
            {'first_name': 'Amanda', 'last_name': 'White', 'code': 'EMP010', 'dept': 2, 'pos': 2, 'sup': 0},
        ]
        
        employees = []
        for data in employees_data:
            username = data['code'].lower()
            email = f"{username}@company.com"
            
            user, created = User.objects.get_or_create(
                username=username,
                defaults={
                    'email': email,
                    'first_name': data['first_name'],
                    'last_name': data['last_name'],
                }
            )
            
            if created:
                user.set_password('password123')
                user.save()
            
            emp, emp_created = Employee.objects.get_or_create(
                user=user,
                defaults={
                    'employee_code': data['code'],
                    'department': departments[data['dept']],
                    'position': positions[data['pos']],
                    'supervisor': supervisors[data['sup']],
                    'is_supervisor': False,
                    'hire_date': timezone.now().date() - timedelta(days=random.randint(30, 300)),
                    'birth_date': datetime(1990 + random.randint(0, 10), random.randint(1, 12), random.randint(1, 28)).date(),
                    'gender': random.choice(['M', 'F']),
                    'phone': f'+1-555-01{random.randint(10, 99)}',
                    'address': f'{random.randint(100, 999)} Main St, City, State',
                    'city': random.choice(['New York', 'Los Angeles', 'Chicago', 'Miami']),
                    'country': 'USA',
                    'education': random.choice(['High School', 'Associate Degree', 'Bachelor Degree', 'Master Degree']),
                    'email': email,
                    'skills': random.choice([
                        'Customer Service,Sales,Communication',
                        'Technical Support,Problem Solving,IT Skills',
                        'Sales,Negotiation,CRM Software',
                        'Support,Troubleshooting,Patience'
                    ]),
                    # FIX THIS LINE - change .title to .name
                    'bio': f"Professional {positions[data['pos']].name} with experience in customer service.",
                    'is_logged_in': random.choice([True, False, False]),  # 33% chance of being logged in
                }
            )
            
            employees.append(emp)
            if emp_created:
                self.stdout.write(f'✅ Created employee: {emp.user.get_full_name()}')

        return employees

    def assign_campaigns(self, employees, campaigns):
        """Asignar campañas a empleados"""
        for employee in employees:
            # Asignar campaña aleatoria
            campaign = random.choice(campaigns)
            employee.current_campaign = campaign
            employee.campaigns.add(campaign)
            employee.save()
            
            # Algunos empleados sin campaña
            if random.random() < 0.2:  # 20% sin campaña
                employee.current_campaign = None
                employee.save()

    def create_attendance_data(self, employees, campaigns):
        """Crear datos de attendance para los últimos 7 días"""
        session_types = ['work', 'break', 'lunch', 'training', 'meeting']
        
        for days_ago in range(7):  # Últimos 7 días
            date = timezone.now().date() - timedelta(days=days_ago)
            
            for employee in employees:
                # 80% de probabilidad de tener datos de attendance ese día
                if random.random() < 0.8:
                    workday, created = WorkDay.objects.get_or_create(
                        employee=employee,
                        date=date,
                        defaults={
                            'check_in': timezone.make_aware(datetime.combine(date, datetime.strptime('09:00', '%H:%M').time())),
                            'status': 'completed' if date < timezone.now().date() else 'active',
                        }
                    )
                    
                    if created:
                        # Crear sesiones para este día
                        start_time = timezone.make_aware(datetime.combine(date, datetime.strptime('09:00', '%H:%M').time()))
                        
                        # Sesión de trabajo mañana
                        morning_end = start_time + timedelta(hours=3)
                        ActivitySession.objects.create(
                            work_day=workday,
                            session_type='work',
                            start_time=start_time,
                            end_time=morning_end,
                            campaign=employee.current_campaign,
                            notes='Morning work session'
                        )
                        
                        # Break
                        break_start = morning_end
                        break_end = break_start + timedelta(minutes=15)
                        ActivitySession.objects.create(
                            work_day=workday,
                            session_type='break',
                            start_time=break_start,
                            end_time=break_end
                        )
                        
                        # Sesión de trabajo tarde
                        afternoon_start = break_end
                        afternoon_end = afternoon_start + timedelta(hours=2, minutes=45)
                        ActivitySession.objects.create(
                            work_day=workday,
                            session_type='work',
                            start_time=afternoon_start,
                            end_time=afternoon_end,
                            campaign=employee.current_campaign,
                            notes='Afternoon work session'
                        )
                        
                        # Lunch
                        lunch_start = afternoon_end
                        lunch_end = lunch_start + timedelta(minutes=30)
                        ActivitySession.objects.create(
                            work_day=workday,
                            session_type='lunch',
                            start_time=lunch_start,
                            end_time=lunch_end
                        )
                        
                        # Sesión final de trabajo
                        final_start = lunch_end
                        final_end = final_start + timedelta(hours=2)
                        ActivitySession.objects.create(
                            work_day=workday,
                            session_type='work',
                            start_time=final_start,
                            end_time=final_end,
                            campaign=employee.current_campaign
                        )
                        
                        # Para hoy, dejar alguna sesión activa
                        if date == timezone.now().date() and employee.is_logged_in:
                            ActivitySession.objects.create(
                                work_day=workday,
                                session_type=random.choice(['work', 'training']),
                                start_time=final_end,
                                campaign=employee.current_campaign,
                                notes='Current active session'
                            )
                        
                        # Calcular métricas del workday
                        workday.calculate_metrics()

    def show_summary(self, supervisors, employees, campaigns):
        """Mostrar resumen de datos creados"""
        self.stdout.write('\n' + '='*50)
        self.stdout.write(self.style.SUCCESS('📊 DUMMY DATA SUMMARY'))
        self.stdout.write('='*50)
        
        self.stdout.write(f'👥 Supervisors: {len(supervisors)}')
        for sup in supervisors:
            team_size = Employee.objects.filter(supervisor=sup).count()
            self.stdout.write(f'   • {sup.user.get_full_name()} - Team: {team_size} employees')
        
        self.stdout.write(f'👨‍💼 Employees: {Employee.objects.filter(is_supervisor=False).count()}')
        self.stdout.write(f'🎯 Campaigns: {len(campaigns)}')
        self.stdout.write(f'📅 WorkDays: {WorkDay.objects.count()}')
        self.stdout.write(f'⏱️  Activity Sessions: {ActivitySession.objects.count()}')
        
        self.stdout.write('\n🔑 Login Credentials:')
        self.stdout.write('   Supervisor 1: supervisor1 / password123')
        self.stdout.write('   Supervisor 2: supervisor2 / password123') 
        self.stdout.write('   Employees: emp001, emp002, etc. / password123')
        
        self.stdout.write('\n🚀 Ready to test! Visit:')
        self.stdout.write('   • /supervisor/dashboard/')
        self.stdout.write('   • /attendance/dashboard/')
        self.stdout.write('   • /employees/profile/')

    def cleanup_data(self):
        """Limpiar datos existentes (usar con cuidado)"""
        if input('⚠️  Delete all existing data? (y/N): ').lower() == 'y':
            self.stdout.write('🧹 Cleaning up existing data...')
            User.objects.filter(username__in=['supervisor1', 'supervisor2']).delete()
            User.objects.filter(username__startswith='emp').delete()
            Employee.objects.all().delete()
            WorkDay.objects.all().delete()
            ActivitySession.objects.all().delete()