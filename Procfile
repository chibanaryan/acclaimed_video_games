web: gunicorn acclaimedgames.wsgi --workers 3 --timeout 600 --graceful-timeout 30 --max-requests 1000 --max-requests-jitter 50
release: python manage.py migrate
