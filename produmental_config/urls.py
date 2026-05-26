from django.contrib import admin
from django.urls import path, include

urlpatterns = [
    path('portal-gerencial-produmetalcm-2026/', admin.site.urls), # Panel de administrador
    path('', include('web.urls')),   # Delega TODAS las demás rutas a la app 'web'
]