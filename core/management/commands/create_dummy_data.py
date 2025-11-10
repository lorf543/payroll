from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
from core.models import Employee, Department, Position, Campaign
from attendance.models import WorkDay, ActivitySession
from django.utils import timezone
from datetime import datetime, timedelta, time, date
import random
from decimal import Decimal


# from django.contrib.auth import get_user_model
# user = get_user_model()
# user = User.objects.get(username='admin')
# user.set_password('adminpass')
# user.save()

class Command(BaseCommand):
    help = 'Create dummy data for testing the supervisor dashboard with active sessions'

    def handle(self, *args, **options):
        self.stdout.write('🚀 Creating dummy data...')

        departments = self.create_departments()
        positions = self.create_positions()
        campaigns = self.create_campaigns()
        supervisors = self.create_supervisors(departments, positions)
        employees = self.create_employees(departments, positions, supervisors)
        self.assign_campaigns(employees, campaigns)
        self.create_attendance_data(employees, campaigns)
        self.stdout.write(self.style.SUCCESS('✅ Dummy data created successfully!'))
        self.show_summary(supervisors, employees, campaigns)

    # ---------- Departments ----------
    def create_departments(self):
        data = [
            {'name': 'Sales', 'description': 'Sales Department'},
            {'name': 'Support', 'description': 'Customer Support Department'},
            {'name': 'Technical', 'description': 'Technical Support Department'},
            {'name': 'Operations', 'description': 'Operations Department'},
        ]
        depts = []
        for d in data:
            dept, created = Department.objects.get_or_create(name=d['name'], defaults=d)
            depts.append(dept)
            if created:
                self.stdout.write(f'✅ Created department: {dept.name}')
        return depts

    # ---------- Positions ----------
    def create_positions(self):
        data = [
            {'name': 'Sales Agent', 'description': 'Sales Representative', 'hour_rate': Decimal('18.50')},
            {'name': 'Support Agent', 'description': 'Customer Support', 'hour_rate': Decimal('16.75')},
            {'name': 'Technical Support', 'description': 'Technical Support Specialist', 'hour_rate': Decimal('20.00')},
            {'name': 'Team Lead', 'description': 'Team Leader', 'hour_rate': Decimal('22.50')},
            {'name': 'Senior Agent', 'description': 'Senior Customer Service', 'hour_rate': Decimal('19.25')},
        ]
        positions = []
        for d in data:
            pos, created = Position.objects.get_or_create(name=d['name'], defaults=d)
            positions.append(pos)
            if created:
                self.stdout.write(f'✅ Created position: {pos.name} (${pos.hour_rate}/hr)')
        return positions

    # ---------- Campaigns ----------
    def create_campaigns(self):
        campaigns_data = [
            {'name': 'Premium Sales Campaign', 'client_name': 'TechCorp Inc.', 'description': 'High-value sales campaign for enterprise clients',
             'start_date': timezone.now().date() - timedelta(days=30), 'end_date': timezone.now().date() + timedelta(days=30),
             'is_active': True, 'hour_rate': Decimal('22.00'), 'shutdown_time': time(hour=18, minute=0)},
            {'name': 'Customer Support 24/7', 'client_name': 'Global Services', 'description': '24/7 customer support campaign',
             'start_date': timezone.now().date() - timedelta(days=15), 'end_date': timezone.now().date() + timedelta(days=45),
             'is_active': True, 'hour_rate': Decimal('18.50'), 'shutdown_time': time(hour=17, minute=30)},
            {'name': 'Technical Support', 'client_name': 'Software Solutions', 'description': 'Technical support for software products',
             'start_date': timezone.now().date() - timedelta(days=10), 'end_date': timezone.now().date() + timedelta(days=20),
             'is_active': True, 'hour_rate': Decimal('21.00'), 'shutdown_time': time(hour=19, minute=0)},
        ]
        campaigns = []
        for data in campaigns_data:
            campaign, created = Campaign.objects.get_or_create(name=data['name'], defaults=data)
            campaigns.append(campaign)
            if created:
                self.stdout.write(f'✅ Created campaign: {campaign.name}')
        return campaigns

    # ---------- Supervisors ----------
    def create_supervisors(self, departments, positions):
        data = [
            {'username': 'supervisor1','email':'supervisor1@company.com','first_name':'Maria','last_name':'Gonzalez','employee_code':'SUP001','department':departments[0],'position':positions[3],'is_supervisor':True},
            {'username': 'supervisor2','email':'supervisor2@company.com','first_name':'James','last_name':'Wilson','employee_code':'SUP002','department':departments[1],'position':positions[3],'is_supervisor':True},
        ]
        supervisors = []
        for d in data:
            user, created = User.objects.get_or_create(username=d['username'], defaults={'email': d['email'],'first_name': d['first_name'],'last_name': d['last_name']})
            if created:
                user.set_password('password123')
                user.save()
            emp, _ = Employee.objects.get_or_create(
                user=user,
                defaults={
                    'employee_code': d['employee_code'],
                    'department': d['department'],
                    'position': d['position'],
                    'is_supervisor': True,
                    'hire_date': timezone.now().date() - timedelta(days=365),
                    'birth_date': date(1985,6,15),
                    'gender': 'F' if d['first_name']=='Maria' else 'M',
                    'phone': '+1-555-0100',
                    'address': '123 Main St, City, State',
                    'city': 'New York',
                    'country': 'USA',
                    'education': 'Bachelor Degree',
                    'email': d['email'],
                    'skills': 'Leadership,Management,Communication,Training',
                    'bio': "Experienced supervisor with 5+ years in team management.",
                }
            )
            supervisors.append(emp)
        return supervisors

    # ---------- Employees ----------
    def create_employees(self, departments, positions, supervisors):
        employees_data = [
            {'first_name':'John','last_name':'Smith','code':'EMP001','dept':0,'pos':0,'sup':0},
            {'first_name':'Sarah','last_name':'Johnson','code':'EMP002','dept':0,'pos':0,'sup':0},
            {'first_name':'Mike','last_name':'Davis','code':'EMP003','dept':0,'pos':0,'sup':0},
            {'first_name':'Emily','last_name':'Brown','code':'EMP004','dept':0,'pos':4,'sup':0},
            {'first_name':'David','last_name':'Wilson','code':'EMP005','dept':1,'pos':1,'sup':1},
            {'first_name':'Lisa','last_name':'Miller','code':'EMP006','dept':1,'pos':1,'sup':1},
            {'first_name':'Robert','last_name':'Taylor','code':'EMP007','dept':1,'pos':2,'sup':1},
            {'first_name':'Jennifer','last_name':'Anderson','code':'EMP008','dept':1,'pos':4,'sup':1},
            {'first_name':'Kevin','last_name':'Thomas','code':'EMP009','dept':2,'pos':2,'sup':0},
            {'first_name':'Amanda','last_name':'White','code':'EMP010','dept':2,'pos':2,'sup':0},
        ]
        employees = []
        for d in employees_data:
            username = d['code'].lower()
            email = f"{username}@company.com"
            user, created = User.objects.get_or_create(username=username, defaults={'email': email,'first_name': d['first_name'],'last_name': d['last_name']})
            if created:
                user.set_password('password123')
                user.save()
            emp, _ = Employee.objects.get_or_create(
                user=user,
                defaults={
                    'employee_code': d['code'],
                    'department': departments[d['dept']],
                    'position': positions[d['pos']],
                    'supervisor': supervisors[d['sup']],
                    'is_supervisor': False,
                    'hire_date': timezone.now().date() - timedelta(days=random.randint(30,300)),
                    'birth_date': date(1990+random.randint(0,10), random.randint(1,12), random.randint(1,28)),
                    'gender': random.choice(['M','F']),
                    'phone': f'+1-555-01{random.randint(10,99)}',
                    'address': f'{random.randint(100,999)} Main St, City, State',
                    'city': random.choice(['New York','Los Angeles','Chicago','Miami']),
                    'country': 'USA',
                    'education': random.choice(['High School','Associate Degree','Bachelor Degree','Master Degree']),
                    'email': email,
                    'skills': random.choice(['Customer Service,Sales,Communication','Technical Support,Problem Solving,IT Skills','Sales,Negotiation,CRM Software','Support,Troubleshooting,Patience']),
                    'bio': f"Professional {positions[d['pos']].name} with experience in customer service.",
                    'is_logged_in': random.choice([True, False, False]),
                }
            )
            employees.append(emp)
        return employees

    # ---------- Assign campaigns ----------
    def assign_campaigns(self, employees, campaigns):
        for emp in employees:
            campaign = random.choice(campaigns)
            emp.current_campaign = campaign
            emp.campaigns.add(campaign)
            emp.save()
            if random.random()<0.2:
                emp.current_campaign = None
                emp.save()

    # ---------- Attendance Data ----------
    def create_attendance_data(self, employees, campaigns):
        for emp in employees:
            created_days = 0
            offset = 0
            while created_days < 10:
                work_date = timezone.now().date() - timedelta(days=offset)
                offset += 1
                if work_date.weekday() == 6:  # Skip Sundays
                    continue

                # Crear WorkDay (9:00 AM - 5:00 PM máximo)
                check_in_time = datetime.combine(work_date, time(9, 0))
                check_out_time = datetime.combine(work_date, time(17, 0))  # 8 horas totales
                workday, _ = WorkDay.objects.get_or_create(
                    employee=emp,
                    date=work_date,
                    defaults={
                        'check_in': check_in_time,
                        'check_out': check_out_time,
                        'status': 'completed'
                    }
                )

                # Definir estructura del día:
                # 9:00 - 11:00  → work
                # 11:00 - 11:15 → break 1
                # 11:15 - 13:15 → work
                # 13:15 - 13:45 → lunch
                # 13:45 - 15:45 → work
                # 15:45 - 16:00 → break 2
                # 16:00 - 17:00 → work

                sessions_plan = [
                    ('work', time(9, 0), time(11, 0)),
                    ('break', time(11, 0), time(11, 15)),
                    ('work', time(11, 15), time(13, 15)),
                    ('lunch', time(13, 15), time(13, 45)),
                    ('work', time(13, 45), time(15, 45)),
                    ('break', time(15, 45), time(16, 0)),
                    ('work', time(16, 0), time(17, 0)),
                ]

                # Crear sesiones según el plan
                for s_type, start_t, end_t in sessions_plan:
                    ActivitySession.objects.create(
                        work_day=workday,
                        session_type=s_type,
                        start_time=datetime.combine(work_date, start_t),
                        end_time=datetime.combine(work_date, end_t),
                        campaign=emp.current_campaign if s_type == 'work' else None
                    )

                # Si el empleado está logueado, crear una sesión activa (sin finalizar)
                if work_date == timezone.now().date() and emp.is_logged_in:
                    ActivitySession.objects.create(
                        work_day=workday,
                        session_type='work',
                        start_time=datetime.combine(work_date, time(17, 0)),
                        campaign=emp.current_campaign,
                        notes='Active live session after main shift'
                    )
                    workday.status = 'active'
                else:
                    workday.status = 'completed'

                # Calcular métricas finales y guardar
                workday.calculate_metrics()
                workday.save()

                created_days += 1
    # ---------- Summary ----------
    def show_summary(self, supervisors, employees, campaigns):
        self.stdout.write('\n'+'='*50)
        self.stdout.write(self.style.SUCCESS('📊 DUMMY DATA SUMMARY'))
        self.stdout.write('='*50)
        self.stdout.write(f'👥 Supervisors: {len(supervisors)}')
        for sup in supervisors:
            team_size = Employee.objects.filter(supervisor=sup).count()
            self.stdout.write(f'   • {sup.user.get_full_name()} - Team: {team_size} employees')
        self.stdout.write(f'👨‍💼 Employees: {len(employees)}')
        self.stdout.write(f'🎯 Campaigns: {len(campaigns)}')
        self.stdout.write(f'📅 WorkDays: {WorkDay.objects.count()}')
        self.stdout.write(f'⏱️ Activity Sessions: {ActivitySession.objects.count()}')
        self.stdout.write('\n🔑 Login Credentials:')
        self.stdout.write('   Supervisor 1: supervisor1 / password123')
        self.stdout.write('   Supervisor 2: supervisor2 / password123')
        self.stdout.write('   Employees: emp001, emp002, etc. / password123')
