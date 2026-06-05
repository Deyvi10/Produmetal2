from django.db import models, transaction
from django.contrib.auth.models import User
from django.core.validators import FileExtensionValidator
from django.utils import timezone
from simple_history.models import HistoricalRecords
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
        """ LÓGICA CORE: Ejecutar cuando el Admin aprueba el requerimiento """
        for detalle in self.detalles.all():
            if detalle.estado_item == 'RECHAZADO':
                continue

            # select_for_update() asegura que nadie mueva el stock mientras calculamos
            material = Material.objects.select_for_update().get(id=detalle.material.id)
            
            if material.stock_actual >= detalle.cantidad_solicitada:
                # Stock suficiente: Todo a bodega
                detalle.estado_item = 'APROBADO_BODEGA'
                detalle.save()
            elif material.stock_actual > 0:
                # Stock parcial: DIVIDIR EL REQUERIMIENTO
                cantidad_en_bodega = material.stock_actual
                cantidad_faltante = detalle.cantidad_solicitada - cantidad_en_bodega
                
                detalle.cantidad_solicitada = cantidad_en_bodega
                detalle.estado_item = 'APROBADO_BODEGA'
                detalle.save()
                
                # Crear el excedente directamente para Compras
                DetalleRequerimiento.objects.create(
                    requerimiento=self,
                    material=material,
                    cantidad_solicitada=cantidad_faltante,
                    estado_item='EN_COMPRAS',
                    motivo_rechazo='División automática por sistema (Falta de stock)'
                )
            else:
                # Sin stock: Todo a compras
                detalle.estado_item = 'EN_COMPRAS'
                detalle.save()

    def __str__(self):
        return f"{self.folio} - {self.proyecto.nombre}"

class DetalleRequerimiento(models.Model):
    ESTADOS_ITEM = [
        ('PENDIENTE', 'Pendiente de Revisión'),
        ('APROBADO_BODEGA', 'Aprobado para Despacho (Bodega)'),
        ('EN_COMPRAS', 'Mandar a Compras (Falta Stock)'),
        ('RECHAZADO', 'Rechazado'),
    ]

    requerimiento = models.ForeignKey(Requerimiento, related_name='detalles', on_delete=models.CASCADE)
    material = models.ForeignKey(Material, on_delete=models.PROTECT)
    cantidad_solicitada = models.DecimalField(max_digits=10, decimal_places=2)
    cantidad_despachada = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    estado_item = models.CharField(max_length=30, choices=ESTADOS_ITEM, default='PENDIENTE')
    motivo_rechazo = models.TextField(blank=True, null=True, verbose_name="Notas u Observaciones")

    def __str__(self):
        return f"{self.cantidad_solicitada} x {self.material.nombre} [{self.estado_item}]"

# =====================================================================
# 4. MÓDULO DE COTIZACIONES Y COMPRAS
# =====================================================================
class SolicitudCompra(models.Model):
    ESTADOS = [
        ('ENVIADO_A_COMPRAS', 'Pendiente de Cotización (En Compras)'),
        ('COTIZADO', 'Cotizado (Esperando Aprobación Admin)'),
        ('PROCESADO', 'Procesado (Órdenes Generadas / Rechazados)'),
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

class DetalleOrdenCompra(models.Model):
    orden = models.ForeignKey(OrdenCompra, related_name='detalles', on_delete=models.CASCADE)
    material = models.ForeignKey(Material, on_delete=models.PROTECT)
    cantidad_pedida = models.DecimalField(max_digits=10, decimal_places=2)
    cantidad_recibida = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)

    def __str__(self):
        return f"{self.cantidad_pedida} de {self.material.nombre} (OC: {self.orden.folio})"

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
    ]

    material = models.ForeignKey(Material, on_delete=models.PROTECT, related_name='movimientos')
    tipo = models.CharField(max_length=15, choices=TIPO_MOVIMIENTO)
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
    
class PerfilEmpleado(models.Model):
    usuario = models.OneToOneField(User, on_delete=models.CASCADE, related_name='perfil')
    bodega_asignada = models.ForeignKey(Bodega, on_delete=models.SET_NULL, null=True, blank=True, help_text="Bodega sobre la cual el usuario tiene control logístico.")
    
    def __str__(self):
        return f"Perfil de {self.usuario.username}"