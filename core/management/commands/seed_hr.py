from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
from faker import Faker
import random
from datetime import date, timedelta, datetime
from decimal import Decimal

from core.models import (
    Department, Position, Employee,
    PaymentConcept, PayPeriod, PayrollRecord, PayrollDetail,
    Attendance, Incident
)


class Command(BaseCommand):
    help = "Seed database with dummy HR/Payroll data"

    def handle(self, *args, **kwargs):
        fake = Faker()

        # --- Departments ---
        departments = []
        for name in ["HR", "IT", "Finance", "Sales", "Operations"]:
            dept, _ = Department.objects.get_or_create(
                name=name,
                defaults={
                    "description": f"{name} Department",
                    "annual_budget": random.randint(100000, 500000)
                }
            )
            departments.append(dept)

        # --- Positions ---
        positions = []
        for dept in departments:
            for title in ["Manager", "Analyst", "Assistant", "Intern"]:
                pos, _ = Position.objects.get_or_create(
                    name=f"{dept.name} {title}",
                    department=dept,
                    defaults={
                        "description": f"{title} in {dept.name}",
                        "base_salary": random.randint(20000, 80000),
                        "contract_type": random.choice(["full_time", "part_time", "temporary", "intern"]),
                    }
                )
                positions.append(pos)

        # --- Users & Employees ---
        employees = []
        for i in range(10):
            user = User.objects.create_user(
                username=fake.user_name(),
                email=fake.email(),
                password="password123",
                first_name=fake.first_name(),
                last_name=fake.last_name(),
            )
            emp = Employee.objects.get(user=user)  # auto-created via signal
            emp.position = random.choice(positions)
            emp.department = emp.position.department
            emp.hire_date = fake.date_between(start_date="-3y", end_date="today")
            emp.birth_date = fake.date_of_birth(minimum_age=22, maximum_age=60)
            emp.phone = fake.phone_number()
            emp.address = fake.address()
            emp.city = fake.city()
            emp.country = fake.country()
            emp.save()
            employees.append(emp)

        # --- Payment Concepts ---
        concepts = [
            ("Salary", "earning", "salary"),
            ("Overtime", "earning", "overtime"),
            ("Bonus", "earning", "bonus"),
            ("Commission", "earning", "commission"),
            ("ISR Tax", "deduction", "isr"),
            ("AFP Pension", "deduction", "afp"),
            ("SFS Health", "deduction", "sfs"),
        ]
        for name, t, code in concepts:
            PaymentConcept.objects.get_or_create(
                name=name,
                type=t,
                code=code,
                defaults={
                    "description": f"{name} concept",
                    "fixed_amount": None,
                    "percentage": random.choice([None, Decimal("5.00"), Decimal("10.00")]),
                    "taxable": True if t == "earning" else False,
                }
            )

        # --- Pay Period ---
        start_date = date.today().replace(day=1)
        end_date = (start_date + timedelta(days=30))
        pay_period, _ = PayPeriod.objects.get_or_create(
            name=f"Period {start_date.strftime('%B %Y')}",
            start_date=start_date,
            end_date=end_date,
            pay_date=end_date,
            frequency="monthly",
        )

        # --- Payroll Records ---
        payment_concepts = list(PaymentConcept.objects.all())
        for emp in employees:
            record, _ = PayrollRecord.objects.get_or_create(
                employee=emp,
                period=pay_period,
                defaults={
                    "pay_date": pay_period.pay_date,
                    "gross_salary": emp.position.base_salary if emp.position else 30000,
                    "status": "calculated",
                }
            )

            # Add payroll details
            for _ in range(random.randint(2, 5)):
                concept = random.choice(payment_concepts)
                amount = random.randint(1000, 5000) if concept.type == "earning" else random.randint(500, 2000)
                PayrollDetail.objects.create(
                    payroll_record=record,
                    concept=concept,
                    quantity=1,
                    amount=amount,
                    description=fake.sentence()
                )
            record.calculate_totals()

        # --- Attendance ---
        for emp in employees:
            for i in range(5):  # last 5 working days
                check_in = fake.date_time_this_month(before_now=True, after_now=False).time()
                check_out = (datetime.combine(date.today(), check_in) + timedelta(hours=8)).time()
                Attendance.objects.create(
                    employee=emp,
                    date=date.today() - timedelta(days=i),
                    check_in=check_in,
                    check_out=check_out,
                    comments="Auto-generated"
                )

        # --- Incidents ---
        for emp in employees:
            if random.choice([True, False]):
                Incident.objects.create(
                    employee=emp,
                    type=random.choice(["late", "absence", "vacation"]),
                    date=date.today() - timedelta(days=random.randint(1, 10)),
                    justified=random.choice([True, False]),
                    comments=fake.sentence()
                )

        self.stdout.write(self.style.SUCCESS("✅ Dummy HR/Payroll data generated successfully!"))
