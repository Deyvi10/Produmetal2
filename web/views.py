from django.shortcuts import render, redirect, get_object_or_404
from django.urls import reverse
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib import messages
from django.contrib.auth.models import User, Group
from django.db.models import Sum, F, Q
from django.core.exceptions import ValidationError
from axes.models import AccessAttempt
from django.db import transaction
from django.core.paginator import Paginator
from .forms import MaterialForm
from decimal import Decimal
from axes.utils import reset
from datetime import datetime, timedelta
import json
# =======================================================
# IMPORTACIONES DE MODELOS Y FORMULARIOS
# =======================================================
from .models import (
    Requerimiento, DetalleRequerimiento, Material, Proyecto, MovimientoInventario,
    OrdenCompra, DetalleOrdenCompra, SolicitudCompra, CotizacionItem, Bodega, StockBodega,
    Categoria, PerfilEmpleado, CierreIncompletoRequerimiento,
    Trabajador, EntregaDirecta, PrestamoHerramienta, DevolucionPrestamo,
    SalarioTrabajador, HorarioTrabajador, HorarioTrabajadorDia, ConfiguracionHorasExtra, Pago, HoraExtra, Descuento,
    PeriodoNominaMensual,
    )
from . import servicios_nomina
from .forms import (
    RequerimientoForm, DetalleRequerimientoForm, RegistroEmpleadoForm,
    OrdenCompraForm, DetalleOrdenCompraForm, AjusteInventarioForm,
    VentaMaterialForm, BodegaForm, CategoriaForm,
    TrabajadorForm, HorarioDiaFormSet, ConfiguracionHorasExtraForm,
)

# IMPORTS PARA GENERACIÓN DE PDF
from django.template.loader import get_template
from django.http import HttpResponse, FileResponse, Http404
from xhtml2pdf import pisa
import os
from django.conf import settings
from django.utils import timezone

# =======================================================
# ARCHIVOS SUBIDOS (cotizaciones, facturas, certificados) SIN S3
# =======================================================

@login_required(login_url='login')
def servir_archivo_media(request, path):
    """
    Sirve /media/<path> solo a usuarios autenticados, en vez de exponerlo
    públicamente (django.views.static.serve no exige ningún login). Los
    archivos aquí son documentos de negocio (cotizaciones de proveedores,
    facturas, certificados de calidad); no hay razón para que sean
    accesibles sin sesión. Solo se usa cuando no hay S3 configurado
    (ver produmental_config/urls.py); con S3, las URLs firmadas de AWS ya
    hacen su propio control de acceso.
    """
    base_dir = os.path.realpath(settings.MEDIA_ROOT)
    target = os.path.realpath(os.path.join(base_dir, path))

    # Blindaje contra path traversal (ej. ?path=../../produmental_config/settings.py)
    if os.path.commonpath([base_dir, target]) != base_dir:
        raise Http404("Archivo no encontrado.")
    if not os.path.isfile(target):
        raise Http404("Archivo no encontrado.")

    return FileResponse(open(target, 'rb'))

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
        {'id': 'campo-oh', 'titulo': 'Casa de Campo "El Refugio" ', 'categoria': 'Residencial / Diseño', 'img': 'oh_main.jpg'},
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
            'titulo': 'Casa de Campo "El Refugio" ',
            'ubicacion': 'Proyecto Residencial',
            'descripcion': 'Residencia "El Refugio" es un proyecto que integra la estructura metálica con principios geométricos...',
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
    
    # 1. CAPTURAMOS LOS FILTROS Y LA PÁGINA DESDE LA URL
    estado_filtro = request.GET.get('estado')
    page_number = request.GET.get('page')

    if es_admin(usuario):
        context['rol'] = 'Administrador'
        
        # Base query: Tickets que necesitan atención del Admin
        qs_tickets = Requerimiento.objects.filter(
            estado__in=['PENDIENTE', 'EN_COMPRAS', 'PARCIALMENTE_DESPACHADO']
        ).distinct().order_by('-fecha_solicitud')
        
        # Aplicamos filtro si el admin hizo clic en alguna píldora
        if estado_filtro:
            qs_tickets = qs_tickets.filter(estado=estado_filtro)
            
        # Paginación (10 tickets por página)
        paginator_tickets = Paginator(qs_tickets, 10)
        context['tickets_pendientes'] = paginator_tickets.get_page(page_number)
        
        context['ultimos_movimientos'] = MovimientoInventario.objects.all().order_by('-fecha_hora')[:5]
        context['cotizaciones_pendientes'] = SolicitudCompra.objects.filter(estado='COTIZADO').order_by('fecha_creacion')
        context['alertas_oc'] = OrdenCompra.objects.filter(estado='RECIBIDA_PARCIAL')
        
    elif es_bodeguero(usuario):
        context['rol'] = 'Bodeguero'
        bodega_asignada = getattr(usuario.perfil, 'bodega_asignada', None) if hasattr(usuario, 'perfil') else None
        bodega_q = request.GET.get('q', '').strip()

        if bodega_asignada:
            qs_tickets = Requerimiento.objects.filter(
                detalles__bodega_destino=bodega_asignada
            ).distinct()

            if estado_filtro == 'PARCIAL':
                qs_tickets = qs_tickets.filter(estado='PARCIALMENTE_DESPACHADO')
            elif estado_filtro == 'COMPLETADO':
                qs_tickets = qs_tickets.filter(estado='DESPACHADO')
            elif estado_filtro == 'CERRADO_INCOMPLETO':
                qs_tickets = qs_tickets.filter(estado='CERRADO_INCOMPLETO')
            elif estado_filtro == 'TODOS':
                pass
            else:
                # Por defecto: solo lo que requiere acción de bodega ahora mismo
                qs_tickets = qs_tickets.filter(
                    detalles__estado_item__in=['APROBADO_BODEGA', 'EN_COMPRAS'],
                    detalles__bodega_destino=bodega_asignada
                ).distinct()

            if bodega_q:
                qs_tickets = qs_tickets.filter(
                    Q(folio__icontains=bodega_q) |
                    Q(solicitante__username__icontains=bodega_q) |
                    Q(solicitante__first_name__icontains=bodega_q) |
                    Q(solicitante__last_name__icontains=bodega_q) |
                    Q(detalles__material__nombre__icontains=bodega_q) |
                    Q(detalles__material__sku__icontains=bodega_q)
                ).distinct()

            qs_tickets = qs_tickets.order_by('fecha_solicitud')
            paginator_tickets = Paginator(qs_tickets, 10)
            context['tickets_por_despachar'] = paginator_tickets.get_page(page_number)
            context['bodega_q'] = bodega_q
        else:
            # Paginador vacío para que no explote el HTML si no tiene bodega
            context['tickets_por_despachar'] = Paginator(Requerimiento.objects.none(), 10).get_page(1)
            
        context['mis_compras_pendientes'] = OrdenCompra.objects.filter(estado__in=['EMITIDA', 'RECIBIDA_PARCIAL'])
        context['alertas_stock'] = Material.objects.filter(stock_actual__lte=F('stock_minimo'))

    elif es_comprador(usuario):
        context['rol'] = 'Compras'
        
        qs_solicitudes = SolicitudCompra.objects.filter(
            estado__in=['ENVIADO_A_COMPRAS', 'REVISADO_ADMIN']
        ).order_by('-fecha_creacion')
        
        # Filtro cruzado: El HTML manda 'NUEVO', pero en BD se llama 'ENVIADO_A_COMPRAS'
        if estado_filtro:
            if estado_filtro == 'NUEVO':
                qs_solicitudes = qs_solicitudes.filter(estado='ENVIADO_A_COMPRAS')
            else:
                qs_solicitudes = qs_solicitudes.filter(estado=estado_filtro)
                
        paginator_solicitudes = Paginator(qs_solicitudes, 10)
        context['solicitudes_compras'] = paginator_solicitudes.get_page(page_number)
        
        context['alertas_oc'] = OrdenCompra.objects.filter(estado='RECIBIDA_PARCIAL')

    else:
        # SOLICITANTES
        context['rol'] = 'Solicitante'
        qs_requerimientos = Requerimiento.objects.filter(solicitante=usuario).order_by('-fecha_solicitud')
        
        if estado_filtro:
            qs_requerimientos = qs_requerimientos.filter(estado=estado_filtro)
            
        paginator_req = Paginator(qs_requerimientos, 10)
        context['mis_requerimientos'] = paginator_req.get_page(page_number)

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
@user_passes_test(es_solicitante, login_url='dashboard_erp')
def finalizar_requerimiento_solicitante(request, req_id):
    """
    Botón "Finalizar y Enviar Requerimiento" del solicitante. El ticket ya
    queda PENDIENTE (visible para Admin) desde que se crea; esta acción solo
    confirma que terminó de añadir materiales y lo regresa a su panel.
    """
    requerimiento = get_object_or_404(Requerimiento, id=req_id, solicitante=request.user)
    if not requerimiento.detalles.exists():
        messages.error(request, f"El ticket {requerimiento.folio} no tiene materiales agregados todavía.")
        return redirect('añadir_materiales', req_id=requerimiento.id)

    messages.success(request, f"Ticket {requerimiento.folio} enviado a gerencia para su revisión.")
    return redirect('dashboard_erp')

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
                    defaults={
                        'cantidad_requerida': detalle.cantidad_solicitada,
                        'bodega_destino': detalle.bodega_destino,
                    }
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

    if es_super:
        items_a_despachar = ticket.detalles.filter(estado_item='APROBADO_BODEGA')
        items_pendientes = ticket.detalles.filter(estado_item='EN_COMPRAS')
    else:
        if not bodega_del_usuario:
            messages.error(request, "No tienes bodega asignada para operar.")
            return redirect('dashboard_erp')
        items_a_despachar = ticket.detalles.filter(estado_item='APROBADO_BODEGA', bodega_destino=bodega_del_usuario)
        items_pendientes = ticket.detalles.filter(estado_item='EN_COMPRAS', bodega_destino=bodega_del_usuario)

    # Si NO hay ítems listos para despachar, Y TAMPOCO hay ítems esperando a compras, ahí recién lo bloqueamos
    if not items_a_despachar.exists() and not items_pendientes.exists():
        messages.warning(request, "El ticket ya no tiene materiales pendientes en tu bodega.")
        return redirect('dashboard_erp')

    if request.method == 'POST':
        algo_despachado = False
        for item in items_a_despachar:
            cant_solicitada = Decimal(str(item.cantidad_solicitada))
            cant_despachada = Decimal(str(item.cantidad_despachada))
            pendiente = cant_solicitada - cant_despachada
            if pendiente <= 0:
                continue

            # Cantidad indicada por el bodeguero para ESTA entrega (permite parcialidad).
            # Si no se envía el campo (compatibilidad hacia atrás), se asume el pendiente total.
            campo = f'cantidad_{item.id}'
            raw_valor = request.POST.get(campo, None)
            if raw_valor is None or raw_valor.strip() == '':
                continue  # el bodeguero no tocó este ítem en esta entrega

            try:
                cantidad_a_entregar = Decimal(raw_valor.replace(',', '.'))
            except Exception:
                messages.error(request, f"Cantidad inválida para {item.material.nombre}.")
                return redirect('despachar_requerimiento', req_id=ticket.id)

            if cantidad_a_entregar <= 0:
                continue

            if cantidad_a_entregar > pendiente:
                messages.error(
                    request,
                    f"No puedes entregar {cantidad_a_entregar} de {item.material.nombre}: "
                    f"solo quedan {pendiente} pendientes de este ítem."
                )
                return redirect('despachar_requerimiento', req_id=ticket.id)

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
                + (" (entrega parcial)" if cantidad_a_entregar < pendiente else "")
            )

            item.cantidad_despachada = cant_despachada + cantidad_a_entregar
            item.estado_item = 'DESPACHADO' if item.cantidad_despachada >= cant_solicitada else 'APROBADO_BODEGA'
            item.save()
            algo_despachado = True

        if not algo_despachado:
            messages.warning(request, "No se registró ninguna entrega: indica una cantidad mayor a cero en al menos un ítem.")
            return redirect('despachar_requerimiento', req_id=ticket.id)

        ticket.actualizar_estado_general()
        messages.success(request, f"Despacho registrado. Los materiales salieron estrictamente de sus bodegas destino.")
        return redirect('dashboard_erp')

    return render(request, 'web/erp/confirmar_despacho.html', {
        'ticket': ticket,
        'items': items_a_despachar,
        'items_pendientes': items_pendientes,
    })


@login_required(login_url='login')
@user_passes_test(lambda u: es_bodeguero(u) or es_admin(u), login_url='dashboard_erp')
def cerrar_requerimiento_incompleto(request, req_id):
    """
    Permite a bodega cerrar definitivamente un requerimiento aunque queden
    cantidades sin entregar. Exige doble confirmación (checkbox + confirm JS)
    y un justificativo obligatorio que queda registrado en auditoría.
    """
    ticket = get_object_or_404(Requerimiento, id=req_id)

    if not ticket.puede_cerrarse_incompleto:
        messages.warning(request, "Este requerimiento ya no tiene cantidades pendientes por cerrar.")
        return redirect('dashboard_erp')

    if request.method == 'POST':
        justificativo = request.POST.get('justificativo', '').strip()
        confirmo = request.POST.get('confirmo_cierre') == 'on'

        if not confirmo:
            messages.error(request, "Debes confirmar explícitamente que entiendes que quedarán materiales pendientes.")
            return redirect('cerrar_requerimiento_incompleto', req_id=ticket.id)

        if len(justificativo) < 10:
            messages.error(request, "El justificativo es obligatorio y debe ser suficientemente descriptivo (mínimo 10 caracteres).")
            return redirect('cerrar_requerimiento_incompleto', req_id=ticket.id)

        try:
            ticket.cerrar_incompleto(usuario=request.user, justificativo=justificativo)
        except ValueError as e:
            messages.error(request, str(e))
            return redirect('dashboard_erp')

        messages.success(request, f"Requerimiento {ticket.folio} cerrado como incompleto. Queda registrado en auditoría.")
        return redirect('dashboard_erp')

    detalles_pendientes = ticket.detalles.exclude(estado_item__in=['DESPACHADO', 'RECHAZADO'])

    return render(request, 'web/erp/cerrar_incompleto.html', {
        'ticket': ticket,
        'detalles_pendientes': detalles_pendientes,
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
                
                # Crear el nuevo clon preservando la solicitud y la bodega de destino original
                CotizacionItem.objects.create(
                    solicitud=item.solicitud, material=item.material,
                    cantidad_requerida=cantidad_nueva, estado_aprobacion=item.estado_aprobacion,
                    bodega_destino=item.bodega_destino
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
    total_estimado_solicitud = sum((i.total_estimado for i in items), Decimal('0.00'))
    return render(request, 'web/erp/revisar_cotizacion.html', {
        'solicitud': solicitud,
        'items': items,
        'materiales_catalogo': materiales_catalogo,
        'total_estimado_solicitud': total_estimado_solicitud,
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
                
                # Crear los detalles de la O.C. (conservando el vínculo a la cotización y su bodega destino)
                for item in items_prov:
                    DetalleOrdenCompra.objects.create(
                        orden=nueva_oc,
                        material=item.material,
                        cantidad_pedida=item.cantidad_requerida,
                        bodega_destino=item.bodega_destino,
                        cotizacion_item_origen=item,
                    )
                
                # Actualizar el estado del ítem cotizado
                items_prov.update(estado_aprobacion='COMPRADO')
                
        # Cerramos la solicitud por completo
        solicitud.estado = 'PROCESADO'
        solicitud.save()
        
        messages.success(request, "¡Check confirmado! Las Órdenes de Compra definitivas han sido generadas exitosamente.")
        return redirect('dashboard_erp')

    # Si entra por GET, le mostramos la pantalla de resumen antes de confirmar
    items_pantalla = solicitud.items_cotizados.all()
    total_a_pagar = sum((i.total_estimado for i in items_pantalla if i.estado_aprobacion == 'APROBADO'), Decimal('0.00'))
    return render(request, 'web/erp/confirmacion_compras.html', {
        'solicitud': solicitud,
        'items': items_pantalla,
        'total_a_pagar': total_a_pagar,
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

    paginator = Paginator(ordenes, 15)
    page_obj = paginator.get_page(request.GET.get('page'))

    return render(request, 'web/erp/listar_oc.html', {
        'ordenes': page_obj,
        'page_obj': page_obj,
        'estados': estados_permitidos,
        'estado_filtro': estado,
        'rol': rol_actual,
    })

@login_required(login_url='login')
@user_passes_test(lambda u: es_bodeguero(u) or es_admin(u) or es_comprador(u), login_url='dashboard_erp')
def detalle_oc(request, oc_id):
    """
    Vista de solo lectura con la trazabilidad completa de una Orden de Compra:
    de dónde salió cada línea (proyecto/requerimiento/cotización), cuánto cuesta
    en total, y qué se ha recibido en bodega hasta el momento.
    """
    oc = get_object_or_404(OrdenCompra, id=oc_id)
    detalles = oc.detalles.select_related(
        'material', 'bodega_destino', 'cotizacion_item_origen',
        'cotizacion_item_origen__solicitud__requerimiento_origen__proyecto',
    ).all()
    recepciones = MovimientoInventario.objects.filter(
        orden_compra_asociada=oc, tipo='INGRESO'
    ).select_related('material', 'bodega_origen', 'responsable').order_by('-fecha_hora')

    return render(request, 'web/erp/detalle_oc.html', {
        'oc': oc,
        'detalles': detalles,
        'recepciones': recepciones,
        'rol': 'Administrador' if es_admin(request.user) else ('Compras' if es_comprador(request.user) else 'Bodeguero'),
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
    bodega_principal = Bodega.objects.filter(is_principal=True).first()
    es_administrador = request.user.is_superuser or es_admin(request.user)
    bodega_bodeguero = getattr(request.user.perfil, 'bodega_asignada', None) if hasattr(request.user, 'perfil') else None

    # SEGURIDAD: un bodeguero SOLO puede ver/recibir las líneas cuya bodega destino
    # sea la suya. Las líneas sin bodega destino definida (órdenes antiguas o ítems
    # añadidos manualmente) caen por defecto en la Bodega Central/Principal.
    todas_las_lineas = list(oc.detalles.select_related('material', 'bodega_destino').all())
    if es_administrador:
        detalles = todas_las_lineas
    else:
        if not bodega_bodeguero:
            messages.error(request, "No tienes bodega asignada para recibir mercadería.")
            return redirect('listar_ordenes_compra')
        detalles = [
            d for d in todas_las_lineas
            if (d.bodega_destino_id or (bodega_principal.id if bodega_principal else None)) == bodega_bodeguero.id
        ]
        if not detalles:
            messages.warning(request, f"La Orden {oc.folio} no tiene materiales destinados a tu bodega ({bodega_bodeguero.nombre}).")
            return redirect('listar_ordenes_compra')

    if request.method == 'POST':
        # Bodega de respaldo SOLO para líneas sin bodega_destino definida (legado / admin).
        bodega_fallback_id = request.POST.get('bodega_destino')
        bodega_fallback = get_object_or_404(Bodega, id=bodega_fallback_id) if bodega_fallback_id else bodega_principal

        for item in detalles:
            bodega = item.bodega_destino or bodega_fallback or bodega_bodeguero
            if not bodega:
                messages.error(request, f"No se pudo determinar la bodega destino para {item.material.nombre}.")
                return redirect('recibir_orden_compra', oc_id=oc.id)

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

                # BLOQUEO DE CONCURRENCIA PARA RECEPCIÓN SEGURA
                material = Material.objects.select_for_update().get(id=item.material.id)

                # PRIMERO ACTUALIZAMOS EL STOCK FÍSICO EN LA BODEGA (solo lo realmente recibido)
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

        # Determinar el estado general de la Orden de Compra en base a TODAS sus líneas
        # (no solo las de esta bodega): mientras algo siga pendiente en cualquier bodega
        # destino, la O.C. permanece RECIBIDA_PARCIAL y visible para Bodega/Compras.
        oc.recalcular_estado_recepcion()
        if oc.estado == 'RECIBIDA_PARCIAL':
            messages.warning(request, "Entrega parcial registrada en bodega. Queda saldo pendiente con el proveedor.")
        else:
            messages.success(request, f"Orden {oc.folio} recibida al 100%. El stock fue actualizado en bodega.")

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
                req_item.estado_item = 'APROBADO_BODEGA'
                req_item.motivo_rechazo = "✅ Material recibido del proveedor. Liberado para despacho a obra."
                req_item.save()
                req_item.requerimiento.actualizar_estado_general()
                
            elif stock_libre > 0: # <-- NUEVA MAGIA: Si llegó una parte de la compra
                cant_faltante = req_item.cantidad_solicitada - stock_libre
                
                # Despertamos la cantidad que sí llegó
                req_item.cantidad_solicitada = stock_libre
                req_item.estado_item = 'APROBADO_BODEGA'
                req_item.motivo_rechazo = "✅ Recepción parcial del proveedor. Liberado para despacho."
                req_item.save()

                # El faltante sigue "dormido" esperando que llegue el resto
                DetalleRequerimiento.objects.create(
                    requerimiento=req_item.requerimiento,
                    material=req_item.material,
                    cantidad_solicitada=cant_faltante,
                    bodega_destino=req_item.bodega_destino,
                    estado_item='EN_COMPRAS',
                    motivo_rechazo="Faltante sigue pendiente de entrega del proveedor."
                )
                req_item.requerimiento.actualizar_estado_general()
        # ========================================================================

        return redirect('listar_ordenes_compra')

    return render(request, 'web/erp/recibir_stock_form.html', {
        'oc': oc,
        'detalles': detalles,
        'bodegas': Bodega.objects.all(),
        'bodega_bodeguero': bodega_bodeguero,
        'es_administrador': es_administrador,
        'hay_lineas_ocultas': not es_administrador and len(detalles) < len(todas_las_lineas),
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
    """
    NOTA: la creación NO usa ProyectoForm directamente sobre el POST completo.
    ProyectoForm incluye 'is_active' (y 'descripcion'), pero el modal "Nuevo
    Proyecto" solo pide nombre y centro de costos; al no venir 'is_active' en
    el POST, un ModelForm lo interpreta como False y el proyecto nacía
    archivado (sin su bodega de obra automática). Se crea directo con el
    default del modelo (is_active=True) y solo se pasan los 2 campos reales.
    """
    proyectos = Proyecto.objects.all().order_by('-fecha_creacion')
    if request.method == 'POST':
        nombre = request.POST.get('nombre', '').strip()
        centro_costos = request.POST.get('centro_costos', '').strip()
        if nombre:
            Proyecto.objects.create(nombre=nombre, centro_costos=centro_costos)
            messages.success(request, "¡Nuevo proyecto creado con éxito!")
            return redirect('gestionar_proyectos')
        else:
            messages.error(request, "El nombre del proyecto es obligatorio.")

    paginator = Paginator(proyectos, 15)
    page_obj = paginator.get_page(request.GET.get('page'))

    return render(request, 'web/erp/gestionar_proyectos.html', {'proyectos': page_obj, 'page_obj': page_obj, 'rol': 'Administrador'})

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
    """
    Edita solo nombre y centro de costos (los únicos campos que expone el modal).
    NO usa ProyectoForm aquí a propósito: ese form también incluye 'is_active' y
    'descripcion', y como el modal no los envía, un ModelForm los pondría en
    blanco/False y archivaría el proyecto en cada edición de nombre.
    """
    proyecto = get_object_or_404(Proyecto, id=proyecto_id)
    if request.method == 'POST':
        nombre = request.POST.get('nombre', '').strip()
        centro_costos = request.POST.get('centro_costos', '').strip()
        if nombre and centro_costos:
            proyecto.nombre = nombre
            proyecto.centro_costos = centro_costos
            proyecto.save()
            messages.success(request, f"Proyecto '{proyecto.nombre}' actualizado.")
        else:
            messages.error(request, "El nombre y el código de centro de costos son obligatorios.")
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
@user_passes_test(lambda u: es_admin(u) or es_comprador(u), login_url='dashboard_erp')
def historial_movimientos(request):
    """
    Bitácora de auditoría. Para Compras es también la forma de consultar
    dónde/cuándo/a qué proveedor y para qué proyecto se compró cada material
    (filtrando por tipo=INGRESO), sin duplicar ninguna vista nueva.
    """
    movimientos_list = MovimientoInventario.objects.select_related(
        'material', 'bodega_origen', 'bodega_destino', 'responsable',
        'requerimiento_asociado__proyecto', 'orden_compra_asociada',
        'entrega_directa__trabajador', 'prestamo_origen__trabajador',
        'devolucion_prestamo__prestamo__trabajador',
    ).order_by('-fecha_hora')

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
        # Cubre tanto despachos (SALIDA, vía requerimiento) como compras (INGRESO, vía la O.C./cotización)
        movimientos_list = movimientos_list.filter(
            Q(requerimiento_asociado__proyecto_id=proyecto_id) |
            Q(
                tipo='INGRESO',
                orden_compra_asociada__detalles__material=F('material'),
                orden_compra_asociada__detalles__cotizacion_item_origen__solicitud__requerimiento_origen__proyecto_id=proyecto_id,
            )
        ).distinct()

    material_q = request.GET.get('material_q', '').strip()
    if material_q:
        movimientos_list = movimientos_list.filter(
            Q(material__nombre__icontains=material_q) | Q(material__sku__icontains=material_q)
        )

    proveedor_q = request.GET.get('proveedor_q', '').strip()
    if proveedor_q:
        movimientos_list = movimientos_list.filter(orden_compra_asociada__proveedor__icontains=proveedor_q)

    proyectos_activos = Proyecto.objects.filter(is_active=True).order_by('nombre')
    proyectos_inactivos = Proyecto.objects.filter(is_active=False).order_by('nombre')

    paginator = Paginator(movimientos_list, 30)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    cierres_incompletos = None
    if es_admin(request.user):
        cierres_qs = CierreIncompletoRequerimiento.objects.select_related(
            'requerimiento', 'requerimiento__proyecto', 'usuario'
        ).order_by('-fecha_hora')
        cierres_paginator = Paginator(cierres_qs, 10)
        cierres_incompletos = cierres_paginator.get_page(request.GET.get('cierre_page'))

    return render(request, 'web/erp/auditoria.html', {
        'page_obj': page_obj, 'tipo_filtro': tipo_filtro, 'mes_filtro': mes_filtro,
        'proyecto_id': proyecto_id, 'material_q': material_q, 'proveedor_q': proveedor_q,
        'proyectos_activos': proyectos_activos,
        'proyectos_inactivos': proyectos_inactivos,
        'cierres_incompletos': cierres_incompletos,
        'rol': 'Administrador' if es_admin(request.user) else 'Compras',
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
    if not es_bodeguero(request.user) and not es_admin(request.user) and not es_comprador(request.user):
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
@user_passes_test(lambda u: es_admin(u) or es_comprador(u), login_url='dashboard_erp')
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

    paginator = Paginator(empleados, 15)
    page_obj = paginator.get_page(request.GET.get('page'))

    # 1. Obtenemos TODOS los registros de bloqueos (con detalles como IP, fallos, fecha)
    intentos_bloqueo = AccessAttempt.objects.all()

    # 2. Creamos un diccionario rápido para cruzar datos { 'nombre_usuario': <Objeto AccessAttempt> }
    dict_bloqueos = {intento.username: intento for intento in intentos_bloqueo}

    # 3. Inyectamos la información detallada en los usuarios de la página actual
    for emp in page_obj:
        if emp.username in dict_bloqueos:
            emp.esta_bloqueado = True
            emp.datos_bloqueo = dict_bloqueos[emp.username] # Contiene IP, failures_since_start, attempt_time
        else:
            emp.esta_bloqueado = False
            emp.datos_bloqueo = None

    if request.method == 'POST':
        # LÓGICA PARA CREAR UN NUEVO EMPLEADO (editar rol/bodega de uno existente se hace en editar_empleado)
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
        'empleados': page_obj,
        'page_obj': page_obj,
        'grupos': grupos,
        'bodegas': bodegas,
        'form': form
    })

@login_required(login_url='login')
@user_passes_test(es_admin, login_url='dashboard_erp')
def editar_empleado(request, empleado_id):
    """
    Permite al Admin corregir, en un solo paso, los datos, el rol/grupo Y la
    bodega asignada de un empleado ya existente (incluye convertir a alguien
    en Bodeguero y asignarle bodega en la misma acción).
    """
    empleado = get_object_or_404(User, id=empleado_id)
    if request.method == 'POST':
        first_name = request.POST.get('first_name', '').strip()
        last_name = request.POST.get('last_name', '').strip()
        email = request.POST.get('email', '').strip()
        grupo_id = request.POST.get('grupo_id')
        bodega_id = request.POST.get('bodega_id')

        if not first_name or not last_name:
            messages.error(request, "El nombre y apellido son obligatorios.")
            return redirect('gestionar_empleados')

        empleado.first_name = first_name
        empleado.last_name = last_name
        empleado.email = email
        empleado.save()

        # El superusuario mantiene su nivel de acceso total; su rol no se toca desde aquí.
        if not empleado.is_superuser:
            empleado.groups.clear()
            if grupo_id:
                grupo = get_object_or_404(Group, id=grupo_id)
                empleado.groups.add(grupo)

            perfil, _ = PerfilEmpleado.objects.get_or_create(usuario=empleado)
            perfil.bodega_asignada = get_object_or_404(Bodega, id=bodega_id) if bodega_id else None
            perfil.save()

        messages.success(request, f"✅ Datos, rol y bodega de '{empleado.username}' actualizados correctamente.")
    return redirect('gestionar_empleados')

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
    paginator = Paginator(intentos_fallidos, 20)
    page_obj = paginator.get_page(request.GET.get('page'))
    return render(request, 'web/erp/gestionar_bloqueos.html', {'intentos': page_obj, 'page_obj': page_obj})

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
def cambiar_clave_admin(request, empleado_id):
    """
    Permite al Administrador forzar el cambio de contraseña de cualquier usuario
    desde el panel de gestión de empleados.
    """
    if request.method == 'POST':
        empleado = get_object_or_404(User, id=empleado_id)
        nueva_clave = request.POST.get('new_password')
        confirmar_clave = request.POST.get('confirm_password')
        
        # Validaciones de seguridad backend
        if not nueva_clave or nueva_clave != confirmar_clave:
            messages.error(request, "Error de seguridad: Las contraseñas no coinciden o están vacías.")
        elif len(nueva_clave) < 8:
            messages.error(request, "Error de seguridad: La contraseña debe tener al menos 8 caracteres.")
        else:
            # Encriptar y guardar la nueva contraseña
            empleado.set_password(nueva_clave)
            empleado.save()
            messages.success(request, f"¡Éxito! Se ha actualizado la contraseña del usuario '{empleado.username}'.")
            
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
            # Este formulario rápido solo pide nombre/prefijo; CategoriaForm también
            # incluye 'is_active' y, al no venir en el POST, un ModelForm lo dejaría
            # en False (categoría archivada desde su creación). Se fuerza activa.
            categoria = form_c.save(commit=False)
            categoria.is_active = True
            categoria.save()
            messages.success(request, "Categoría creada exitosamente.")
            return redirect('configuracion_erp')

    # Formulario para la configuración global de rangos de horas extra
    config_horas_extra = ConfiguracionHorasExtra.obtener()
    if 'form_horas_extra' in request.POST:
        form_he = ConfiguracionHorasExtraForm(request.POST, instance=config_horas_extra)
        if form_he.is_valid():
            config = form_he.save(commit=False)
            config.actualizado_por = request.user
            config.save()
            messages.success(request, "Configuración de horas extra actualizada.")
            return redirect('configuracion_erp')

    return render(request, 'web/erp/configuracion.html', {
        'form_bodega': BodegaForm(),
        'form_categoria': CategoriaForm(),
        'form_horas_extra': ConfiguracionHorasExtraForm(instance=config_horas_extra),
        'bodegas': Bodega.objects.all(),
        'categorias': Categoria.objects.all()
    })
@login_required(login_url='login')
@user_passes_test(es_admin, login_url='dashboard_erp')
def editar_categoria(request, cat_id):
    categoria = get_object_or_404(Categoria, id=cat_id)
    if request.method == 'POST':
        nombre = request.POST.get('nombre')
        prefijo = request.POST.get('prefijo')
        if nombre and prefijo:
            categoria.nombre = nombre
            categoria.prefijo = prefijo
            categoria.save()
            messages.success(request, f"Categoría '{nombre}' actualizada correctamente.")
        else:
            messages.error(request, "El nombre y el prefijo son obligatorios.")
    return redirect('configuracion_erp')

@login_required(login_url='login')
@user_passes_test(es_admin, login_url='dashboard_erp')
def editar_bodega(request, bodega_id):
    bodega = get_object_or_404(Bodega, id=bodega_id)
    if request.method == 'POST':
        nombre = request.POST.get('nombre')
        ubicacion = request.POST.get('ubicacion')
        es_principal = request.POST.get('is_principal') == 'on'
        if nombre:
            bodega.nombre = nombre
            bodega.ubicacion = ubicacion
            bodega.is_principal = es_principal
            bodega.save()  # el save() del modelo garantiza que solo haya UNA bodega matriz
            messages.success(request, f"La información de la bodega '{nombre}' fue actualizada. (El historial se mantiene intacto).")
        else:
            messages.error(request, "El nombre de la bodega no puede estar vacío.")
    return redirect('configuracion_erp')

@login_required(login_url='login')
@user_passes_test(es_admin, login_url='dashboard_erp')
def eliminar_bodega(request, bodega_id):
    """
    Solo permite eliminar bodegas que JAMÁS se usaron: sin stock, sin movimientos,
    sin compras, sin requerimientos y sin proyectos/empleados vinculados.
    Si alguna vez se usó, se bloquea y se explica el motivo exacto.
    """
    bodega = get_object_or_404(Bodega, id=bodega_id)
    motivos = bodega.obtener_motivos_bloqueo_eliminacion()
    if motivos:
        messages.error(
            request,
            f"No se puede eliminar la bodega '{bodega.nombre}': " + " · ".join(motivos)
        )
    else:
        nombre = bodega.nombre
        bodega.delete()
        messages.success(request, f"Bodega '{nombre}' eliminada definitivamente (nunca tuvo uso registrado).")
    return redirect('configuracion_erp')

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
    """Muestra el rastreo completo de todos los tickets en el sistema, con filtros y paginación."""
    requerimientos = Requerimiento.objects.all().order_by('-fecha_solicitud')
    
    # 1. Capturar parámetros de búsqueda
    estado_filtro = request.GET.get('estado')
    fecha_inicio = request.GET.get('fecha_inicio')
    fecha_fin = request.GET.get('fecha_fin')
    
    # 2. Aplicar Filtros
    if estado_filtro:
        requerimientos = requerimientos.filter(estado=estado_filtro)
        
    if fecha_inicio:
        requerimientos = requerimientos.filter(fecha_solicitud__gte=fecha_inicio)
        
    if fecha_fin:
        # Cubrir todo el día hasta las 23:59
        requerimientos = requerimientos.filter(fecha_solicitud__lte=f"{fecha_fin} 23:59:59")
        
    # 3. Paginación (10 tickets por página para no sobrecargar el celular)
    paginator = Paginator(requerimientos, 10)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    return render(request, 'web/erp/trazabilidad.html', {
        'page_obj': page_obj,
        'estado_actual': estado_filtro,
        'fecha_inicio': fecha_inicio,
        'fecha_fin': fecha_fin,
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
    """Muestra todas las solicitudes de compra históricas filtradas y paginadas"""
    solicitudes = SolicitudCompra.objects.all().order_by('-fecha_creacion')
    
    # 1. Capturar parámetros de búsqueda
    estado_filtro = request.GET.get('estado')
    fecha_inicio = request.GET.get('fecha_inicio')
    fecha_fin = request.GET.get('fecha_fin')
    
    # 2. Aplicar Filtros
    if estado_filtro:
        solicitudes = solicitudes.filter(estado=estado_filtro)
        
    if fecha_inicio:
        solicitudes = solicitudes.filter(fecha_creacion__gte=fecha_inicio)
        
    if fecha_fin:
        # Añadimos 23:59:59 al día final para que incluya todo lo de ese día
        solicitudes = solicitudes.filter(fecha_creacion__lte=f"{fecha_fin} 23:59:59")
        
    # 3. Paginación (Mostramos 15 registros por página)
    paginator = Paginator(solicitudes, 15)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    return render(request, 'web/erp/historial_solicitudes.html', {
        'page_obj': page_obj,
        'estado_actual': estado_filtro,
        'fecha_inicio': fecha_inicio,
        'fecha_fin': fecha_fin,
        'rol': 'Administrador' if es_admin(request.user) else 'Compras'
    })

@login_required(login_url='login')
@user_passes_test(lambda u: es_comprador(u) or es_admin(u), login_url='dashboard_erp')
def detalle_solicitud_procesada(request, solicitud_id):
    """Vista de Solo Lectura para ver qué aprobó o rechazó el Administrador"""
    solicitud = get_object_or_404(SolicitudCompra, id=solicitud_id)
    items = solicitud.items_cotizados.select_related('bodega_destino').prefetch_related('detalles_orden__orden').all()
    total_general_solicitud = sum((i.total_estimado for i in items), Decimal('0.00'))
    return render(request, 'web/erp/detalle_solicitud_procesada.html', {
        'solicitud': solicitud,
        'items': items,
        'total_general_solicitud': total_general_solicitud,
    })

# AGREGAR nueva vista
@login_required(login_url='login')
@user_passes_test(es_bodeguero, login_url='dashboard_erp')
@transaction.atomic
def entrega_directa_bodeguero(request):
    bodega_asignada = getattr(request.user.perfil, 'bodega_asignada', None) if hasattr(request.user, 'perfil') else None
    if not bodega_asignada:
        messages.error(request, "No tienes una bodega asignada para realizar despachos.")
        return redirect('dashboard_erp')

    if request.method == 'POST':
        material_id = request.POST.get('material_id')
        trabajador_id = request.POST.get('trabajador_id')
        proyecto_id = request.POST.get('proyecto_id')  # Destino administrativo (opcional)
        observaciones = (request.POST.get('observaciones') or '').strip()

        try:
            cantidad = Decimal(request.POST.get('cantidad', '0').replace(',', '.'))
        except Exception:
            messages.error(request, "Cantidad inválida.")
            return redirect('entrega_directa_bodeguero')

        if not trabajador_id:
            messages.error(request, "Debes indicar a qué trabajador se le entrega el material.")
            return redirect('entrega_directa_bodeguero')

        trabajador = get_object_or_404(Trabajador, id=trabajador_id, estado='ACTIVO')
        material = get_object_or_404(Material, id=material_id)

        if cantidad <= 0:
            messages.error(request, "La cantidad debe ser mayor a cero.")
            return redirect('entrega_directa_bodeguero')

        if not observaciones:
            messages.error(request, "El justificativo de la entrega directa es obligatorio.")
            return redirect('entrega_directa_bodeguero')

        stock_b = StockBodega.objects.select_for_update().filter(bodega=bodega_asignada, material=material).first()
        cant_disponible = stock_b.cantidad if stock_b else Decimal('0.00')

        if cant_disponible < cantidad:
            messages.error(request, f"Stock insuficiente de {material.nombre} en tu bodega (disponible: {cant_disponible}).")
            return redirect('entrega_directa_bodeguero')

        stock_b.cantidad = cant_disponible - cantidad
        stock_b.save()
        material.save()

        proyecto = Proyecto.objects.filter(id=proyecto_id, is_active=True).first() if proyecto_id else None

        movimiento = MovimientoInventario.objects.create(
            material=material, tipo='SALIDA', cantidad=cantidad, bodega_origen=bodega_asignada,
            responsable=request.user,
            observaciones=f"[ENTREGA DIRECTA] Para {trabajador.nombre_completo} | {observaciones}"
        )
        EntregaDirecta.objects.create(
            movimiento=movimiento, trabajador=trabajador, proyecto=proyecto, justificativo=observaciones,
        )

        messages.success(request, f"Entrega directa de {cantidad} {material.nombre} a {trabajador.nombre_completo} registrada en auditoría.")
        return redirect('dashboard_erp')

    materiales = Material.objects.filter(stocks_bodegas__bodega=bodega_asignada, stocks_bodegas__cantidad__gt=0).distinct()
    proyectos = Proyecto.objects.filter(is_active=True)
    trabajadores = Trabajador.objects.filter(estado='ACTIVO').order_by('nombres', 'apellidos')
    return render(request, 'web/erp/entrega_directa.html', {
        'materiales': materiales, 'proyectos': proyectos, 'trabajadores': trabajadores,
    })

# =======================================================
# MÓDULO DE PRÉSTAMOS DE HERRAMIENTAS/MATERIALES/MAQUINARIA
# =======================================================
@login_required(login_url='login')
@user_passes_test(lambda u: es_bodeguero(u) or es_admin(u), login_url='dashboard_erp')
def listar_prestamos(request):
    prestamos = PrestamoHerramienta.objects.select_related(
        'trabajador', 'material', 'bodega_origen', 'entregado_por', 'devolucion__recibido_por'
    ).all()

    estado_filtro = request.GET.get('estado')
    if estado_filtro == 'PRESTADO':
        prestamos = prestamos.filter(estado='PRESTADO')
    elif estado_filtro == 'DEVUELTO':
        prestamos = prestamos.filter(estado='DEVUELTO')

    q = request.GET.get('q', '').strip()
    if q:
        prestamos = prestamos.filter(
            Q(trabajador__nombres__icontains=q) | Q(trabajador__apellidos__icontains=q) |
            Q(material__nombre__icontains=q)
        )

    paginator = Paginator(prestamos, 15)
    page_obj = paginator.get_page(request.GET.get('page'))
    return render(request, 'web/erp/listar_prestamos.html', {
        'page_obj': page_obj, 'estado_filtro': estado_filtro, 'q': q,
        'rol': 'Administrador' if es_admin(request.user) else 'Bodeguero',
    })


@login_required(login_url='login')
@user_passes_test(lambda u: es_bodeguero(u) or es_admin(u), login_url='dashboard_erp')
@transaction.atomic
def crear_prestamo(request):
    bodega_asignada = getattr(request.user.perfil, 'bodega_asignada', None) if hasattr(request.user, 'perfil') else None
    if not bodega_asignada:
        messages.error(request, "No tienes una bodega asignada para registrar préstamos.")
        return redirect('dashboard_erp')

    if request.method == 'POST':
        material_id = request.POST.get('material_id')
        trabajador_id = request.POST.get('trabajador_id')
        observaciones = (request.POST.get('observaciones') or '').strip()

        try:
            cantidad = Decimal((request.POST.get('cantidad') or '1').replace(',', '.'))
        except Exception:
            messages.error(request, "Cantidad inválida.")
            return redirect('crear_prestamo')

        if cantidad <= 0:
            messages.error(request, "La cantidad debe ser mayor a cero.")
            return redirect('crear_prestamo')

        if not trabajador_id:
            messages.error(request, "Debes indicar a qué trabajador se le presta el material.")
            return redirect('crear_prestamo')

        trabajador = get_object_or_404(Trabajador, id=trabajador_id, estado='ACTIVO')
        material = get_object_or_404(Material, id=material_id)

        stock_b = StockBodega.objects.select_for_update().filter(bodega=bodega_asignada, material=material).first()
        cant_disponible = stock_b.cantidad if stock_b else Decimal('0.00')

        if cant_disponible < cantidad:
            messages.error(request, f"Stock insuficiente de {material.nombre} en tu bodega (disponible: {cant_disponible}).")
            return redirect('crear_prestamo')

        stock_b.cantidad = cant_disponible - cantidad
        stock_b.save()
        material.save()

        movimiento = MovimientoInventario.objects.create(
            material=material, tipo='PRESTAMO', cantidad=cantidad, bodega_origen=bodega_asignada,
            responsable=request.user,
            observaciones=f"Préstamo a {trabajador.nombre_completo}" + (f" | {observaciones}" if observaciones else "")
        )
        PrestamoHerramienta.objects.create(
            trabajador=trabajador, material=material, bodega_origen=bodega_asignada, cantidad=cantidad,
            entregado_por=request.user, observaciones=observaciones, movimiento_salida=movimiento,
        )

        messages.success(request, f"Préstamo de {cantidad} {material.nombre} a {trabajador.nombre_completo} registrado.")
        return redirect('listar_prestamos')

    materiales = Material.objects.filter(stocks_bodegas__bodega=bodega_asignada, stocks_bodegas__cantidad__gt=0).distinct()
    trabajadores = Trabajador.objects.filter(estado='ACTIVO').order_by('nombres', 'apellidos')
    return render(request, 'web/erp/crear_prestamo.html', {
        'materiales': materiales, 'trabajadores': trabajadores,
    })


@login_required(login_url='login')
@user_passes_test(lambda u: es_bodeguero(u) or es_admin(u), login_url='dashboard_erp')
def registrar_devolucion_prestamo(request, prestamo_id):
    prestamo = get_object_or_404(PrestamoHerramienta, id=prestamo_id)

    if prestamo.esta_devuelto:
        messages.warning(request, "Este préstamo ya fue devuelto anteriormente.")
        return redirect('listar_prestamos')

    if request.method == 'POST':
        condicion = request.POST.get('condicion')
        observaciones = (request.POST.get('observaciones') or '').strip()

        if condicion not in dict(DevolucionPrestamo.CONDICIONES):
            messages.error(request, "Selecciona una condición de devolución válida.")
            return redirect('registrar_devolucion_prestamo', prestamo_id=prestamo.id)

        try:
            prestamo.registrar_devolucion(usuario=request.user, condicion=condicion, observaciones=observaciones)
        except ValueError as e:
            messages.error(request, str(e))
            return redirect('listar_prestamos')

        messages.success(request, f"Devolución de {prestamo.material.nombre} registrada correctamente.")
        return redirect('listar_prestamos')

    return render(request, 'web/erp/registrar_devolucion.html', {'prestamo': prestamo})


# =======================================================
# MÓDULO ADMINISTRADOR: TRABAJADORES (RRHH)
# =======================================================
@login_required(login_url='login')
@user_passes_test(es_admin, login_url='dashboard_erp')
def listar_trabajadores(request):
    trabajadores = Trabajador.objects.all()

    estado_filtro = request.GET.get('estado', 'ACTIVO')
    if estado_filtro in ('ACTIVO', 'INACTIVO'):
        trabajadores = trabajadores.filter(estado=estado_filtro)

    q = request.GET.get('q', '').strip()
    if q:
        trabajadores = trabajadores.filter(
            Q(nombres__icontains=q) | Q(apellidos__icontains=q) | Q(documento_identidad__icontains=q)
        )

    paginator = Paginator(trabajadores, 15)
    page_obj = paginator.get_page(request.GET.get('page'))

    return render(request, 'web/erp/listar_trabajadores.html', {
        'page_obj': page_obj, 'estado_filtro': estado_filtro, 'q': q,
    })


@login_required(login_url='login')
@user_passes_test(es_admin, login_url='dashboard_erp')
def crear_trabajador(request):
    if request.method == 'POST':
        form = TrabajadorForm(request.POST)
        if form.is_valid():
            trabajador = form.save()
            messages.success(request, f"Trabajador {trabajador.nombre_completo} registrado correctamente.")
            return redirect('listar_trabajadores')
    else:
        form = TrabajadorForm()
    return render(request, 'web/erp/form_trabajador.html', {'form': form, 'modo': 'crear'})


@login_required(login_url='login')
@user_passes_test(es_admin, login_url='dashboard_erp')
def editar_trabajador(request, trabajador_id):
    trabajador = get_object_or_404(Trabajador, id=trabajador_id)
    if request.method == 'POST':
        form = TrabajadorForm(request.POST, instance=trabajador)
        if form.is_valid():
            form.save()
            messages.success(request, "Datos del trabajador actualizados.")
            return redirect('listar_trabajadores')
    else:
        form = TrabajadorForm(instance=trabajador)
    return render(request, 'web/erp/form_trabajador.html', {'form': form, 'modo': 'editar', 'trabajador': trabajador})


@login_required(login_url='login')
@user_passes_test(es_admin, login_url='dashboard_erp')
def desactivar_trabajador(request, trabajador_id):
    trabajador = get_object_or_404(Trabajador, id=trabajador_id)
    if request.method == 'POST':
        motivo = (request.POST.get('motivo') or '').strip()
        if len(motivo) < 5:
            messages.error(request, "Debes indicar un motivo de salida (mínimo 5 caracteres).")
            return redirect('desactivar_trabajador', trabajador_id=trabajador.id)
        try:
            trabajador.desactivar(motivo=motivo)
        except ValueError as e:
            messages.error(request, str(e))
            return redirect('listar_trabajadores')
        messages.success(request, f"{trabajador.nombre_completo} fue marcado como inactivo. Su historial se conserva íntegro.")
        return redirect('listar_trabajadores')
    return render(request, 'web/erp/desactivar_trabajador.html', {'trabajador': trabajador})


@login_required(login_url='login')
@user_passes_test(es_admin, login_url='dashboard_erp')
def reactivar_trabajador(request, trabajador_id):
    trabajador = get_object_or_404(Trabajador, id=trabajador_id)
    if request.method == 'POST':
        try:
            trabajador.reactivar()
        except ValueError as e:
            messages.error(request, str(e))
        else:
            messages.success(request, f"{trabajador.nombre_completo} fue reactivado y puede volver a recibir material.")
    return redirect('listar_trabajadores')


@login_required(login_url='login')
@user_passes_test(es_admin, login_url='dashboard_erp')
def ficha_trabajador(request, trabajador_id):
    """Historial integral del trabajador: salarios, pagos, horas extra, descuentos, préstamos y entregas directas."""
    trabajador = get_object_or_404(Trabajador, id=trabajador_id)

    horario = getattr(trabajador, 'horario', None)
    horas_extras = trabajador.horas_extras.filter(pago__isnull=True).order_by('-fecha')
    horas_extras_historial = trabajador.horas_extras.filter(pago__isnull=False).order_by('-fecha')
    descuentos = trabajador.descuentos.filter(pago__isnull=True).order_by('-fecha')
    descuentos_historial = trabajador.descuentos.filter(pago__isnull=False).order_by('-fecha')

    def paginar(queryset, param, por_pagina=5):
        return Paginator(queryset, por_pagina).get_page(request.GET.get(param))

    return render(request, 'web/erp/ficha_trabajador.html', {
        'trabajador': trabajador,
        'salarios': paginar(trabajador.salarios.all(), 'page_salarios'),
        'pagos': paginar(trabajador.pagos.all(), 'page_pagos'),
        'horas_extras': paginar(horas_extras, 'page_horas'),
        'horas_extras_historial': paginar(horas_extras_historial, 'page_horas_hist'),
        'descuentos': paginar(descuentos, 'page_descuentos'),
        'descuentos_historial': paginar(descuentos_historial, 'page_descuentos_hist'),
        'prestamos': paginar(trabajador.prestamos.select_related('material', 'devolucion').all(), 'page_prestamos'),
        'entregas_directas': paginar(trabajador.entregas_directas.select_related('movimiento__material').order_by('-movimiento__fecha_hora'), 'page_entregas'),
        'periodos_mensuales': paginar(trabajador.periodos_mensuales.all(), 'page_periodos'),
        'horario': horario,
        'hoy': timezone.localdate(),
    })


@login_required(login_url='login')
@user_passes_test(es_admin, login_url='dashboard_erp')
def asignar_salario_trabajador(request, trabajador_id):
    trabajador = get_object_or_404(Trabajador, id=trabajador_id)
    if request.method == 'POST':
        try:
            monto = Decimal((request.POST.get('monto') or '0').replace(',', '.'))
            fecha_inicio = datetime.strptime(request.POST.get('fecha_inicio_vigencia'), '%Y-%m-%d').date()
        except Exception:
            messages.error(request, "Datos inválidos para el salario.")
            return redirect('ficha_trabajador', trabajador_id=trabajador.id)

        try:
            trabajador.asignar_salario(monto=monto, fecha_inicio_vigencia=fecha_inicio, usuario=request.user)
        except ValueError as e:
            messages.error(request, str(e))
        else:
            messages.success(request, "Salario registrado. El historial anterior se conserva sin modificarse.")
    return redirect('ficha_trabajador', trabajador_id=trabajador.id)


@login_required(login_url='login')
@user_passes_test(es_admin, login_url='dashboard_erp')
def registrar_horario_trabajador(request, trabajador_id):
    """
    Horario normal detallado por día de la semana (qué días trabaja y su
    hora desde/hasta). Es la base para calcular automáticamente horas
    normales vs. horas extra al registrar un pago.
    """
    trabajador = get_object_or_404(Trabajador, id=trabajador_id)
    horario = HorarioTrabajador.para_trabajador(trabajador, usuario=request.user)
    queryset = HorarioTrabajadorDia.objects.filter(horario=horario).order_by('dia_semana')

    if request.method == 'POST':
        formset = HorarioDiaFormSet(request.POST, queryset=queryset)
        if formset.is_valid():
            formset.save()
            horario.actualizado_por = request.user
            horario.save(update_fields=['actualizado_por', 'fecha_actualizacion'])
            messages.success(request, "Horario normal actualizado. Se usará para calcular horas extra automáticamente.")
            return redirect('ficha_trabajador', trabajador_id=trabajador.id)
        messages.error(request, "Revisa el horario: hay días marcados como laborables sin hora de inicio/fin válida.")
    else:
        formset = HorarioDiaFormSet(queryset=queryset)

    dias_formularios = list(zip([d for d, _ in HorarioTrabajadorDia.DIAS_SEMANA], formset.forms))

    return render(request, 'web/erp/horario_trabajador.html', {
        'trabajador': trabajador, 'formset': formset, 'dias_formularios': dias_formularios,
    })


@login_required(login_url='login')
@user_passes_test(es_admin, login_url='dashboard_erp')
def eliminar_hora_extra(request, trabajador_id, hora_id):
    trabajador = get_object_or_404(Trabajador, id=trabajador_id)
    hora = get_object_or_404(HoraExtra, id=hora_id, trabajador=trabajador)
    if request.method == 'POST':
        hora.delete()
        messages.success(request, "Hora extra eliminada.")
    return redirect('ficha_trabajador', trabajador_id=trabajador.id)


@login_required(login_url='login')
@user_passes_test(es_admin, login_url='dashboard_erp')
def eliminar_descuento(request, trabajador_id, descuento_id):
    trabajador = get_object_or_404(Trabajador, id=trabajador_id)
    descuento = get_object_or_404(Descuento, id=descuento_id, trabajador=trabajador)
    if request.method == 'POST':
        tipo_display = descuento.get_tipo_display()
        descuento.delete()
        messages.success(request, f"{tipo_display} eliminado.")
    return redirect('ficha_trabajador', trabajador_id=trabajador.id)


@login_required(login_url='login')
@user_passes_test(es_admin, login_url='dashboard_erp')
def registrar_hora_extra(request, trabajador_id):
    trabajador = get_object_or_404(Trabajador, id=trabajador_id)
    if request.method == 'POST':
        tipo = request.POST.get('tipo')
        observaciones = (request.POST.get('observaciones') or '').strip()
        try:
            fecha_raw = (request.POST.get('fecha') or '').strip()
            fecha = datetime.strptime(fecha_raw, '%Y-%m-%d').date() if fecha_raw else timezone.localdate()
            cantidad_horas = Decimal((request.POST.get('cantidad_horas') or '0').replace(',', '.'))
        except Exception:
            messages.error(request, "Datos inválidos para la hora extra.")
            return redirect('ficha_trabajador', trabajador_id=trabajador.id)

        if tipo not in dict(HoraExtra.TIPOS):
            messages.error(request, "Selecciona un tipo de hora extra válido.")
            return redirect('ficha_trabajador', trabajador_id=trabajador.id)

        hora_extra = HoraExtra(
            trabajador=trabajador, fecha=fecha, tipo=tipo, cantidad_horas=cantidad_horas,
            observaciones=observaciones, registrado_por=request.user,
        )
        try:
            hora_extra.full_clean(exclude=['valor_calculado', 'pago'])
        except ValidationError as e:
            messages.error(request, " ".join(e.messages))
            return redirect('ficha_trabajador', trabajador_id=trabajador.id)

        try:
            hora_extra.valor_calculado = servicios_nomina.calcular_valor_hora_extra(trabajador, tipo, cantidad_horas)
        except ValueError as e:
            messages.error(request, str(e))
            return redirect('ficha_trabajador', trabajador_id=trabajador.id)

        hora_extra.save()
        messages.success(request, f"Hora extra registrada: ${hora_extra.valor_calculado} ({trabajador.get_periodicidad_pago_display()}, recargo {'50%' if tipo == 'ORDINARIA' else '100%'}).")
    return redirect('ficha_trabajador', trabajador_id=trabajador.id)


@login_required(login_url='login')
@user_passes_test(es_admin, login_url='dashboard_erp')
def registrar_descuento(request, trabajador_id):
    trabajador = get_object_or_404(Trabajador, id=trabajador_id)
    if request.method == 'POST':
        tipo = request.POST.get('tipo', 'DESCUENTO')
        motivo = (request.POST.get('motivo') or '').strip()
        observaciones = (request.POST.get('observaciones') or '').strip()
        try:
            fecha = datetime.strptime(request.POST.get('fecha'), '%Y-%m-%d').date()
            monto = Decimal((request.POST.get('monto') or '0').replace(',', '.'))
        except Exception:
            messages.error(request, "Datos inválidos para el descuento/anticipo.")
            return redirect('ficha_trabajador', trabajador_id=trabajador.id)

        if tipo not in dict(Descuento.TIPOS):
            messages.error(request, "Selecciona un tipo válido (Descuento o Anticipo).")
            return redirect('ficha_trabajador', trabajador_id=trabajador.id)

        if not motivo:
            messages.error(request, "El motivo es obligatorio.")
            return redirect('ficha_trabajador', trabajador_id=trabajador.id)

        descuento = Descuento(
            trabajador=trabajador, tipo=tipo, motivo=motivo, monto=monto, fecha=fecha,
            observaciones=observaciones, registrado_por=request.user,
        )
        try:
            descuento.full_clean(exclude=['pago'])
        except ValidationError as e:
            messages.error(request, " ".join(e.messages))
            return redirect('ficha_trabajador', trabajador_id=trabajador.id)

        descuento.save()
        messages.success(request, f"{descuento.get_tipo_display()} registrado correctamente.")
    return redirect('ficha_trabajador', trabajador_id=trabajador.id)


@login_required(login_url='login')
@user_passes_test(es_admin, login_url='dashboard_erp')
def iniciar_pago(request, trabajador_id):
    """Paso 1: elegir el rango de fechas del periodo a pagar mediante un calendario visual."""
    trabajador = get_object_or_404(Trabajador, id=trabajador_id)
    if not trabajador.salario_actual:
        messages.error(request, "Asigna un salario al trabajador antes de registrar un pago.")
        return redirect('ficha_trabajador', trabajador_id=trabajador.id)

    dias_pagados = sorted(trabajador.dias_pagados())
    pagos_previos = trabajador.pagos.order_by('-periodo_inicio')[:8]

    return render(request, 'web/erp/iniciar_pago.html', {
        'trabajador': trabajador, 'hoy': timezone.localdate(),
        'dias_pagados_json': json.dumps([d.strftime('%Y-%m-%d') for d in dias_pagados]),
        'pagos_previos': pagos_previos,
    })


@login_required(login_url='login')
@user_passes_test(es_admin, login_url='dashboard_erp')
def preparar_pago(request, trabajador_id):
    """
    Paso 2: genera automáticamente todos los días del rango elegido,
    indicando el día de la semana, si es un día normal según el horario
    configurado, y si ya fue pagado (bloqueado) o está pendiente.
    """
    trabajador = get_object_or_404(Trabajador, id=trabajador_id)

    try:
        periodo_inicio = datetime.strptime(request.GET.get('periodo_inicio', ''), '%Y-%m-%d').date()
        periodo_fin = datetime.strptime(request.GET.get('periodo_fin', ''), '%Y-%m-%d').date()
    except Exception:
        messages.error(request, "Selecciona un rango de fechas válido.")
        return redirect('iniciar_pago', trabajador_id=trabajador.id)

    if periodo_fin < periodo_inicio:
        messages.error(request, "La fecha final no puede ser anterior a la inicial.")
        return redirect('iniciar_pago', trabajador_id=trabajador.id)

    if (periodo_fin - periodo_inicio).days > 45:
        messages.error(request, "El rango de un pago no puede superar 45 días.")
        return redirect('iniciar_pago', trabajador_id=trabajador.id)

    if not trabajador.salario_actual:
        messages.error(request, "Asigna un salario al trabajador antes de registrar un pago.")
        return redirect('ficha_trabajador', trabajador_id=trabajador.id)

    pago_id = request.GET.get('pago_id')

    # Autoguardado de sesión: lo último que se calculó/revisó para este trabajador
    # y este mismo periodo, aunque todavía no se haya guardado como borrador.
    # Así "Volver a Editar" nunca borra lo que ya se había corregido.
    sesion_datos = request.session.get(f'pago_form_datos_{trabajador.id}')
    if sesion_datos and sesion_datos.get('periodo_inicio') != periodo_inicio.isoformat():
        sesion_datos = None
    if sesion_datos and sesion_datos.get('periodo_fin') != periodo_fin.isoformat():
        sesion_datos = None

    pid_efectivo = pago_id or (sesion_datos.get('pago_id') if sesion_datos else None)
    pago_borrador = None
    if pid_efectivo:
        pago_borrador = Pago.objects.filter(id=pid_efectivo, trabajador=trabajador, estado='BORRADOR').first()

    if sesion_datos:
        datos_previos = sesion_datos
    elif pago_borrador:
        datos_previos = pago_borrador.datos_formulario or {}
    else:
        datos_previos = {}
    dias_previos = datos_previos.get('dias', {})

    horario = HorarioTrabajador.para_trabajador(trabajador)
    dias_ya_pagados = trabajador.dias_pagados(
        periodo_inicio, periodo_fin, excluir_pago_id=pago_borrador.id if pago_borrador else None
    )

    dias = []
    d = periodo_inicio
    while d <= periodo_fin:
        fecha_str = d.strftime('%Y-%m-%d')
        horario_dia = horario.dia(d.weekday())
        previo = dias_previos.get(fecha_str, {})
        entrada_default = previo.get('entrada') or (horario_dia.hora_inicio.strftime('%H:%M') if horario_dia and horario_dia.hora_inicio else '')
        salida_default = previo.get('salida') or (horario_dia.hora_fin.strftime('%H:%M') if horario_dia and horario_dia.hora_fin else '')
        dias.append({
            'fecha': d,
            'fecha_str': fecha_str,
            'nombre_dia': dict(HorarioTrabajadorDia.DIAS_SEMANA)[d.weekday()],
            'es_normal': bool(horario_dia and horario_dia.trabaja),
            'hora_inicio_normal': horario_dia.hora_inicio if horario_dia else None,
            'hora_fin_normal': horario_dia.hora_fin if horario_dia else None,
            'ya_pagado': d in dias_ya_pagados,
            'previo_incluir': previo.get('incluir') == 'on',
            'entrada_valor': entrada_default,
            'salida_valor': salida_default,
        })
        d += timedelta(days=1)

    filtro_disponible = Q(pago__isnull=True)
    if pago_borrador:
        filtro_disponible |= Q(pago=pago_borrador)
    horas_extras = trabajador.horas_extras.filter(filtro_disponible, generado_automaticamente=False)
    descuentos = trabajador.descuentos.filter(filtro_disponible)
    ids_horas_previas = set(datos_previos.get('horas_extra_ids', []))
    ids_descuentos_previos = set(datos_previos.get('descuento_ids', []))

    return render(request, 'web/erp/preparar_pago.html', {
        'trabajador': trabajador, 'periodo_inicio': periodo_inicio, 'periodo_fin': periodo_fin,
        'dias': dias,
        'horas_extra_disponibles': horas_extras,
        'descuentos_disponibles': descuentos.filter(tipo='DESCUENTO'),
        'anticipos_disponibles': descuentos.filter(tipo='ANTICIPO'),
        'periodos_mensuales': trabajador.periodos_mensuales.all(),
        'hoy': timezone.localdate(),
        'pago_borrador': pago_borrador,
        'datos_previos': datos_previos,
        'ids_horas_previas': ids_horas_previas,
        'ids_descuentos_previos': ids_descuentos_previos,
    })


def _procesar_dias_pago(request, trabajador, periodo_inicio, periodo_fin, pago_id_excluir=None):
    """
    Calcula el desglose de un pago día por día.

    IMPORTANTE sobre `dias_laborados`: el sueldo es periódico (cubre TODO el
    rango de fechas del pago, incluidos sábados/domingos), así que
    dias_laborados es simplemente el número de días de calendario del
    periodo — nunca depende de qué casillas se marcaron. Por eso una
    quincena de 15 días (aunque tenga fines de semana) paga Valor Día x 15,
    no Valor Día x días-hábiles.

    Sobre las horas extra (mismas fórmulas ya validadas contra el Excel):
    - Día normal según el horario configurado: se usa la entrada/salida
      indicada (por defecto, la del horario) para detectar excedente sobre
      la jornada -> hora "ORDINARIA" (recargo 50%). Si no hay excedente,
      ese día no genera ninguna hora extra (su pago ya está cubierto por el
      salario base).
    - Día de descanso (fuera del horario normal): solo se procesa si se
      marcó explícitamente "trabajó este día"; toda la duración trabajada
      cuenta como hora "EXTRAORDINARIA" (recargo 100%), ADEMÁS del salario
      base (que ya incluye ese día de descanso dentro del periodo pagado).

    Re-valida en backend que ningún día del periodo ya esté pagado, sin
    confiar en lo que haya deshabilitado el frontend.
    """
    horario = HorarioTrabajador.para_trabajador(trabajador)
    dias_ya_pagados = trabajador.dias_pagados(periodo_inicio, periodo_fin, excluir_pago_id=pago_id_excluir)

    errores = []
    dias_detalle = []
    total_horas_normales = Decimal('0.00')
    entradas_horas_extra = []

    dias_laborados = Decimal((periodo_fin - periodo_inicio).days + 1)

    d = periodo_inicio
    while d <= periodo_fin:
        fecha_str = d.strftime('%Y-%m-%d')
        horario_dia = horario.dia(d.weekday())
        es_normal = bool(horario_dia and horario_dia.trabaja and horario_dia.hora_inicio and horario_dia.hora_fin)

        if d in dias_ya_pagados:
            errores.append(f"El día {d.strftime('%d/%m/%Y')} ya fue pagado antes; no puede incluirse de nuevo.")
            d += timedelta(days=1)
            continue

        if es_normal:
            entrada_raw = request.POST.get(f'entrada_{fecha_str}', '').strip() or horario_dia.hora_inicio.strftime('%H:%M')
            salida_raw = request.POST.get(f'salida_{fecha_str}', '').strip() or horario_dia.hora_fin.strftime('%H:%M')
            try:
                hora_entrada = datetime.strptime(entrada_raw, '%H:%M').time()
                hora_salida = datetime.strptime(salida_raw, '%H:%M').time()
            except Exception:
                errores.append(f"Hora de entrada/salida inválida para el {d.strftime('%d/%m/%Y')}.")
                d += timedelta(days=1)
                continue

            normales, ordinarias, extraordinarias = servicios_nomina.calcular_horas_dia(horario_dia, hora_entrada, hora_salida)
            total_horas_normales += normales

            for tipo, horas in (('ORDINARIA', ordinarias), ('EXTRAORDINARIA', extraordinarias)):
                if horas > 0:
                    try:
                        valor = servicios_nomina.calcular_valor_hora_extra(trabajador, tipo, horas)
                    except ValueError as e:
                        errores.append(str(e))
                        valor = Decimal('0.00')
                    entradas_horas_extra.append({'fecha': d, 'tipo': tipo, 'horas': horas, 'valor': valor})

            dias_detalle.append({
                'fecha': d, 'incluido': True, 'entrada': hora_entrada, 'salida': hora_salida, 'es_normal': True,
                'horas_normales': normales, 'horas_ordinarias': ordinarias, 'horas_extraordinarias': extraordinarias,
            })
        else:
            trabajo_descanso = request.POST.get(f'incluir_{fecha_str}') == 'on'
            if not trabajo_descanso:
                dias_detalle.append({'fecha': d, 'incluido': False, 'es_normal': False})
                d += timedelta(days=1)
                continue

            try:
                hora_entrada = datetime.strptime(request.POST.get(f'entrada_{fecha_str}', ''), '%H:%M').time()
                hora_salida = datetime.strptime(request.POST.get(f'salida_{fecha_str}', ''), '%H:%M').time()
            except Exception:
                errores.append(f"Indica la hora de entrada y salida del {d.strftime('%d/%m/%Y')} (día de descanso trabajado).")
                d += timedelta(days=1)
                continue

            normales, ordinarias, extraordinarias = servicios_nomina.calcular_horas_dia(horario_dia, hora_entrada, hora_salida)
            if extraordinarias > 0:
                try:
                    valor = servicios_nomina.calcular_valor_hora_extra(trabajador, 'EXTRAORDINARIA', extraordinarias)
                except ValueError as e:
                    errores.append(str(e))
                    valor = Decimal('0.00')
                entradas_horas_extra.append({'fecha': d, 'tipo': 'EXTRAORDINARIA', 'horas': extraordinarias, 'valor': valor})

            dias_detalle.append({
                'fecha': d, 'incluido': True, 'entrada': hora_entrada, 'salida': hora_salida, 'es_normal': False,
                'horas_normales': normales, 'horas_ordinarias': ordinarias, 'horas_extraordinarias': extraordinarias,
            })

        d += timedelta(days=1)

    total_ordinaria_horas = sum((e['horas'] for e in entradas_horas_extra if e['tipo'] == 'ORDINARIA'), Decimal('0.00'))
    total_ordinaria_valor = sum((e['valor'] for e in entradas_horas_extra if e['tipo'] == 'ORDINARIA'), Decimal('0.00'))
    total_extraordinaria_horas = sum((e['horas'] for e in entradas_horas_extra if e['tipo'] == 'EXTRAORDINARIA'), Decimal('0.00'))
    total_extraordinaria_valor = sum((e['valor'] for e in entradas_horas_extra if e['tipo'] == 'EXTRAORDINARIA'), Decimal('0.00'))

    return {
        'errores': errores,
        'dias_detalle': dias_detalle,
        'dias_laborados': dias_laborados,
        'total_horas_normales': total_horas_normales,
        'entradas_horas_extra': entradas_horas_extra,
        'total_ordinaria_horas': total_ordinaria_horas,
        'total_ordinaria_valor': total_ordinaria_valor,
        'total_extraordinaria_horas': total_extraordinaria_horas,
        'total_extraordinaria_valor': total_extraordinaria_valor,
        'total_horas_extra_valor': total_ordinaria_valor + total_extraordinaria_valor,
    }


def _construir_datos_formulario(periodo_mensual_id, aplicar_iess, horas_extra_ids_manual, descuento_ids_manual, observaciones, fecha_pago, resultado):
    """Snapshot de un envío del formulario de pago (día por día), reutilizado tanto
    para el autoguardado en sesión (cada vista previa) como para el borrador en BD."""
    return {
        'periodo_mensual_id': periodo_mensual_id or '',
        'aplicar_iess': 'on' if aplicar_iess else '',
        'horas_extra_ids': horas_extra_ids_manual,
        'descuento_ids': descuento_ids_manual,
        'observaciones': observaciones,
        'fecha_pago': fecha_pago.isoformat(),
        'dias': {
            dia['fecha'].strftime('%Y-%m-%d'): {
                'incluir': 'on' if dia['incluido'] else '',
                'entrada': dia['entrada'].strftime('%H:%M') if dia.get('entrada') else '',
                'salida': dia['salida'].strftime('%H:%M') if dia.get('salida') else '',
            }
            for dia in resultado['dias_detalle'] if dia['incluido']
        },
    }


@login_required(login_url='login')
@user_passes_test(es_admin, login_url='dashboard_erp')
def registrar_pago(request, trabajador_id):
    """
    Paso 3 (vista previa) y 4 (confirmación) del registro de pago.

    - Sin `confirmado=1`: solo calcula y muestra el desglose completo
      (horas normales, ordinarias, extraordinarias, bonificación, IESS,
      descuentos, anticipos y total) para revisión, SIN escribir nada en
      la base de datos.
    - Con `confirmado=1`: repite exactamente el mismo cálculo y esta vez sí
      crea las HoraExtra automáticas y el Pago, de forma transaccional.
    """
    trabajador = get_object_or_404(Trabajador, id=trabajador_id)
    if request.method != 'POST':
        return redirect('ficha_trabajador', trabajador_id=trabajador.id)

    try:
        periodo_inicio = datetime.strptime(request.POST.get('periodo_inicio'), '%Y-%m-%d').date()
        periodo_fin = datetime.strptime(request.POST.get('periodo_fin'), '%Y-%m-%d').date()
    except Exception:
        messages.error(request, "Periodo inválido.")
        return redirect('ficha_trabajador', trabajador_id=trabajador.id)

    pago_id = request.POST.get('pago_id') or None
    resultado = _procesar_dias_pago(request, trabajador, periodo_inicio, periodo_fin, pago_id_excluir=pago_id)

    periodo_mensual = None
    periodo_mensual_id = request.POST.get('periodo_mensual_id')
    if periodo_mensual_id:
        periodo_mensual = get_object_or_404(PeriodoNominaMensual, id=periodo_mensual_id, trabajador=trabajador)

    aplicar_iess = request.POST.get('aplicar_iess') == 'on'
    horas_extra_ids_manual = [i for i in request.POST.getlist('horas_extra_ids') if i]
    descuento_ids_manual = [i for i in request.POST.getlist('descuento_ids') if i]
    observaciones = (request.POST.get('observaciones') or '').strip()

    try:
        fecha_pago = datetime.strptime(request.POST.get('fecha_pago', ''), '%Y-%m-%d').date()
    except Exception:
        fecha_pago = timezone.localdate()

    if resultado['errores']:
        for error in resultado['errores']:
            messages.error(request, error)
        sufijo_pago = f"&pago_id={pago_id}" if pago_id else ""
        return redirect(
            f"{reverse('preparar_pago', args=[trabajador.id])}"
            f"?periodo_inicio={periodo_inicio}&periodo_fin={periodo_fin}{sufijo_pago}"
        )

    # "Disponible para incluir" = libre, o ya vinculado al borrador que se está editando/reemplazando
    # (si no se incluye esta segunda condición, al recalcular la vista previa de un borrador ya
    # guardado los descuentos/horas manuales que quedaron enlazados a él parecen "desaparecer").
    filtro_incluible = Q(pago__isnull=True)
    if pago_id:
        filtro_incluible |= Q(pago_id=pago_id)
    horas_manuales = HoraExtra.objects.filter(filtro_incluible, id__in=horas_extra_ids_manual, trabajador=trabajador)
    descuentos_manuales = Descuento.objects.filter(filtro_incluible, id__in=descuento_ids_manual, trabajador=trabajador)

    accion = request.POST.get('accion')  # None en la vista previa; 'confirmar' o 'borrador' al finalizar

    if accion not in ('confirmar', 'borrador'):
        try:
            salario_preview = servicios_nomina.calcular_salario_periodo(trabajador, resultado['dias_laborados'])
        except ValueError as e:
            messages.error(request, str(e))
            return redirect('ficha_trabajador', trabajador_id=trabajador.id)

        total_descuentos_manual = sum((d.monto for d in descuentos_manuales if d.tipo == 'DESCUENTO'), Decimal('0.00'))
        total_anticipos_manual = sum((d.monto for d in descuentos_manuales if d.tipo == 'ANTICIPO'), Decimal('0.00'))
        total_horas_manuales_valor = sum((h.valor_calculado or Decimal('0.00') for h in horas_manuales), Decimal('0.00'))
        bonificacion = periodo_mensual.bonificacion_quincenal if periodo_mensual else Decimal('0.00')
        aporte_iess = trabajador.aporte_iess_quincenal if aplicar_iess else Decimal('0.00')
        total_estimado = (
            salario_preview + resultado['total_horas_extra_valor'] + total_horas_manuales_valor + bonificacion
            - total_descuentos_manual - total_anticipos_manual - aporte_iess
        )

        # Autoguardado en sesión: si el admin vuelve a "Volver a Editar" no debe
        # perder lo que ya había corregido, aunque todavía no confirme ni guarde borrador.
        request.session[f'pago_form_datos_{trabajador.id}'] = {
            **_construir_datos_formulario(
                periodo_mensual_id, aplicar_iess, horas_extra_ids_manual, descuento_ids_manual,
                observaciones, fecha_pago, resultado,
            ),
            'periodo_inicio': periodo_inicio.isoformat(),
            'periodo_fin': periodo_fin.isoformat(),
            'pago_id': pago_id,
        }

        return render(request, 'web/erp/revisar_pago.html', {
            'trabajador': trabajador, 'periodo_inicio': periodo_inicio, 'periodo_fin': periodo_fin,
            'fecha_pago': fecha_pago, 'resultado': resultado, 'salario_preview': salario_preview,
            'periodo_mensual': periodo_mensual, 'bonificacion': bonificacion,
            'aplicar_iess': aplicar_iess, 'aporte_iess': aporte_iess,
            'horas_manuales': horas_manuales, 'descuentos_manuales': descuentos_manuales,
            'total_horas_manuales_valor': total_horas_manuales_valor,
            'total_descuentos_manual': total_descuentos_manual, 'total_anticipos_manual': total_anticipos_manual,
            'total_estimado': total_estimado, 'observaciones': observaciones,
            'horas_extra_ids_manual': horas_extra_ids_manual, 'descuento_ids_manual': descuento_ids_manual,
            'pago_id': pago_id,
        })

    # accion == 'confirmar' o 'borrador': crear (o reemplazar el borrador anterior) de verdad, en una sola transacción
    try:
        with transaction.atomic():
            if pago_id:
                pago_anterior = get_object_or_404(Pago, id=pago_id, trabajador=trabajador, estado='BORRADOR')
                pago_anterior.horas_extras_incluidas.filter(generado_automaticamente=True).delete()
                pago_anterior.horas_extras_incluidas.update(pago=None)
                pago_anterior.descuentos_incluidos.update(pago=None)
                pago_anterior.delete()

            horas_extra_auto_ids = []
            for entrada in resultado['entradas_horas_extra']:
                he = HoraExtra.objects.create(
                    trabajador=trabajador, fecha=entrada['fecha'], tipo=entrada['tipo'],
                    cantidad_horas=entrada['horas'], valor_calculado=entrada['valor'],
                    observaciones=f"Generado automáticamente del pago ({entrada['fecha'].strftime('%d/%m/%Y')}).",
                    generado_automaticamente=True, registrado_por=request.user,
                )
                horas_extra_auto_ids.append(he.id)

            pago = trabajador.registrar_pago(
                periodo_inicio=periodo_inicio, periodo_fin=periodo_fin, fecha_pago=fecha_pago,
                usuario=request.user, dias_laborados=resultado['dias_laborados'],
                horas_extra_ids=horas_extra_auto_ids + horas_extra_ids_manual,
                descuento_ids=descuento_ids_manual,
                periodo_mensual=periodo_mensual, aplicar_iess=aplicar_iess, observaciones=observaciones,
                total_horas_normales=resultado['total_horas_normales'],
            )

            if accion == 'borrador':
                pago.estado = 'BORRADOR'
                pago.datos_formulario = _construir_datos_formulario(
                    periodo_mensual_id, aplicar_iess, horas_extra_ids_manual, descuento_ids_manual,
                    observaciones, fecha_pago, resultado,
                )
                pago.save(update_fields=['estado', 'datos_formulario'])
    except ValueError as e:
        messages.error(request, str(e))
        return redirect('ficha_trabajador', trabajador_id=trabajador.id)

    request.session.pop(f'pago_form_datos_{trabajador.id}', None)

    if accion == 'borrador':
        messages.success(request, "Pago guardado como borrador. Puedes continuar editándolo desde la ficha del trabajador antes de confirmarlo.")
    else:
        messages.success(request, f"Pago registrado correctamente. Total a pagar: ${pago.total_pagado}.")
    return redirect('ficha_trabajador', trabajador_id=trabajador.id)


@login_required(login_url='login')
@user_passes_test(lambda u: es_admin(u) or es_comprador(u), login_url='dashboard_erp')
def listar_pagos(request):
    """
    Pagos Realizados. Administrador y Compras pueden ver y ejecutar
    "Proceder al Pago"; solo Administrador puede editar un pago ya generado.
    """
    pagos = Pago.objects.select_related('trabajador', 'pagado_por', 'registrado_por').exclude(estado='BORRADOR')

    estado_filtro = request.GET.get('estado')
    if estado_filtro in ('PENDIENTE', 'PAGADO'):
        pagos = pagos.filter(estado=estado_filtro)

    q = request.GET.get('q', '').strip()
    if q:
        pagos = pagos.filter(Q(trabajador__nombres__icontains=q) | Q(trabajador__apellidos__icontains=q))

    paginator = Paginator(pagos, 15)
    page_obj = paginator.get_page(request.GET.get('page'))

    return render(request, 'web/erp/listar_pagos.html', {
        'page_obj': page_obj, 'estado_filtro': estado_filtro, 'q': q,
        'es_admin_actual': es_admin(request.user),
        'rol': 'Administrador' if es_admin(request.user) else 'Compras',
    })


@login_required(login_url='login')
@user_passes_test(lambda u: es_admin(u) or es_comprador(u), login_url='dashboard_erp')
def confirmar_pago(request, pago_id):
    """"Proceder al Pago": confirma que la transferencia ya se hizo, marca PAGADO y notifica por correo."""
    pago = get_object_or_404(Pago, id=pago_id)
    if request.method == 'POST':
        try:
            pago.marcar_como_pagado(usuario=request.user)
        except ValueError as e:
            messages.error(request, str(e))
            return redirect('listar_pagos')

        try:
            servicios_nomina.enviar_email_pago_confirmado(pago)
        except Exception as e:
            pago.email_enviado = False
            pago.email_error = str(e)
            pago.save(update_fields=['email_enviado', 'email_error'])
            messages.warning(request, f"El pago quedó marcado como PAGADO, pero el correo al trabajador NO se pudo enviar: {e}")
        else:
            pago.email_enviado = True
            pago.email_error = ''
            pago.save(update_fields=['email_enviado', 'email_error'])
            messages.success(request, f"Pago marcado como PAGADO y correo enviado a {pago.trabajador.email}.")
    return redirect('listar_pagos')


@login_required(login_url='login')
@user_passes_test(es_admin, login_url='dashboard_erp')
def editar_pago(request, pago_id):
    """
    Solo Administrador. Permite corregir tanto la fecha/observaciones como
    los montos calculados de un pago ya generado (incluso ya PAGADO), para
    arreglar un error puntual sin tener que rehacer todo el registro desde
    el día-a-día. El total se recalcula siempre en el servidor a partir de
    los componentes editados (nunca se confía en un total enviado directo).

    Si el pago ya estaba PAGADO Y algún monto realmente cambia, se anula esa
    aprobación (vuelve a PENDIENTE) para que Compras deba pagar de nuevo con
    el valor correcto. Si no cambia ningún monto (p. ej. solo se corrigió la
    fecha u observaciones), el estado PAGADO se conserva tal cual.
    """
    pago = get_object_or_404(Pago, id=pago_id)
    if request.method == 'POST':
        if pago.estado == 'PAGADO' and request.POST.get('confirmar_edicion') != 'on':
            messages.error(request, "Este pago ya fue realizado. Debes confirmar explícitamente que deseas editarlo.")
            return redirect('editar_pago', pago_id=pago.id)

        try:
            fecha_pago = datetime.strptime(request.POST.get('fecha_pago', ''), '%Y-%m-%d').date()
        except Exception:
            messages.error(request, "Fecha de pago inválida.")
            return redirect('editar_pago', pago_id=pago.id)

        campos_monto = ['salario_base', 'total_horas_extras', 'bonificacion', 'total_descuentos', 'total_anticipos', 'aporte_iess']
        try:
            nuevos_montos = {
                campo: Decimal((request.POST.get(campo) or '0').replace(',', '.'))
                for campo in campos_monto
            }
        except Exception:
            messages.error(request, "Alguno de los montos ingresados no es válido.")
            return redirect('editar_pago', pago_id=pago.id)

        if any(v < 0 for v in nuevos_montos.values()):
            messages.error(request, "Ningún monto puede ser negativo.")
            return redirect('editar_pago', pago_id=pago.id)

        nuevo_total = (
            nuevos_montos['salario_base'] + nuevos_montos['total_horas_extras'] + nuevos_montos['bonificacion']
            - nuevos_montos['total_descuentos'] - nuevos_montos['total_anticipos'] - nuevos_montos['aporte_iess']
        )
        if nuevo_total < 0:
            messages.error(request, "El total a pagar no puede quedar negativo con esos montos.")
            return redirect('editar_pago', pago_id=pago.id)

        cambio_algun_monto = any(getattr(pago, campo) != valor for campo, valor in nuevos_montos.items())

        campos = ['fecha_pago', 'observaciones', 'total_pagado'] + campos_monto
        pago.fecha_pago = fecha_pago
        pago.observaciones = (request.POST.get('observaciones') or '').strip()
        for campo, valor in nuevos_montos.items():
            setattr(pago, campo, valor)
        pago.total_pagado = nuevo_total

        if pago.estado == 'PAGADO' and cambio_algun_monto:
            pago.estado = 'PENDIENTE'
            pago.pagado_por = None
            pago.fecha_pago_confirmado = None
            pago.email_enviado = False
            pago.email_error = ''
            campos += ['estado', 'pagado_por', 'fecha_pago_confirmado', 'email_enviado', 'email_error']
            messages.warning(request, "Cambiaste un monto de un pago ya realizado: volvió a quedar PENDIENTE y Compras deberá confirmar de nuevo la transferencia.")

        pago.save(update_fields=campos)
        messages.success(request, "Pago actualizado.")
        return redirect('listar_pagos')

    return render(request, 'web/erp/editar_pago.html', {'pago': pago})


@login_required(login_url='login')
@user_passes_test(lambda u: es_admin(u) or es_comprador(u), login_url='dashboard_erp')
def imprimir_pdf_pago(request, pago_id):
    pago = get_object_or_404(Pago, id=pago_id)
    context = {
        'pago': pago,
        'trabajador': pago.trabajador,
        'horas_extras': pago.horas_extras_incluidas.all(),
        'descuentos': pago.descuentos_incluidos.filter(tipo='DESCUENTO'),
        'anticipos': pago.descuentos_incluidos.filter(tipo='ANTICIPO'),
        'logo_path': os.path.join(settings.BASE_DIR, 'web', 'static', 'web', 'img', 'logo.jpg'),
        'fecha_impresion': timezone.now(),
    }
    html = get_template('web/erp/pdf_pago.html').render(context)
    response = HttpResponse(content_type='application/pdf')
    response['Content-Disposition'] = (
        f'attachment; filename="RolDePago_{pago.trabajador.documento_identidad}_{pago.periodo_inicio}_{pago.periodo_fin}.pdf"'
    )
    if pisa.CreatePDF(html, dest=response).err:
        return HttpResponse('Hubo un error al generar el PDF del rol de pagos.')
    return response


@login_required(login_url='login')
@user_passes_test(es_admin, login_url='dashboard_erp')
def registrar_periodo_mensual(request, trabajador_id):
    """
    Registra (o actualiza) la Bonificación del MES para un trabajador. El
    sistema aplicará automáticamente la mitad en cada pago quincenal de ese
    mes que la referencie. El Aporte IESS NO va aquí: es un valor fijo del
    trabajador (ver configurar_iess_trabajador).
    """
    trabajador = get_object_or_404(Trabajador, id=trabajador_id)
    if request.method == 'POST':
        try:
            anio = int(request.POST.get('anio'))
            mes = int(request.POST.get('mes'))
            bonificacion = Decimal((request.POST.get('bonificacion') or '0').replace(',', '.'))
        except Exception:
            messages.error(request, "Datos inválidos para la bonificación del mes.")
            return redirect('ficha_trabajador', trabajador_id=trabajador.id)

        periodo, creado = PeriodoNominaMensual.objects.get_or_create(
            trabajador=trabajador, anio=anio, mes=mes,
            defaults={'bonificacion': bonificacion, 'registrado_por': request.user},
        )
        if not creado:
            periodo.bonificacion = bonificacion
            periodo.registrado_por = request.user

        try:
            periodo.full_clean()
        except ValidationError as e:
            messages.error(request, " ".join(e.messages))
            return redirect('ficha_trabajador', trabajador_id=trabajador.id)

        periodo.save()
        messages.success(request, f"Bonificación de {mes}/{anio} registrada. Se aplicará la mitad en cada quincena.")
    return redirect('ficha_trabajador', trabajador_id=trabajador.id)


@login_required(login_url='login')
@user_passes_test(es_admin, login_url='dashboard_erp')
def configurar_iess_trabajador(request, trabajador_id):
    """
    Define el aporte IESS MENSUAL FIJO del trabajador (no es un valor que se
    registre mes a mes: se actualiza aquí cuando corresponda, p.ej. tras un
    cambio de salario, y queda vigente hasta la próxima actualización).
    """
    trabajador = get_object_or_404(Trabajador, id=trabajador_id)
    if request.method == 'POST':
        try:
            monto = Decimal((request.POST.get('aporte_iess_mensual') or '0').replace(',', '.'))
        except Exception:
            messages.error(request, "Monto de aporte IESS inválido.")
            return redirect('ficha_trabajador', trabajador_id=trabajador.id)

        if monto < 0:
            messages.error(request, "El aporte IESS no puede ser negativo.")
            return redirect('ficha_trabajador', trabajador_id=trabajador.id)

        trabajador.aporte_iess_mensual = monto
        trabajador.save(update_fields=['aporte_iess_mensual'])
        messages.success(request, f"Aporte IESS fijo actualizado: ${monto}/mes (${trabajador.aporte_iess_quincenal}/quincena).")
    return redirect('ficha_trabajador', trabajador_id=trabajador.id)