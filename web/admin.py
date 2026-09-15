from django.contrib import admin
from .models import (
    Proyecto, Material, Requerimiento, DetalleRequerimiento,
    MovimientoInventario, OrdenCompra, DetalleOrdenCompra, CierreIncompletoRequerimiento,
    Trabajador, EntregaDirecta, PrestamoHerramienta, DevolucionPrestamo,
    SalarioTrabajador, HorarioTrabajador, ConfiguracionHorasExtra, Pago, HoraExtra, Descuento,
    PeriodoNominaMensual,
)
from django.contrib.auth.admin import UserAdmin
from django.contrib.auth.models import User
from .models import PerfilEmpleado

# =====================================================================
# 1. PROYECTOS
# =====================================================================
@admin.register(Proyecto)
class ProyectoAdmin(admin.ModelAdmin):
    list_display = ('centro_costos', 'nombre', 'is_active', 'fecha_creacion')
    list_filter = ('is_active',)
    search_fields = ('nombre', 'centro_costos')

# =====================================================================
# 2. INVENTARIO (Materiales y Consumibles)
# =====================================================================
@admin.register(Material)
class MaterialAdmin(admin.ModelAdmin):
    # 'tipo' ya no existe, usamos 'categoria'
    list_display = ('sku', 'nombre', 'categoria', 'stock_actual') 
    list_filter = ('categoria',) # Filtramos por la relación de Categoria
    search_fields = ('nombre', 'sku')

# =====================================================================
# 3. REQUERIMIENTOS (Tickets Internos)
# =====================================================================
class DetalleRequerimientoInline(admin.TabularInline):
    model = DetalleRequerimiento
    extra = 0

@admin.register(Requerimiento)
class RequerimientoAdmin(admin.ModelAdmin):
    list_display = ('folio', 'solicitante', 'proyecto', 'fecha_solicitud', 'estado')
    list_filter = ('estado', 'proyecto', 'fecha_solicitud')
    search_fields = ('folio', 'solicitante__username', 'proyecto__nombre')
    inlines = [DetalleRequerimientoInline]
    # Hacemos que el folio sea de solo lectura para evitar que alguien lo altere
    readonly_fields = ('folio',) 

# =====================================================================
# 4. AUDITORÍA (Movimientos de Inventario)
# =====================================================================
@admin.register(MovimientoInventario)
class MovimientoInventarioAdmin(admin.ModelAdmin):
    list_display = ('material', 'tipo', 'cantidad', 'fecha_hora', 'responsable')
    list_filter = ('tipo', 'fecha_hora')
    search_fields = ('material__nombre', 'responsable__username')
    # Estos campos son de auditoría, no deberían poder editarse a mano
    readonly_fields = ('fecha_hora',) 

# =====================================================================
# 5. ÓRDENES DE COMPRA (Abastecimiento)
# =====================================================================
class DetalleOrdenCompraInline(admin.TabularInline):
    model = DetalleOrdenCompra
    extra = 0

@admin.register(OrdenCompra)
class OrdenCompraAdmin(admin.ModelAdmin):
    list_display = ('folio', 'proveedor', 'creado_por', 'fecha_creacion', 'estado')
    list_filter = ('estado', 'fecha_creacion')
    search_fields = ('folio', 'proveedor', 'creado_por__username')
    inlines = [DetalleOrdenCompraInline]
    readonly_fields = ('folio',)

@admin.register(CierreIncompletoRequerimiento)
class CierreIncompletoRequerimientoAdmin(admin.ModelAdmin):
    list_display = ('requerimiento', 'usuario', 'fecha_hora', 'cantidad_pendiente_snapshot')
    list_filter = ('fecha_hora',)
    search_fields = ('requerimiento__folio', 'usuario__username', 'justificativo')
    readonly_fields = (
        'requerimiento', 'usuario', 'fecha_hora', 'justificativo',
        'cantidad_solicitada_snapshot', 'cantidad_despachada_snapshot', 'cantidad_pendiente_snapshot',
    )

# =====================================================================
# 6. RECURSOS HUMANOS: TRABAJADORES, PRÉSTAMOS Y NÓMINA
# =====================================================================
@admin.register(Trabajador)
class TrabajadorAdmin(admin.ModelAdmin):
    list_display = ('nombre_completo', 'documento_identidad', 'cargo', 'estado', 'fecha_ingreso')
    list_filter = ('estado', 'cargo')
    search_fields = ('nombres', 'apellidos', 'documento_identidad')

@admin.register(EntregaDirecta)
class EntregaDirectaAdmin(admin.ModelAdmin):
    list_display = ('trabajador', 'movimiento', 'proyecto')
    search_fields = ('trabajador__nombres', 'trabajador__apellidos', 'justificativo')
    readonly_fields = ('movimiento',)

class DevolucionPrestamoInline(admin.StackedInline):
    model = DevolucionPrestamo
    extra = 0
    can_delete = False

@admin.register(PrestamoHerramienta)
class PrestamoHerramientaAdmin(admin.ModelAdmin):
    list_display = ('material', 'trabajador', 'cantidad', 'estado', 'fecha_entrega')
    list_filter = ('estado', 'fecha_entrega')
    search_fields = ('material__nombre', 'trabajador__nombres', 'trabajador__apellidos')
    inlines = [DevolucionPrestamoInline]

@admin.register(SalarioTrabajador)
class SalarioTrabajadorAdmin(admin.ModelAdmin):
    list_display = ('trabajador', 'monto', 'fecha_inicio_vigencia', 'fecha_fin_vigencia')
    list_filter = ('fecha_inicio_vigencia',)
    search_fields = ('trabajador__nombres', 'trabajador__apellidos')
    readonly_fields = ('fecha_creacion',)

@admin.register(HorarioTrabajador)
class HorarioTrabajadorAdmin(admin.ModelAdmin):
    list_display = ('trabajador', 'hora_inicio', 'hora_fin')

@admin.register(ConfiguracionHorasExtra)
class ConfiguracionHorasExtraAdmin(admin.ModelAdmin):
    list_display = ('hora_inicio_ordinaria', 'hora_fin_ordinaria', 'hora_inicio_extraordinaria', 'hora_fin_extraordinaria')

@admin.register(HoraExtra)
class HoraExtraAdmin(admin.ModelAdmin):
    list_display = ('trabajador', 'fecha', 'tipo', 'cantidad_horas', 'valor_calculado', 'pago')
    list_filter = ('tipo', 'fecha')
    search_fields = ('trabajador__nombres', 'trabajador__apellidos')

@admin.register(Descuento)
class DescuentoAdmin(admin.ModelAdmin):
    list_display = ('trabajador', 'tipo', 'motivo', 'monto', 'fecha', 'pago')
    list_filter = ('tipo', 'fecha')
    search_fields = ('trabajador__nombres', 'trabajador__apellidos', 'motivo')

@admin.register(PeriodoNominaMensual)
class PeriodoNominaMensualAdmin(admin.ModelAdmin):
    list_display = ('trabajador', 'mes', 'anio', 'bonificacion', 'aporte_iess')
    list_filter = ('anio', 'mes')
    search_fields = ('trabajador__nombres', 'trabajador__apellidos')

@admin.register(Pago)
class PagoAdmin(admin.ModelAdmin):
    list_display = ('trabajador', 'periodo_inicio', 'periodo_fin', 'salario_base', 'total_horas_extras', 'bonificacion', 'total_descuentos', 'total_anticipos', 'aporte_iess', 'total_pagado')
    list_filter = ('periodo_inicio',)
    search_fields = ('trabajador__nombres', 'trabajador__apellidos')
    readonly_fields = ('fecha_registro',)

class PerfilEmpleadoInline(admin.StackedInline):
    model = PerfilEmpleado
    can_delete = False
    verbose_name_plural = 'Asignación de Bodega (Solo para Bodegueros)'
    fk_name = 'usuario'

class CustomUserAdmin(UserAdmin):
    inlines = (PerfilEmpleadoInline, )

# Re-registramos el modelo User con nuestra nueva configuración
admin.site.unregister(User)
admin.site.register(User, CustomUserAdmin)