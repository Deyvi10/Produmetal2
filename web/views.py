from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib import messages
from django.contrib.auth.models import User, Group
from django.db.models import F, Q
from axes.models import AccessAttempt
from django.db import transaction
from django.core.paginator import Paginator
from .forms import MaterialForm
from decimal import Decimal
from axes.utils import reset

# =======================================================
# IMPORTACIONES DE MODELOS Y FORMULARIOS
# =======================================================
from .models import (
    Requerimiento, DetalleRequerimiento, Material, Proyecto, MovimientoInventario, 
    OrdenCompra, DetalleOrdenCompra, SolicitudCompra, CotizacionItem, Bodega, StockBodega,
    Categoria, PerfilEmpleado
    )
from .forms import (
    RequerimientoForm, DetalleRequerimientoForm, RegistroEmpleadoForm, 
    ProyectoForm, OrdenCompraForm, DetalleOrdenCompraForm, AjusteInventarioForm,
    VentaMaterialForm, BodegaForm, CategoriaForm
)

# IMPORTS PARA GENERACIÓN DE PDF
from django.template.loader import get_template
from django.http import HttpResponse
from xhtml2pdf import pisa
import os
from django.conf import settings
from django.utils import timezone

# =======================================================
# VISTAS DE LA PÁGINA WEB PÚBLICA
# =======================================================

def inicio(request):
    return render(request, 'web/inicio.html')

def nosotros(request):
    context = {
        'historia': "ProduMetal CM es una empresa dedicada a la gestión, diseño, fabricación y montaje de estructuras y carpintería metálica de alta calidad. Con 8 años de experiencia en estructuras metálicas y más de 20 años en carpintería metálica, nos hemos establecido como una opción confiable para proyectos residenciales, industriales y comerciales.",
        'mision': "Nos comprometemos a gestionar, diseñar y fabricar estructuras metálicas de alta calidad que superen las expectativas de nuestros clientes, garantizando la eficiencia, seguridad y sostenibilidad en cada proyecto.",
        'vision': "Ser una opción confiable para nuestros clientes en la fabricación de estructuras metálicas, mediante la innovación continua, la mejora de nuestros procesos y la entrega de soluciones de alta calidad."
    }
    return render(request, 'web/nosotros.html', context)

def servicios(request):
    lista_servicios = [
        {'titulo': 'Análisis y Diseño Estructural', 'desc': 'Cálculos precisos y seguridad.', 'img': 'serv_diseno.jpg'},
        {'titulo': 'Fabricación y Montaje', 'desc': 'Construcciones de gran envergadura.', 'img': 'serv_montaje.jpg'},
        {'titulo': 'Planos de Fabricación', 'desc': 'Detalles técnicos para taller.', 'img': 'serv_planos.jpg'},
        {'titulo': 'Control de Calidad', 'desc': 'Supervisión y dossier técnico.', 'img': 'serv_calidad.jpg'},
        {'titulo': 'Protección Anticorrosiva', 'desc': 'Pintura y galvanizado.', 'img': 'serv_pintura.jpg'},
        {'titulo': 'Soldadores Calificados', 'desc': 'Personal certificado AWS.', 'img': 'serv_soldadura.jpg'},
        {'titulo': 'Estructuras Metálicas', 'desc': 'Naves industriales optimizadas.', 'img': 'serv_galpon.jpg'},
        {'titulo': 'Techos y Cubiertas', 'desc': 'Galvalume y policarbonato.', 'img': 'serv_techo.jpg'},
        {'titulo': 'Losa Colaborante', 'desc': 'Instalación de Steel Deck.', 'img': 'serv_losa.jpg'},
        {'titulo': 'Gradas Metálicas', 'desc': 'Escaleras industriales y de lujo.', 'img': 'serv_grada.jpg'},
        {'titulo': 'Carpintería Metálica', 'desc': 'Puertas, rejas y pasamanos.', 'img': 'serv_puerta.jpg'},
    ]
    return render(request, 'web/servicios.html', {'servicios': lista_servicios})

def detalle_especialidad(request, tipo):
    datos = {
        'estructuras': {
            'titulo': 'Estructuras Metálicas',
            'desc_larga': 'Nos especializamos en el diseño, fabricación y montaje de estructuras de acero de alta complejidad. Desde naves industriales hasta edificios comerciales, garantizamos resistencia sísmica y durabilidad.',
            'galeria': ['est1.jpg', 'est2.jpg', 'est3.jpg', 'est4.jpg','est5.jpg','est6.jpg', 'est7.jpg', 'est8.jpg', 'est9.jpg']
        },
        'carpinteria': {
            'titulo': 'Carpintería Metálica',
            'desc_larga': 'El arte del metal aplicado a tu hogar o negocio. Creamos portones, pasamanos, rejas de seguridad y muebles con acabados finos y soldadura invisible donde se requiere.',
            'galeria': ['carp1.jpg', 'carp2.jpg', 'carp3.jpg', 'carp4.jpg', 'carp5.jpg']
        },
        'ingenieria': {
            'titulo': 'Ingeniería y Diseño',
            'desc_larga': 'Antes de soldar, calculamos. Nuestro departamento de ingeniería elabora planos de taller, memorias de cálculo y modelado 3D para asegurar que tu proyecto sea viable y seguro.',
            'galeria': ['ing1.jpg', 'ing2.jpg', 'ing3.jpg', 'ing4.jpg']
        }
    }
    
    info = datos.get(tipo)
    return render(request, 'web/detalle_especialidad.html', {'info': info})

def proyectos(request):
    lista_proyectos = [
        {'id': 'plaza-kocoa', 'titulo': 'Plaza Kocoa', 'categoria': 'Comercial / Estructuras', 'img': 'kocoa/kocoa_main.jpg'},
        {'id': 'campo-oh', 'titulo': 'Casa de Campo O&H', 'categoria': 'Residencial / Diseño', 'img': 'oh_main.jpg'},
        {'id': 'san-isidro', 'titulo': 'Conjunto San Isidro', 'categoria': 'Residencial / Carpintería', 'img': 'isidro_main.jpg'},
        {'id': 'vaca-lima', 'titulo': 'Residencia Vaca Lima', 'categoria': 'Residencial / Estructura Mixta', 'img': 'vaca_main.jpg'},
        {'id': 'residencia-art', 'titulo': 'Residencia Arteaga', 'categoria': 'Residencial / Estructura Mixta', 'img': 'arteaga_main.jpg'}
    ]
    return render(request, 'web/proyectos.html', {'proyectos': lista_proyectos})

def detalle_proyecto(request, proyecto_id):
    datos_proyectos = {
        'plaza-kocoa': {
            'titulo': 'Plaza Kocoa',
            'ubicacion': 'Conocoto',
            'descripcion': 'Plaza Kocoa es un moderno proyecto comercial ubicado en Conocoto, diseñado para ofrecer espacios funcionales...',
            'fotos': ['kocoa/kocoa1.jpg', 'kocoa/kocoa2.jpg', 'kocoa/kocoa3.jpg', 'kocoa/kocoa4.jpg'],
            'videos': ['kocoa/kocoa_vid.mp4']
        },
        'campo-oh': {
            'titulo': 'Casa de Campo O&H',
            'ubicacion': 'Proyecto Residencial',
            'descripcion': 'Residencia O&H es un proyecto que integra la estructura metálica con principios geométricos...',
            'fotos': ['campo/campo1.jpg', 'campo/campo2.jpg', 'campo/campo3.jpg', 'campo/campo4.jpg', 'campo/campo5.jpg', 'campo/campo6.jpg', 'campo/campo7.jpg', 'campo/campo8.jpg', 'campo/campo9.jpg'],
            'videos': ['campo/campo_video1.mp4','campo/campo_video2.mp4']
        },
        'san-isidro': {
            'titulo': 'Conjunto de Casas San Isidro',
            'ubicacion': 'San Isidro',
            'descripcion': 'Un desarrollo residencial de primer nivel donde la carpintería y estructura metálica de ProduMetal CM aportan seguridad...',
            'fotos': ['conjunto/isidro1.jpg', 'conjunto/isidro2.jpg', 'conjunto/isidro3.jpg', 'conjunto/isidro4.jpg', 'conjunto/isidro5.jpg', 'conjunto/isidro6.jpg', 'conjunto/isidro7.jpg', 'conjunto/isidro8.jpg', 'conjunto/isidro9.jpg', 'conjunto/isidro10.jpg', 'conjunto/isidro11.jpg'],
            'videos': [] 
        },
        'vaca-lima': {
            'titulo': 'Residencia Vaca Lima',
            'ubicacion': 'Proyecto Residencial Privado',
            'descripcion': 'Vivienda de diseño exclusivo que fusiona la robustez del acero con acabados arquitectónicos de alta gama...',
            'fotos': ['vaca/vaca1.jpg', 'vaca/vaca2.jpg', 'vaca/vaca3.jpg', 'vaca/vaca4.jpg', 'vaca/vaca5.jpg', 'vaca/vaca6.jpg', 'vaca/vaca7.jpg', 'vaca/vaca8.jpg', 'vaca/vaca9.jpg', 'vaca/vaca10.jpg', 'vaca/vaca11.jpg', 'vaca/vaca12.jpg'],
            'videos': ['vaca/vaca_video1.mp4','vaca/vaca_video2.mp4','vaca/vaca_video3.mp4']
        },
        'residencia-art':{
            'titulo': 'Residencia Arteaga',
            'ubicacion': 'Proyecto Residencial Sangolquí',
            'descripcion': 'Proyecto de vivienda con estructura metálica portante de dos niveles, compuesta por columnas y vigas tipo IPE...',
            'fotos': ['arteaga/arteaga1.jpg', 'arteaga/arteaga2.jpg', 'arteaga/arteaga3.jpg', 'arteaga/arteaga4.jpg', 'arteaga/arteaga5.jpg', 'arteaga/arteaga6.jpg', 'arteaga/arteaga7.jpg', 'arteaga/arteaga8.jpg', 'arteaga/arteaga9.jpg', 'arteaga/arteaga10.jpg', 'arteaga/arteaga11.jpg', 'arteaga/arteaga12.jpg', 'arteaga/arteaga13.jpg', 'arteaga/arteaga14.jpg'],
            'videos': ['arteaga/arteaga_video1.mp4']
        }
    }
    proyecto = datos_proyectos.get(proyecto_id)
    return render(request, 'web/detalle_proyecto.html', {'p': proyecto})

def contacto(request):
    return render(request, 'web/contacto.html')


# =======================================================
# DEFINICIÓN DE ROLES (RBAC) 
# =======================================================
def es_admin(user):
    return user.is_superuser

def es_solicitante(user):
    return user.groups.filter(name='Solicitante').exists() or user.is_superuser

def es_bodeguero(user):
    return user.groups.filter(name='Bodeguero').exists() or user.is_superuser

def es_comprador(user):
    return user.groups.filter(name='Compras').exists() or user.is_superuser


# =======================================================
# VISTAS DEL SISTEMA ERP (INTERNO)
# =======================================================

@login_required(login_url='login')
def dashboard_erp(request):
    usuario = request.user
    context = {}

    Bodega.objects.get_or_create(nombre='Bodega Central', defaults={'is_principal': True})

    if es_admin(usuario):
        context['rol'] = 'Administrador'
        context['tickets_pendientes'] = Requerimiento.objects.filter(estado='PENDIENTE').order_by('fecha_solicitud')
        context['ultimos_movimientos'] = MovimientoInventario.objects.all().order_by('-fecha_hora')[:5]
        context['cotizaciones_pendientes'] = SolicitudCompra.objects.filter(estado='COTIZADO').order_by('fecha_creacion')
        context['alertas_oc'] = OrdenCompra.objects.filter(estado='RECIBIDA_PARCIAL')
        
    elif es_bodeguero(usuario):
        context['rol'] = 'Bodeguero'
        context['tickets_por_despachar'] = Requerimiento.objects.filter(estado='APROBADO')
        context['mis_compras_pendientes'] = OrdenCompra.objects.filter(estado__in=['EMITIDA', 'RECIBIDA_PARCIAL'])
        context['alertas_stock'] = Material.objects.filter(stock_actual__lte=F('stock_minimo'))

    elif es_comprador(usuario):
        context['rol'] = 'Compras'
        context['solicitudes_compras'] = SolicitudCompra.objects.filter(estado='ENVIADO_A_COMPRAS').order_by('-fecha_creacion')
        context['alertas_oc'] = OrdenCompra.objects.filter(estado='RECIBIDA_PARCIAL')

    else:
        context['rol'] = 'Solicitante'
        context['mis_requerimientos'] = Requerimiento.objects.filter(solicitante=usuario).order_by('-fecha_solicitud')

    return render(request, 'web/erp/dashboard.html', context)


# --- GESTIÓN DE REQUERIMIENTOS (SOLICITANTES) ---

@login_required(login_url='login')
@user_passes_test(es_solicitante, login_url='dashboard_erp')
def crear_requerimiento(request):
    if request.method == 'POST':
        form_req = RequerimientoForm(request.POST)
        if form_req.is_valid():
            nuevo_req = form_req.save(commit=False)
            nuevo_req.solicitante = request.user 
            nuevo_req.save() 
            messages.success(request, f'Ticket {nuevo_req.folio} creado con éxito. Ahora añade los materiales.')
            return redirect('añadir_materiales', req_id=nuevo_req.id)
    else:
        form_req = RequerimientoForm()
    return render(request, 'web/erp/crear_requerimiento.html', {'form': form_req})

@login_required(login_url='login')
@user_passes_test(es_solicitante, login_url='dashboard_erp')
def añadir_materiales(request, req_id):
    requerimiento = get_object_or_404(Requerimiento, id=req_id, solicitante=request.user)
    detalles = requerimiento.detalles.all() 

    if request.method == 'POST':
        form_detalle = DetalleRequerimientoForm(request.POST)
        if form_detalle.is_valid():
            nuevo_detalle = form_detalle.save(commit=False)
            nuevo_detalle.requerimiento = requerimiento
            nuevo_detalle.save()
            messages.success(request, 'Material añadido al ticket.')
            return redirect('añadir_materiales', req_id=requerimiento.id)
    else:
        form_detalle = DetalleRequerimientoForm()

    context = {
        'requerimiento': requerimiento,
        'detalles': detalles,
        'form': form_detalle
    }
    return render(request, 'web/erp/añadir_materiales.html', context)

@login_required(login_url='login')
@user_passes_test(es_solicitante, login_url='dashboard_erp')
def eliminar_item_requerimiento(request, item_id):
    """Permite al solicitante eliminar un material de su ticket antes de enviarlo."""
    if request.method == 'POST':
        item = get_object_or_404(DetalleRequerimiento, id=item_id)
        
        # Validar que el ticket pertenezca al usuario y siga en PENDIENTE
        if item.requerimiento.solicitante == request.user and item.requerimiento.estado == 'PENDIENTE':
            nombre_material = item.material.nombre
            item.delete()
            messages.success(request, f'Se eliminó "{nombre_material}" de tu lista.')
        else:
            messages.error(request, 'No puedes modificar este ticket porque ya está en proceso.')
            
        return redirect('añadir_materiales', req_id=item.requerimiento.id)
    return redirect('dashboard_erp')

# --- VISTA DE APROBACIÓN DE TICKETS AUTOMÁTICA (Admin) ---
@login_required(login_url='login')
@user_passes_test(es_admin, login_url='dashboard_erp')
def procesar_ticket(request, req_id, accion):
    ticket = get_object_or_404(Requerimiento, id=req_id)
    
    if accion == 'aprobar':
        # AQUÍ OCURRE LA MAGIA AUTOMÁTICA DE DIVISIÓN DE STOCK
        ticket.procesar_y_dividir_stock()
        
        # Validar cómo quedó el ticket tras la división
        estados = ticket.detalles.values_list('estado_item', flat=True)
        
        if all(e == 'APROBADO_BODEGA' for e in estados):
            ticket.estado = 'APROBADO'
            messages.success(request, f"Ticket {ticket.folio} aprobado al 100% para despacho en bodega.")
        elif 'EN_COMPRAS' in estados and 'APROBADO_BODEGA' in estados:
            ticket.estado = 'PARCIALMENTE_DESPACHADO'
            messages.info(request, f"Stock insuficiente para {ticket.folio}. Se dividió automáticamente: una parte a bodega y los faltantes a compras.")
        elif all(e == 'EN_COMPRAS' for e in estados):
            ticket.estado = 'EN_COMPRAS'
            messages.warning(request, f"Sin stock. El ticket {ticket.folio} ha sido enviado completamente a compras.")
            
        # Generar las solicitudes de compra si hubo faltantes
        if 'EN_COMPRAS' in estados:
            solicitud, _ = SolicitudCompra.objects.get_or_create(
                requerimiento_origen=ticket, defaults={'estado': 'ENVIADO_A_COMPRAS'}
            )
            for detalle in ticket.detalles.filter(estado_item='EN_COMPRAS'):
                CotizacionItem.objects.get_or_create(
                    solicitud=solicitud, material=detalle.material,
                    defaults={'cantidad_requerida': detalle.cantidad_solicitada}
                )
        
    elif accion == 'rechazar':
        ticket.estado = 'RECHAZADO'
        for detalle in ticket.detalles.all():
            detalle.estado_item = 'RECHAZADO'
            detalle.save()
        messages.warning(request, f"Ticket {ticket.folio} ha sido rechazado.")

    ticket.save()
    return redirect('dashboard_erp')

@login_required(login_url='login')
@user_passes_test(lambda u: es_bodeguero(u) or es_admin(u), login_url='dashboard_erp')
@transaction.atomic
def despachar_requerimiento(request, req_id):
    ticket = get_object_or_404(Requerimiento, id=req_id)
    
    # Solo podemos despachar si el ticket está aprobado o parcialmente despachado
    if ticket.estado not in ['APROBADO', 'PARCIALMENTE_DESPACHADO']:
        messages.error(request, "Este ticket no está listo para despacho.")
        return redirect('dashboard_erp')

    # Lógica de seguridad: El Administrador ve todas las bodegas. 
    # El Bodeguero SOLO ve la bodega a la que está asignado.
    if request.user.is_superuser:
        bodegas_permitidas = Bodega.objects.all()
    else:
        if hasattr(request.user, 'perfil') and request.user.perfil.bodega_asignada:
            bodegas_permitidas = Bodega.objects.filter(id=request.user.perfil.bodega_asignada.id)
        else:
            bodegas_permitidas = Bodega.objects.none()

    if request.method == 'POST':
        bodega_origen_id = request.POST.get('bodega_origen')
        
        # Validar que la bodega seleccionada exista y el usuario tenga acceso a ella
        bodega_origen = bodegas_permitidas.filter(id=bodega_origen_id).first() if bodega_origen_id else bodegas_permitidas.filter(is_principal=True).first()
        
        if not bodega_origen:
            messages.error(request, "Acceso denegado. No tienes permisos sobre la bodega seleccionada.")
            return redirect('despachar_requerimiento', req_id=ticket.id)
        
        items_a_despachar = ticket.detalles.filter(estado_item='APROBADO_BODEGA')
        
        if not items_a_despachar.exists():
            messages.warning(request, "No hay ítems aprobados listos para despachar en este ticket.")
            return redirect('dashboard_erp')

        for item in items_a_despachar:
            # Blindaje Decimal: Conversión de cantidades
            cant_solicitada = Decimal(str(item.cantidad_solicitada))
            cant_despachada = Decimal(str(item.cantidad_despachada))
            cantidad_a_entregar = cant_solicitada - cant_despachada
            
            if cantidad_a_entregar > 0:
                # 1. Bloqueo de concurrencia
                material = Material.objects.select_for_update().get(id=item.material.id)
                
                # Obtener el stock real de la bodega de origen
                stock_bodega = StockBodega.objects.select_for_update().filter(bodega=bodega_origen, material=material).first()
                cant_en_bodega = Decimal(str(stock_bodega.cantidad)) if stock_bodega and stock_bodega.cantidad else Decimal('0.0')
                
                # Validar disponibilidad estricta
                if cant_en_bodega < cantidad_a_entregar:
                    messages.error(request, f"Error de stock: Se requieren {cantidad_a_entregar} de {material.nombre}, pero solo tienes {cant_en_bodega} en {bodega_origen.nombre}.")
                    return redirect('despachar_requerimiento', req_id=ticket.id)

                # 2. RESTAR DE LA BODEGA ESPECÍFICA Y GUARDAR PRIMERO
                stock_bodega.cantidad = cant_en_bodega - cantidad_a_entregar
                stock_bodega.save()

                # 3. GUARDAR EL MATERIAL LUEGO (El modelo suma todas las bodegas y recalcula el stock_actual solo)
                material.save()

                # 4. Registrar el movimiento de SALIDA hacia el proyecto
                MovimientoInventario.objects.create(
                    material=material, 
                    tipo='SALIDA', 
                    cantidad=cantidad_a_entregar, 
                    bodega_origen=bodega_origen,
                    responsable=request.user, 
                    requerimiento_asociado=ticket,
                    proyecto_asociado=ticket.proyecto, # Dejamos asentado en auditoría a qué obra se fue
                    observaciones=f"Despacho del ticket {ticket.folio} para el proyecto {ticket.proyecto.centro_costos}"
                )

                # 5. Actualizar el detalle del requerimiento
                item.cantidad_despachada = cant_despachada + cantidad_a_entregar
                item.estado_item = 'DESPACHADO'
                item.save()

        # 6. Actualizar el estado maestro del ticket
        estados_restantes = list(ticket.detalles.exclude(estado_item__in=['DESPACHADO', 'RECHAZADO']).values_list('estado_item', flat=True))
        
        if not estados_restantes:
            # Si ya no le falta ningún ítem por despachar o comprar
            ticket.estado = 'DESPACHADO'
        
        ticket.save()
        messages.success(request, f"✅ Despacho exitoso. Los materiales del ticket {ticket.folio} han salido de {bodega_origen.nombre}.")
        return redirect('dashboard_erp')

    # Si es GET, mostramos el formulario
    return render(request, 'web/erp/confirmar_despacho.html', {
        'ticket': ticket,
        'items': ticket.detalles.filter(estado_item='APROBADO_BODEGA'),
        'bodegas': bodegas_permitidas # Solo mandamos al HTML las bodegas a las que tiene acceso
    })

# =======================================================
# MÓDULO DE COMPRAS Y COTIZACIONES (DESGLOSE INCLUIDO)
# =======================================================

@login_required(login_url='login')
@user_passes_test(es_comprador, login_url='dashboard_erp')
def atender_cotizacion(request, solicitud_id):
    solicitud = get_object_or_404(SolicitudCompra, id=solicitud_id)
    items = solicitud.items_cotizados.all()
    
    if request.method == 'POST':
        for item in items:
            proveedor = request.POST.get(f'proveedor_{item.id}')
            precio = request.POST.get(f'precio_{item.id}')
            tiempo = request.POST.get(f'tiempo_{item.id}', 0) # CAPTURA DE TIEMPO DE ENTREGA
            especificaciones = request.POST.get(f'especificaciones_{item.id}')
            certificado = request.POST.get(f'certificado_{item.id}') == 'on'
            archivo_pdf = request.FILES.get(f'archivo_cotizacion_{item.id}')

            if proveedor and precio:
                item.proveedor_cotizado = proveedor
                item.precio_unitario = precio
                item.tiempo_entrega_dias = tiempo
                item.especificaciones_tecnicas = especificaciones
                item.certificado_calidad_incluido = certificado
                if archivo_pdf:
                    item.archivo_cotizacion = archivo_pdf
                item.save()

        solicitud.estado = 'COTIZADO'
        solicitud.save()
        messages.success(request, f"Cotización {solicitud.folio} enviada al Administrador para su aprobación.")
        return redirect('dashboard_erp')
        
    return render(request, 'web/erp/atender_cotizacion.html', {'solicitud': solicitud, 'items': items})


@login_required(login_url='login')
@user_passes_test(es_comprador, login_url='dashboard_erp')
def desglosar_item_cotizacion(request, item_id):
    item = get_object_or_404(CotizacionItem, id=item_id)
    if request.method == 'POST':
        cantidad_nueva = float(request.POST.get('cantidad_separar', 0))
        if 0 < cantidad_nueva < float(item.cantidad_requerida):
            item.cantidad_requerida -= cantidad_nueva
            item.save()
            CotizacionItem.objects.create(
                solicitud=item.solicitud, material=item.material, cantidad_requerida=cantidad_nueva
            )
            messages.success(request, "Material desglosado en dos registros para comprar a distintos proveedores.")
    return redirect('atender_cotizacion', solicitud_id=item.solicitud.id)


# En tu views.py
@login_required(login_url='login')
@user_passes_test(es_admin, login_url='dashboard_erp')
@transaction.atomic
def revisar_cotizacion(request, solicitud_id):
    """
    Vista de Consolidación de Compras. 
    Aquí el admin ve la solicitud, puede aumentar las cantidades para stock, 
    o rechazar ítems antes de convertirlos en Orden de Compra.
    """
    solicitud = get_object_or_404(SolicitudCompra, id=solicitud_id)
    items = solicitud.items_cotizados.all()
    
    if request.method == 'POST':
        for item in items:
            estado = request.POST.get(f'estado_{item.id}')
            motivo = request.POST.get(f'motivo_{item.id}', '')
            
            # EL ADMIN PUEDE MODIFICAR LA CANTIDAD A COMPRAR AQUÍ
            nueva_cantidad = request.POST.get(f'cantidad_final_{item.id}')
            if nueva_cantidad:
                try:
                    item.cantidad_requerida = Decimal(nueva_cantidad.replace(',', '.'))
                except:
                    pass # Manejo de error si envían texto

            if estado in ['APROBADO', 'RECHAZADO']:
                item.estado_aprobacion = estado
                if estado == 'RECHAZADO':
                    item.motivo_rechazo = motivo
                item.save()

        # Si el admin quiere agregar un ítem extra que nadie pidió pero hace falta en stock
        nuevo_material_id = request.POST.get('agregar_material_id')
        nueva_cantidad_extra = request.POST.get('agregar_cantidad_extra')
        
        if nuevo_material_id and nueva_cantidad_extra:
            mat_extra = Material.objects.get(id=nuevo_material_id)
            CotizacionItem.objects.create(
                solicitud=solicitud,
                material=mat_extra,
                cantidad_requerida=Decimal(nueva_cantidad_extra),
                estado_aprobacion='PENDIENTE' # Se agrega para que sea revisado
            )
            messages.info(request, f"Se agregó {mat_extra.nombre} a la solicitud de compras.")
            return redirect('revisar_cotizacion', solicitud_id=solicitud.id) # Recargar página

        # Si todo se procesó, vamos a la generación de OC
        return redirect('finalizar_revision_cotizacion', solicitud_id=solicitud.id)
        
    # Agregamos la lista de materiales por si el Admin quiere añadir cosas nuevas
    materiales_catalogo = Material.objects.filter(is_active=True).order_by('nombre')
    return render(request, 'web/erp/revisar_cotizacion.html', {
        'solicitud': solicitud, 
        'items': items,
        'materiales_catalogo': materiales_catalogo
    })

@login_required(login_url='login')
@user_passes_test(es_admin, login_url='dashboard_erp')
@transaction.atomic
def finalizar_revision_cotizacion(request, solicitud_id):
    solicitud = get_object_or_404(SolicitudCompra, id=solicitud_id)
    
    items_aprobados = solicitud.items_cotizados.filter(estado_aprobacion='APROBADO')
    items_pendientes = solicitud.items_cotizados.filter(estado_aprobacion='PENDIENTE')
    
    proveedores = items_aprobados.values_list('proveedor_cotizado', flat=True).distinct()
    
    for prov in proveedores:
        if prov: 
            items_prov = items_aprobados.filter(proveedor_cotizado=prov)
            nueva_oc = OrdenCompra.objects.create(
                proveedor=prov,
                creado_por=request.user,
                estado='EMITIDA', 
                observaciones=f"Generada automáticamente desde Solicitud {solicitud.folio}"
            )
            for item in items_prov:
                DetalleOrdenCompra.objects.create(
                    orden=nueva_oc, material=item.material, cantidad_pedida=item.cantidad_requerida
                )
            items_prov.update(estado_aprobacion='COMPRADO')
            
    if items_pendientes.exists():
        solicitud.estado = 'COTIZADO'
        messages.warning(request, f"Se generaron O.C. parciales. Aún te quedan {items_pendientes.count()} ítems pendientes por decidir.")
    else:
        solicitud.estado = 'PROCESADO'
        messages.success(request, "Todas las órdenes fueron generadas y la solicitud fue cerrada por completo.")
        
    solicitud.save()
    return redirect('dashboard_erp')


# =======================================================
# MÓDULO DE INVENTARIO Y ABASTECIMIENTO TRADICIONAL
# =======================================================

# En views.py
@login_required(login_url='login')
@user_passes_test(lambda u: es_bodeguero(u) or es_admin(u), login_url='dashboard_erp')
def crear_solicitud_abastecimiento(request):
    """El bodeguero solicita material cuando ve que el stock baja"""
    if request.method == 'POST':
        # Creas un Requerimiento sin Proyecto asignado (o con un proyecto por defecto de 'Inventario Interno')
        # O creas directamente una SolicitudCompra.
        nueva_solicitud = SolicitudCompra.objects.create(
            estado='ENVIADO_A_COMPRAS',
            observaciones_admin="Solicitud manual generada por bodega"
        )
        return redirect('añadir_items_solicitud', solicitud_id=nueva_solicitud.id)
        
    return render(request, 'web/erp/crear_solicitud_abastecimiento.html')

@login_required(login_url='login')
@user_passes_test(lambda u: es_bodeguero(u) or es_admin(u), login_url='dashboard_erp')
def añadir_items_oc(request, oc_id):
    oc = get_object_or_404(OrdenCompra, id=oc_id)
    detalles = oc.detalles.all()

    if request.method == 'POST':
        form_detalle = DetalleOrdenCompraForm(request.POST)
        if form_detalle.is_valid():
            material = form_detalle.cleaned_data['material']
            item_existente = detalles.filter(material=material).first()
            if item_existente:
                item_existente.cantidad_pedida += form_detalle.cleaned_data['cantidad_pedida']
                item_existente.save()
            else:
                nuevo_item = form_detalle.save(commit=False)
                nuevo_item.orden = oc
                nuevo_item.save()
            
            messages.success(request, f'Se añadió {material.nombre} a la orden.')
            return redirect('añadir_items_oc', oc_id=oc.id)
    else:
        form_detalle = DetalleOrdenCompraForm()

    return render(request, 'web/erp/añadir_items_oc.html', {
        'oc': oc, 'detalles': detalles, 'form': form_detalle
    })

@login_required(login_url='login')
@user_passes_test(lambda u: es_bodeguero(u) or es_admin(u), login_url='dashboard_erp')
def listar_ordenes_compra(request):
    es_administrador = es_admin(request.user)
    
    if es_administrador:
        ordenes = OrdenCompra.objects.all().order_by('-fecha_creacion')
        estados_permitidos = OrdenCompra.ESTADOS
    else:
        ordenes = OrdenCompra.objects.exclude(estado='BORRADOR').order_by('-fecha_creacion')
        estados_permitidos = [est for est in OrdenCompra.ESTADOS if est[0] != 'BORRADOR']

    estado = request.GET.get('estado')
    if estado:
        ordenes = ordenes.filter(estado=estado)

    return render(request, 'web/erp/listar_oc.html', {
        'ordenes': ordenes,
        'estados': estados_permitidos, 
        'estado_filtro': estado,
        'rol': 'Administrador' if es_administrador else 'Bodeguero',
    })

@login_required(login_url='login')
@user_passes_test(es_admin, login_url='dashboard_erp')
def aprobar_oc(request, oc_id):
    oc = get_object_or_404(OrdenCompra, id=oc_id)
    if oc.estado == 'BORRADOR':
        oc.estado = 'EMITIDA' 
        oc.save()
        messages.success(request, f"¡Orden de Compra {oc.folio} APROBADA! El bodeguero ya puede verla para recibir el stock.")
    return redirect('listar_ordenes_compra')


@login_required(login_url='login')
@user_passes_test(lambda u: es_bodeguero(u) or es_admin(u), login_url='dashboard_erp')
@transaction.atomic
def recibir_orden_compra(request, oc_id):
    oc = get_object_or_404(OrdenCompra, id=oc_id)
    detalles = oc.detalles.all()
    
    if request.method == 'POST':
        bodega_id = request.POST.get('bodega_destino')
        bodega = get_object_or_404(Bodega, id=bodega_id) if bodega_id else Bodega.objects.filter(is_principal=True).first()
        entrega_incompleta = False

        for item in detalles:
            # BLINDAJE: Capturar errores y convertir a Decimal (Alta precisión)
            try:
                # Obtenemos el texto, por defecto '0'
                valor_texto = request.POST.get(f'recibido_{item.id}', '0')
                # Reemplazamos coma por punto por si el navegador manda formato europeo
                valor_texto = valor_texto.replace(',', '.') 
                # Convertimos estrictamente a Decimal
                ingresado = Decimal(valor_texto)
            except Exception:
                ingresado = Decimal('0.0')

            # BLINDAJE: Evitar ingresos negativos (restar stock maliciosamente)
            if ingresado < 0:
                messages.error(request, "No se permiten valores negativos en la recepción.")
                return redirect('recibir_orden_compra', oc_id=oc.id)

            archivo_certificado = request.FILES.get(f'certificado_{item.id}')

            if ingresado > 0:
                # 1. Homologar todos los valores de la base de datos a Decimal
                cant_recibida = Decimal(str(item.cantidad_recibida))
                cant_pedida = Decimal(str(item.cantidad_pedida))

                # BLINDAJE: Evitar que el bodeguero reciba más de lo que se pidió
                if (cant_recibida + ingresado) > cant_pedida:
                    messages.error(request, f"Error: Estás intentando recibir más {item.material.nombre} del que se solicitó.")
                    return redirect('recibir_orden_compra', oc_id=oc.id)

                item.cantidad_recibida = cant_recibida + ingresado
                item.save()

                if item.cantidad_recibida < cant_pedida:
                    entrega_incompleta = True

                # BLOQUEO DE CONCURRENCIA PARA RECEPCIÓN SEGURA
                material = Material.objects.select_for_update().get(id=item.material.id)

                # 1. PRIMERO ACTUALIZAMOS EL STOCK EN LA BODEGA
                stock_b, _ = StockBodega.objects.select_for_update().get_or_create(bodega=bodega, material=material)
                
                # Prevenir error si la cantidad de la bodega viene vacía o nula
                cant_bodega = Decimal(str(stock_b.cantidad)) if stock_b.cantidad else Decimal('0.0')
                
                # CORRECCIÓN APLICADA: Sumamos la variable correcta de esta vista
                stock_b.cantidad = cant_bodega + ingresado
                stock_b.save() # <-- Se guarda la bodega primero

                # 2. LUEGO GUARDAMOS EL MATERIAL
                # Como la bodega ya tiene el nuevo stock, el save() del modelo hará la suma matemática perfecta automáticamente.
                material.save() 

                MovimientoInventario.objects.create(
                    material=material, tipo='INGRESO', cantidad=ingresado, bodega_destino=bodega,
                    responsable=request.user, orden_compra_asociada=oc, certificado_calidad=archivo_certificado
                )

                # ==========================================================
                # MAGIA: DESPERTAR TICKETS EN ESPERA (BACKORDER)
                # ==========================================================
                # Buscamos los tickets antiguos que se quedaron esperando este material
                detalles_en_espera = DetalleRequerimiento.objects.filter(
                    material=material, 
                    estado_item='EN_COMPRAS'
                ).order_by('requerimiento__fecha_solicitud')
                
                stock_restante = ingresado # Usamos el stock que acaba de llegar
                
                for det in detalles_en_espera:
                    # Blindaje: Conversión a Decimal para la lógica de Backorder
                    cant_solicitada_det = Decimal(str(det.cantidad_solicitada))
                    cant_despachada_det = Decimal(str(det.cantidad_despachada))
                    cantidad_pendiente = cant_solicitada_det - cant_despachada_det
                    
                    if stock_restante >= cantidad_pendiente:
                        # Si alcanza, lo liberamos para que el bodeguero lo despache
                        det.estado_item = 'APROBADO_BODEGA'
                        det.save()
                        stock_restante -= cantidad_pendiente
                        
                        # Actualizamos el estado del ticket padre para que vuelva a aparecer en el Dashboard
                        req = det.requerimiento
                        estados_req = list(req.detalles.values_list('estado_item', flat=True))
                        
                        if 'EN_COMPRAS' not in estados_req:
                            # Si ya no le falta nada por comprar
                            req.estado = 'APROBADO'
                        else:
                            req.estado = 'PARCIALMENTE_DESPACHADO'
                        req.save()
                    else:
                        # Si el stock no alcanzó para este ticket, rompemos el ciclo
                        break
                # ==========================================================
        
        if entrega_incompleta:
            oc.estado = 'RECIBIDA_PARCIAL'
            messages.warning(request, "Entrega parcial registrada. Se ha notificado al departamento de Compras.")
        else:
            oc.estado = 'RECIBIDA'
            messages.success(request, f"Orden {oc.folio} recibida al 100%. Inventario actualizado en la {bodega.nombre}.")
            
        oc.save()
        return redirect('listar_ordenes_compra')

    return render(request, 'web/erp/recibir_stock_form.html', {
        'oc': oc, 'detalles': detalles, 'bodegas': Bodega.objects.all()
    })

@login_required(login_url='login')
@user_passes_test(es_admin, login_url='dashboard_erp')
def editar_movimiento_auditoria(request, movimiento_id):
    movimiento = get_object_or_404(MovimientoInventario, id=movimiento_id)
    pass


# --- VENTA DE MATERIALES ---
@login_required(login_url='login')
@user_passes_test(es_admin, login_url='dashboard_erp')
@transaction.atomic
def venta_material(request):
    if request.method == 'POST':
        form = VentaMaterialForm(request.POST)
        if form.is_valid():
            cant = form.cleaned_data['cantidad']
            comprador = form.cleaned_data['comprador']
            factura = form.cleaned_data['factura']
            
            # BLOQUEO DE CONCURRENCIA EN VENTA
            mat = Material.objects.select_for_update().get(id=form.cleaned_data['material'].id)
            bod = form.cleaned_data['bodega_origen']
            
            stock_bodega = StockBodega.objects.select_for_update().filter(material=mat, bodega=bod).first()
            
            if not stock_bodega or stock_bodega.cantidad < cant:
                messages.error(request, f"Stock insuficiente en la {bod.nombre}.")
            else:
                stock_bodega.cantidad -= cant
                stock_bodega.save()
                mat.stock_actual -= cant
                mat.save()
                
                obs = f"Venta externa a: {comprador} | Factura: {factura}"
                MovimientoInventario.objects.create(
                    material=mat, tipo='VENTA', cantidad=cant, bodega_origen=bod,
                    responsable=request.user, observaciones=obs
                )
                messages.success(request, "Venta registrada con éxito. Inventario actualizado.")
                return redirect('inventario_actual')
    else: 
        form = VentaMaterialForm()
    return render(request, 'web/erp/venta_material.html', {'form': form})


@login_required(login_url='login')
def inventario_actual(request):
    # 1. SEGURIDAD LOGÍSTICA: Qué ve cada usuario
    if request.user.is_superuser:
        materiales_list = Material.objects.all().order_by('nombre')
    else:
        # El Bodeguero solo ve los materiales que tengan stock físico en su bodega asignada
        if hasattr(request.user, 'perfil') and request.user.perfil.bodega_asignada:
            bodega_empleado = request.user.perfil.bodega_asignada
            materiales_list = Material.objects.filter(
                stocks_bodegas__bodega=bodega_empleado,
                stocks_bodegas__cantidad__gt=0
            ).distinct().order_by('nombre')
        else:
            materiales_list = Material.objects.none()

    # 2. BÚSQUEDA DINÁMICA POR CATEGORÍA
    # En lugar de buscar por "tipo", buscaremos por las categorías reales creadas en el ERP
    categorias = Categoria.objects.filter(is_active=True)
    categoria_id = request.GET.get('categoria')
    if categoria_id:
        materiales_list = materiales_list.filter(categoria_id=categoria_id)

    # 3. BÚSQUEDA POR TEXTO (Servidor)
    query = request.GET.get('q', '').strip()
    if query:
        materiales_list = materiales_list.filter(
            Q(nombre__icontains=query) | Q(sku__icontains=query)
        )

    # Alertas Globales de Stock
    alertas = Material.objects.filter(stock_actual__lte=F('stock_minimo'))

    # 4. PAGINACIÓN (Evita que el servidor colapse)
    paginator = Paginator(materiales_list, 20) # 20 materiales por página
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    return render(request, 'web/erp/inventario.html', {
        'page_obj': page_obj, # El HTML debe usar page_obj ahora
        'categorias': categorias,
        'alertas': alertas,
        'rol': 'Administrador' if request.user.is_superuser else 'Bodeguero'
    })
@login_required(login_url='login')
@user_passes_test(es_admin, login_url='dashboard_erp')
def crear_material(request):
    """
    Vista para crear nuevo material en el catálogo maestro.
    Solo administrador puede acceder.
    
    GET: Muestra formulario vacío
    POST: Valida y guarda material (genera SKU automático)
    """
    if request.method == 'POST':
        form = MaterialForm(request.POST, request.FILES)
        
        if form.is_valid():
            try:
                material = form.save(commit=False)
                material.save()  # Aquí se genera el SKU automáticamente
                
                # Mensaje de éxito con el código generado
                messages.success(
                    request,
                    f"✅ Material '{material.nombre}' creado exitosamente. "
                    f"Código asignado: <strong>{material.sku}</strong>"
                )
                
                # Log para auditoría (implementar después)
                # log_auditoria(request.user, 'CREATE', 'Material', material.id)
                
                return redirect('inventario_actual')
            
            except Exception as e:
                # Capturar errores de base de datos
                messages.error(
                    request,
                    f"❌ Error al guardar material: {str(e)}"
                )
                import logging
                logger = logging.getLogger(__name__)
                logger.error(f"Error creando material: {str(e)}", exc_info=True)
        
        else:
            # Mostrar errores de validación específicos
            error_messages = []
            for field, errors in form.errors.items():
                for error in errors:
                    if field == '__all__':
                        error_messages.append(f"⚠️ {error}")
                    else:
                        field_label = form.fields[field].label if field in form.fields else field
                        error_messages.append(f"⚠️ {field_label}: {error}")
            
            for error_msg in error_messages:
                messages.error(request, error_msg)
    
    else:
        # GET: mostrar formulario vacío
        form = MaterialForm()
    
    context = {
        'form': form,
        'editando': False,
        'titulo': 'Crear Nuevo Material',
    }
    return render(request, 'web/erp/crear_material.html', context)

@login_required(login_url='login')
@user_passes_test(es_admin, login_url='dashboard_erp')
def editar_material(request, material_id):
    """
    Vista para editar propiedades de un material existente.
    Solo administrador puede acceder.
    
    Nota: El SKU es inmutable (auto-generado)
    """
    material = get_object_or_404(Material, id=material_id)
    
    if request.method == 'POST':
        form = MaterialForm(request.POST, request.FILES, instance=material)
        
        if form.is_valid():
            try:
                form.save()
                messages.success(
                    request,
                    f"✅ Material {material.sku} actualizado correctamente."
                )
                return redirect('inventario_actual')
            
            except Exception as e:
                messages.error(
                    request,
                    f"❌ Error al actualizar material: {str(e)}"
                )
                import logging
                logger = logging.getLogger(__name__)
                logger.error(f"Error editando material {material_id}: {str(e)}", 
                           exc_info=True)
        
        else:
            # Mostrar errores de validación
            error_messages = []
            for field, errors in form.errors.items():
                for error in errors:
                    if field == '__all__':
                        error_messages.append(f"⚠️ {error}")
                    else:
                        field_label = form.fields[field].label if field in form.fields else field
                        error_messages.append(f"⚠️ {field_label}: {error}")
            
            for error_msg in error_messages:
                messages.error(request, error_msg)
    
    else:
        form = MaterialForm(instance=material)
    
    context = {
        'form': form,
        'editando': True,
        'material': material,
        'titulo': f'Editar Material: {material.sku}',
    }
    return render(request, 'web/erp/crear_material.html', context)

    
@login_required(login_url='login')
@user_passes_test(es_admin, login_url='dashboard_erp')
def realizar_ajuste(request, material_id):
    material = get_object_or_404(Material, id=material_id)
    
    if request.method == 'POST':
        form = AjusteInventarioForm(request.POST)
        if form.is_valid():
            bodega_seleccionada = form.cleaned_data['bodega']
            
            # 1. Extraemos el número y lo BLINDAMOS convirtiéndolo a Decimal (Evita errores de Float)
            ajuste_crudo = form.cleaned_data['cantidad_ajuste']
            cantidad_ajuste = Decimal(str(ajuste_crudo))
            
            observaciones = form.cleaned_data['observaciones']

            with transaction.atomic():
                # Bloqueo para evitar colisiones (Concurrencia)
                material_bloqueado = Material.objects.select_for_update().get(id=material.id)
                
                # Buscamos el stock de esa bodega en específico
                stock_b, _ = StockBodega.objects.select_for_update().get_or_create(
                    bodega=bodega_seleccionada, 
                    material=material_bloqueado
                )

                # 2. Blindamos la cantidad actual de la bodega (por si estaba nula/vacía)
                cant_actual = Decimal(str(stock_b.cantidad)) if stock_b.cantidad else Decimal('0.0')

                # 3. GUARDAMOS PRIMERO LA BODEGA (Suma segura: Decimal + Decimal)
                stock_b.cantidad = cant_actual + cantidad_ajuste
                stock_b.save() 

                # 4. LUEGO GUARDAMOS EL MATERIAL (Dispara el recálculo automático del total global)
                material_bloqueado.save()

                # 5. Registramos en la auditoría separando si fue entrada o salida
                tipo_mov = 'AJUSTE_INGRESO' if cantidad_ajuste > 0 else 'AJUSTE_SALIDA'
                MovimientoInventario.objects.create(
                    material=material_bloqueado,
                    tipo=tipo_mov,
                    cantidad=abs(cantidad_ajuste), # En auditoría siempre se guarda el valor en positivo
                    bodega_origen=bodega_seleccionada if cantidad_ajuste < 0 else None,
                    bodega_destino=bodega_seleccionada if cantidad_ajuste > 0 else None,
                    responsable=request.user,
                    observaciones=f"Ajuste manual: {observaciones}"
                )

            messages.success(request, f"¡Ajuste aplicado correctamente a {material_bloqueado.sku} en {bodega_seleccionada.nombre}!")
            return redirect('inventario_actual')
    else:
        form = AjusteInventarioForm()
        
    return render(request, 'web/erp/ajustar_inventario.html', {
        'form': form, 'material': material, 'rol': 'Administrador'
    })

@login_required(login_url='login')
@user_passes_test(es_admin, login_url='dashboard_erp')
def eliminar_material(request, material_id):
    material = get_object_or_404(Material, id=material_id)
    nombre_temp = material.nombre
    try:
        material.delete()
        messages.success(request, f'Material "{nombre_temp}" eliminado definitivamente.')
    except Exception: 
        material.is_active = False
        material.save()
        messages.warning(request, f'El material "{nombre_temp}" tiene historial. Ha sido desactivado.')
    return redirect('inventario_actual')


# =======================================================
# MÓDULO DE PROYECTOS Y AUDITORÍA
# =======================================================

@login_required(login_url='login')
@user_passes_test(es_admin, login_url='dashboard_erp')
def gestionar_proyectos(request):
    proyectos = Proyecto.objects.all().order_by('-fecha_creacion')
    if request.method == 'POST':
        form = ProyectoForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, "¡Nuevo proyecto creado con éxito!")
            return redirect('gestionar_proyectos')
    else:
        form = ProyectoForm()
    return render(request, 'web/erp/gestionar_proyectos.html', {'proyectos': proyectos, 'form': form, 'rol': 'Administrador'})

@login_required(login_url='login')
@user_passes_test(es_admin, login_url='dashboard_erp')
@transaction.atomic
def alternar_estado_proyecto(request, proyecto_id):
    proyecto = get_object_or_404(Proyecto, id=proyecto_id)
    
    # TRANSFERENCIA AUTOMÁTICA DE SOBRANTES AL CERRAR OBRA
    if proyecto.is_active:
        bodega_obra = proyecto.bodega_proyecto
        bodega_central = Bodega.objects.filter(is_principal=True).first()
        
        if bodega_obra and bodega_central:
            stocks = StockBodega.objects.filter(bodega=bodega_obra, cantidad__gt=0)
            for s in stocks:
                cant_migrar = s.cantidad
                s.cantidad = 0
                s.save()
                
                stock_c, _ = StockBodega.objects.get_or_create(bodega=bodega_central, material=s.material)
                stock_c.cantidad += cant_migrar
                stock_c.save()
                
                MovimientoInventario.objects.create(
                    material=s.material, tipo='TRANSFERENCIA', cantidad=cant_migrar,
                    bodega_origen=bodega_obra, bodega_destino=bodega_central,
                    responsable=request.user, observaciones=f"Cierre de Proyecto {proyecto.centro_costos}"
                )
            if stocks.exists():
                messages.info(request, f"Los saldos sobrantes del proyecto se han transferido automáticamente a la {bodega_central.nombre}.")

    proyecto.is_active = not proyecto.is_active
    proyecto.save()
    estado = "activado" if proyecto.is_active else "cerrado"
    messages.success(request, f"Proyecto '{proyecto.nombre}' {estado} correctamente.")
    return redirect('gestionar_proyectos')

@login_required(login_url='login')
@user_passes_test(es_admin, login_url='dashboard_erp')
def editar_proyecto(request, proyecto_id):
    proyecto = get_object_or_404(Proyecto, id=proyecto_id)
    if request.method == 'POST':
        form = ProyectoForm(request.POST, instance=proyecto)
        if form.is_valid():
            form.save()
            messages.success(request, f"Proyecto '{proyecto.nombre}' actualizado.")
    return redirect('gestionar_proyectos')

@login_required(login_url='login')
@user_passes_test(es_admin, login_url='dashboard_erp')
def eliminar_proyecto_erp(request, proyecto_id):
    proyecto = get_object_or_404(Proyecto, id=proyecto_id)
    nombre_temp = proyecto.nombre
    try:
        proyecto.delete()
        messages.success(request, f'Proyecto "{nombre_temp}" eliminado definitivamente.')
    except Exception:
        proyecto.is_active = False
        proyecto.save()
        messages.warning(request, f'El proyecto "{nombre_temp}" tiene requerimientos. Ha sido archivado.')
    return redirect('gestionar_proyectos')

@login_required(login_url='login')
@user_passes_test(es_admin, login_url='dashboard_erp')
def historial_movimientos(request):
    movimientos_list = MovimientoInventario.objects.all().order_by('-fecha_hora')
    
    tipo_filtro = request.GET.get('tipo')
    if tipo_filtro:
        movimientos_list = movimientos_list.filter(tipo=tipo_filtro)
        
    mes_filtro = request.GET.get('mes')
    if mes_filtro:
        try:
            year, month = mes_filtro.split('-')
            movimientos_list = movimientos_list.filter(fecha_hora__year=year, fecha_hora__month=month)
        except ValueError:
            pass 
            
    proyecto_id = request.GET.get('proyecto')
    if proyecto_id:
        movimientos_list = movimientos_list.filter(requerimiento_asociado__proyecto_id=proyecto_id)

    proyectos_activos = Proyecto.objects.filter(is_active=True).order_by('nombre')
    proyectos_inactivos = Proyecto.objects.filter(is_active=False).order_by('nombre')
            
    paginator = Paginator(movimientos_list, 30) 
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
        
    return render(request, 'web/erp/auditoria.html', {
        'page_obj': page_obj, 'tipo_filtro': tipo_filtro, 'mes_filtro': mes_filtro,
        'proyecto_id': proyecto_id, 'proyectos_activos': proyectos_activos,
        'proyectos_inactivos': proyectos_inactivos, 'rol': 'Administrador'
    })


# =======================================================
# MÓDULO DE REPORTES Y EXPORTACIÓN PDF
# =======================================================

@login_required(login_url='login')
def imprimir_pdf_ticket(request, req_id):
    ticket = get_object_or_404(Requerimiento, id=req_id)
    if not es_admin(request.user) and ticket.solicitante != request.user:
        messages.error(request, "No tienes permiso para ver este comprobante.")
        return redirect('dashboard_erp')
 
    context = {
        'ticket': ticket,
        'detalles': ticket.detalles.all(),
        'logo_path': os.path.join(settings.BASE_DIR, 'web', 'static', 'web', 'img', 'logo.jpg'),
        'fecha_impresion': timezone.now(),
    }
 
    html = get_template('web/erp/pdf_ticket.html').render(context)
    response = HttpResponse(content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="Comprobante_Entrega_{ticket.folio}.pdf"'
 
    if pisa.CreatePDF(html, dest=response).err:
        return HttpResponse('Hubo un error al generar el PDF del ticket.')
    return response

@login_required(login_url='login')
def imprimir_pdf_oc(request, oc_id):
    if not es_bodeguero(request.user) and not es_admin(request.user):
        messages.error(request, "No tienes permiso para imprimir órdenes de compra.")
        return redirect('dashboard_erp')
 
    oc = get_object_or_404(OrdenCompra, id=oc_id)
    context = {
        'oc': oc, 'detalles': oc.detalles.all(),
        'logo_path': os.path.join(settings.BASE_DIR, 'web', 'static', 'web', 'img', 'logo.jpg'),
        'fecha_impresion': timezone.now(),
    }
 
    html = get_template('web/erp/pdf_oc.html').render(context)
    response = HttpResponse(content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="OrdenCompra_{oc.folio}.pdf"'
 
    if pisa.CreatePDF(html, dest=response).err:
        return HttpResponse('Hubo un error al generar el PDF de la orden de compra.')
    return response

@login_required(login_url='login')
@user_passes_test(es_admin, login_url='dashboard_erp')
def imprimir_pdf_auditoria(request):
    movimientos = MovimientoInventario.objects.all().order_by('-fecha_hora')
    
    tipo_filtro = request.GET.get('tipo')
    if tipo_filtro: movimientos = movimientos.filter(tipo=tipo_filtro)
        
    mes_filtro = request.GET.get('mes')
    if mes_filtro:
        try:
            year, month = mes_filtro.split('-')
            movimientos = movimientos.filter(fecha_hora__year=year, fecha_hora__month=month)
        except ValueError: pass
            
    proyecto_obj = None
    proyecto_id = request.GET.get('proyecto')
    if proyecto_id:
        movimientos = movimientos.filter(requerimiento_asociado__proyecto_id=proyecto_id)
        proyecto_obj = get_object_or_404(Proyecto, id=proyecto_id)

    context = {
        'ingresos': movimientos.filter(tipo='INGRESO'),
        'salidas': movimientos.filter(tipo='SALIDA'),
        'ajustes': movimientos.filter(tipo='AJUSTE'),
        'tipo_filtro': tipo_filtro, 'mes_filtro': mes_filtro, 'proyecto': proyecto_obj,
        'logo_path': os.path.join(settings.BASE_DIR, 'web', 'static', 'web', 'img', 'logo.jpg'),
        'fecha_impresion': timezone.now(),
    }
    
    html = get_template('web/erp/pdf_auditoria.html').render(context)
    response = HttpResponse(content_type='application/pdf')
    nombre_archivo = f"Auditoria_{proyecto_obj.nombre.replace(' ', '_')}" if proyecto_obj else "Auditoria_Inventario_ProduMetal"
    response['Content-Disposition'] = f'attachment; filename="{nombre_archivo}.pdf"'
    
    if pisa.CreatePDF(html, dest=response).err:
        return HttpResponse('Hubo un error al generar el PDF de la auditoría.')
    return response


# =======================================================
# MÓDULO DE SEGURIDAD (Gestión de Bloqueos)
# =======================================================

@login_required(login_url='login')
@user_passes_test(es_admin, login_url='dashboard_erp')
def gestionar_empleados(request):
    # Optimizamos con select_related para traer el perfil de un solo golpe de base de datos
    empleados = User.objects.all().select_related('perfil').order_by('-date_joined')
    grupos = Group.objects.all()
    bodegas = Bodega.objects.all() # Traemos las bodegas para el modal de asignación
    
    # 1. Obtenemos TODOS los registros de bloqueos (con detalles como IP, fallos, fecha)
    intentos_bloqueo = AccessAttempt.objects.all()
    
    # 2. Creamos un diccionario rápido para cruzar datos { 'nombre_usuario': <Objeto AccessAttempt> }
    dict_bloqueos = {intento.username: intento for intento in intentos_bloqueo}
    
    # 3. Inyectamos la información detallada en los usuarios
    for emp in empleados:
        if emp.username in dict_bloqueos:
            emp.esta_bloqueado = True
            emp.datos_bloqueo = dict_bloqueos[emp.username] # Contiene IP, failures_since_start, attempt_time
        else:
            emp.esta_bloqueado = False
            emp.datos_bloqueo = None

    if request.method == 'POST':
        # 1. LÓGICA PARA ASIGNAR BODEGA AL BODEGUERO
        if 'asignar_bodega' in request.POST:
            user_id = request.POST.get('user_id')
            bodega_id = request.POST.get('bodega_id')
            
            usuario_mod = get_object_or_404(User, id=user_id)
            # Obtenemos o creamos el perfil para que no dé error si es un usuario antiguo
            perfil, created = PerfilEmpleado.objects.get_or_create(usuario=usuario_mod)
            
            if bodega_id:
                bodega_seleccionada = get_object_or_404(Bodega, id=bodega_id)
                perfil.bodega_asignada = bodega_seleccionada
                messages.success(request, f"✅ Bodega '{bodega_seleccionada.nombre}' asignada a {usuario_mod.username}.")
            else:
                perfil.bodega_asignada = None
                messages.success(request, f"✅ Se quitó la asignación de bodega para {usuario_mod.username}.")
                
            perfil.save()
            return redirect('gestionar_empleados')

        # 2. LÓGICA ORIGINAL PARA CREAR UN NUEVO EMPLEADO
        form = RegistroEmpleadoForm(request.POST)
        if form.is_valid():
            user = form.save()
            grupo_id = request.POST.get('grupo')
            if grupo_id:
                grupo = Group.objects.get(id=grupo_id)
                user.groups.add(grupo)
            messages.success(request, f"✅ Empleado {user.username} creado y asignado al grupo con éxito.")
            return redirect('gestionar_empleados')
        else:
            messages.error(request, "❌ Error al crear el usuario. Revisa los datos e intenta de nuevo.")
    else:
        form = RegistroEmpleadoForm()

    return render(request, 'web/erp/gestionar_empleados.html', {
        'empleados': empleados,
        'grupos': grupos,
        'bodegas': bodegas,
        'form': form
    })

@login_required(login_url='login')
@user_passes_test(es_admin, login_url='dashboard_erp')
def desbloquear_empleado(request, username):
    """Filtra y elimina el registro de bloqueos de un empleado real en la base de datos de Axes"""
    # Verificación estricta de seguridad: Confirmar que es un empleado existente
    empleado_valido = User.objects.filter(username=username).exists()
    
    if empleado_valido:
        intentos_limpiados = reset(username=username)
        if intentos_limpiados:
            messages.success(request, f"🔒 Seguridad: El acceso para el usuario '{username}' ha sido restaurado con éxito.")
        else:
            messages.info(request, f"El usuario '{username}' no presentaba restricciones de acceso.")
    else:
        messages.error(request, "Acción rechazada: El usuario solicitado no pertenece al sistema.")
        
    return redirect('gestionar_empleados')

@login_required(login_url='login')
@user_passes_test(es_admin, login_url='dashboard_erp')
def gestionar_bloqueos(request):
    intentos_fallidos = AccessAttempt.objects.all().order_by('-attempt_time')
    return render(request, 'web/erp/gestionar_bloqueos.html', {'intentos': intentos_fallidos})

@login_required(login_url='login')
@user_passes_test(es_admin, login_url='dashboard_erp')
def desbloquear_usuario(request, intento_id):
    intento = get_object_or_404(AccessAttempt, id=intento_id)
    usuario = intento.username
    intento.delete()
    messages.success(request, f"¡El usuario '{usuario}' ha sido desbloqueado con éxito! Ya puede iniciar sesión.")
    return redirect('gestionar_bloqueos')

@login_required(login_url='login')
@user_passes_test(es_admin, login_url='dashboard_erp')
def subir_certificado_lote(request, movimiento_id):
    movimiento = get_object_or_404(MovimientoInventario, id=movimiento_id, tipo='INGRESO')
    
    if request.method == 'POST':
        archivo_pdf = request.FILES.get('certificado_pdf')
        if archivo_pdf:
            movimiento.certificado_calidad = archivo_pdf
            movimiento.save()
            messages.success(request, f'Certificado de calidad adjuntado al lote de {movimiento.material.sku}.')
        else:
            messages.error(request, 'Debes seleccionar un archivo PDF.')
            
        return redirect('historial_movimientos')
    
@login_required(login_url='login')
@user_passes_test(es_admin, login_url='dashboard_erp')
def alternar_estado_empleado(request, empleado_id):
    empleado = get_object_or_404(User, id=empleado_id)
    
    if empleado.is_superuser:
        messages.error(request, "Por seguridad, no puedes suspender al Administrador principal.")
        return redirect('gestionar_empleados')
        
    empleado.is_active = not empleado.is_active
    empleado.save()
    
    estado = "restaurado" if empleado.is_active else "suspendido"
    messages.success(request, f"El acceso del usuario '{empleado.username}' ha sido {estado} correctamente.")
    return redirect('gestionar_empleados')

@login_required(login_url='login')
@user_passes_test(es_admin, login_url='dashboard_erp')
@transaction.atomic
def revisar_requerimiento_items(request, req_id):
    requerimiento = get_object_or_404(Requerimiento, id=req_id)
    items = requerimiento.detalles.all()
    
    if request.method == 'POST':
        for item in items:
            if item.estado_item != 'PENDIENTE':
                continue

            decision = request.POST.get(f'decision_{item.id}')
            motivo = request.POST.get(f'motivo_{item.id}', '')

            # Ahora procesamos TODAS las decisiones manuales, no solo los rechazos
            if decision in ['RECHAZADO', 'APROBADO_BODEGA', 'EN_COMPRAS']:
                item.estado_item = decision
                if decision == 'RECHAZADO':
                    item.motivo_rechazo = motivo
                item.save()

        # Si el administrador mandó manualmente ítems a compras, generamos la solicitud
        if requerimiento.detalles.filter(estado_item='EN_COMPRAS').exists():
            solicitud, _ = SolicitudCompra.objects.get_or_create(
                requerimiento_origen=requerimiento, defaults={'estado': 'ENVIADO_A_COMPRAS'}
            )
            for detalle in requerimiento.detalles.filter(estado_item='EN_COMPRAS'):
                CotizacionItem.objects.get_or_create(
                    solicitud=solicitud, material=detalle.material,
                    defaults={'cantidad_requerida': detalle.cantidad_solicitada}
                )

        # Actualizamos el estado maestro del ticket según las decisiones tomadas
        estados = list(requerimiento.detalles.values_list('estado_item', flat=True))
        if all(e == 'RECHAZADO' for e in estados):
            requerimiento.estado = 'RECHAZADO'
        elif all(e == 'APROBADO_BODEGA' for e in estados):
            requerimiento.estado = 'APROBADO'
        elif 'EN_COMPRAS' in estados and 'APROBADO_BODEGA' in estados:
            requerimiento.estado = 'PARCIALMENTE_DESPACHADO'
        elif all(e == 'EN_COMPRAS' for e in estados):
            requerimiento.estado = 'EN_COMPRAS'
            
        requerimiento.save()
        messages.success(request, f"Las decisiones manuales para el ticket {requerimiento.folio} han sido guardadas y procesadas.")
        return redirect('dashboard_erp')

    return render(request, 'web/erp/revisar_requerimiento.html', {
        'requerimiento': requerimiento,
        'items': items
    })
@login_required(login_url='login')
@user_passes_test(es_admin, login_url='dashboard_erp')
def configuracion_erp(request):
    # Formulario para Bodegas
    if 'form_bodega' in request.POST:
        form = BodegaForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, "Bodega creada exitosamente.")
            return redirect('configuracion_erp')
    
    # Formulario para Categorías
    if 'form_categoria' in request.POST:
        form_c = CategoriaForm(request.POST)
        if form_c.is_valid():
            form_c.save()
            messages.success(request, "Categoría creada exitosamente.")
            return redirect('configuracion_erp')

    return render(request, 'web/erp/configuracion.html', {
        'form_bodega': BodegaForm(),
        'form_categoria': CategoriaForm(),
        'bodegas': Bodega.objects.all(),
        'categorias': Categoria.objects.all()
    })
@login_required(login_url='login')
@user_passes_test(es_admin, login_url='dashboard_erp')
def crear_categoria(request):
    """
    Vista para crear una nueva categoría en el catálogo maestro.
    Acceso restringido estrictamente al Administrador.
    """
    if request.method == 'POST':
        form = CategoriaForm(request.POST)
        if form.is_valid():
            try:
                categoria = form.save()
                messages.success(
                    request, 
                    f"✅ Categoría '{categoria.nombre}' creada con éxito. Prefijo asignado: <strong>{categoria.prefijo}</strong>"
                )
                return redirect('inventario_actual')
            except Exception as e:
                messages.error(request, f"❌ Error al guardar la categoría: {str(e)}")
        else:
            for field, errors in form.errors.items():
                for error in errors:
                    messages.error(request, f"⚠️ {form.fields[field].label}: {error}")
    else:
        form = CategoriaForm()

    context = {
        'form': form,
        'titulo': 'Crear Nueva Categoría de Materiales',
    }
    return render(request, 'web/erp/crear_categoria.html', context)


@login_required(login_url='login')
@user_passes_test(es_admin, login_url='dashboard_erp')
def alternar_estado_categoria(request, categoria_id):
    """Permite encender o apagar una categoría desde la vista de configuración"""
    categoria = get_object_or_404(Categoria, id=categoria_id)
    
    # Invertimos el estado (Si era True, pasa a False, y viceversa)
    categoria.is_active = not categoria.is_active
    categoria.save()
    
    estado_texto = "activada" if categoria.is_active else "desactivada"
    if categoria.is_active:
        messages.success(request, f"¡La categoría '{categoria.nombre}' ha sido {estado_texto} con éxito!")
    else:
        messages.warning(request, f"La categoría '{categoria.nombre}' ha sido {estado_texto}. Ya no aparecerá en los nuevos ingresos.")
        
    return redirect('configuracion_erp')

@login_required(login_url='login')
@user_passes_test(es_admin, login_url='dashboard_erp')
def trazabilidad_requerimientos(request):
    """
    Panel de control maestro para el Administrador.
    Permite ver el ciclo de vida completo de cada solicitud ordenada por fecha.
    """
    # Traemos todos los tickets ordenados del más reciente al más antiguo
    requerimientos = Requerimiento.objects.all().order_by('-fecha_solicitud')
    
    # Filtro opcional por estado
    estado_filtro = request.GET.get('estado')
    if estado_filtro:
        requerimientos = requerimientos.filter(estado=estado_filtro)
        
    return render(request, 'web/erp/trazabilidad.html', {
        'requerimientos': requerimientos,
        'estado_actual': estado_filtro
    })

@login_required(login_url='login')
@user_passes_test(lambda u: es_bodeguero(u) or es_admin(u), login_url='dashboard_erp')
@transaction.atomic
def trasladar_material(request, material_id):
    material = get_object_or_404(Material, id=material_id)
    
    # 1. Filtramos las bodegas de origen permitidas según el rol
    if request.user.is_superuser:
        bodegas_origen_permitidas = Bodega.objects.all()
    else:
        # El bodeguero solo puede sacar material de su bodega asignada
        if hasattr(request.user, 'perfil') and request.user.perfil.bodega_asignada:
            bodegas_origen_permitidas = Bodega.objects.filter(id=request.user.perfil.bodega_asignada.id)
        else:
            messages.error(request, "Acceso denegado: No tienes una bodega asignada para realizar traslados.")
            return redirect('inventario_actual')

    # El destino sí puede ser cualquier bodega (para recibir el material)
    bodegas_destino = Bodega.objects.all()

    if request.method == 'POST':
        origen_id = request.POST.get('bodega_origen')
        destino_id = request.POST.get('bodega_destino')
        
        try:
            cantidad = Decimal(request.POST.get('cantidad', '0').replace(',', '.'))
        except:
            cantidad = Decimal('0')
            
        if cantidad > 0 and origen_id and destino_id and origen_id != destino_id:
            # 2. VALIDACIÓN DE SEGURIDAD CRÍTICA
            # Verificamos que el origen seleccionado esté dentro de las permitidas para este usuario
            bod_origen = bodegas_origen_permitidas.filter(id=origen_id).first()
            
            if not bod_origen:
                messages.error(request, "Vulnerabilidad bloqueada: No puedes extraer stock de una bodega que no administras.")
                return redirect('trasladar_material', material_id=material.id)
                
            bod_destino = get_object_or_404(Bodega, id=destino_id)
            
            # Bloqueo de concurrencia
            mat_lock = Material.objects.select_for_update().get(id=material.id)
            stock_origen = StockBodega.objects.select_for_update().filter(bodega=bod_origen, material=mat_lock).first()
            cant_origen = Decimal(str(stock_origen.cantidad)) if stock_origen else Decimal('0')
            
            if cant_origen < cantidad:
                messages.error(request, f"No puedes trasladar {cantidad}. Solo hay {cant_origen} en {bod_origen.nombre}.")
            else:
                # 1. Restamos del origen
                stock_origen.cantidad = cant_origen - cantidad
                stock_origen.save()
                
                # 2. Sumamos al destino
                stock_dest, _ = StockBodega.objects.select_for_update().get_or_create(bodega=bod_destino, material=mat_lock)
                cant_dest = Decimal(str(stock_dest.cantidad)) if stock_dest.cantidad else Decimal('0')
                stock_dest.cantidad = cant_dest + cantidad
                stock_dest.save()
                
                # 3. Guardar material (El total general no cambia, pero se sincroniza el log)
                mat_lock.save() 
                
                # 4. Registrar en la auditoría como TRASLADO
                MovimientoInventario.objects.create(
                    material=mat_lock, tipo='TRASLADO', cantidad=cantidad, 
                    bodega_origen=bod_origen, bodega_destino=bod_destino,
                    responsable=request.user, observaciones=request.POST.get('observaciones', 'Traslado logístico interno')
                )
                messages.success(request, f"🚚 Traslado Exitoso: Se movieron {cantidad} ítems a {bod_destino.nombre}.")
                return redirect('inventario_actual')
        else:
            messages.error(request, "Datos inválidos. Asegúrate de que la cantidad sea mayor a 0 y que el origen y destino sean distintos.")

    return render(request, 'web/erp/traslado_bodegas.html', {
        'material': material, 
        'bodegas_origen': bodegas_origen_permitidas, # Mandamos solo las permitidas para el select de origen
        'bodegas_destino': bodegas_destino           # Mandamos todas para el select de destino
    })

@login_required(login_url='login')
@user_passes_test(lambda u: es_bodeguero(u) or es_admin(u), login_url='dashboard_erp')
def iniciar_solicitud_abastecimiento(request):
    """Crea el documento 'Borrador' de la solicitud y redirige a la pantalla para añadir ítems"""
    # Creamos una solicitud en estado inicial directamente
    nueva_solicitud = SolicitudCompra.objects.create(
        estado='ENVIADO_A_COMPRAS',
        observaciones_admin="Solicitud de reabastecimiento generada desde Bodega"
    )
    return redirect('añadir_items_solicitud', solicitud_id=nueva_solicitud.id)

@login_required(login_url='login')
@user_passes_test(lambda u: es_bodeguero(u) or es_admin(u), login_url='dashboard_erp')
def añadir_items_solicitud(request, solicitud_id):
    """Vista donde el bodeguero escanea o selecciona lo que le falta en perchas"""
    solicitud = get_object_or_404(SolicitudCompra, id=solicitud_id)
    
    # IMPORTANTE: Ordenamos por ID descendente para que el último agregado salga primero
    items_agregados = solicitud.items_cotizados.all().order_by('-id')
    
    # Materiales activos para el selector
    materiales_catalogo = Material.objects.filter(is_active=True).order_by('nombre')

    if request.method == 'POST':
        # Validar si apretaron el botón de "Añadir Material"
        if 'btn_agregar_item' in request.POST:
            material_id = request.POST.get('material_id')
            
            try:
                cantidad = Decimal(request.POST.get('cantidad', '0').replace(',', '.'))
            except:
                cantidad = Decimal('0')

            if material_id and cantidad > 0:
                material = get_object_or_404(Material, id=material_id)
                
                # Verificamos si ya lo agregó antes en esta misma solicitud para sumar la cantidad
                item_existente = items_agregados.filter(material=material).first()
                if item_existente:
                    item_existente.cantidad_requerida += cantidad
                    item_existente.save()
                    messages.info(request, f'Se sumaron {cantidad} a {material.nombre} en la lista.')
                else:
                    CotizacionItem.objects.create(
                        solicitud=solicitud,
                        material=material,
                        cantidad_requerida=cantidad
                    )
                    messages.success(request, f'{material.nombre} añadido a la solicitud.')
            else:
                messages.error(request, "Asegúrate de seleccionar un material y una cantidad mayor a cero.")
            
            return redirect('añadir_items_solicitud', solicitud_id=solicitud.id)
            
        # Si aprieta el botón final de "Enviar al Administrador"
        elif 'btn_finalizar' in request.POST:
            if not items_agregados.exists():
                messages.error(request, "No puedes enviar una solicitud vacía.")
                return redirect('añadir_items_solicitud', solicitud_id=solicitud.id)
                
            messages.success(request, f"¡Solicitud {solicitud.folio} enviada! El Administrador ya la tiene en su bandeja para consolidar la compra.")
            return redirect('dashboard_erp')

    # === LÓGICA DE PAGINACIÓN ===
    paginator = Paginator(items_agregados, 5) # Muestra 5 materiales por página (ideal para celular)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    return render(request, 'web/erp/solicitar_abastecimiento.html', {
        'solicitud': solicitud,
        'items': items_agregados, # Se manda la lista completa por si necesitas contar el total (.count)
        'page_obj': page_obj,     # <-- ESTA ES LA VARIABLE QUE USA EL HTML PARA MOSTRAR LA TABLA Y LOS BOTONES DE PAGINACIÓN
        'materiales': materiales_catalogo
    })




@login_required(login_url='login')
@transaction.atomic
def actualizar_item_solicitud(request, item_id):
    """Permite al bodeguero corregir la cantidad de un ítem antes de enviarlo"""
    if request.method == 'POST':
        item = get_object_or_404(CotizacionItem, id=item_id)
        try:
            nueva_cantidad = Decimal(request.POST.get('nueva_cantidad', '0').replace(',', '.'))
            if nueva_cantidad > 0:
                item.cantidad_requerida = nueva_cantidad
                item.save()
                messages.success(request, f"Cantidad de {item.material.nombre} actualizada a {nueva_cantidad}.")
            else:
                messages.error(request, "La cantidad debe ser mayor a cero.")
        except:
            messages.error(request, "Valor inválido.")
            
        return redirect('añadir_items_solicitud', solicitud_id=item.solicitud.id)
    return redirect('dashboard_erp')

@login_required(login_url='login')
@transaction.atomic
def eliminar_item_requerimiento(request, item_id):
    """Permite al bodeguero borrar un material que agregó por error"""
    if request.method == 'POST':
        item = get_object_or_404(CotizacionItem, id=item_id)
        solicitud_id = item.solicitud.id
        nombre_material = item.material.nombre
        item.delete()
        messages.warning(request, f"Se eliminó {nombre_material} de la solicitud.")
        return redirect('añadir_items_solicitud', solicitud_id=solicitud_id)
    return redirect('dashboard_erp')

@login_required(login_url='login')
@transaction.atomic
def actualizar_item_requerimiento(request, item_id):
    """Permite al solicitante corregir la cantidad (en enteros) antes de mandar el ticket"""
    item = get_object_or_404(DetalleRequerimiento, id=item_id)
    
    # Validar por seguridad que el ticket siga en borrador (PENDIENTE)
    if item.requerimiento.estado == 'PENDIENTE':
        if request.method == 'POST':
            try:
                # Convertimos estrictamente a entero (int)
                nueva_cantidad = int(request.POST.get('nueva_cantidad', 0))
                
                if nueva_cantidad > 0:
                    item.cantidad_solicitada = nueva_cantidad
                    item.save()
                    messages.success(request, f"Se actualizó la cantidad de {item.material.nombre} a {nueva_cantidad} unidades.")
                else:
                    messages.error(request, "La cantidad debe ser mayor a cero.")
            except ValueError:
                messages.error(request, "Error: Solo se permiten números enteros para solicitar material de obra.")
    else:
        messages.error(request, "No puedes modificar este ticket porque ya fue enviado o está siendo procesado.")
        
    return redirect('añadir_materiales', req_id=item.requerimiento.id)