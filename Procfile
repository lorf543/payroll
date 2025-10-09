web: python manage.py migrate && gunicorn payroll.wsgi:application --bind 0.0.0.0:$PORT
worker: python manage.py migrate && python manage.py qcluster