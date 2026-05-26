from django.urls import path
from django.contrib.auth import views as auth_views
from . import views

urlpatterns = [
    # Web pública
    path('', views.inicio, name='inicio'),
    path('nosotros/', views.nosotros, name='nosotros'),
    path('servicios/', views.servicios, name='servicios'),
    path('proyectos/', views.proyectos, name='proyectos'),
    path('contacto/', views.contacto, name='contacto'),
    path('especialidad/<str:tipo>/', views.detalle_especialidad, name='detalle_especialidad'),
    path('proyecto/<str:proyecto_id>/', views.detalle_proyecto, name='detalle_proyecto'),

    # Auth
    path('login/', auth_views.LoginView.as_view(template_name='web/login.html'), name='login'),
    path('logout/', auth_views.LogoutView.as_view(next_page='inicio'), name='logout'),

    # ERP
    path('erp/dashboard/', views.dashboard_erp, name='dashboard_erp'),
    path('erp/empleados/', views.gestionar_empleados, name='gestionar_empleados'),
    path('erp/empleados/alternar/<int:empleado_id>/', views.alternar_estado_empleado, name='alternar_estado_empleado'),

    # Tickets / Requerimientos
    path('erp/nuevo-ticket/', views.crear_requerimiento, name='crear_requerimiento'),
    path('erp/ticket/<int:req_id>/materiales/', views.añadir_materiales, name='añadir_materiales'),
    path('erp/ticket/<int:req_id>/pdf/', views.imprimir_pdf_ticket, name='imprimir_pdf_ticket'),
    path('erp/ticket/<int:req_id>/procesar/<str:accion>/', views.procesar_ticket, name='procesar_ticket'),

    # Proyectos
    path('erp/proyectos/', views.gestionar_proyectos, name='gestionar_proyectos'),
    path('erp/proyectos/estado/<int:proyecto_id>/', views.alternar_estado_proyecto, name='alternar_estado_proyecto'),
    path('erp/proyectos/editar/<int:proyecto_id>/', views.editar_proyecto, name='editar_proyecto'),
    path('erp/proyectos/eliminar/<int:proyecto_id>/', views.eliminar_proyecto_erp, name='eliminar_proyecto_erp'),

    # Órdenes de Compra
    path('erp/ordenes-compra/', views.listar_ordenes_compra, name='listar_ordenes_compra'),
    path('erp/ordenes-compra/nueva/', views.crear_orden_compra, name='crear_orden_compra'),
    path('erp/ordenes-compra/<int:oc_id>/items/', views.añadir_items_oc, name='añadir_items_oc'),
    path('erp/ordenes-compra/recibir/<int:oc_id>/', views.recibir_orden_compra, name='recibir_orden_compra'),
    path('erp/ordenes-compra/<int:oc_id>/pdf/', views.imprimir_pdf_oc, name='imprimir_pdf_oc'),
    path('erp/ordenes-compra/aprobar/<int:oc_id>/', views.aprobar_oc, name='aprobar_oc'),

    # Seguridad
    path('erp/seguridad/bloqueos/', views.gestionar_bloqueos, name='gestionar_bloqueos'),
    path('erp/seguridad/desbloquear/<int:intento_id>/', views.desbloquear_usuario, name='desbloquear_usuario'),
    
    # Inventario y Ventas
    path('erp/inventario/', views.inventario_actual, name='inventario_actual'),
    path('erp/inventario/nuevo-material/', views.crear_material, name='crear_material'),
    path('erp/inventario/editar-material/<int:material_id>/', views.editar_material, name='editar_material'),
    path('erp/inventario/ajustar/<int:material_id>/', views.realizar_ajuste, name='realizar_ajuste'),
    path('erp/inventario/auditoria/', views.historial_movimientos, name='historial_movimientos'),
    path('erp/inventario/auditoria/pdf/', views.imprimir_pdf_auditoria, name='imprimir_pdf_auditoria'),
    path('erp/inventario/eliminar/<int:material_id>/', views.eliminar_material, name='eliminar_material'),
    path('erp/inventario/ventas/', views.venta_material, name='venta_material'), # NUEVO REQUERIMIENTO
    
    # Cotizaciones y Compras
    path('erp/cotizacion/atender/<int:solicitud_id>/', views.atender_cotizacion, name='atender_cotizacion'),
    path('erp/cotizacion/desglosar/<int:item_id>/', views.desglosar_item_cotizacion, name='desglosar_item_cotizacion'), # NUEVO REQUERIMIENTO
    path('erp/cotizacion/revisar/<int:solicitud_id>/', views.revisar_cotizacion, name='revisar_cotizacion'),
    path('erp/cotizacion/finalizar/<int:solicitud_id>/', views.finalizar_revision_cotizacion, name='finalizar_revision_cotizacion'),
    path('erp/requerimiento/revisar/<int:req_id>/', views.revisar_requerimiento_items, name='revisar_requerimiento_items'),
]