"""
Django settings for produmental_config project.
"""

from pathlib import Path
import os # Importante para leer variables de entorno
import dj_database_url
from decouple import config

# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent

# ==============================================================================
# 1. CONFIGURACIÓN DE SEGURIDAD Y DESPLIEGUE (Variables de Entorno)
# ==============================================================================
# En producción (Render), debes crear estas variables en su panel de control.
# Si no existen (como en tu PC local), usa valores por defecto.

SECRET_KEY = os.environ.get('DJANGO_SECRET_KEY', 'django-insecure-=acf2&x9ijyhcy-(gaoi%d1nkx#a_9r3z&$ta#t!kfm1@)8l1c')

# DEBUG será True en tu PC, pero se apagará automáticamente en producción si configuras la variable en Render.
DEBUG = os.environ.get('DJANGO_DEBUG', 'True') == 'True'

ALLOWED_HOSTS = [
    'localhost', 
    '127.0.0.1', 
    'produmetal.onrender.com', 
    'produmetalcm.com', 
    'www.produmetalcm.com'
]

# ==============================================================================
# 2. DEFINICIÓN DE APLICACIONES Y MIDDLEWARE
# ==============================================================================

INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'web',
    'axes', # <-- NUEVO: Escudo protector contra fuerza bruta
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
    'axes.middleware.AxesMiddleware', # <-- NUEVO: Interceptor de logins de Axes
]

ROOT_URLCONF = 'produmental_config.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

WSGI_APPLICATION = 'produmental_config.wsgi.application'

# ==============================================================================
# 3. BASE DE DATOS
# ==============================================================================

DATABASES = {
    'default': dj_database_url.config(
        default=f'sqlite:///{BASE_DIR / "db.sqlite3"}',
        conn_max_age=600
    )
}
# NOTA: Para subir a Render, más adelante cambiaremos esto a PostgreSQL para no perder datos.

# ==============================================================================
# 4. AUTENTICACIÓN Y PROTECCIÓN DE LOGIN (AXES)
# ==============================================================================

AUTHENTICATION_BACKENDS = [
    'axes.backends.AxesStandaloneBackend',
    'django.contrib.auth.backends.ModelBackend',
]

# Reglas de bloqueo
AXES_FAILURE_LIMIT = 3               # Máximo 3 intentos fallidos
AXES_LOCK_OUT_AT_FAILURE = True      # Bloquear cuenta al llegar al límite
AXES_COOLOFF_TIME = 1                # Tiempo de castigo en horas (1 hora)
AXES_RESET_ON_SUCCESS = True         # Si entra bien a la 2da vez, la cuenta vuelve a 0
AXES_LOCKOUT_PARAMETERS = ["username"] # Bloquea al usuario, no a la IP (evita bloquear a toda la empresa)
#AXES_ONLY_USER_FAILURES = True

AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator',},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator',},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator',},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator',},
]

# ==============================================================================
# 5. REGIONALIZACIÓN (Idioma y Hora ERP)
# ==============================================================================

LANGUAGE_CODE = 'es-ec' # Español de Ecuador
TIME_ZONE = 'America/Guayaquil' # Zona horaria local exacta para el registro del ERP
USE_I18N = True
USE_TZ = True

# ==============================================================================
# 6. ARCHIVOS ESTÁTICOS Y MULTIMEDIA
# ==============================================================================

STATIC_URL = 'static/'
STATICFILES_DIRS = [
    os.path.join(BASE_DIR, 'web/static'),
]
STATIC_ROOT = os.path.join(BASE_DIR, 'staticfiles')

MEDIA_URL = '/media/'
MEDIA_ROOT = os.path.join(BASE_DIR, 'media')

# ==============================================================================
# 7. REGLAS DE SEGURIDAD ESTRICTA (Se activan solas en Producción)
# ==============================================================================
# Las encerramos en un "if not DEBUG" para que no rompan tu entorno local.
# Cuando subas a Render y apagues el DEBUG, tu página se volverá un búnker.

if not DEBUG:
    SECURE_BROWSER_XSS_FILTER = True
    SECURE_CONTENT_TYPE_NOSNIFF = True
    SESSION_COOKIE_SECURE = True 
    CSRF_COOKIE_SECURE = True    
    SECURE_SSL_REDIRECT = True
    
    # Previene que otras páginas clonen la tuya en un recuadro falso (Clickjacking)
    X_FRAME_OPTIONS = 'DENY'
    
    # HSTS: Obliga a los navegadores de los clientes a comunicarse SOLO por HTTPS cifrado
    SECURE_HSTS_SECONDS = 31536000 
    SECURE_HSTS_INCLUDE_SUBDOMAINS = True
    SECURE_HSTS_PRELOAD = True

    SECRET_KEY = config('DJANGO_SECRET_KEY')
    DEBUG = config('DJANGO_DEBUG', cast=bool)


# Cloudinary — solo activar cuando vayas a producción en Render
# Cuando tengas las credenciales, descomenta esto y añádelas al .env
# CLOUDINARY_STORAGE = {
#     'CLOUD_NAME': config('CLOUDINARY_NAME'),
#     'API_KEY': config('CLOUDINARY_KEY'),
#     'API_SECRET': config('CLOUDINARY_SECRET'),
# }
# DEFAULT_FILE_STORAGE = 'cloudinary_storage.storage.MediaCloudinaryStorage'