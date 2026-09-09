from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.views.static import serve as serve_static_file

urlpatterns = [
    path('portal-gerencial-produmetalcm-2026/', admin.site.urls), # Panel de administrador
    path('', include('web.urls')),   # Delega TODAS las demás rutas a la app 'web'
]

if not settings.USING_S3_STORAGE:
    # Sin S3 configurado, los archivos subidos (cotizaciones, facturas,
    # certificados) quedan en disco local bajo MEDIA_ROOT. Sin esta ruta,
    # Django nunca sirve /media/*: cualquier enlace a un archivo subido
    # devuelve 404 "Not Found" aunque el archivo exista en el servidor.
    # Nota: en Render el disco es efímero (se borra en cada deploy); para
    # que los archivos persistan de verdad hay que configurar las
    # variables AWS_ACCESS_KEY_ID / AWS_SECRET_ACCESS_KEY / etc. en el
    # panel de Render, no solo servir este directorio.
    urlpatterns += [
        path('media/<path:path>', serve_static_file, {'document_root': settings.MEDIA_ROOT}),
    ]