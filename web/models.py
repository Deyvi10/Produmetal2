from django.db import models
from django.contrib.auth.models import User
from django.core.validators import FileExtensionValidator
from django.utils import timezone
import datetime

# =====================================================================
# NUEVO: SOPORTE MULTIBODEGA Y SUBCATEGORÍAS
# =====================================================================
class Bodega(models.Model):
    nombre = models.CharField(max_length=100, unique=True)
    ubicacion = models.CharField(max_length=200, blank=True, null=True)
    is_principal = models.BooleanField(default=False, help_text="¿Es la bodega central?")
    
    def __str__(self):
        return self.nombre

class SubCategoria(models.Model):
    # Relacionado al TIPO_CATEGORIA de Material
    categoria_padre = models.CharField(max_length=20, choices=[('MATERIAL', 'Material Estructural / Acero'), ('CONSUMIBLE', 'Consumible / Herramienta Menor')])
    nombre = models.CharField(max_length=100)

    def __str__(self):
        return f"{self.get_categoria_padre_display()} -> {self.nombre}"

# 1. Modelo de Proyectos (ACTUALIZADO: Descripción y Bodega asociada)
class Proyecto(models.Model):
    nombre = models.CharField(max_length=200)
    centro_costos = models.CharField(max_length=100, unique=True)
    descripcion = models.TextField(blank=True, null=True, verbose_name="Descripción del Proyecto") # NUEVO
    is_active = models.BooleanField(default=True, help_text="Desmarcar para borrado lógico")
    fecha_creacion = models.DateTimeField(auto_now_add=True)
    
    # NUEVO: Cada proyecto puede tener su propia bodega física temporal
    bodega_proyecto = models.OneToOneField(Bodega, on_delete=models.SET_NULL, null=True, blank=True, related_name='proyecto_asociado')

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

# 2. Catálogo de Inventario (ACTUALIZADO: Auto-Código y Subcategoría)
class Material(models.Model):
    TIPO_CATEGORIA = [
        ('MATERIAL', 'Material Estructural / Acero'),
        ('CONSUMIBLE', 'Consumible / Herramienta Menor'),
    ]

    sku = models.CharField(max_length=50, unique=True, blank=True, editable=False, verbose_name="Código/SKU") # AUTO
    nombre = models.CharField(max_length=200)
    tipo = models.CharField(max_length=20, choices=TIPO_CATEGORIA, default='MATERIAL')
    subcategoria = models.ForeignKey(SubCategoria, on_delete=models.SET_NULL, null=True, blank=True) # NUEVO
    descripcion = models.TextField(blank=True, null=True)
    stock_actual = models.DecimalField(max_digits=10, decimal_places=2, default=0.00, help_text="Stock Total (Suma de bodegas)")
    stock_minimo = models.DecimalField(max_digits=10, decimal_places=2, default=5.00, help_text="Umbral para alertas")
    is_active = models.BooleanField(default=True)

    class Meta:
        verbose_name_plural = "Inventario (Materiales y Consumibles)"

    def save(self, *args, **kwargs):
        # GENERACIÓN AUTOMÁTICA DE CÓDIGO
        if not self.sku:
            prefijo = 'MAT' if self.tipo == 'MATERIAL' else 'CON'
            ultimo = Material.objects.filter(sku__startswith=prefijo).order_by('id').last()
            if ultimo and '-' in ultimo.sku:
                try:
                    secuencia = int(ultimo.sku.split('-')[-1]) + 1
                except ValueError:
                    secuencia = 1
            else:
                secuencia = 1
            self.sku = f'{prefijo}-{secuencia:04d}'
        super().save(*args, **kwargs)

    def __str__(self):
        return f"[{self.sku}] {self.nombre} (Total: {self.stock_actual})"

# NUEVO: Control exacto por bodega
class StockBodega(models.Model):
    material = models.ForeignKey(Material, on_delete=models.CASCADE, related_name='stocks_bodegas')
    bodega = models.ForeignKey(Bodega, on_delete=models.CASCADE, related_name='inventario')
    cantidad = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)

    class Meta:
        unique_together = ('material', 'bodega')

    def __str__(self):
        return f"{self.material.sku} en {self.bodega.nombre}: {self.cantidad}"

# =====================================================================
# MÓDULO DE ABASTECIMIENTO Y COMPRAS (ACTUALIZADO: Alertas Parciales)
# =====================================================================
class OrdenCompra(models.Model):
    ESTADOS = [
        ('BORRADOR', 'Borrador (Cotizando)'),
        ('EMITIDA', 'Emitida al Proveedor'),
        ('RECIBIDA_PARCIAL', 'Recibida Parcialmente (Alerta Compras)'), # NUEVO
        ('RECIBIDA', 'Recibida Total (Stock Actualizado)'),
        ('CANCELADA', 'Cancelada'),
    ]

    folio = models.CharField(max_length=20, unique=True, blank=True, editable=False)
    proveedor = models.CharField(max_length=200, help_text="Nombre de la ferretería o distribuidor")
    fecha_creacion = models.DateTimeField(auto_now_add=True)
    creado_por = models.ForeignKey(User, on_delete=models.PROTECT, related_name='ordenes_compra')
    estado = models.CharField(max_length=20, choices=ESTADOS, default='BORRADOR')
    numero_factura = models.CharField(max_length=100, blank=True, null=True, verbose_name="N° de Factura")
    observaciones = models.TextField(blank=True, null=True, verbose_name="Observaciones")   
    
    # Soporte Documental Compras (Facturas/Certificados origen)
    documento_respaldo = models.FileField(
        upload_to='compras_facturas/%Y/%m/', blank=True, null=True,
        validators=[FileExtensionValidator(allowed_extensions=['pdf', 'jpg', 'png'])],
        help_text="Factura o Certificado provisto por el proveedor"
    )

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
# MÓDULO DE REQUERIMIENTOS INTERNOS 
# =====================================================================
class Requerimiento(models.Model):
    ESTADOS = [
        ('PENDIENTE', 'Pendiente de Aprobación'),
        ('APROBADO', 'Aprobado'),
        ('RECHAZADO', 'Rechazado'),
        ('DESPACHADO', 'Despachado'),
        ('EN_COMPRAS', 'Enviado a Compras'),
    ]

    folio = models.CharField(max_length=20, unique=True, blank=True, editable=False)
    solicitante = models.ForeignKey(User, on_delete=models.PROTECT, related_name='requerimientos')
    proyecto = models.ForeignKey(Proyecto, on_delete=models.PROTECT)
    fecha_solicitud = models.DateTimeField(auto_now_add=True)
    estado = models.CharField(max_length=20, choices=ESTADOS, default='PENDIENTE')
    observaciones = models.TextField(blank=True)

    def save(self, *args, **kwargs):
        if not self.folio:
            year = datetime.date.today().year
            ultimo_req = Requerimiento.objects.filter(folio__startswith=f'REQ-{year}').order_by('id').last()
            secuencia = int(ultimo_req.folio.split('-')[-1]) + 1 if ultimo_req else 1
            self.folio = f'REQ-{year}-{secuencia:03d}'
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.folio} - {self.proyecto.nombre}"

class DetalleRequerimiento(models.Model):
    ESTADOS_ITEM = [
        ('PENDIENTE', 'Pendiente de Revisión'),
        ('APROBADO_BODEGA', 'Aprobado para Despacho en Bodega'),
        ('EN_COMPRAS', 'Mandar a Compras (Falta Stock)'),
        ('RECHAZADO', 'Rechazado'),
    ]

    requerimiento = models.ForeignKey(Requerimiento, related_name='detalles', on_delete=models.CASCADE)
    material = models.ForeignKey(Material, on_delete=models.PROTECT)
    cantidad_solicitada = models.DecimalField(max_digits=10, decimal_places=2)
    cantidad_despachada = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    
    # NUEVOS CAMPOS PARA EL CONTROL DE FLUJO GRANULAR
    estado_item = models.CharField(max_length=20, choices=ESTADOS_ITEM, default='PENDIENTE')
    motivo_rechazo = models.TextField(blank=True, null=True, verbose_name="Notas u Observaciones")

    def __str__(self):
        return f"{self.cantidad_solicitada} x {self.material.nombre} [{self.estado_item}]"

        
# =====================================================================
# AUDITORÍA Y TRAZABILIDAD (ACTUALIZADO: Bodegas, Ventas, Transferencias)
# =====================================================================
class MovimientoInventario(models.Model):
    TIPO_MOVIMIENTO = [
        ('INGRESO', 'Ingreso por Compra (Abastecimiento)'),
        ('SALIDA', 'Salida por Requerimiento (Despacho)'),
        ('AJUSTE', 'Ajuste Manual de Inventario'),
        ('VENTA', 'Venta a Terceros'), # NUEVO REQUERIMIENTO
        ('TRANSFERENCIA', 'Transferencia entre Bodegas'), # NUEVO REQUERIMIENTO
    ]

    material = models.ForeignKey(Material, on_delete=models.PROTECT, related_name='movimientos')
    tipo = models.CharField(max_length=15, choices=TIPO_MOVIMIENTO)
    cantidad = models.DecimalField(max_digits=10, decimal_places=2)
    bodega_origen = models.ForeignKey(Bodega, on_delete=models.SET_NULL, null=True, blank=True, related_name='movimientos_salida')
    bodega_destino = models.ForeignKey(Bodega, on_delete=models.SET_NULL, null=True, blank=True, related_name='movimientos_ingreso')
    fecha_hora = models.DateTimeField(default=timezone.now)
    responsable = models.ForeignKey(User, on_delete=models.PROTECT)
    
    requerimiento_asociado = models.ForeignKey('Requerimiento', on_delete=models.SET_NULL, null=True, blank=True)
    orden_compra_asociada = models.ForeignKey('OrdenCompra', on_delete=models.SET_NULL, null=True, blank=True)
    
    observaciones = models.TextField(blank=True, null=True)
    
    # Certificado subido por Bodega al momento de la recepción física
    certificado_calidad = models.FileField(
        upload_to='certificados/%Y/%m/', blank=True, null=True,
        validators=[FileExtensionValidator(allowed_extensions=['pdf'])],
        help_text="Certificado de calidad subido por bodega"
    )

    def __str__(self):
        return f"{self.tipo} - {self.cantidad} de {self.material.sku}"

# =====================================================================
# MÓDULO DE COTIZACIONES Y COMPRAS (Flujo de desglose)
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
        ('COMPRADO', 'Órden de Compra Generada'), # <-- NUEVO: Evita duplicados en revisiones parciales
        ('RECHAZADO', 'Rechazado'),
    ]

    solicitud = models.ForeignKey(SolicitudCompra, related_name='items_cotizados', on_delete=models.CASCADE)
    material = models.ForeignKey(Material, on_delete=models.PROTECT) 
    cantidad_requerida = models.DecimalField(max_digits=10, decimal_places=2)
    
    proveedor_cotizado = models.CharField(max_length=200, blank=True, null=True)
    precio_unitario = models.DecimalField(max_digits=10, decimal_places=2, blank=True, null=True)
    especificaciones_tecnicas = models.TextField(blank=True)
    certificado_calidad_incluido = models.BooleanField(default=False)
    archivo_cotizacion = models.FileField(upload_to='cotizaciones/%Y/%m/', blank=True, null=True)
    
    estado_aprobacion = models.CharField(max_length=15, choices=ESTADOS_APROBACION, default='PENDIENTE')
    motivo_rechazo = models.TextField(blank=True)

    # <-- NUEVO: Cálculo automático para la vista del Administrador
    @property
    def total_estimado(self):
        if self.cantidad_requerida and self.precio_unitario:
            return self.cantidad_requerida * self.precio_unitario
        return 0