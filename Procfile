release: python backend/src/baserow/manage.py migrate
web: gunicorn baserow.config.wsgi:application --bind 0.0.0.0:$PORT --workers 4 --timeout 120
worker: celery -A baserow.config worker -l info
