web: gunicorn acclaimedgames.wsgi --workers 3 --timeout 30 --graceful-timeout 10 --max-requests 1000 --max-requests-jitter 50
release: python manage.py migrate