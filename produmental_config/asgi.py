"""
ASGI config for produmental_config project.

It exposes the ASGI callable as a module-level variable named ``application``.

For more information on this file, see
https://docs.djangoproject.com/en/6.0/howto/deployment/asgi/
"""

import os

from django.core.asgi import get_asgi_application

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'produmental_config.settings')

application = get_asgi_application()

# Redirecciones de Login y Logout
LOGIN_REDIRECT_URL = 'dashboard_erp'
LOGOUT_REDIRECT_URL = 'inicio'