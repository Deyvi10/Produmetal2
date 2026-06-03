"""
Django settings for produmental_config project.
"""

from pathlib import Path
import os 
import dj_database_url

# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent

# ==============================================================================
# 1. CONFIGURACIÓN DE SEGURIDAD Y DESPLIEGUE
# ==============================================================================
# Se utilizan variables de entorno nativas (os.environ) para máxima compatibilidad con Render
SECRET_KEY = os.environ.get('DJANGO_SECRET_KEY', 'django-insecure-=acf2&x9ijyhcy-(gaoi%d1nkx#a_9r3z&$ta#t!kfm1@)8l1c')

# DEBUG será True en local, pero se apagará automáticamente en producción si se configura la variable
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
    'axes', 
    'simple_history', # <-- AGREGADO: Motor de trazabilidad absoluta
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
    'axes.middleware.AxesMiddleware', 
    'simple_history.middleware.HistoryRequestMiddleware', # <-- AGREGADO: Captura el usuario e IP en cada cambio
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
# dj_database_url detectará automáticamente si existe una URL de PostgreSQL en producción.
# Si no la hay (desarrollo local), utilizará SQLite3 por defecto.
DATABASES = {
    'default': dj_database_url.config(
        default=f'sqlite:///{BASE_DIR / "db.sqlite3"}',
        conn_max_age=600,
        conn_health_checks=True, # <-- AGREGADO: Previene caídas por pérdida de conexión
    )
}

# ==============================================================================
# 4. AUTENTICACIÓN Y PROTECCIÓN DE LOGIN (AXES)
# ==============================================================================
AUTHENTICATION_BACKENDS = [
    'axes.backends.AxesStandaloneBackend',
    'django.contrib.auth.backends.ModelBackend',
]

AXES_FAILURE_LIMIT = 3               
AXES_LOCK_OUT_AT_FAILURE = True      
AXES_COOLOFF_TIME = 1                
AXES_RESET_ON_SUCCESS = True         
AXES_LOCKOUT_PARAMETERS = ["username"] 

AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator',},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator',},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator',},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator',},
]

# ==============================================================================
# 5. REGIONALIZACIÓN (Idioma y Hora ERP)
# ==============================================================================
LANGUAGE_CODE = 'es-ec' 
TIME_ZONE = 'America/Guayaquil' 
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
# 7. REGLAS DE SEGURIDAD ESTRICTA (Producción)
# ==============================================================================
if not DEBUG:
    SECURE_BROWSER_XSS_FILTER = True
    SECURE_CONTENT_TYPE_NOSNIFF = True
    SESSION_COOKIE_SECURE = True 
    CSRF_COOKIE_SECURE = True    
    SECURE_SSL_REDIRECT = True
    
    X_FRAME_OPTIONS = 'DENY'
    
    SECURE_HSTS_SECONDS = 31536000 
    SECURE_HSTS_INCLUDE_SUBDOMAINS = True
    SECURE_HSTS_PRELOAD = True

    # <-- AGREGADO: Motor de compresión de estáticos obligatorio para despliegues modernos (Render/Heroku)
    STATICFILES_STORAGE = 'whitenoise.storage.CompressedManifestStaticFilesStorage'


# Cloudinary — solo activar cuando vayas a producción en Render
# Cuando tengas las credenciales, descomenta esto y añádelas al .env
# CLOUDINARY_STORAGE = {
#     'CLOUD_NAME': config('CLOUDINARY_NAME'),
#     'API_KEY': config('CLOUDINARY_KEY'),
#     'API_SECRET': config('CLOUDINARY_SECRET'),
# }
# DEFAULT_FILE_STORAGE = 'cloudinary_storage.storage.MediaCloudinaryStorage'