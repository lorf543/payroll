from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
from core.models import Employee, Department, Position, Campaign
from django.utils import timezone
from datetime import date, timedelta


class Command(BaseCommand):
    help = "Crea empleados normales y los asigna a la primera campaña existente."

    def handle(self, *args, **options):
        # Validar datos base
        departments = list(Department.objects.all())
        positions = list(Position.objects.all())
        campaigns = list(Campaign.objects.all())

        if not departments or not positions or not campaigns:
            self.stdout.write(self.style.ERROR("❌ Debes tener al menos un Department, Position y Campaign creados."))
            return

        self.create_employees(departments, positions, campaigns)

    def create_employees(self, departments, positions, campaigns):
        employees_data = [
            {'username': 'employee1','email':'employee1@company.com','first_name':'Ana','last_name':'Martinez','employee_code':'EMP001','department':departments[0],'position':positions[0]},
            {'username': 'employee2','email':'employee2@company.com','first_name':'Carlos','last_name':'Lopez','employee_code':'EMP002','department':departments[1],'position':positions[1]},
            {'username': 'employee3','email':'employee3@company.com','first_name':'Lucia','last_name':'Fernandez','employee_code':'EMP003','department':departments[0],'position':positions[2]},
            {'username': 'employee4','email':'employee4@company.com','first_name':'Pedro','last_name':'Ramirez','employee_code':'EMP004','department':departments[1],'position':positions[0]},
            {'username': 'employee5','email':'employee5@company.com','first_name':'Sofia','last_name':'Torres','employee_code':'EMP005','department':departments[0],'position':positions[1]},
        ]

        employees = []
        for d in employees_data:
            user, created = User.objects.get_or_create(
                username=d['username'],
                defaults={
                    'email': d['email'],
                    'first_name': d['first_name'],
                    'last_name': d['last_name'],
                }
            )
            if created:
                user.set_password('password123')
                user.save()

            emp, emp_created = Employee.objects.get_or_create(
                user=user,
                defaults={
                    'employee_code': d['employee_code'],
                    'department': d['department'],
                    'position': d['position'],
                    'is_supervisor': False,
                    'hire_date': timezone.now().date() - timedelta(days=200),
                    'birth_date': date(1992, 5, 20),
                    'gender': 'F' if d['first_name'] in ['Ana', 'Lucia', 'Sofia'] else 'M',
                    'phone': '+1-555-0101',
                    'address': '123 Main St, City, State',
                    'city': 'New York',
                    'country': 'USA',
                    'education': 'Bachelor Degree',
                    'email': d['email'],
                    'skills': 'Teamwork,Communication,Problem-solving',
                    'bio': "Dedicated employee with solid work ethic and commitment to company goals.",
                    'current_campaign': campaigns[0],
                }
            )

            employees.append(emp)
            status = "🆕 Created" if emp_created else "⚠️ Already exists"
            self.stdout.write(f"{status}: {emp.full_name} ({emp.employee_code})")

        self.stdout.write(self.style.SUCCESS(f"\n✅ {len(employees)} employees processed and assigned to campaign '{campaigns[0].name}'"))
