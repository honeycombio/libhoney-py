import os

from django.core.wsgi import get_wsgi_application

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "django_dynamic_fields.settings")

application = get_wsgi_application()
