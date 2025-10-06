import random
from faker import Faker
from decimal import Decimal
from datetime import date, timedelta

from django.contrib.auth.models import User
from core.models import Department, Position, Employee

fake = Faker()

# Call Center Departments (ensure these exist in DB)
departments = Department.objects.all()
if not departments.exists():
    # Optional: Create some if none exist
    departments = [
        Department.objects.create(name="Customer Support"),
        Department.objects.create(name="Technical Support"),
        Department.objects.create(name="Sales"),
        Department.objects.create(name="Human Resources"),
        Department.objects.create(name="IT"),
    ]
else:
    departments = list(departments)

# Call center positions
call_center_positions = [
    {
        "name": "Call Center Agent",
        "contract_type": "full_time",
        "base_salary": Decimal("30000.00"),
        "description": "Handles inbound and outbound calls from customers.",
    },
    {
        "name": "Team Leader",
        "contract_type": "full_time",
        "base_salary": Decimal("40000.00"),
        "description": "Leads a team of agents.",
    },
    {
        "name": "Quality Assurance Analyst",
        "contract_type": "full_time",
        "base_salary": Decimal("42000.00"),
        "description": "Monitors and evaluates agent performance.",
    },
    {
        "name": "Trainer",
        "contract_type": "full_time",
        "base_salary": Decimal("45000.00"),
        "description": "Trains new hires and existing staff.",
    },
    {
        "name": "Workforce Analyst",
        "contract_type": "full_time",
        "base_salary": Decimal("48000.00"),
        "description": "Monitors call volume and staffing levels.",
    },
    {
        "name": "Operations Manager",
        "contract_type": "full_time",
        "base_salary": Decimal("60000.00"),
        "description": "Oversees call center operations.",
    },
    {
        "name": "IT Support Specialist",
        "contract_type": "full_time",
        "base_salary": Decimal("50000.00"),
        "description": "Supports technical infrastructure.",
    },
    {
        "name": "HR Coordinator",
        "contract_type": "full_time",
        "base_salary": Decimal("40000.00"),
        "description": "Manages employee-related processes.",
    },
]

# Create Positions if not exist
created_positions = []
for pos in call_center_positions:
    dept = random.choice(departments)
    position, created = Position.objects.get_or_create(
        name=pos["name"],
        department=dept,
        defaults={
            "description": pos["description"],
            "contract_type": pos["contract_type"],
            "base_salary": pos["base_salary"],
            "hour_rate": None,
            "fixed_rate": True,
            "benefits": "Standard company benefits",
        }
    )
    created_positions.append(position)

# Generate 20 employees
for i in range(20):
    first_name = fake.first_name()
    last_name = fake.last_name()
    email = fake.unique.email()
    username = f"{first_name.lower()}.{last_name.lower()}{random.randint(100,999)}"

    # Create user
    user = User.objects.create_user(
        username=username,
        first_name=first_name,
        last_name=last_name,
        email=email,
        password='defaultpassword123'
    )

    position = random.choice(created_positions)
    department = position.department
    birth_date = fake.date_of_birth(minimum_age=21, maximum_age=45)
    hire_date = fake.date_between(start_date="-5y", end_date="today")

    employee = Employee.objects.create(
        user=user,
        identification=fake.unique.ssn(),
        employee_code=f"EMP{1000+i}",
        position=position,
        department=department,
        hire_date=hire_date,
        birth_date=birth_date,
        gender=random.choice(["M", "F"]),
        marital_status=random.choice(['single', 'married', 'divorced']),
        phone=fake.phone_number(),
        address=fake.address(),
        city=fake.city(),
        country=fake.country(),
        is_active=True,
        bio=fake.text(max_nb_chars=100),
        education=random.choice(["High School", "Associate Degree", "Bachelor's"]),
        skills=", ".join(fake.words(nb=5)),
        email=email,
        bank_name=random.choice(["Bank A", "Bank B", "Bank C"]),
        bank_account=fake.bban(),
    )

print("✅ Successfully created 20 employees with positions.")
