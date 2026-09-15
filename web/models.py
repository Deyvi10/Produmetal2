from django.db import models, transaction
from django.contrib.auth.models import User
from django.core.validators import FileExtensionValidator
from django.core.exceptions import ValidationError
from django.utils import timezone
from simple_history.models import HistoricalRecords
from decimal import Decimal
import datetime

# =====================================================================
# CONFIGURACIONES BASE Y CATEGORÍAS
# =====================================================================
class Bodega(models.Model):
    nombre = models.CharField(max_length=100, unique=True)
    ubicacion = models.CharField(max_length=200, blank=True, null=True)
    is_principal = models.BooleanField(default=False)

    def __str__(self):
        return self.nombre

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        if self.is_principal:
            # Solo puede existir UNA bodega matriz a la vez
            Bodega.objects.exclude(pk=self.pk).update(is_principal=False)

    def obtener_motivos_bloqueo_eliminacion(self):
        """
        Recorre TODAS las relaciones existentes de la bodega para determinar
        si ya fue utilizada. Si la lista vuelve vacía, es seguro eliminarla.
        """
        motivos = []
        if self.is_principal:
            motivos.append("Es la bodega principal/matriz del sistema.")

        if self.inventario.filter(cantidad__gt=0).exists():
            motivos.append("Tiene stock físico de materiales registrado.")
        elif self.inventario.exists():
            motivos.append("Tiene historial de inventario asociado (registros en cero).")

        if self.movimientos_salida.exists() or self.movimientos_ingreso.exists():
            motivos.append("Tiene movimientos registrados en la bitácora de auditoría.")

        proyecto = getattr(self, 'proyecto_asociado', None)
        if proyecto:
            motivos.append(f"Está vinculada al proyecto '{proyecto.nombre}'.")

        if self.detallerequerimiento_set.exists():
            motivos.append("Tiene requerimientos internos que la referencian como destino.")

        if self.cotizacionitem_set.exists():
            motivos.append("Tiene cotizaciones de compra que la referencian.")

        if self.detalleordencompra_set.exists():
            motivos.append("Tiene órdenes de compra que la referencian como destino.")

        if self.perfilempleado_set.exists():
            motivos.append("Tiene empleados con esta bodega asignada.")

        return motivos

    @property
    def puede_eliminarse(self):
        return len(self.obtener_motivos_bloqueo_eliminacion()) == 0

class Categoria(models.Model):
    nombre = models.CharField(max_length=100)
    prefijo = models.CharField(max_length=10, unique=True, help_text="Ej: FER, ELE, PVC")
    is_active = models.BooleanField(default=True)

    def __str__(self):
        return f"{self.prefijo} - {self.nombre}"

class SecuenciaCodigo(models.Model):
    prefijo = models.CharField(max_length=10, unique=True)
    ultimo_valor = models.IntegerField(default=0)

# =====================================================================
# 1. MODELO DE PROYECTOS (Con Trazabilidad Histórica)
# =====================================================================
class Proyecto(models.Model):
    nombre = models.CharField(max_length=200)
    centro_costos = models.CharField(max_length=100, unique=True, blank=True)
    descripcion = models.TextField(blank=True, null=True, verbose_name="Descripción del Proyecto")
    is_active = models.BooleanField(default=True, help_text="Desmarcar para borrado lógico")
    fecha_creacion = models.DateTimeField(auto_now_add=True)
    bodega_proyecto = models.OneToOneField(Bodega, on_delete=models.SET_NULL, null=True, blank=True, related_name='proyecto_asociado')
    
    history = HistoricalRecords() # AUDITORÍA TOTAL

    def save(self, *args, **kwargs):
        # Generar código automático para centro de costos si está vacío
        if not self.centro_costos:
            year = datetime.date.today().year
            ultimo = Proyecto.objects.order_by('id').last()
            sec = (ultimo.id + 1) if ultimo else 1
            self.centro_costos = f'PROY-{year}-{sec:03d}'
            
        super().save(*args, **kwargs)
        
        # Crear bodega automática para el proyecto
        if self.is_active and not self.bodega_proyecto:
            nueva_bodega = Bodega.objects.create(nombre=f"Bodega Obra: {self.nombre}")
            self.bodega_proyecto = nueva_bodega
            self.save()

    def __str__(self):
        return f"{self.centro_costos} - {self.nombre}"

# =====================================================================
# 2. CATÁLOGO DE INVENTARIO (Anti-Duplicados y Concurrencia)
# =====================================================================
class Material(models.Model):
    """
    Catálogo maestro de materiales y consumibles.
    
    Características:
    - SKU auto-generado por categoría (FERR-0001, ELEC-0002, etc)
    - Stock denormalizado pero actualizable
    - Trazabilidad histórica completa
    - Cálculo automático de precio con impuesto
    """
    categoria = models.ForeignKey(Categoria, on_delete=models.PROTECT) 
    sku = models.CharField(
        max_length=50, unique=True, blank=True, editable=False,
        help_text="Código único auto-generado"
    )
    nombre = models.CharField(
        max_length=200,
        help_text="Nombre comercial o norma técnica"
    )
    descripcion = models.TextField(blank=True, null=True)
    
    # INVENTARIO
    stock_actual = models.DecimalField(
        max_digits=10, decimal_places=2, default=0.00,
        help_text="Stock Total (Suma de bodegas). Denormalizado para reportes rápidos."
    )
    stock_minimo = models.DecimalField(
        max_digits=10, decimal_places=2, default=5.00,
        help_text="Umbral para alertas de reabastecimiento"
    )
    
    # PRECIOS Y COSTOS
    precio_base = models.DecimalField(
        max_digits=10, decimal_places=2, default=0.00,
        help_text="Precio unitario sin impuesto"
    )
    impuesto_porcentaje = models.DecimalField(
        max_digits=5, decimal_places=2, default=15.00,
        help_text="Porcentaje de impuesto (IVA, etc)"
    )
    
    # ESTADO
    is_active = models.BooleanField(
        default=True,
        help_text="Desmarcar para borrado lógico (mantiene histórico)"
    )
    
    # AUDITORÍA
    fecha_creacion = models.DateTimeField(auto_now_add=True)
    fecha_modificacion = models.DateTimeField(auto_now=True)
    history = HistoricalRecords()

    class Meta:
        verbose_name_plural = "Inventario (Materiales y Consumibles)"
        ordering = ['-fecha_creacion']
        indexes = [
            models.Index(fields=['sku']),
            models.Index(fields=['categoria', 'is_active']),
        ]

    def save(self, *args, **kwargs):
        """
        Genera SKU automático en primera creación.
        Usa transacción para evitar race conditions.
        """
        if not self.sku:
            with transaction.atomic():
                secuencia, created = SecuenciaCodigo.objects.select_for_update().get_or_create(
                    prefijo=self.categoria.prefijo,
                    defaults={'ultimo_valor': 0}
                )
                secuencia.ultimo_valor += 1
                secuencia.save()
                self.sku = f'{self.categoria.prefijo}-{secuencia.ultimo_valor:04d}'
        
        # EL FIX: Solo calcular stock de bodegas si el material YA EXISTE (tiene ID/PK)
        if self.pk:
            self.stock_actual = self._calcular_stock_total()
        else:
            self.stock_actual = 0.00  # Si es nuevo, arranca con stock cero
        
        super().save(*args, **kwargs)

    def __str__(self):
        return f"[{self.sku}] {self.nombre}"
    
    def _calcular_stock_total(self):
        """Suma el stock de todas las bodegas"""
        return sum(sb.cantidad for sb in self.stocks_bodegas.all()) or 0
    
    @property
    def precio_total_con_impuesto(self):
        """Calcula el precio final con impuesto incluido"""
        impuesto = (self.precio_base * self.impuesto_porcentaje) / 100
        return self.precio_base + impuesto
    
    @property
    def stock_en_alerta(self):
        """Retorna True si stock está por debajo del mínimo"""
        return self.stock_actual < self.stock_minimo
    
    def tiene_movimientos(self):
        """Verifica si el material tiene auditoría de movimientos"""
        return self.movimientos.exists()
    @property
    def ultimo_certificado_url(self):
        mov = self.movimientos.filter(tipo='INGRESO', certificado_calidad__isnull=False).order_by('-fecha_hora').first()
        return mov.certificado_calidad.url if mov and mov.certificado_calidad else None

    @property
    def desglose_stock_bodegas(self):
        """Retorna un diccionario o queryset con el stock por bodega para el tooltip/UI"""
        return self.stocks_bodegas.filter(cantidad__gt=0)
    
class StockBodega(models.Model):
    material = models.ForeignKey(Material, on_delete=models.CASCADE, related_name='stocks_bodegas')
    bodega = models.ForeignKey(Bodega, on_delete=models.CASCADE, related_name='inventario')
    cantidad = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)

    class Meta:
        unique_together = ('material', 'bodega')

    def __str__(self):
        return f"{self.material.sku} en {self.bodega.nombre}: {self.cantidad}"

# =====================================================================
# 3. MÓDULO DE REQUERIMIENTOS INTERNOS (División Automática)
# =====================================================================
class Requerimiento(models.Model):
    ESTADOS = [
        ('PENDIENTE', 'Pendiente de Aprobación Admin'),
        ('APROBADO', 'Aprobado'),
        ('RECHAZADO', 'Rechazado'),
        ('PARCIALMENTE_DESPACHADO', 'Parcialmente Despachado'),
        ('DESPACHADO', 'Despachado Totalmente'),
        ('EN_COMPRAS', 'Enviado a Compras'),
        ('CERRADO_INCOMPLETO', 'Cerrado Incompleto por Bodega'),
    ]

    folio = models.CharField(max_length=20, unique=True, blank=True, editable=False)
    solicitante = models.ForeignKey(User, on_delete=models.PROTECT, related_name='requerimientos')
    proyecto = models.ForeignKey(Proyecto, on_delete=models.PROTECT)
    fecha_solicitud = models.DateTimeField(auto_now_add=True)
    estado = models.CharField(max_length=30, choices=ESTADOS, default='PENDIENTE')
    observaciones = models.TextField(blank=True)

    history = HistoricalRecords()

    def save(self, *args, **kwargs):
        if not self.folio:
            year = datetime.date.today().year
            ultimo_req = Requerimiento.objects.filter(folio__startswith=f'REQ-{year}').order_by('id').last()
            secuencia = int(ultimo_req.folio.split('-')[-1]) + 1 if ultimo_req else 1
            self.folio = f'REQ-{year}-{secuencia:03d}'
        super().save(*args, **kwargs)

    @transaction.atomic
    def procesar_y_dividir_stock(self):
        for detalle in self.detalles.all():
            if detalle.estado_item == 'RECHAZADO': continue

            material = Material.objects.select_for_update().get(id=detalle.material.id)
            bodega_req = detalle.bodega_destino
            
            # Buscar stock SOLO en la bodega solicitada
            stock_bodega = StockBodega.objects.filter(material=material, bodega=bodega_req).first()
            cant_bodega = stock_bodega.cantidad if stock_bodega else Decimal('0.0')

            if cant_bodega >= detalle.cantidad_solicitada:
                detalle.estado_item = 'APROBADO_BODEGA'
                detalle.save()
            elif cant_bodega > 0:
                cantidad_faltante = detalle.cantidad_solicitada - cant_bodega
                detalle.cantidad_solicitada = cant_bodega
                detalle.estado_item = 'APROBADO_BODEGA'
                detalle.save()
                
                DetalleRequerimiento.objects.create(
                    requerimiento=self, material=material, cantidad_solicitada=cantidad_faltante,
                    bodega_destino=bodega_req, estado_item='EN_COMPRAS',
                    motivo_rechazo='División automática (Falta de stock en bodega seleccionada)'
                )
            else:
                detalle.estado_item = 'EN_COMPRAS'
                detalle.save()

    def __str__(self):
        return f"{self.folio} - {self.proyecto.nombre}"
    def actualizar_estado_general(self):
        """
        Calcula y actualiza automáticamente el estado maestro del Requerimiento 
        basándose en las decisiones que se tomaron ítem por ítem.
        """
        # El cierre incompleto es una decisión definitiva de bodega: no se
        # recalcula automáticamente a partir de los estados de los ítems.
        if self.estado == 'CERRADO_INCOMPLETO':
            return

        detalles = list(self.detalles.all())
        if not detalles:
            return

        estados = [item.estado_item for item in detalles]
        algo_despachado = any(item.cantidad_despachada > 0 for item in detalles)
        algo_pendiente = any(item.estado_item in ('APROBADO_BODEGA', 'EN_COMPRAS') for item in detalles)

        # 1. Si absolutamente todo fue rechazado por el Admin
        if all(estado == 'RECHAZADO' for estado in estados):
            self.estado = 'RECHAZADO'

        # 2. Si todo lo que no fue rechazado ya se entregó físicamente al técnico
        elif all(estado in ('DESPACHADO', 'RECHAZADO') for estado in estados) and any(estado == 'DESPACHADO' for estado in estados):
            self.estado = 'DESPACHADO'

        # 3. Ya se entregó una parte, pero todavía queda cantidad pendiente (en bodega o en compras)
        elif algo_despachado and algo_pendiente:
            self.estado = 'PARCIALMENTE_DESPACHADO'

        # 4. Todo el material válido está en la bodega listo para que el técnico lo retire (nada entregado aún)
        elif all(estado in ('APROBADO_BODEGA', 'DESPACHADO', 'RECHAZADO') for estado in estados) and any(estado == 'APROBADO_BODEGA' for estado in estados):
            self.estado = 'APROBADO'

        # 5. Todo el material faltante se fue directo al departamento de Compras
        elif all(estado in ('EN_COMPRAS', 'RECHAZADO') for estado in estados) and any(estado == 'EN_COMPRAS' for estado in estados):
            self.estado = 'EN_COMPRAS'

        # 6. SPLIT: mezcla de estados sin que se haya entregado nada todavía
        elif any(estado in ('EN_COMPRAS', 'APROBADO_BODEGA', 'DESPACHADO') for estado in estados):
            self.estado = 'PARCIALMENTE_DESPACHADO'

        # 7. Si todavía el Admin no revisa nada
        else:
            self.estado = 'PENDIENTE'

        self.save()

    @property
    def cantidad_total_solicitada(self):
        return sum((d.cantidad_solicitada for d in self.detalles.all()), Decimal('0.00'))

    @property
    def cantidad_total_despachada(self):
        return sum((d.cantidad_despachada for d in self.detalles.all()), Decimal('0.00'))

    @property
    def cantidad_total_pendiente(self):
        return sum((d.cantidad_pendiente for d in self.detalles.all()), Decimal('0.00'))

    @property
    def puede_cerrarse_incompleto(self):
        """Solo tiene sentido cerrar incompleto si aún queda algo por entregar."""
        return self.estado not in ('DESPACHADO', 'RECHAZADO', 'CERRADO_INCOMPLETO') and self.cantidad_total_pendiente > 0

    @transaction.atomic
    def cerrar_incompleto(self, usuario, justificativo):
        """
        Cierra definitivamente el requerimiento aunque queden cantidades sin
        entregar. Exige justificativo y deja auditoría permanente.
        """
        justificativo = (justificativo or '').strip()
        if not justificativo:
            raise ValueError("El justificativo es obligatorio para cerrar un requerimiento incompleto.")
        if not self.puede_cerrarse_incompleto:
            raise ValueError("Este requerimiento no tiene cantidades pendientes por cerrar.")

        solicitada = self.cantidad_total_solicitada
        despachada = self.cantidad_total_despachada
        pendiente = self.cantidad_total_pendiente

        for item in self.detalles.exclude(estado_item__in=['DESPACHADO', 'RECHAZADO']):
            item.estado_item = 'CERRADO_INCOMPLETO'
            item.save(update_fields=['estado_item'])

        self.estado = 'CERRADO_INCOMPLETO'
        self.save(update_fields=['estado'])

        return CierreIncompletoRequerimiento.objects.create(
            requerimiento=self,
            usuario=usuario,
            justificativo=justificativo,
            cantidad_solicitada_snapshot=solicitada,
            cantidad_despachada_snapshot=despachada,
            cantidad_pendiente_snapshot=pendiente,
        )

class DetalleRequerimiento(models.Model):
    ESTADOS_ITEM = [
        ('PENDIENTE', 'Pendiente de Revisión'),
        ('APROBADO_BODEGA', 'Aprobado para Despacho (Bodega)'),
        ('EN_COMPRAS', 'Mandar a Compras (Falta Stock)'),
        ('DESPACHADO', 'Despachado Totalmente'),
        ('CERRADO_INCOMPLETO', 'Cerrado Incompleto por Bodega'),
        ('RECHAZADO', 'Rechazado'),
    ]

    requerimiento = models.ForeignKey(Requerimiento, related_name='detalles', on_delete=models.CASCADE)
    material = models.ForeignKey(Material, on_delete=models.PROTECT)
    bodega_destino = models.ForeignKey(Bodega, on_delete=models.PROTECT, null=True, help_text="Bodega donde se necesita el material") # NUEVO
    cantidad_solicitada = models.DecimalField(max_digits=10, decimal_places=2)
    cantidad_despachada = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    estado_item = models.CharField(max_length=30, choices=ESTADOS_ITEM, default='PENDIENTE')
    motivo_rechazo = models.TextField(blank=True, null=True, verbose_name="Notas u Observaciones")

    def __str__(self):
        return f"{self.cantidad_solicitada} x {self.material.nombre} [{self.estado_item}]"

    @property
    def stock_en_bodega_destino(self):
        """Devuelve el stock físico que existe ÚNICAMENTE en la bodega solicitada para este ítem."""
        if self.bodega_destino:
            stock = self.material.stocks_bodegas.filter(bodega=self.bodega_destino).first()
            return stock.cantidad if stock else 0
        return 0

    @property
    def cantidad_pendiente(self):
        pendiente = self.cantidad_solicitada - self.cantidad_despachada
        return pendiente if pendiente > 0 else Decimal('0.00')


class CierreIncompletoRequerimiento(models.Model):
    """
    Auditoría permanente del cierre de un Requerimiento sin haber sido
    entregado al 100%. El justificativo es obligatorio y no se sobrescribe.
    """
    requerimiento = models.OneToOneField(
        Requerimiento, on_delete=models.CASCADE, related_name='cierre_incompleto'
    )
    usuario = models.ForeignKey(User, on_delete=models.PROTECT, related_name='cierres_incompletos')
    fecha_hora = models.DateTimeField(default=timezone.now)
    justificativo = models.TextField()

    # Fotografía de las cantidades al momento del cierre (auditoría, no se recalcula)
    cantidad_solicitada_snapshot = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    cantidad_despachada_snapshot = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    cantidad_pendiente_snapshot = models.DecimalField(max_digits=10, decimal_places=2, default=0)

    def __str__(self):
        return f"Cierre incompleto de {self.requerimiento.folio}"

# =====================================================================
# 4. MÓDULO DE COTIZACIONES Y COMPRAS
# =====================================================================
class SolicitudCompra(models.Model):
    ESTADOS = [
        ('ENVIADO_A_COMPRAS', 'Pendiente de Cotización (En Compras)'),
        ('COTIZADO', 'Cotizado (Esperando Aprobación Admin)'),
        ('REVISADO_ADMIN', 'Revisado por Admin (Requiere Acción Compras)'), # NUEVO
        ('PROCESADO', 'Procesado (Órdenes Generadas)'),
    ]

    folio = models.CharField(max_length=20, unique=True, blank=True, editable=False)
    requerimiento_origen = models.ForeignKey(Requerimiento, on_delete=models.SET_NULL, null=True, blank=True)
    fecha_creacion = models.DateTimeField(auto_now_add=True)
    estado = models.CharField(max_length=30, choices=ESTADOS, default='ENVIADO_A_COMPRAS')
    observaciones_admin = models.TextField(blank=True)

    def save(self, *args, **kwargs):
        if not self.folio:
            year = datetime.date.today().year
            ultima_sol = SolicitudCompra.objects.filter(folio__startswith=f'SC-{year}').order_by('id').last()
            secuencia = int(ultima_sol.folio.split('-')[-1]) + 1 if ultima_sol else 1
            self.folio = f'SC-{year}-{secuencia:03d}'
        super().save(*args, **kwargs)

class CotizacionItem(models.Model):
    ESTADOS_APROBACION = [
        ('PENDIENTE', 'Pendiente de Revisión'),
        ('APROBADO', 'Aprobado para Compra'),
        ('COMPRADO', 'Órden de Compra Generada'), 
        ('RECHAZADO', 'Rechazado'),
    ]

    solicitud = models.ForeignKey(SolicitudCompra, related_name='items_cotizados', on_delete=models.CASCADE)
    material = models.ForeignKey(Material, on_delete=models.PROTECT) 
    cantidad_requerida = models.DecimalField(max_digits=10, decimal_places=2)
    
    proveedor_cotizado = models.CharField(max_length=200, blank=True, null=True)
    precio_unitario = models.DecimalField(max_digits=10, decimal_places=2, blank=True, null=True)
    tiempo_entrega_dias = models.PositiveIntegerField(default=0, help_text="Días hábiles para entrega") # NUEVO: Crucial para gerencia
    especificaciones_tecnicas = models.TextField(blank=True)
    certificado_calidad_incluido = models.BooleanField(default=False)
    archivo_cotizacion = models.FileField(upload_to='cotizaciones/%Y/%m/%d/', blank=True, null=True) # ORGANIZACIÓN DIARIA
    
    estado_aprobacion = models.CharField(max_length=15, choices=ESTADOS_APROBACION, default='PENDIENTE')
    motivo_rechazo = models.TextField(blank=True)
    bodega_destino = models.ForeignKey(Bodega, on_delete=models.SET_NULL, null=True, blank=True)
    @property
    def total_estimado(self):
        if self.cantidad_requerida and self.precio_unitario:
            return self.cantidad_requerida * self.precio_unitario
        return 0

class OrdenCompra(models.Model):
    ESTADOS = [
        ('BORRADOR', 'Borrador (Cotizando)'),
        ('EMITIDA', 'Emitida al Proveedor'),
        ('EN_TRANSITO', 'En tránsito (Logística)'),
        ('RECIBIDA_PARCIAL', 'Recibida Parcialmente (Alerta Compras)'),
        ('RECIBIDA', 'Recibida Total (Stock Actualizado)'),
        ('CANCELADA', 'Cancelada'),
    ]

    folio = models.CharField(max_length=20, unique=True, blank=True, editable=False)
    proveedor = models.CharField(max_length=200, help_text="Nombre de la ferretería o distribuidor")
    fecha_creacion = models.DateTimeField(auto_now_add=True)
    creado_por = models.ForeignKey(User, on_delete=models.PROTECT, related_name='ordenes_compra')
    estado = models.CharField(max_length=25, choices=ESTADOS, default='BORRADOR')
    numero_factura = models.CharField(max_length=100, blank=True, null=True, verbose_name="N° de Factura")
    observaciones = models.TextField(blank=True, null=True, verbose_name="Observaciones")   
    
    documento_respaldo = models.FileField(
        upload_to='compras_facturas/%Y/%m/%d/', blank=True, null=True,
        validators=[FileExtensionValidator(allowed_extensions=['pdf', 'jpg', 'png'])],
        help_text="Factura o Certificado provisto por el proveedor"
    )

    history = HistoricalRecords()

    def save(self, *args, **kwargs):
        if not self.folio:
            year = datetime.date.today().year
            ultima_oc = OrdenCompra.objects.filter(folio__startswith=f'OC-{year}').order_by('id').last()
            secuencia = int(ultima_oc.folio.split('-')[-1]) + 1 if ultima_oc else 1
            self.folio = f'OC-{year}-{secuencia:03d}'
        super().save(*args, **kwargs)

    class Meta:
        verbose_name_plural = "Órdenes de Compra"

    def __str__(self):
        return f"{self.folio} - {self.proveedor} ({self.estado})"

    @property
    def total_general(self):
        """Suma el valor real (precio cotizado x cantidad pedida) de todas las líneas."""
        return sum((d.subtotal for d in self.detalles.all()), Decimal('0.00'))

    @property
    def cantidad_pendiente_total(self):
        return sum((d.cantidad_pendiente for d in self.detalles.all()), Decimal('0.00'))

    @property
    def esta_recibida_completa(self):
        return all(d.cantidad_recibida >= d.cantidad_pedida for d in self.detalles.all())

    def recalcular_estado_recepcion(self):
        """
        Único punto de verdad para decidir si la O.C. sigue Parcial o ya está
        Recibida al 100%. Se basa en TODAS las líneas, sin importar qué bodeguero
        haya registrado cada recepción.
        """
        if self.estado in ('BORRADOR', 'CANCELADA'):
            return
        self.estado = 'RECIBIDA' if self.esta_recibida_completa else 'RECIBIDA_PARCIAL'
        self.save(update_fields=['estado'])

class DetalleOrdenCompra(models.Model):
    orden = models.ForeignKey(OrdenCompra, related_name='detalles', on_delete=models.CASCADE)
    material = models.ForeignKey(Material, on_delete=models.PROTECT)
    cantidad_pedida = models.DecimalField(max_digits=10, decimal_places=2)
    cantidad_recibida = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    bodega_destino = models.ForeignKey(Bodega, on_delete=models.SET_NULL, null=True, blank=True)
    cotizacion_item_origen = models.ForeignKey(
        CotizacionItem, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='detalles_orden',
        help_text="Línea de cotización de la que nació esta línea de Orden de Compra (trazabilidad)."
    )

    def __str__(self):
        return f"{self.cantidad_pedida} de {self.material.nombre} (OC: {self.orden.folio})"

    @property
    def precio_unitario(self):
        if self.cotizacion_item_origen and self.cotizacion_item_origen.precio_unitario:
            return self.cotizacion_item_origen.precio_unitario
        return Decimal('0.00')

    @property
    def subtotal(self):
        return self.cantidad_pedida * self.precio_unitario

    @property
    def cantidad_pendiente(self):
        return self.cantidad_pedida - self.cantidad_recibida

    @property
    def solicitud_origen(self):
        return self.cotizacion_item_origen.solicitud if self.cotizacion_item_origen else None

    @property
    def requerimiento_origen(self):
        solicitud = self.solicitud_origen
        return solicitud.requerimiento_origen if solicitud else None

    @property
    def proyecto_origen(self):
        requerimiento = self.requerimiento_origen
        return requerimiento.proyecto if requerimiento else None

# =====================================================================
# 5. AUDITORÍA Y TRAZABILIDAD DE INVENTARIO LOGÍSTICO
# =====================================================================
class MovimientoInventario(models.Model):
    TIPO_MOVIMIENTO = [
        ('INGRESO', 'Ingreso por Compra (Abastecimiento)'),
        ('SALIDA', 'Salida por Requerimiento (Despacho)'),
        ('AJUSTE', 'Ajuste Manual de Inventario'),
        ('VENTA', 'Venta a Terceros'),
        ('TRANSFERENCIA', 'Transferencia entre Bodegas'),
        ('PRESTAMO', 'Préstamo a Trabajador'),
        ('DEVOLUCION_PRESTAMO', 'Devolución de Préstamo'),
    ]

    material = models.ForeignKey(Material, on_delete=models.PROTECT, related_name='movimientos')
    tipo = models.CharField(max_length=20, choices=TIPO_MOVIMIENTO)
    cantidad = models.DecimalField(max_digits=10, decimal_places=2)
    bodega_origen = models.ForeignKey(Bodega, on_delete=models.SET_NULL, null=True, blank=True, related_name='movimientos_salida')
    bodega_destino = models.ForeignKey(Bodega, on_delete=models.SET_NULL, null=True, blank=True, related_name='movimientos_ingreso')
    fecha_hora = models.DateTimeField(default=timezone.now)
    responsable = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    
    requerimiento_asociado = models.ForeignKey('Requerimiento', on_delete=models.SET_NULL, null=True, blank=True)
    orden_compra_asociada = models.ForeignKey('OrdenCompra', on_delete=models.SET_NULL, null=True, blank=True)
    observaciones = models.TextField(blank=True, null=True)
    
    certificado_calidad = models.FileField(
        upload_to='certificados/%Y/%m/%d/', blank=True, null=True,
        validators=[FileExtensionValidator(allowed_extensions=['pdf'])],
        help_text="Certificado de calidad subido por bodega"
    )

    history = HistoricalRecords()

    def __str__(self):
        return f"{self.tipo} - {self.cantidad} de {self.material.sku}"

    @property
    def proyecto_relacionado(self):
        """Proyecto para el que se despachó (SALIDA) o se compró (INGRESO) este material."""
        if self.tipo == 'SALIDA' and self.requerimiento_asociado:
            return self.requerimiento_asociado.proyecto
        if self.tipo == 'INGRESO' and self.orden_compra_asociada:
            detalle = self.orden_compra_asociada.detalles.filter(material=self.material).first()
            if detalle:
                return detalle.proyecto_origen
        return None

class PerfilEmpleado(models.Model):
    usuario = models.OneToOneField(User, on_delete=models.CASCADE, related_name='perfil')
    bodega_asignada = models.ForeignKey(Bodega, on_delete=models.SET_NULL, null=True, blank=True, help_text="Bodega sobre la cual el usuario tiene control logístico.")

    def __str__(self):
        return f"Perfil de {self.usuario.username}"

# =====================================================================
# 6. RECURSOS HUMANOS: TRABAJADORES DE CAMPO (RECEPTORES DE MATERIAL)
# =====================================================================
class Trabajador(models.Model):
    """
    Trabajador de obra/campo: recibe materiales, herramientas y maquinaria,
    y es sujeto de nómina (salario, horas extra, descuentos, pagos).

    Distinto de PerfilEmpleado: PerfilEmpleado es la cuenta de acceso al
    sistema (login) de un Administrador/Bodeguero/Compras/Solicitante. Un
    Trabajador puede o no tener también una cuenta de usuario del sistema.
    """
    ESTADOS = [
        ('ACTIVO', 'Activo'),
        ('INACTIVO', 'Inactivo / Anterior'),
    ]
    PERIODICIDADES = [
        ('MENSUAL', 'Mensual'),
        ('QUINCENAL', 'Quincenal'),
        ('SEMANAL', 'Semanal'),
    ]

    nombres = models.CharField(max_length=100)
    apellidos = models.CharField(max_length=100)
    documento_identidad = models.CharField(max_length=20, unique=True, help_text="Cédula o documento de identidad")
    cargo = models.CharField(max_length=100, blank=True)
    telefono = models.CharField(max_length=20, blank=True)
    estado = models.CharField(max_length=10, choices=ESTADOS, default='ACTIVO')
    fecha_ingreso = models.DateField(default=timezone.localdate)
    fecha_salida = models.DateField(null=True, blank=True)
    motivo_salida = models.TextField(blank=True)
    periodicidad_pago = models.CharField(max_length=10, choices=PERIODICIDADES, default='MENSUAL')
    fecha_creacion = models.DateTimeField(auto_now_add=True)

    history = HistoricalRecords()

    class Meta:
        ordering = ['apellidos', 'nombres']
        verbose_name_plural = "Trabajadores"

    def __str__(self):
        return f"{self.nombres} {self.apellidos}"

    def clean(self):
        if self.fecha_salida and self.fecha_ingreso and self.fecha_salida < self.fecha_ingreso:
            raise ValidationError("La fecha de salida no puede ser anterior a la fecha de ingreso.")

    @property
    def nombre_completo(self):
        return f"{self.nombres} {self.apellidos}"

    @property
    def salario_actual(self):
        return self.salarios.filter(fecha_fin_vigencia__isnull=True).order_by('-fecha_inicio_vigencia').first()

    @property
    def tiene_prestamos_pendientes(self):
        return self.prestamos.filter(estado='PRESTADO').exists()

    def desactivar(self, motivo=''):
        if self.estado == 'INACTIVO':
            raise ValueError("El trabajador ya está inactivo.")
        self.estado = 'INACTIVO'
        self.fecha_salida = timezone.localdate()
        self.motivo_salida = (motivo or '').strip()
        self.full_clean()
        self.save()

    def reactivar(self):
        if self.estado == 'ACTIVO':
            raise ValueError("El trabajador ya está activo.")
        self.estado = 'ACTIVO'
        self.fecha_salida = None
        self.motivo_salida = ''
        self.save()

    @transaction.atomic
    def asignar_salario(self, monto, fecha_inicio_vigencia, usuario):
        """
        Cierra la vigencia del salario anterior (si existe) y crea uno nuevo.
        Nunca sobrescribe ni borra el registro anterior: los pagos ya
        generados siguen mostrando el salario que tenían en su momento.
        """
        if monto is None or monto <= 0:
            raise ValueError("El salario debe ser un monto mayor a cero.")

        actual = self.salario_actual
        if actual:
            if fecha_inicio_vigencia <= actual.fecha_inicio_vigencia:
                raise ValueError("La nueva vigencia debe ser posterior a la del salario actualmente vigente.")
            actual.fecha_fin_vigencia = fecha_inicio_vigencia - datetime.timedelta(days=1)
            actual.save(update_fields=['fecha_fin_vigencia'])

        return SalarioTrabajador.objects.create(
            trabajador=self, monto=monto,
            fecha_inicio_vigencia=fecha_inicio_vigencia, creado_por=usuario,
        )

    @transaction.atomic
    def registrar_pago(self, periodo_inicio, periodo_fin, fecha_pago, usuario,
                        dias_laborados=None, horas_extra_ids=None, descuento_ids=None,
                        periodo_mensual=None, observaciones=''):
        """
        Genera un pago con desglose transparente, replicando la lógica real
        del rol de pagos de la empresa:

            Salario del periodo + Horas Extra + Bonificación (mitad del mes)
            - Descuentos - Anticipos - Aporte IESS (mitad del mes)

        Si `periodicidad_pago` es QUINCENAL/SEMANAL, el salario del periodo
        se prorratea por días laborados (Valor Día = Sueldo Mensual / 30).
        Si es MENSUAL, se paga el sueldo completo.

        `periodo_mensual` (un PeriodoNominaMensual) aporta la Bonificación y
        el Aporte IESS mensuales; el sistema registra automáticamente la
        MITAD de cada uno en este pago (igual que el Excel de la empresa).

        Es transaccional y evita duplicar el pago de un mismo periodo.
        """
        if periodo_fin < periodo_inicio:
            raise ValueError("El periodo de pago es inválido (la fecha final es anterior a la inicial).")

        if Pago.objects.filter(trabajador=self, periodo_inicio=periodo_inicio, periodo_fin=periodo_fin).exists():
            raise ValueError("Ya existe un pago registrado para este trabajador en ese periodo.")

        salario_vigente = self.salario_actual
        if not salario_vigente:
            raise ValueError("El trabajador no tiene un salario asignado todavía.")

        dias_calendario = (periodo_fin - periodo_inicio).days + 1
        if dias_laborados is None:
            dias_laborados = Decimal(dias_calendario)
        dias_laborados = Decimal(dias_laborados)
        if dias_laborados <= 0:
            raise ValueError("Los días laborados deben ser mayores a cero.")

        if self.periodicidad_pago == 'MENSUAL':
            salario_periodo = salario_vigente.monto
        else:
            valor_dia = salario_vigente.monto / Decimal('30')
            salario_periodo = (valor_dia * dias_laborados).quantize(Decimal('0.01'))

        horas = HoraExtra.objects.select_for_update().filter(
            id__in=(horas_extra_ids or []), trabajador=self, pago__isnull=True
        )
        descuentos = Descuento.objects.select_for_update().filter(
            id__in=(descuento_ids or []), trabajador=self, pago__isnull=True
        )
        descuentos_lista = list(descuentos)

        total_horas_extras = sum((h.valor_calculado or Decimal('0.00')) for h in horas) or Decimal('0.00')
        total_descuentos = sum(
            (d.monto for d in descuentos_lista if d.tipo == 'DESCUENTO'), Decimal('0.00')
        )
        total_anticipos = sum(
            (d.monto for d in descuentos_lista if d.tipo == 'ANTICIPO'), Decimal('0.00')
        )

        bonificacion = Decimal('0.00')
        aporte_iess = Decimal('0.00')
        if periodo_mensual is not None:
            if periodo_mensual.trabajador_id != self.id:
                raise ValueError("El periodo mensual seleccionado no corresponde a este trabajador.")
            bonificacion = periodo_mensual.bonificacion_quincenal
            aporte_iess = periodo_mensual.aporte_iess_quincenal

        total_pagado = salario_periodo + total_horas_extras + bonificacion - total_descuentos - total_anticipos - aporte_iess

        if total_pagado < 0:
            raise ValueError("El total a pagar no puede quedar negativo. Revisa los descuentos/anticipos ingresados.")

        pago = Pago.objects.create(
            trabajador=self, periodo_inicio=periodo_inicio, periodo_fin=periodo_fin, fecha_pago=fecha_pago,
            dias_laborados=dias_laborados, salario_base=salario_periodo,
            bonificacion=bonificacion, aporte_iess=aporte_iess,
            total_horas_extras=total_horas_extras, total_descuentos=total_descuentos,
            total_anticipos=total_anticipos, total_pagado=total_pagado,
            periodo_mensual=periodo_mensual, observaciones=observaciones, registrado_por=usuario,
        )
        horas.update(pago=pago)
        descuentos.update(pago=pago)
        return pago


class EntregaDirecta(models.Model):
    """
    Detalle de una entrega directa/urgente de bodega a un trabajador.
    Vinculada 1 a 1 con su MovimientoInventario (tipo SALIDA) para dejar
    la trazabilidad completa: Movimiento -> Entrega Directa -> Trabajador ->
    Material -> Justificativo, consultable desde Auditoría.
    """
    movimiento = models.OneToOneField(MovimientoInventario, on_delete=models.CASCADE, related_name='entrega_directa')
    trabajador = models.ForeignKey(Trabajador, on_delete=models.PROTECT, related_name='entregas_directas')
    proyecto = models.ForeignKey(Proyecto, on_delete=models.SET_NULL, null=True, blank=True)
    justificativo = models.TextField()

    def __str__(self):
        return f"Entrega directa a {self.trabajador} - {self.movimiento.material.nombre}"


# =====================================================================
# 7. PRÉSTAMOS DE HERRAMIENTAS/MATERIALES/MAQUINARIA A TRABAJADORES
# =====================================================================
class PrestamoHerramienta(models.Model):
    ESTADOS = [
        ('PRESTADO', 'Prestado / Pendiente de Devolución'),
        ('DEVUELTO', 'Devuelto'),
    ]

    trabajador = models.ForeignKey(Trabajador, on_delete=models.PROTECT, related_name='prestamos')
    material = models.ForeignKey(Material, on_delete=models.PROTECT, related_name='prestamos')
    bodega_origen = models.ForeignKey(Bodega, on_delete=models.PROTECT, related_name='prestamos_entregados')
    cantidad = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('1.00'))
    fecha_entrega = models.DateTimeField(default=timezone.now)
    entregado_por = models.ForeignKey(User, on_delete=models.PROTECT, related_name='prestamos_entregados')
    observaciones = models.TextField(blank=True)
    estado = models.CharField(max_length=10, choices=ESTADOS, default='PRESTADO')
    movimiento_salida = models.OneToOneField(
        MovimientoInventario, on_delete=models.SET_NULL, null=True, blank=True, related_name='prestamo_origen'
    )

    history = HistoricalRecords()

    class Meta:
        ordering = ['-fecha_entrega']

    def __str__(self):
        return f"{self.material.nombre} -> {self.trabajador} ({self.get_estado_display()})"

    @property
    def esta_devuelto(self):
        return self.estado == 'DEVUELTO'

    @transaction.atomic
    def registrar_devolucion(self, usuario, condicion, observaciones=''):
        if self.estado == 'DEVUELTO':
            raise ValueError("Este préstamo ya fue devuelto anteriormente.")

        material = Material.objects.select_for_update().get(id=self.material_id)
        stock_bodega, _ = StockBodega.objects.select_for_update().get_or_create(
            material=material, bodega=self.bodega_origen, defaults={'cantidad': Decimal('0.00')}
        )
        stock_bodega.cantidad = (stock_bodega.cantidad or Decimal('0.00')) + self.cantidad
        stock_bodega.save()
        material.save()

        movimiento = MovimientoInventario.objects.create(
            material=material, tipo='DEVOLUCION_PRESTAMO', cantidad=self.cantidad,
            bodega_destino=self.bodega_origen, responsable=usuario,
            observaciones=f"Devolución de préstamo a {self.trabajador.nombre_completo}"
        )

        self.estado = 'DEVUELTO'
        self.save(update_fields=['estado'])

        return DevolucionPrestamo.objects.create(
            prestamo=self, recibido_por=usuario, condicion=condicion,
            observaciones=(observaciones or '').strip(), movimiento_ingreso=movimiento,
        )


class DevolucionPrestamo(models.Model):
    CONDICIONES = [
        ('BUEN_ESTADO', 'Buenas condiciones'),
        ('CON_OBSERVACIONES', 'Con observaciones / daños'),
    ]

    prestamo = models.OneToOneField(PrestamoHerramienta, on_delete=models.CASCADE, related_name='devolucion')
    fecha_devolucion = models.DateTimeField(default=timezone.now)
    recibido_por = models.ForeignKey(User, on_delete=models.PROTECT, related_name='devoluciones_recibidas')
    condicion = models.CharField(max_length=20, choices=CONDICIONES, default='BUEN_ESTADO')
    observaciones = models.TextField(blank=True)
    movimiento_ingreso = models.OneToOneField(
        MovimientoInventario, on_delete=models.SET_NULL, null=True, blank=True, related_name='devolucion_prestamo'
    )

    def __str__(self):
        return f"Devolución de {self.prestamo}"


# =====================================================================
# 8. NÓMINA: SALARIOS, HORARIO, HORAS EXTRA, DESCUENTOS Y PAGOS
# =====================================================================
class SalarioTrabajador(models.Model):
    """
    Historial de salarios de un trabajador. Nunca se edita/sobrescribe un
    registro existente: para cambiar el salario se cierra la vigencia
    anterior y se crea uno nuevo (ver Trabajador.asignar_salario).
    """
    trabajador = models.ForeignKey(Trabajador, on_delete=models.CASCADE, related_name='salarios')
    monto = models.DecimalField(max_digits=10, decimal_places=2)
    fecha_inicio_vigencia = models.DateField(default=timezone.localdate)
    fecha_fin_vigencia = models.DateField(null=True, blank=True, help_text="Vacío = salario vigente actual")
    creado_por = models.ForeignKey(User, on_delete=models.PROTECT, related_name='salarios_registrados')
    fecha_creacion = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-fecha_inicio_vigencia']

    def __str__(self):
        return f"{self.trabajador} - ${self.monto} desde {self.fecha_inicio_vigencia}"

    @property
    def esta_vigente(self):
        return self.fecha_fin_vigencia is None


class HorarioTrabajador(models.Model):
    """Horario normal de trabajo de un trabajador (para cálculo/validación de horas)."""
    trabajador = models.OneToOneField(Trabajador, on_delete=models.CASCADE, related_name='horario')
    hora_inicio = models.TimeField()
    hora_fin = models.TimeField()
    actualizado_por = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    fecha_actualizacion = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Horario de {self.trabajador}: {self.hora_inicio} - {self.hora_fin}"


class ConfiguracionHorasExtra(models.Model):
    """
    Configuración global (fila única) de los rangos horarios que definen
    cuándo una hora trabajada cuenta como extra ordinaria o extraordinaria.
    """
    hora_inicio_ordinaria = models.TimeField()
    hora_fin_ordinaria = models.TimeField()
    hora_inicio_extraordinaria = models.TimeField()
    hora_fin_extraordinaria = models.TimeField()
    actualizado_por = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    fecha_actualizacion = models.DateTimeField(auto_now=True)

    def __str__(self):
        return "Configuración de Horas Extra"

    @classmethod
    def obtener(cls):
        config, _ = cls.objects.get_or_create(pk=1, defaults={
            'hora_inicio_ordinaria': datetime.time(18, 0),
            'hora_fin_ordinaria': datetime.time(22, 0),
            'hora_inicio_extraordinaria': datetime.time(22, 0),
            'hora_fin_extraordinaria': datetime.time(6, 0),
        })
        return config


class PeriodoNominaMensual(models.Model):
    """
    Bonificación y Aporte IESS del MES completo de un trabajador. Replica el
    Excel de nómina de la empresa: estos valores se registran una sola vez
    al mes y el sistema aplica automáticamente la MITAD de cada uno en cada
    Pago quincenal de ese mes (ver Trabajador.registrar_pago).
    """
    trabajador = models.ForeignKey(Trabajador, on_delete=models.CASCADE, related_name='periodos_mensuales')
    anio = models.PositiveIntegerField()
    mes = models.PositiveSmallIntegerField(help_text="1 = Enero ... 12 = Diciembre")
    bonificacion = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    aporte_iess = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    registrado_por = models.ForeignKey(User, on_delete=models.PROTECT, related_name='periodos_nomina_registrados')
    fecha_registro = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-anio', '-mes']
        constraints = [
            models.UniqueConstraint(fields=['trabajador', 'anio', 'mes'], name='unico_periodo_mensual_por_trabajador')
        ]

    def __str__(self):
        return f"{self.trabajador} - {self.mes}/{self.anio}"

    def clean(self):
        if self.mes and not (1 <= self.mes <= 12):
            raise ValidationError("El mes debe estar entre 1 y 12.")
        if self.bonificacion is not None and self.bonificacion < 0:
            raise ValidationError("La bonificación no puede ser negativa.")
        if self.aporte_iess is not None and self.aporte_iess < 0:
            raise ValidationError("El aporte IESS no puede ser negativo.")

    @property
    def bonificacion_quincenal(self):
        return (self.bonificacion / 2).quantize(Decimal('0.01'))

    @property
    def aporte_iess_quincenal(self):
        return (self.aporte_iess / 2).quantize(Decimal('0.01'))


class Pago(models.Model):
    """
    Pago de nómina de un periodo (quincena, semana o mes según la
    periodicidad del trabajador). Guarda todos los componentes COMO
    SNAPSHOT (no referencias vivas) para que cambios posteriores de salario,
    bonificación o IESS nunca alteren el histórico de pagos ya generados.

    Total = salario_base + total_horas_extras + bonificacion
            - total_descuentos - total_anticipos - aporte_iess
    """
    trabajador = models.ForeignKey(Trabajador, on_delete=models.PROTECT, related_name='pagos')
    periodo_inicio = models.DateField()
    periodo_fin = models.DateField()
    fecha_pago = models.DateField(default=timezone.localdate)
    dias_laborados = models.DecimalField(max_digits=5, decimal_places=2, default=Decimal('15.00'))
    salario_base = models.DecimalField(max_digits=10, decimal_places=2)
    bonificacion = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    aporte_iess = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    total_horas_extras = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    total_descuentos = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    total_anticipos = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    total_pagado = models.DecimalField(max_digits=10, decimal_places=2)
    periodo_mensual = models.ForeignKey(
        PeriodoNominaMensual, on_delete=models.SET_NULL, null=True, blank=True, related_name='pagos'
    )
    observaciones = models.TextField(blank=True)
    registrado_por = models.ForeignKey(User, on_delete=models.PROTECT, related_name='pagos_registrados')
    fecha_registro = models.DateTimeField(auto_now_add=True)

    history = HistoricalRecords()

    class Meta:
        ordering = ['-periodo_fin']
        constraints = [
            models.UniqueConstraint(fields=['trabajador', 'periodo_inicio', 'periodo_fin'], name='unico_pago_por_periodo')
        ]

    def __str__(self):
        return f"Pago {self.trabajador} [{self.periodo_inicio} - {self.periodo_fin}]"


class HoraExtra(models.Model):
    TIPOS = [
        ('ORDINARIA', 'Ordinaria'),
        ('EXTRAORDINARIA', 'Extraordinaria'),
    ]

    trabajador = models.ForeignKey(Trabajador, on_delete=models.CASCADE, related_name='horas_extras')
    fecha = models.DateField()
    tipo = models.CharField(max_length=15, choices=TIPOS)
    cantidad_horas = models.DecimalField(max_digits=5, decimal_places=2)
    valor_calculado = models.DecimalField(
        max_digits=10, decimal_places=2, null=True, blank=True,
        help_text="Pendiente hasta integrar la fórmula oficial de cálculo de horas extra."
    )
    observaciones = models.TextField(blank=True)
    registrado_por = models.ForeignKey(User, on_delete=models.PROTECT, related_name='horas_extras_registradas')
    fecha_registro = models.DateTimeField(auto_now_add=True)
    pago = models.ForeignKey(Pago, on_delete=models.SET_NULL, null=True, blank=True, related_name='horas_extras_incluidas')

    class Meta:
        ordering = ['-fecha']
        verbose_name_plural = "Horas Extra"

    def __str__(self):
        return f"{self.cantidad_horas}h {self.tipo} - {self.trabajador} ({self.fecha})"

    def clean(self):
        if self.cantidad_horas is not None and self.cantidad_horas <= 0:
            raise ValidationError("Las horas extra deben ser mayores a cero.")
        if self.cantidad_horas is not None and self.cantidad_horas > 24:
            raise ValidationError("No es posible registrar más de 24 horas extra en un mismo día.")


class Descuento(models.Model):
    """
    Descuento o Anticipo aplicado al pago de un trabajador. El Excel de
    nómina de la empresa lleva ambos como categorías separadas (mismo
    registro de motivo/monto/fecha), por eso se distinguen aquí con `tipo`
    en vez de duplicar el modelo.
    """
    TIPOS = [
        ('DESCUENTO', 'Descuento (multa, atraso, etc.)'),
        ('ANTICIPO', 'Anticipo (adelanto de dinero)'),
    ]

    trabajador = models.ForeignKey(Trabajador, on_delete=models.CASCADE, related_name='descuentos')
    tipo = models.CharField(max_length=10, choices=TIPOS, default='DESCUENTO')
    motivo = models.CharField(max_length=200)
    monto = models.DecimalField(max_digits=10, decimal_places=2)
    fecha = models.DateField(default=timezone.localdate)
    observaciones = models.TextField(blank=True)
    registrado_por = models.ForeignKey(User, on_delete=models.PROTECT, related_name='descuentos_registrados')
    fecha_registro = models.DateTimeField(auto_now_add=True)
    pago = models.ForeignKey(Pago, on_delete=models.SET_NULL, null=True, blank=True, related_name='descuentos_incluidos')

    class Meta:
        ordering = ['-fecha']

    def __str__(self):
        return f"{self.get_tipo_display()} {self.monto} a {self.trabajador} ({self.motivo})"

    def clean(self):
        if self.monto is not None and self.monto <= 0:
            raise ValidationError("El monto debe ser mayor a cero.")