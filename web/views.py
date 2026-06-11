from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib import messages
from django.contrib.auth.models import User, Group
from django.db.models import Sum, F, Q
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
        # El admin debe ver todo ticket que tenga al menos un ítem PENDIENTE (independiente de si está parcialmente despachado)
        context['tickets_pendientes'] = Requerimiento.objects.filter(detalles__estado_item='PENDIENTE').distinct().order_by('fecha_solicitud')
        context['ultimos_movimientos'] = MovimientoInventario.objects.all().order_by('-fecha_hora')[:5]
        context['cotizaciones_pendientes'] = SolicitudCompra.objects.filter(estado='COTIZADO').order_by('fecha_creacion')
        context['alertas_oc'] = OrdenCompra.objects.filter(estado='RECIBIDA_PARCIAL')
        
    elif es_bodeguero(usuario):
        context['rol'] = 'Bodeguero'
        bodega_asignada = getattr(usuario.perfil, 'bodega_asignada', None) if hasattr(usuario, 'perfil') else None
        
        # El bodeguero SOLO ve tickets que tengan ítems aprobados y que pertenezcan a SU bodega
        if bodega_asignada:
            context['tickets_por_despachar'] = Requerimiento.objects.filter(detalles__estado_item='APROBADO_BODEGA', detalles__bodega_destino=bodega_asignada).distinct()
        else:
            context['tickets_por_despachar'] = Requerimiento.objects.none()
            
        context['mis_compras_pendientes'] = OrdenCompra.objects.filter(estado__in=['EMITIDA', 'RECIBIDA_PARCIAL'])
        context['alertas_stock'] = Material.objects.filter(stock_actual__lte=F('stock_minimo'))

    elif es_comprador(usuario):
        context['rol'] = 'Compras'
        context['solicitudes_compras'] = SolicitudCompra.objects.filter(estado__in=['ENVIADO_A_COMPRAS', 'REVISADO_ADMIN']).order_by('-fecha_creacion')
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
    # Obtenemos el requerimiento asegurándonos de que pertenezca al usuario
    requerimiento = get_object_or_404(Requerimiento, id=req_id, solicitante=request.user)
    
    # BLOQUEO MAESTRO: Si el administrador ya lo revisó, el solicitante NO PUEDE entrar aquí
    if requerimiento.estado != 'PENDIENTE':
        messages.error(
            request, 
            f"El ticket {requerimiento.folio} ya se encuentra en proceso de {requerimiento.get_estado_display().lower()} y no puede ser modificado."
        )
        return redirect('dashboard_erp')

    # Si sigue PENDIENTE, el flujo continúa normalmente para añadir materiales
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
@transaction.atomic
def actualizar_item_ticket(request, item_id):
    item = get_object_or_404(DetalleRequerimiento, id=item_id)
    
    # BLOQUEO DE SEGURIDAD
    if item.requerimiento.estado != 'PENDIENTE':
        messages.error(request, "No puedes modificar las cantidades de un ticket que ya está en proceso.")
        return redirect('añadir_materiales', req_id=item.requerimiento.id)

    if request.method == 'POST':
        try:
            nueva_cantidad = int(request.POST.get('nueva_cantidad', 0))
            if nueva_cantidad > 0:
                item.cantidad_solicitada = nueva_cantidad
                item.save()
                messages.success(request, f"Cantidad de {item.material.nombre} actualizada.")
            else:
                messages.error(request, "La cantidad debe ser mayor a 0.")
        except ValueError:
            messages.error(request, "Ingrese un número entero válido.")
            
    return redirect('añadir_materiales', req_id=item.requerimiento.id)

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
    
    es_super = request.user.is_superuser
    bodega_del_usuario = getattr(request.user.perfil, 'bodega_asignada', None) if hasattr(request.user, 'perfil') else None

    # Filtrado Estricto de ítems a despachar
    if es_super:
        items_a_despachar = ticket.detalles.filter(estado_item='APROBADO_BODEGA')
    else:
        if not bodega_del_usuario:
            messages.error(request, "No tienes bodega asignada para operar.")
            return redirect('dashboard_erp')
        items_a_despachar = ticket.detalles.filter(estado_item='APROBADO_BODEGA', bodega_destino=bodega_del_usuario)

    if not items_a_despachar.exists():
        messages.warning(request, "No tienes autorización para despachar materiales de este ticket en tu bodega.")
        return redirect('dashboard_erp')

    if request.method == 'POST':
        for item in items_a_despachar:
            cant_solicitada = Decimal(str(item.cantidad_solicitada))
            cant_despachada = Decimal(str(item.cantidad_despachada))
            cantidad_a_entregar = cant_solicitada - cant_despachada
            
            if cantidad_a_entregar > 0:
                material = Material.objects.select_for_update().get(id=item.material.id)
                bodega_origen = item.bodega_destino # EXTRAE DIRECTO DE LA VINCULADA
                stock_bodega = StockBodega.objects.select_for_update().filter(bodega=bodega_origen, material=material).first()
                
                cant_en_bodega = Decimal(str(stock_bodega.cantidad)) if stock_bodega and stock_bodega.cantidad else Decimal('0.0')
                
                if cant_en_bodega < cantidad_a_entregar:
                    messages.error(request, f"Error físico: Faltan existencias en {bodega_origen.nombre} para {material.nombre}.")
                    return redirect('despachar_requerimiento', req_id=ticket.id)

                # Descuenta de la bodega específica
                stock_bodega.cantidad = cant_en_bodega - cantidad_a_entregar
                stock_bodega.save()
                material.save()

                MovimientoInventario.objects.create(
                    material=material, tipo='SALIDA', cantidad=cantidad_a_entregar, bodega_origen=bodega_origen,
                    responsable=request.user, requerimiento_asociado=ticket,
                    observaciones=f"Despacho físico desde {bodega_origen.nombre}"
                )
                
                item.cantidad_despachada = cant_despachada + cantidad_a_entregar
                item.estado_item = 'DESPACHADO'
                item.save()

        ticket.actualizar_estado_general()
        messages.success(request, f"Despacho completado. Los materiales salieron estrictamente de sus bodegas destino.")
        return redirect('dashboard_erp')

    return render(request, 'web/erp/confirmar_despacho.html', {
        'ticket': ticket,
        'items': items_a_despachar,
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
@transaction.atomic
def desglosar_item_cotizacion(request, item_id):
    item = get_object_or_404(CotizacionItem, id=item_id)
    if request.method == 'POST':
        try:
            # Blindaje con Decimal
            cantidad_nueva = Decimal(request.POST.get('cantidad_separar', '0').replace(',', '.'))
            if Decimal('0') < cantidad_nueva < item.cantidad_requerida:
                item.cantidad_requerida -= cantidad_nueva
                item.save()
                
                # Crear el nuevo clon preservando la solicitud
                CotizacionItem.objects.create(
                    solicitud=item.solicitud, material=item.material, 
                    cantidad_requerida=cantidad_nueva, estado_aprobacion=item.estado_aprobacion
                )
                messages.success(request, "Material desglosado correctamente para asignar a otro proveedor.")
            else:
                messages.error(request, "La cantidad a separar es inválida o excede lo requerido.")
        except Exception as e:
            messages.error(request, "Error de formato numérico.")
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
    """
    VISTA DEL ADMIN: Solo finaliza su revisión y le pasa la pelota a Compras.
    Ya no genera las órdenes de compra aquí.
    """
    solicitud = get_object_or_404(SolicitudCompra, id=solicitud_id)
    
    # Cambiamos al nuevo estado (asegúrate de haberlo agregado en models.py como se indicó en la mejora 9)
    solicitud.estado = 'REVISADO_ADMIN'
    solicitud.save()
    
    messages.success(request, "Revisión finalizada. Se notificó al departamento de Compras para que procedan con la generación definitiva de las Órdenes.")
    return redirect('dashboard_erp')

# AGREGAR NUEVA VISTA PARA COMPRADOR
@login_required(login_url='login')
@user_passes_test(es_comprador, login_url='dashboard_erp')
@transaction.atomic
def confirmar_compra_definitiva(request, solicitud_id):
    """
    VISTA DE COMPRAS: El comprador revisa lo que el admin aprobó/rechazó
    y le da al botón final para generar las Órdenes de Compra reales.
    """
    solicitud = get_object_or_404(SolicitudCompra, id=solicitud_id)
    
    if request.method == 'POST':
        # Buscamos solo los ítems que el Administrador dejó como APROBADO
        items_aprobados = solicitud.items_cotizados.filter(estado_aprobacion='APROBADO')
        proveedores = items_aprobados.values_list('proveedor_cotizado', flat=True).distinct()
        
        # Generamos una Orden de Compra por cada proveedor distinto
        for prov in proveedores:
            if prov: 
                items_prov = items_aprobados.filter(proveedor_cotizado=prov)
                
                # Crear la O.C. Cabecera
                nueva_oc = OrdenCompra.objects.create(
                    proveedor=prov, 
                    creado_por=request.user, 
                    estado='EMITIDA', 
                    observaciones=f"Generada formalmente por Compras desde Solicitud {solicitud.folio}"
                )
                
                # Crear los detalles de la O.C.
                for item in items_prov:
                    DetalleOrdenCompra.objects.create(
                        orden=nueva_oc, 
                        material=item.material, 
                        cantidad_pedida=item.cantidad_requerida
                    )
                
                # Actualizar el estado del ítem cotizado
                items_prov.update(estado_aprobacion='COMPRADO')
                
        # Cerramos la solicitud por completo
        solicitud.estado = 'PROCESADO'
        solicitud.save()
        
        messages.success(request, "¡Check confirmado! Las Órdenes de Compra definitivas han sido generadas exitosamente.")
        return redirect('dashboard_erp')

    # Si entra por GET, le mostramos la pantalla de resumen antes de confirmar
    return render(request, 'web/erp/confirmacion_compras.html', {
        'solicitud': solicitud, 
        'items': solicitud.items_cotizados.all()
    })
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
@user_passes_test(lambda u: es_bodeguero(u) or es_admin(u) or es_comprador(u), login_url='dashboard_erp')
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

    # Identificamos el rol para la interfaz
    rol_actual = 'Administrador' if es_administrador else ('Compras' if es_comprador(request.user) else 'Bodeguero')

    return render(request, 'web/erp/listar_oc.html', {
        'ordenes': ordenes,
        'estados': estados_permitidos, 
        'estado_filtro': estado,
        'rol': rol_actual,
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
        # 1. SEGURIDAD: Identificamos la bodega donde se está recibiendo.
        bodega_id = request.POST.get('bodega_destino')
        bodega = get_object_or_404(Bodega, id=bodega_id) if bodega_id else Bodega.objects.filter(is_principal=True).first()
        
        entrega_incompleta = False

        for item in detalles:
            # BLINDAJE 1: Capturar errores y convertir a Decimal (Alta precisión)
            try:
                valor_texto = request.POST.get(f'recibido_{item.id}', '0').replace(',', '.')
                ingresado = Decimal(valor_texto)
            except Exception:
                ingresado = Decimal('0.0')

            # BLINDAJE 2: Evitar ingresos negativos (restar stock maliciosamente)
            if ingresado < 0:
                messages.error(request, "No se permiten valores negativos en la recepción.")
                return redirect('recibir_orden_compra', oc_id=oc.id)

            archivo_certificado = request.FILES.get(f'certificado_{item.id}')

            if ingresado > 0:
                cant_recibida = Decimal(str(item.cantidad_recibida))
                cant_pedida = Decimal(str(item.cantidad_pedida))

                # BLINDAJE 3: Evitar que el bodeguero reciba más de lo que se pidió
                if (cant_recibida + ingresado) > cant_pedida:
                    messages.error(request, f"Fallo Logístico: Estás intentando ingresar más {item.material.nombre} de lo que Compras autorizó.")
                    return redirect('recibir_orden_compra', oc_id=oc.id)

                item.cantidad_recibida = cant_recibida + ingresado
                item.save()

                if item.cantidad_recibida < cant_pedida:
                    entrega_incompleta = True

                # BLOQUEO DE CONCURRENCIA PARA RECEPCIÓN SEGURA
                material = Material.objects.select_for_update().get(id=item.material.id)

                # PRIMERO ACTUALIZAMOS EL STOCK FÍSICO EN LA BODEGA
                stock_b, _ = StockBodega.objects.select_for_update().get_or_create(bodega=bodega, material=material)
                cant_bodega = Decimal(str(stock_b.cantidad)) if stock_b.cantidad else Decimal('0.0')
                
                stock_b.cantidad = cant_bodega + ingresado
                stock_b.save()

                # LUEGO ACTUALIZAMOS EL MATERIAL (Suma total auto)
                material.save() 

                # Registrar el movimiento de Ingreso en Bitácora
                MovimientoInventario.objects.create(
                    material=material, tipo='INGRESO', cantidad=ingresado, bodega_origen=bodega,
                    responsable=request.user, orden_compra_asociada=oc, certificado_calidad=archivo_certificado,
                    observaciones=f"Ingreso físico de proveedor (O.C. #{oc.folio})"
                )

        # Determinar el estado general de la Orden de Compra
        if entrega_incompleta:
            oc.estado = 'RECIBIDA_PARCIAL'
            messages.warning(request, "Entrega parcial registrada en bodega. Queda saldo pendiente con el proveedor.")
        else:
            oc.estado = 'RECIBIDA'
            messages.success(request, f"Orden {oc.folio} recibida al 100%. Las perchas de la {bodega.nombre} fueron actualizadas.")
        
        oc.save()

        # ========================================================================
        # 🧠 MAGIA LOGÍSTICA: EL DESPERTADOR DE TICKETS (FIFO)
        # ========================================================================
        # Al ingresar cualquier mercadería, el sistema escanea qué tickets antiguos 
        # estaban detenidos esperando material (Ordenados por fecha, del más viejo al más nuevo)
        
        tickets_dormidos = DetalleRequerimiento.objects.filter(
            estado_item__in=['EN_COMPRAS', 'COMPRADO']
        ).order_by('requerimiento__fecha_solicitud')
        
        for req_item in tickets_dormidos:
            # Vemos si hay stock real en la Bodega a la que el ticket pidió el material
            stock_b = StockBodega.objects.filter(material=req_item.material, bodega=req_item.bodega_destino).first()
            cant_fisica = Decimal(str(stock_b.cantidad)) if stock_b and stock_b.cantidad else Decimal('0.0')
            
            # Restamos el stock "comprometido" por otros tickets que ya se aprobaron pero el bodeguero no ha despachado
            comprometido_query = DetalleRequerimiento.objects.filter(
                material=req_item.material,
                bodega_destino=req_item.bodega_destino,
                estado_item='APROBADO_BODEGA'
            ).aggregate(total=Sum('cantidad_solicitada'))['total']
            
            comprometido = Decimal(str(comprometido_query)) if comprometido_query else Decimal('0.0')
            stock_libre = cant_fisica - comprometido
            
            # Si el Stock Libre (Real - Apartado) alcanza para cubrir este ítem antiguo...
            if stock_libre >= Decimal(str(req_item.cantidad_solicitada)):
                # ...Lo liberamos para que el bodeguero pueda despacharlo inmediatamente
                req_item.estado_item = 'APROBADO_BODEGA'
                req_item.motivo_rechazo = "✅ Material recibido del proveedor. Liberado para despacho a obra."
                req_item.save()
                
                # Despertamos al Ticket Maestro para que reaparezca en el Dashboard del Bodeguero
                req_item.requerimiento.actualizar_estado_general()
        # ========================================================================

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
@user_passes_test(lambda u: es_bodeguero(u) or es_admin(u) or es_solicitante(u), login_url='dashboard_erp')
def inventario_actual(request):
    usuario = request.user
    
    # 1. SEGURIDAD LOGÍSTICA: Qué ve cada usuario
    if es_admin(usuario) or es_solicitante(usuario):
        # Admin y Solicitantes deben ver TODO el catálogo maestro para auditar o pedir
        materiales_list = Material.objects.all().order_by('nombre')
    else:
        # El Bodeguero ve los materiales enrutados a su bodega 
        # (¡CORRECCIÓN: Se eliminó el límite de cantidad > 0 para que los ceros NUNCA desaparezcan!)
        bodega_empleado = getattr(usuario.perfil, 'bodega_asignada', None) if hasattr(usuario, 'perfil') else None
        
        if bodega_empleado:
            materiales_list = Material.objects.filter(
                stocks_bodegas__bodega=bodega_empleado
            ).distinct().order_by('nombre')
        else:
            materiales_list = Material.objects.none()

    # 2. BÚSQUEDA DINÁMICA POR CATEGORÍA
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

    # 5. ASIGNACIÓN DINÁMICA DE ROLES PARA LA VISTA (Soluciona fallos en botones)
    if es_admin(usuario):
        rol_actual = 'Administrador'
    elif es_bodeguero(usuario):
        rol_actual = 'Bodeguero'
    else:
        rol_actual = 'Solicitante'

    return render(request, 'web/erp/inventario.html', {
        'page_obj': page_obj, 
        'categorias': categorias,
        'alertas': alertas,
        'rol': rol_actual
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
        'firma_bodeguero': request.user.get_full_name() or request.user.username,
        'firma_solicitante': ticket.solicitante.get_full_name() or ticket.solicitante.username,
        'firma_admin': 'Administración ProduMetal',
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
        'firma_compras': oc.creado_por.get_full_name() or oc.creado_por.username,
        'firma_admin': 'Gerencia de ProduMetal',
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
    
    if request.method == 'POST':
        # Solo audita los ítems que siguen pendientes, ignora los que ya fueron procesados
        items_pendientes = requerimiento.detalles.filter(estado_item='PENDIENTE')
        
        for item in items_pendientes:
            decision = request.POST.get(f'decision_{item.id}')
            motivo = request.POST.get(f'motivo_{item.id}')

            if decision:
                cant_solicitada = Decimal(str(item.cantidad_solicitada))
                stock_b = StockBodega.objects.filter(material=item.material, bodega=item.bodega_destino).first()
                cant_bodega = Decimal(str(stock_b.cantidad)) if stock_b and stock_b.cantidad else Decimal('0.0')

                if decision == 'APROBADO_BODEGA':
                    if cant_bodega >= cant_solicitada:
                        item.estado_item = 'APROBADO_BODEGA'
                        item.motivo_rechazo = motivo or "Aprobado. Hay stock en bodega."
                        item.save()
                    elif cant_bodega > 0:
                        # División Inteligente #1: Aprueba lo que hay, DEJA EL RESTO PENDIENTE para el Admin
                        cant_faltante = cant_solicitada - cant_bodega
                        item.cantidad_solicitada = cant_bodega
                        item.estado_item = 'APROBADO_BODEGA'
                        item.motivo_rechazo = "División: Despacho de existencia actual."
                        item.save()
                        
                        DetalleRequerimiento.objects.create(
                            requerimiento=requerimiento, material=item.material,
                            cantidad_solicitada=cant_faltante, bodega_destino=item.bodega_destino,
                            estado_item='PENDIENTE', motivo_rechazo="Faltante auto-generado. Esperando decisión."
                        )
                    else:
                        messages.warning(request, f"El ítem '{item.material.nombre}' NO tiene stock en {item.bodega_destino.nombre}. Se mantuvo Pendiente.")

                elif decision == 'EN_COMPRAS':
                    solicitud, _ = SolicitudCompra.objects.get_or_create(requerimiento_origen=requerimiento, defaults={'estado': 'ENVIADO_A_COMPRAS'})
                    
                    if cant_bodega >= cant_solicitada:
                        item.estado_item = 'APROBADO_BODEGA'
                        item.motivo_rechazo = "Mando a compras abortado: Hay stock 100%. Aprobado a bodega."
                        item.save()
                    elif cant_bodega > 0:
                        # División Inteligente #2: Aprueba lo que hay, EL RESTO SE VA A COMPRAS MANTENIENDO LA BODEGA
                        cant_faltante = cant_solicitada - cant_bodega
                        item.cantidad_solicitada = cant_bodega
                        item.estado_item = 'APROBADO_BODEGA'
                        item.motivo_rechazo = "División: Stock a bodega, resto a compras."
                        item.save()
                        
                        nuevo_item = DetalleRequerimiento.objects.create(
                            requerimiento=requerimiento, material=item.material,
                            cantidad_solicitada=cant_faltante, bodega_destino=item.bodega_destino,
                            estado_item='EN_COMPRAS', motivo_rechazo="Faltante enrutado a compras."
                        )
                        CotizacionItem.objects.create(solicitud=solicitud, material=nuevo_item.material, bodega_destino=nuevo_item.bodega_destino, cantidad_requerida=nuevo_item.cantidad_solicitada)
                    else:
                        item.estado_item = 'EN_COMPRAS'
                        item.motivo_rechazo = motivo or "Enviado directo a compras."
                        item.save()
                        CotizacionItem.objects.create(solicitud=solicitud, material=item.material, bodega_destino=item.bodega_destino, cantidad_requerida=item.cantidad_solicitada)

                elif decision == 'RECHAZADO':
                    item.estado_item = 'RECHAZADO'
                    item.motivo_rechazo = motivo or "Ítem denegado."
                    item.save()

        # Recalcula el estado general (Parcial, Pendiente, Aprobado...)
        requerimiento.actualizar_estado_general()
        messages.success(request, "Ticket procesado con trazabilidad estricta. Los faltantes siguen en su bandeja de PENDIENTES.")
        return redirect('dashboard_erp')

    return render(request, 'web/erp/revisar_requerimiento.html', {
        'requerimiento': requerimiento,
        'items': requerimiento.detalles.all().order_by('estado_item')
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
def eliminar_item_ticket(request, item_id):
    item = get_object_or_404(DetalleRequerimiento, id=item_id)
    req_id = item.requerimiento.id
    
    # BLOQUEO DE SEGURIDAD
    if item.requerimiento.estado != 'PENDIENTE':
        messages.error(request, "No puedes eliminar ítems de un ticket que ya está en proceso.")
        return redirect('añadir_materiales', req_id=req_id)

    if request.method == 'POST':
        item.delete()
        messages.warning(request, "Material eliminado del ticket.")
        
    return redirect('añadir_materiales', req_id=req_id)

@login_required(login_url='login')
@transaction.atomic
def eliminar_item_solicitud(request, item_id):
    """Permite al bodeguero borrar un material que agregó por error en su solicitud"""
    if request.method == 'POST':
        item = get_object_or_404(CotizacionItem, id=item_id)
        solicitud_id = item.solicitud.id
        nombre_material = item.material.nombre
        item.delete()
        messages.warning(request, f"Se eliminó {nombre_material} de la solicitud.")
        return redirect('añadir_items_solicitud', solicitud_id=solicitud_id)
    return redirect('dashboard_erp')

@login_required(login_url='login')
@user_passes_test(lambda u: es_comprador(u) or es_admin(u), login_url='dashboard_erp')
def historial_solicitudes(request):
    """Muestra todas las solicitudes de compra históricas para Admin y Compras"""
    solicitudes = SolicitudCompra.objects.all().order_by('-fecha_creacion')
    return render(request, 'web/erp/historial_solicitudes.html', {
        'solicitudes': solicitudes,
        'rol': 'Administrador' if es_admin(request.user) else 'Compras'
    })

@login_required(login_url='login')
@user_passes_test(lambda u: es_comprador(u) or es_admin(u), login_url='dashboard_erp')
def detalle_solicitud_procesada(request, solicitud_id):
    """Vista de Solo Lectura para ver qué aprobó o rechazó el Administrador"""
    solicitud = get_object_or_404(SolicitudCompra, id=solicitud_id)
    items = solicitud.items_cotizados.all()
    return render(request, 'web/erp/detalle_solicitud_procesada.html', {
        'solicitud': solicitud, 
        'items': items
    })

# AGREGAR nueva vista
@login_required(login_url='login')
@user_passes_test(es_bodeguero, login_url='dashboard_erp')
@transaction.atomic
def entrega_directa_bodeguero(request):
    bodega_asignada = getattr(request.user.perfil, 'bodega_asignada', None)
    if not bodega_asignada:
        messages.error(request, "No tienes una bodega asignada para realizar despachos.")
        return redirect('dashboard_erp')

    if request.method == 'POST':
        material_id = request.POST.get('material_id')
        cantidad = Decimal(request.POST.get('cantidad', '0').replace(',', '.'))
        observaciones = request.POST.get('observaciones')
        proyecto_id = request.POST.get('proyecto_id') # Destino administrativo

        material = get_object_or_404(Material, id=material_id)
        stock_b = StockBodega.objects.select_for_update().filter(bodega=bodega_asignada, material=material).first()

        if stock_b and stock_b.cantidad >= cantidad > 0 and observaciones:
            stock_b.cantidad -= cantidad
            stock_b.save()
            material.save()

            MovimientoInventario.objects.create(
                material=material, tipo='SALIDA', cantidad=cantidad, bodega_origen=bodega_asignada,
                responsable=request.user, 
                observaciones=f"[ENTREGA DIRECTA URGENTE] Proyecto ID: {proyecto_id} | {observaciones}"
            )
            # Aquí podrías crear un registro de Notificación si tuvieras el modelo
            messages.success(request, f"Entrega directa de {cantidad} {material.nombre} registrada. El administrador ha sido notificado en la auditoría.")
            return redirect('dashboard_erp')
        else:
            messages.error(request, "Error: Stock insuficiente u observaciones vacías.")
            
    materiales = Material.objects.filter(stocks_bodegas__bodega=bodega_asignada, stocks_bodegas__cantidad__gt=0).distinct()
    proyectos = Proyecto.objects.filter(is_active=True)
    return render(request, 'web/erp/entrega_directa.html', {'materiales': materiales, 'proyectos': proyectos})