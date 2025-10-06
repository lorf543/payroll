# Procfile
web: gunicorn payroll.wsgi:application --bind 0.0.0.0:$PORT

# railway.json
{
  "deploy": {
"startCommand": "python manage.py migrate && python manage.py collectstatic --noinput && gunicorn payroll.wsgi:application --bind 0.0.0.0:$PORT"
  }
}