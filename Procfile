<<<<<<< HEAD
web: gunicorn core.wsgi:application --bind 0.0.0.0:$PORT
<<<<<<< HEAD
worker: python manage.py qcluster
=======
worker: python manage.py qcluster
>>>>>>> d818f4ab883b42c31c85fbe1fd689e6bf14ae702
=======
web: python manage.py migrate && gunicorn payroll.wsgi:application --bind 0.0.0.0:$PORT
worker: python manage.py migrate && python manage.py qcluster
>>>>>>> parent of f05d775 (cluster)
